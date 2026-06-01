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
ICLOUD_RULES = os.path.expanduser("~/Library/Mobile Documents/com~apple~CloudDocs/TimeLogger/rules.json")

def _sync_rules_from_icloud():
    """如果 iCloud 上的规则比本地新，拉过来。"""
    if os.path.exists(ICLOUD_RULES) and os.path.exists(RULES_FILE):
        try:
            if os.path.getmtime(ICLOUD_RULES) > os.path.getmtime(RULES_FILE):
                import shutil
                shutil.copy2(ICLOUD_RULES, RULES_FILE)
        except: pass

def _sync_rules_to_icloud():
    """推送本地规则到 iCloud（忽略权限错误）。"""
    try:
        os.makedirs(os.path.dirname(ICLOUD_RULES), exist_ok=True)
        import shutil
        shutil.copy2(RULES_FILE, ICLOUD_RULES)
    except: pass
IGNORE_LIST = ["System Settings", "Finder", "loginwindow", "Window Server", "Control Center", "Activity Monitor", "Spotlight", "NotificationCenter", "Terminal", "iTerm2", "IINA", "TimeWidget", "Steam Helper"]

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
    _sync_rules_from_icloud()
    if os.path.exists(RULES_FILE):
        try:
            with open(RULES_FILE, "r") as f: return json.load(f)
        except: pass
    return {}

def save_rules(rules):
    with open(RULES_FILE, "w", encoding="utf-8") as f: json.dump(rules, f, indent=4, ensure_ascii=False)
    _sync_rules_to_icloud()

def _existing_categories(rules):
    """提取已有的一级分类（去重），用于弹窗提示。"""
    cats = sorted(set(v[0] for v in rules.values()
                     if v[0] not in ("IGNORE", "Uncategorized")))
    return ", ".join(cats) if cats else "无"

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

def _run_osascript(script):
    try:
        result = subprocess.check_output(
            ['osascript', '-e', script], text=True, stderr=subprocess.DEVNULL).strip()
        return result
    except:
        return None

def ask_classification_dialog(context_name, rules):
    """两步分类弹窗：先选大类，再选/输该项目名（只展示该大类下的已有项目）。"""
    cats = sorted(set(v[0] for v in rules.values()
                     if v[0] not in ("IGNORE", "Uncategorized")))
    cats_for_list = '", "'.join(cats)
    cats_for_list = f'"新建...", "{cats_for_list}"' if cats else '"新建..."'

    # 第一步：选大类
    step1 = f'''
    tell application "System Events"
        activate
        set catList to {{{cats_for_list}}}
        set catChoice to choose from list catList with title "分类: {context_name}" with prompt "选择大类（或选「新建...」）" default items {{item 1 of catList}}
        if catChoice is false then return "CANCEL"
        set chosenCat to item 1 of catChoice
        if chosenCat is "新建..." then
            set catDialog to display dialog "输入新大类名称:" default answer "" buttons {{"取消", "确定"}} default button "确定" with title "新建大类"
            if button returned of catDialog is "取消" then return "CANCEL"
            set chosenCat to text returned of catDialog
        end if
        return chosenCat
    end tell
    '''
    chosenCat = _run_osascript(step1)
    if chosenCat is None or chosenCat == "CANCEL":
        return "TIMEOUT"

    # 第二步：选/输入项目名（只展示该大类下的已有项目）
    safe_cat = chosenCat.replace('"', "'")
    projs = sorted(set(v[1] for v in rules.values()
                       if v[0] == chosenCat and v[1] not in ("IGNORE", "Uncategorized", "Pending")))
    if projs:
        proj_list = '", "'.join(projs)
        step2 = f'''
        tell application "System Events"
            activate
            set chosenCat to "{safe_cat}"
            set projList to {{"新建...", "{proj_list}"}}
            set projChoice to choose from list projList with title "{safe_cat} 下的项目" with prompt "选择项目（或选「新建...」）"
            if projChoice is false then return chosenCat & "/CANCEL"
            set chosenProj to item 1 of projChoice
            if chosenProj is "新建..." then
                set projDialog to display dialog "大类: " & chosenCat & return & "输入新项目名:" default answer "" buttons {{"忽略", "确定"}} default button "确定" with title "新建项目"
                if button returned of projDialog is "忽略" then return chosenCat & "/IGNORE"
                return chosenCat & "/" & (text returned of projDialog)
            end if
            return chosenCat & "/" & chosenProj
        end tell
        '''
    else:
        step2 = f'''
        tell application "System Events"
            activate
            set chosenCat to "{safe_cat}"
            set projDialog to display dialog "大类: " & chosenCat & return & "输入项目名:" default answer "" buttons {{"忽略", "确定"}} default button "确定" with title "新建项目"
            if button returned of projDialog is "忽略" then return chosenCat & "/IGNORE"
            return chosenCat & "/" & (text returned of projDialog)
        end tell
        '''
    result = _run_osascript(step2)
    if result is None or result == "CANCEL" or (result and result.endswith("/CANCEL")):
        return "TIMEOUT"
    return result

