import os
import requests
import json
import time
import re
import subprocess
from urllib.parse import urlparse
from datetime import datetime, timedelta, timezone
from config import get_notion_api_key, get_notion_database_id

NOTION_API_KEY = get_notion_api_key()
DATABASE_ID = get_notion_database_id()
AW_API_URL = "http://localhost:5600/api/0"

RULES_FILE = "rules.json"
STATE_FILE = "state.json"
IGNORE_LIST = ["System Settings", "Finder", "loginwindow", "Window Server", "Control Center", "Activity Monitor", "Spotlight", "NotificationCenter", "Terminal", "iTerm2", "IINA"]

CONTAINER_APPS = {
    "browsers": ["Google Chrome", "Safari", "Arc", "Edge"],
    "editors": ["Code", "Cursor", "Sublime Text"],
    "notes": ["Notion", "Obsidian", "Logseq", "Evernote"],
    "office": ["Microsoft Word", "Microsoft Excel", "Microsoft PowerPoint", "Pages", "Numbers"]
}

# AI 对话/智能平台：提取标题中的对话主题，用于区分不同项目
SMART_WEB_DOMAINS = {
    "gemini.google.com": "Gemini",
    "platform.deepseek.com": "DeepSeek",
    "chatgpt.com": "ChatGPT",
    "chat.openai.com": "ChatGPT",
    "claude.ai": "Claude",
}

def _clean_browser_title(title):
    for suffix in [" - Google Chrome", " - Safari", " - Arc", " - Edge", " - Firefox"]:
        if title.endswith(suffix):
            title = title[:-len(suffix)]
    return title.strip()

def load_state():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r") as f:
                data = json.load(f)
                return datetime.fromisoformat(data["last_check"])
        except: pass
    return datetime.now(timezone.utc) - timedelta(minutes=10)

def save_state(now_time):
    with open(STATE_FILE, "w") as f: json.dump({"last_check": now_time.isoformat()}, f)

def load_rules():
    if os.path.exists(RULES_FILE):
        try:
            with open(RULES_FILE, "r") as f: return json.load(f)
        except: pass
    return {}

def save_rules(rules):
    with open(RULES_FILE, "w", encoding="utf-8") as f: json.dump(rules, f, indent=4, ensure_ascii=False)

def ask_mac_dialog(title, prompt, default_ans=""):
    safe_prompt = prompt.replace('"', "'")
    applescript = f'''
    tell application "System Events"
        activate
        set dialogResult to display dialog "{safe_prompt}" default answer "{default_ans}" buttons {{"忽略 (Ignore)", "提交 (Submit)"}} default button "提交 (Submit)" with title "{title}" giving up after 120
        if gave up of dialogResult then return "TIMEOUT"
        if button returned of dialogResult is "忽略 (Ignore)" then return "IGNORE"
        return text returned of dialogResult
    end tell
    '''
    try:
        return subprocess.check_output(['osascript', '-e', applescript], text=True, stderr=subprocess.DEVNULL).strip()
    except: return "TIMEOUT"

def parse_vscode_project(title):
    match = re.search(r'[—\-]\s*(.*?)\s*(?:\[SSH:|\(Workspace\))', title)
    if match: return match.group(1).strip() 
    parts = re.split(r'[—\-]', title)
    if len(parts) > 1:
        proj = parts[-1].replace("Visual Studio Code", "").strip()
        if proj: return proj
    clean_title = title.replace("Visual Studio Code", "").strip()
    return clean_title if clean_title else "Unnamed"

