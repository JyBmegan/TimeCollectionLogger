#!/usr/bin/env python3
"""从 Notion 导出本周数据为 Widget JSON 缓存。
   由 launchd 每 10 分钟调用一次，或手动运行。"""

import sys, os, json
from datetime import datetime, timezone, timedelta
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import get_notion_api_key, get_notion_database_id
import requests

NOTION_KEY = get_notion_api_key()
DATABASE_ID = get_notion_database_id()
CACHE_DIR = os.path.expanduser("~/.timecollectionlogger")
CACHE_FILE = os.path.join(CACHE_DIR, "widget_data.json")


def get_monday(dt=None):
    dt = dt or datetime.now(timezone.utc)
    return (dt - timedelta(days=dt.weekday())).replace(
        hour=0, minute=0, second=0, microsecond=0)


def _notion_post(url, body, max_retries=3):
    import time
    headers = {
        "Authorization": f"Bearer {NOTION_KEY}",
        "Content-Type": "application/json",
        "Notion-Version": "2022-06-28",
    }
    for attempt in range(max_retries):
        try:
            return requests.post(url, headers=headers, json=body, timeout=15)
        except requests.exceptions.ConnectionError:
            if attempt < max_retries - 1:
                time.sleep(2)
            else:
                raise


def fetch_week_entries(monday=None):
    if monday is None:
        monday = get_monday()
    now = datetime.now(timezone.utc)
    current_monday = get_monday()

    filter_conditions = [
        {"property": "Time", "date": {"on_or_after": monday.isoformat()}},
    ]
    # 如果是过去的一周，限制到该周周日，避免混入后续数据
    if monday < current_monday:
        sunday = monday + timedelta(days=6, hours=23, minutes=59, seconds=59)
        filter_conditions.append(
            {"property": "Time", "date": {"on_or_before": sunday.isoformat()}}
        )

    url = f"https://api.notion.com/v1/databases/{DATABASE_ID}/query"
    body = {
        "filter": {
            "and": filter_conditions,
        },
        "sorts": [{"property": "Time", "direction": "ascending"}],
        "page_size": 100,
    }

    entries = []
    has_more = True
    while has_more:
        resp = _notion_post(url, body)
        if resp.status_code != 200:
            print(f"Notion 查询失败: {resp.status_code} {resp.text[:200]}")
            break
        data = resp.json()
        for page in data.get("results", []):
            props = page.get("properties", {})
            name = _get_title(props.get("App/Task", {}))
            cat = _get_select(props.get("Category", {}))
            proj = _get_select(props.get("Project", {}))
            duration = _get_number(props.get("Duration", {}))
            time_range = _get_date(props.get("Time", {}))

            if not name or not time_range:
                continue

            entries.append({
                "category": cat or "Uncategorized",
                "project": proj or "Uncategorized",
                "start": time_range["start"],
                "end": time_range["end"] or time_range["start"],
                "name": name,
                "durationMin": duration or 0,
            })
        has_more = data.get("has_more", False)
        if has_more:
            body["start_cursor"] = data.get("next_cursor")

    return entries


def _get_title(prop):
    title_arr = prop.get("title", [])
    return title_arr[0].get("plain_text", "") if title_arr else ""


def _get_select(prop):
    sel = prop.get("select")
    return sel.get("name", "") if sel else ""


def _get_number(prop):
    return prop.get("number", 0)


def _get_date(prop):
    d = prop.get("date", {})
    if d.get("start"):
        return {"start": d["start"], "end": d.get("end")}
    return None


def main():
    os.makedirs(CACHE_DIR, exist_ok=True)

    # 支持命令行指定周一日期：widget_export.py --monday 2026-05-18
    monday = None
    args = sys.argv[1:]
    if len(args) >= 2 and args[0] == "--monday":
        try:
            monday = datetime.fromisoformat(args[1]).replace(tzinfo=timezone.utc)
        except ValueError:
            print(f"无效日期: {args[1]}")
            sys.exit(1)

    label = monday.strftime("%Y-%m-%d") if monday else "本周"
    print(f"查询 Notion {label} 数据...")
    entries = fetch_week_entries(monday=monday)
    if monday is None:
        monday = get_monday()

    output = {
        "updated": datetime.now(timezone.utc).isoformat(),
        "weekStart": monday.strftime("%Y-%m-%d"),
        "entries": entries,
    }

    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"已导出 {len(entries)} 条记录 → {CACHE_FILE}")


if __name__ == "__main__":
    main()