def _looks_like_file(name):
    """扩展名判定：含 '.' 且不在开头（排除 .git .claude 等隐藏目录）"""
    return '.' in name and not name.startswith('.')


def parse_vscode_project(title):
    # 去掉脏文件标记 ● 和 SSH/Workspace 噪音
    title = re.sub(r'^[●◉○]\s*', '', title)
    title = re.sub(r'\s*\[SSH:\s*[^\]]+\]', '', title)
    title = re.sub(r'\s*\(Workspace\)', '', title)

    parts = re.split(r'\s+[—\-]\s+', title)
    # 去掉末尾的 "Visual Studio Code"
    clean_parts = [p.strip() for p in parts if p.strip() and 'Visual Studio Code' not in p]

    if not clean_parts:
        return "Unnamed"

    # workspace 是最后一段（文件夹/项目根目录名）
    workspace = clean_parts[-1]

    # 剩余部分是文件名/文件夹名（从 workspace 往前）
    sub_parts = clean_parts[:-1]

    # 从后往前找第一个不是文件的层级（目录名），跳过所有文件名
    for part in reversed(sub_parts):
        if not _looks_like_file(part):
            return f"{workspace} / {part}"

    # 全是文件 → 只用 workspace 级别
    return workspace

def parse_office_document(title, app):
    """从 Office 窗口标题提取文档名（类似 VSCode 提取项目名）"""
    # 处理英文/中文破折号和连字符（macOS 用 —，Windows 用 -）
    # 去掉末尾的 " — AppName" 或 " - AppName"
    clean = re.sub(r'\s*[—\-]\s*' + re.escape(app) + r'\s*$', '', title)
    # 也去掉不带分隔符的 app 名称
    clean = clean.replace(app, '').strip()
    # 去掉前后残留的标点
    clean = clean.strip(' —-–    ').strip()
    # 保留常见临时/无意义标题的原始值（后续仍需用户分类确认）
    return clean if clean else None

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
        clean_title = parse_office_document(title, app)
        if clean_title:
            return f"{app}: {clean_title[:40]}"
        return f"{app}: 未命名"
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

            if actual_duration > 10:
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

STABILITY_TIMEOUT = 300        # 超过 5min 没活动 → 可以推送
LONG_SESSION_THRESHOLD = 3600  # 持续 1h+ → 立刻推送
MAX_BUFFER_SIZE = 30           # 缓冲区上限

CATEGORY_MIN_DURATION = {
    "Research": 5, "Work": 5,
    "Entertainment": 5, "Offline": 5,
}
CATEGORY_MIN_DURATION_DEFAULT = 5