def extract_context_identifier(app, title, url):
    if app in CONTAINER_APPS["browsers"]:
        try:
            full_domain = urlparse(url).netloc.replace("www.", "").lower()
            if not full_domain: return None

            # AI 对话平台：先按完整域名匹配（gemini.google.com），
            # 再提取对话主题
            platform = SMART_WEB_DOMAINS.get(full_domain)
            if platform:
                cleaned = _clean_browser_title(title)
                for suffix in [f" - Google {platform}", f" - {platform}"]:
                    if cleaned.endswith(suffix):
                        cleaned = cleaned[:-len(suffix)]
                cleaned = cleaned.strip()
                if cleaned and cleaned != platform and cleaned != f"Google {platform}":
                    return f"{platform}: {cleaned[:40]}"
                return platform

            # 普通网站：提取主域名（feishu.cn 而非 jwolpxeehx.feishu.cn）
            parts = full_domain.split(".")
            main_domain = ".".join(parts[-2:]) if len(parts) > 2 else full_domain
            return f"Web: {main_domain}"
        except: return None
    elif app in CONTAINER_APPS["editors"]:
        if app == "Code": return f"VSCode: {parse_vscode_project(title)}"
        return f"{app}: {title[:20]}"
    elif app in CONTAINER_APPS["notes"] or app in CONTAINER_APPS["office"]:
        clean_title = title.replace(f" - {app}", "").replace(app, "").strip()
        return f"{app}: {clean_title[:25]}" if clean_title else f"{app}: 未命名"
    return app

def push_to_notion(name, cat, proj, duration_mins, start_time, end_time):
    # 低于 2 分钟的碎渣不上传
    if duration_mins < 2: 
        print(f"丢弃短时碎片: {name} ({duration_mins}m)")
        return False 
        
    headers = {
        "Authorization": f"Bearer {NOTION_API_KEY}",
        "Content-Type": "application/json",
        "Notion-Version": "2022-06-28"
    }
    data = {
        "parent": {"database_id": DATABASE_ID},
        "properties": {
            "App/Task": {"title": [{"text": {"content": name}}]},
            "Category": {"select": {"name": cat}},
            "Project": {"select": {"name": proj}},
            "Duration": {"number": duration_mins},
            "Time": {"date": {"start": start_time.isoformat(), "end": end_time.isoformat()}}
        }
    }
    for _ in range(3):
        try:
            res = requests.post("https://api.notion.com/v1/pages", headers=headers, json=data, timeout=10)
            if res.status_code == 200:
                print(f"已同步: [{name}] -> {cat}/{proj} ({duration_mins}m)")
                return True
        except: time.sleep(2)
    return False

def fetch_and_cut_events(start_iso, end_iso):
    try:
        buckets = requests.get(f"{AW_API_URL}/buckets").json()
        win_bucket = next((b for b in buckets if "aw-watcher-window" in b), None)
        afk_bucket = next((b for b in buckets if "aw-watcher-afk" in b), None)
        web_bucket = next((b for b in buckets if "aw-watcher-web" in b), None)

        if not win_bucket or not afk_bucket: return [], [], {}

        params = {"start": start_iso, "end": end_iso}
        win_events = requests.get(f"{AW_API_URL}/buckets/{win_bucket}/events", params=params).json()
        afk_events = requests.get(f"{AW_API_URL}/buckets/{afk_bucket}/events", params=params).json()

        # 拉取网页浏览历史 (Chrome watcher-web)
        web_url_map = {}  # time_slot -> url
        if web_bucket:
            try:
                web_events = requests.get(f"{AW_API_URL}/buckets/{web_bucket}/events", params=params).json()
                for we in web_events:
                    ts = datetime.fromisoformat(we['timestamp'].replace('Z', '+00:00'))
                    url = we['data'].get('url', '')
                    if url:
                        # 以分钟为槽位，把 URL 填进去
                        slot = ts.replace(second=0, microsecond=0)
                        if slot not in web_url_map:
                            web_url_map[slot] = url
            except Exception:
                pass

        afk_periods = []
        real_afk_events = []
        for e in afk_events:
            if e['data'].get('status') == 'afk':
                real_afk_events.append(e)
                st = datetime.fromisoformat(e['timestamp'].replace('Z', '+00:00'))
                ed = st + timedelta(seconds=e['duration'])
                afk_periods.append((st, ed))

        real_win_events = []
        for w in win_events:
            w_st = datetime.fromisoformat(w['timestamp'].replace('Z', '+00:00'))
            w_ed = w_st + timedelta(seconds=w['duration'])
            total_overlap = 0
            for a_st, a_ed in afk_periods:
                overlap_st = max(w_st, a_st)
                overlap_ed = min(w_ed, a_ed)
                if overlap_st < overlap_ed:
                    total_overlap += (overlap_ed - overlap_st).total_seconds()
            actual_duration = w['duration'] - total_overlap

            if actual_duration > 5:
                w['duration'] = actual_duration
                # 为浏览器窗口补上 URL（扫描窗口跨度的每分钟槽位）
                app = w['data'].get('app', '')
                if app in CONTAINER_APPS["browsers"] and not w['data'].get('url'):
                    cursor = w_st.replace(second=0, microsecond=0)
                    end_slot = w_ed.replace(second=0, microsecond=0)
                    while cursor <= end_slot:
                        if cursor in web_url_map:
                            w['data']['url'] = web_url_map[cursor]
                            break
                        cursor += timedelta(minutes=1)
                real_win_events.append(w)

        print(f"  -> 分析: {len(real_win_events)} 条活跃窗口记录 (web: {len(web_url_map)} 条)")
        return real_win_events, real_afk_events, web_url_map
    except Exception as e:
        return [], [], {}