def _push_session(sess):
    return push_to_notion(
        sess['name'], sess['category'], sess['project'],
        int(sess['duration'] // 60), sess['start'], sess['end'])

_WIDGET_EXPORT_LAST = None
_RULES_SYNC_LAST = None
BUFFER_DUMP_PATH = os.path.expanduser("~/.timecollectionlogger/buffer_dump.json")

def _dump_buffer_for_widget(session_buffer):
    """把当前缓冲区写到本地文件，供 widget 展示今天未推送数据。"""
    os.makedirs(os.path.dirname(BUFFER_DUMP_PATH), exist_ok=True)
    entries = []
    for s in session_buffer:
        entries.append({
            "category": s["category"], "project": s["project"],
            "start": s["start"].isoformat(), "end": s["end"].isoformat(),
            "name": s["name"],
            "durationMin": int(s["duration"] // 60),
        })
    with open(BUFFER_DUMP_PATH, "w") as f:
        json.dump({"entries": entries}, f)

def _export_widget_cache(session_buffer=None):
    """每次扫描周期刷新 widget JSON（但最多每 10 分钟一次）。"""
    global _WIDGET_EXPORT_LAST
    now = datetime.now(timezone.utc)
    if _WIDGET_EXPORT_LAST and (now - _WIDGET_EXPORT_LAST).total_seconds() < 180:
        if session_buffer:
            _dump_buffer_for_widget(session_buffer)
        return

    if session_buffer:
        _dump_buffer_for_widget(session_buffer)

    import sys
    script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "widget_export.py")
    subprocess.run(
        [sys.executable, script],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        timeout=30
    )
    _WIDGET_EXPORT_LAST = now

def _drain_buffer(buffer, now, force=False, rules=None):
    """推出所有满足条件的 session，返回剩余 buffer。"""
    # 用最新规则刷新 session 的分类
    if rules:
        for sess in buffer:
            ctx_key = sess.get('context_key', '')
            if ctx_key and ctx_key in rules:
                new_cat, new_proj = rules[ctx_key]
                # 如果规则里还是 Pending/Uncategorized → 不采用，保留原分类
                if "Uncategorized" in (new_cat, new_proj) or "Pending" in (new_cat, new_proj) or "IGNORE" in (new_cat, new_proj):
                    continue
                sess['category'], sess['project'] = new_cat, new_proj
                sess['key'] = f"{sess['name']}|{sess['category']}|{sess['project']}"

    remaining = []
    to_push = []
    for sess in buffer:
        # 安全阀：绝对不推送 Pending/Uncategorized/IGNORE 的 session
        cat, proj = sess.get('category', ''), sess.get('project', '')
        if "Uncategorized" in (cat, proj) or "Pending" in (cat, proj) or "IGNORE" in (cat, proj):
            continue  # 直接丢弃，不再放回缓冲区

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
        min_dur = CATEGORY_MIN_DURATION.get(sess.get('category', ''), CATEGORY_MIN_DURATION_DEFAULT)
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
                    session_buffer = _drain_buffer(session_buffer, now, force=True, rules=rules)
                continue

            print(f"\n[{datetime.now().strftime('%H:%M:%S')}] 扫描新活动 (缓冲: {len(session_buffer)} 个 session)...")
            win_events, afk_events, _ = fetch_and_cut_events(last_check.isoformat(), now.isoformat())
            rules = load_rules()

            # ---------------- A. 处理离线回归 ----------------
            for event in afk_events:
                mins = int(event['duration'] // 60)
                if mins >= 15:
                    session_buffer = _drain_buffer(session_buffer, now, force=True, rules=rules)
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
                    if "Uncategorized" in (l1_cat, l2_proj) or l2_proj == "Pending":
                        l1_cat, l2_proj = None, None  # 当作未分类，重新弹窗
                elif context_name.startswith("Web: "):
                    # 普通网页自动归类，不弹窗
                    domain = context_name.replace("Web: ", "")
                    l1_cat, l2_proj = "Web", domain
                    rules[context_name.lower()] = [l1_cat, l2_proj]
                    save_rules(rules)
                elif any(context_name.startswith(p) for p in SMART_WEB_DOMAINS.values()):
                    # AI 对话平台 → 两步分类弹窗
                    res = ask_classification_dialog("AI: " + context_name, rules)
                    if res == "TIMEOUT" or res is None:
                        continue  # 未分类 = 不记录、不学规则
                    elif "/IGNORE" in res:
                        l1_cat, l2_proj = "IGNORE", "IGNORE"
                    else:
                        parts = res.split("/", 1)
                        l1_cat = parts[0].strip()
                        l2_proj = parts[1].strip() if len(parts) > 1 else "General"
                    rules[context_name.lower()] = [l1_cat, l2_proj]
                    save_rules(rules)
                else:
                    res = ask_classification_dialog(context_name, rules)
                    if res == "TIMEOUT" or res is None:
                        continue  # 未分类 = 不记录、不学规则
                    elif "/IGNORE" in res:
                        parts = res.split("/", 1)
                        l1_cat = parts[0].strip()
                        l2_proj = "IGNORE"
                    else:
                        parts = res.split("/", 1)
                        l1_cat = parts[0].strip()
                        l2_proj = parts[1].strip() if len(parts) > 1 else "Uncategorized"
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
                        "context_key": context_name.lower(),
                        "category": l1_cat, "project": l2_proj,
                        "start": evt_start, "end": evt_end,
                        "duration": duration, "last_active": evt_end
                    })

            # ---------------- C. 排水：推送稳定/超长的 session ----------------
            session_buffer = _drain_buffer(session_buffer, now, rules=rules)

            save_state(now)

            # 每 30 分钟从 Notion 同步规则（自动学习你手动改的分类）
            global _RULES_SYNC_LAST
            if _RULES_SYNC_LAST is None or (now - _RULES_SYNC_LAST).total_seconds() >= 1800:
                try:
                    cmd_sync_rules_from_notion()
                    _RULES_SYNC_LAST = now
                except Exception:
                    pass

            # 每次扫描后刷新 widget 数据（含缓冲区未推送条目）
            try:
                _export_widget_cache(session_buffer)
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

def cmd_sync_rules_from_notion():
    """从 Notion 数据库中提取每个 context 最新的分类，更新 rules.json。"""
    url = f"https://api.notion.com/v1/databases/{DATABASE_ID}/query"
    headers = {"Authorization": f"Bearer {NOTION_API_KEY}", "Content-Type": "application/json", "Notion-Version": "2022-06-28"}
    body = {"sorts": [{"property": "Time", "direction": "descending"}], "page_size": 100}

    context_rules = {}
    has_more = True
    while has_more:
        r = requests.post(url, headers=headers, json=body, timeout=15)
        if r.status_code != 200:
            print(f"查询失败: {r.status_code}")
            return
        data = r.json()
        for page in data.get("results", []):
            props = page.get("properties", {})
            name = _get_title(props.get("App/Task", {}))
            cat = _get_select(props.get("Category", {}))
            proj = _get_select(props.get("Project", {}))
            if name and cat and cat not in ("IGNORE",) and proj not in ("IGNORE", "Pending") and "Uncategorized" not in (cat, proj) and name.lower() not in context_rules:
                context_rules[name.lower()] = [cat, proj]
        has_more = data.get("has_more", False)
        if has_more:
            body["start_cursor"] = data.get("next_cursor")

    # 合并到现有规则（保留 IGNORE 条目和未出现的规则）
    rules = load_rules()
    for k, v in context_rules.items():
        rules[k] = v
    save_rules(rules)
    print(f"从 Notion 同步了 {len(context_rules)} 条规则")

def _get_title(prop):
    title = prop.get("title", [])
    return title[0].get("plain_text", "") if title else ""

def _get_select(prop):
    sel = prop.get("select")
    return sel.get("name", "") if sel else ""

def cmd_set_rule(context, category, project):
    rules = load_rules()
    rules[context.lower()] = [category.strip(), project.strip()]
    save_rules(rules)
    print(f"已更新: {context} → {category} / {project}")

def cmd_delete_from_notion(keyword):
    """归档 Notion 中匹配关键词的条目（关键词匹配 App/Task 标题）。"""
    url = f"https://api.notion.com/v1/databases/{DATABASE_ID}/query"
    headers = {"Authorization": f"Bearer {NOTION_API_KEY}", "Content-Type": "application/json", "Notion-Version": "2022-06-28"}
    body = {"page_size": 100}
    keyword_lower = keyword.lower()
    archived = 0
    has_more = True
    while has_more:
        resp = requests.post(url, headers=headers, json=body, timeout=15)
        if resp.status_code != 200:
            print(f"查询失败: {resp.status_code}")
            return
        data = resp.json()
        for page in data.get("results", []):
            props = page.get("properties", {})
            name = _get_title(props.get("App/Task", {}))
            if keyword_lower in name.lower():
                del_resp = requests.patch(
                    f"https://api.notion.com/v1/pages/{page['id']}",
                    headers=headers,
                    json={"archived": True, "properties": {}},
                    timeout=10)
                if del_resp.status_code == 200:
                    print(f"  已归档: {name}")
                    archived += 1
        has_more = data.get("has_more", False)
        if has_more:
            body["start_cursor"] = data.get("next_cursor")
    print(f"共归档 {archived} 条匹配「{keyword}」的记录。")
    if archived > 0:
        print("提示：下次 widget 刷新后桌面即消失。")


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
        elif cmd == "--delete-from-notion" and len(sys.argv) >= 3:
            cmd_delete_from_notion(sys.argv[2])
        elif cmd == "--test-push" and len(sys.argv) >= 5:
            from datetime import datetime, timezone
            now = datetime.now(timezone.utc)
            push_to_notion(sys.argv[2], sys.argv[3], sys.argv[4], int(sys.argv[5]), now, now)
        elif cmd == "--sync-rules-from-notion":
            cmd_sync_rules_from_notion()
        else:
            print("用法:")
            print("  uv run aw_sync.py                     # 启动后台守护")
            print("  uv run aw_sync.py --list-rules        # 列出所有规则")
            print("  uv run aw_sync.py --delete-rule <关键词> # 删除匹配的规则")
            print("  uv run aw_sync.py --set-rule <上下文> <大类> <项目>  # 添加/修改规则")
            print("  uv run aw_sync.py --delete-from-notion <关键词>  # 归档 Notion 匹配条目")
            print("  uv run aw_sync.py --sync-rules-from-notion  # 从 Notion 同步规则")
            print("  uv run aw_sync.py --test-push <名> <类> <项> <分钟>  # 测试推送")
    else:
        daemon_loop()