# ---------- 缓冲区配置 ----------
SAME_KEY_MERGE_GAP = 600       # 通用同 key 缝合间隔 10min（会被下面覆盖）

# 按分类的合并窗口：同一个项目，间隔多久内继续算同一段
CATEGORY_MERGE_GAP = {
    "Research": 1800,          # 30min — 项目工作允许较长中断
    "Work": 1800,
    "Entertainment": 300,      # 5min — 聊天/社交短间隔才算一次
    "Web": 300,                # 5min — 网页浏览碎片较多，短间隔合并
    "Offline": 900,
}
CATEGORY_MERGE_GAP_DEFAULT = 600

def _merge_gap_for(category):
    return CATEGORY_MERGE_GAP.get(category, CATEGORY_MERGE_GAP_DEFAULT)

STABILITY_TIMEOUT = 900        # 超过 15min 没活动 → 可以推送
LONG_SESSION_THRESHOLD = 3600  # 持续 1h+ → 立刻推送
MAX_BUFFER_SIZE = 30           # 缓冲区上限

CATEGORY_MIN_DURATION = {
    "Research": 3, "Work": 3,
    "Entertainment": 3, "Offline": 2,
}
CATEGORY_MIN_DURATION_DEFAULT = 3

def _push_session(sess):
    return push_to_notion(
        sess['name'], sess['category'], sess['project'],
        int(sess['duration'] // 60), sess['start'], sess['end'])

_WIDGET_EXPORT_LAST = None

def _export_widget_cache():
    """每次扫描周期刷新 widget JSON（但最多每 10 分钟一次）。"""
    global _WIDGET_EXPORT_LAST
    now = datetime.now(timezone.utc)
    if _WIDGET_EXPORT_LAST and (now - _WIDGET_EXPORT_LAST).total_seconds() < 600:
        return

    import sys, os
    script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "widget_export.py")
    subprocess.run(
        [sys.executable, script],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        timeout=30
    )
    _WIDGET_EXPORT_LAST = now

def _drain_buffer(buffer, now, force=False):
    """推出所有满足条件的 session，返回剩余 buffer。"""
    remaining = []
    to_push = []
    for sess in buffer:
        inactive_sec = (now - sess['last_active']).total_seconds()
        total_sec = (now - sess['start']).total_seconds()
        if force or inactive_sec > STABILITY_TIMEOUT or total_sec > LONG_SESSION_THRESHOLD:
            to_push.append(sess)
        else:
            remaining.append(sess)

    # 合并同 key 的待推送 session
    to_push.sort(key=lambda s: s['start'])
    merged = []
    for sess in to_push:
        if merged and merged[-1]['key'] == sess['key']:
            gap = (sess['start'] - merged[-1]['end']).total_seconds()
            mg = _merge_gap_for(sess.get('category', ''))
            if gap < mg:
                merged[-1]['end'] = max(merged[-1]['end'], sess['end'])
                merged[-1]['duration'] += sess['duration']
                continue
        merged.append(sess)

    for sess in merged:
        mins = int(sess['duration'] // 60)
        min_dur = CATEGORY_MIN_DURATION.get(sess['category'], CATEGORY_MIN_DURATION_DEFAULT)
        inactive_sec = (now - sess['last_active']).total_seconds()
        if mins >= min_dur:
            _push_session(sess)
        elif inactive_sec <= STABILITY_TIMEOUT and not force:
            # 还有机会增长，放回缓冲区
            remaining.append(sess)
        # 否则：已经稳定但不够最小粒度 → 丢弃

    return remaining

def daemon_loop():
    print("Start！")
    session_buffer = []

    while True:
        try:
            last_check = load_state()
            now = datetime.now(timezone.utc)

            if (now - last_check).total_seconds() < 300:
                time.sleep(30)
                # 即使不满 5 分钟，也检查有没有该推的 session
                if len(session_buffer) > MAX_BUFFER_SIZE:
                    session_buffer = _drain_buffer(session_buffer, now, force=True)
                continue

            print(f"\n[{datetime.now().strftime('%H:%M:%S')}] 扫描新活动 (缓冲: {len(session_buffer)} 个 session)...")
            win_events, afk_events, _ = fetch_and_cut_events(last_check.isoformat(), now.isoformat())
            rules = load_rules()

            # ---------------- A. 处理离线回归 ----------------
            for event in afk_events:
                mins = int(event['duration'] // 60)
                if mins >= 15:
                    session_buffer = _drain_buffer(session_buffer, now, force=True)
                    prompt = f"欢迎回来！\n系统检测到你离开了 {mins} 分钟。\n这段时间你在做什么？"
                    res = ask_mac_dialog("离线时间捕捉", prompt)
                    if res == "IGNORE":
                        continue
                    elif res == "TIMEOUT" or not res:
                        cat, proj = "Offline", "Uncategorized"
                    else:
                        cat, proj = res.split("/", 1) if "/" in res else ("Offline", res)

                    evt_start = datetime.fromisoformat(event['timestamp'].replace('Z', '+00:00'))
                    evt_end = evt_start + timedelta(minutes=mins)
                    push_to_notion(f"Offline: {proj.strip()}", cat.strip(), proj.strip(), mins, evt_start, evt_end)

            # ---------------- B. 处理窗口事件 → 喂入缓冲区 ----------------
            win_events.sort(key=lambda x: x['timestamp'])

            for event in win_events:
                app = event['data'].get('app', 'Unknown')
                title = event['data'].get('title', '')
                duration = event['duration']

                evt_start = datetime.fromisoformat(event['timestamp'].replace('Z', '+00:00'))
                evt_end = evt_start + timedelta(seconds=duration)

                if app in IGNORE_LIST or duration < 10 or not app or not app.strip():
                    continue

                context_name = extract_context_identifier(app, title, event['data'].get('url', ''))
                if not context_name:
                    continue

                l1_cat, l2_proj = None, None
                found = rules.get(context_name.lower())

                if found:
                    l1_cat, l2_proj = found
                elif context_name.startswith("Web: "):
                    # 普通网页自动归类，不弹窗
                    domain = context_name.replace("Web: ", "")
                    l1_cat, l2_proj = "Web", domain
                    rules[context_name.lower()] = [l1_cat, l2_proj]
                    save_rules(rules)
                elif any(context_name.startswith(p) for p in SMART_WEB_DOMAINS.values()):
                    # AI 对话平台 → 弹窗分类（可能属于不同项目）
                    prompt = f"AI 对话: 【{context_name}】\n-> 请分类 (格式: 大类/具体项目)"
                    res = ask_mac_dialog("待分类记录", prompt)
                    if res == "TIMEOUT" or res is None:
                        l1_cat, l2_proj = "Web", "AI Chat"
                    elif res == "IGNORE" or not res:
                        l1_cat, l2_proj = "IGNORE", "IGNORE"
                    else:
                        l1_cat, l2_proj = res.split("/", 1) if "/" in res else ("Uncategorized", res)
                        l1_cat, l2_proj = l1_cat.strip(), l2_proj.strip()
                    rules[context_name.lower()] = [l1_cat, l2_proj]
                    save_rules(rules)
                else:
                    prompt = f"发现新活动: 【{context_name}】\n-> 请分类 (格式: 大类/具体项目)"
                    res = ask_mac_dialog("待分类记录", prompt)
                    if res == "TIMEOUT" or res is None:
                        l1_cat, l2_proj = "Uncategorized", "Pending"
                    elif res == "IGNORE" or not res:
                        l1_cat, l2_proj = "IGNORE", "IGNORE"
                    else:
                        l1_cat, l2_proj = res.split("/", 1) if "/" in res else ("Uncategorized", res)
                        l1_cat, l2_proj = l1_cat.strip(), l2_proj.strip()

                    rules[context_name.lower()] = [l1_cat, l2_proj]
                    save_rules(rules)

                if l1_cat == "IGNORE" or l2_proj == "IGNORE":
                    continue

                session_key = f"{context_name}|{l1_cat}|{l2_proj}"

                # 在缓冲区中找同 key 且间隔短的 session 缝合
                matched = False
                for sess in session_buffer:
                    if sess['key'] == session_key:
                        gap = (evt_start - sess['last_active']).total_seconds()
                        mg = _merge_gap_for(l1_cat)
                        if gap < mg:
                            sess['end'] = evt_end
                            sess['duration'] += duration
                            sess['last_active'] = evt_end
                            matched = True
                            break

                if not matched:
                    session_buffer.append({
                        "key": session_key, "name": context_name,
                        "category": l1_cat, "project": l2_proj,
                        "start": evt_start, "end": evt_end,
                        "duration": duration, "last_active": evt_end
                    })

            # ---------------- C. 排水：推送稳定/超长的 session ----------------
            session_buffer = _drain_buffer(session_buffer, now)

            save_state(now)

            # 每次扫描后刷新 widget 数据
            try:
                _export_widget_cache()
            except Exception:
                pass

            time.sleep(30)

        except Exception as e:
            print(f"内部错误: {e}")
            time.sleep(60)

def cmd_list_rules():
    rules = load_rules()
    if not rules:
        print("暂无分类规则。")
        return
    active = {k: v for k, v in rules.items() if v[0] not in ("IGNORE",)}
    ignored = {k: v for k, v in rules.items() if v[0] == "IGNORE"}
    print(f"=== 活跃规则 ({len(active)} 条) ===")
    for ctx, (cat, proj) in sorted(active.items()):
        print(f"  {ctx}  →  {cat} / {proj}")
    if ignored:
        print(f"\n=== 已忽略 ({len(ignored)} 条) ===")
        for ctx, _ in sorted(ignored.items()):
            print(f"  {ctx}")

def cmd_delete_rule(pattern):
    rules = load_rules()
    pattern = pattern.lower()
    matched = [k for k in rules if pattern in k]
    if not matched:
        print(f"没有匹配 '{pattern}' 的规则。")
        return
    for k in matched:
        print(f"已删除: {k} → {rules[k]}")
        del rules[k]
    save_rules(rules)

def cmd_set_rule(context, category, project):
    rules = load_rules()
    rules[context.lower()] = [category.strip(), project.strip()]
    save_rules(rules)
    print(f"已更新: {context} → {category} / {project}")

if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(line_buffering=True)  # launchd 后台模式实时写日志
    if len(sys.argv) > 1:
        cmd = sys.argv[1]
        if cmd == "--list-rules":
            cmd_list_rules()
        elif cmd == "--delete-rule" and len(sys.argv) >= 3:
            cmd_delete_rule(sys.argv[2])
        elif cmd == "--set-rule" and len(sys.argv) >= 5:
            cmd_set_rule(sys.argv[2], sys.argv[3], sys.argv[4])
        elif cmd == "--test-push" and len(sys.argv) >= 5:
            # 测试推送: uv run aw_sync.py --test-push "name" cat proj mins
            from datetime import datetime, timezone
            now = datetime.now(timezone.utc)
            push_to_notion(sys.argv[2], sys.argv[3], sys.argv[4], int(sys.argv[5]), now, now)
        else:
            print("用法:")
            print("  uv run aw_sync.py                     # 启动后台守护")
            print("  uv run aw_sync.py --list-rules        # 列出所有规则")
            print("  uv run aw_sync.py --delete-rule <关键词> # 删除匹配的规则")
            print("  uv run aw_sync.py --set-rule <上下文> <大类> <项目>  # 添加/修改规则")
            print("  uv run aw_sync.py --test-push <名> <类> <项> <分钟>  # 测试推送")
    else:
        daemon_loop()