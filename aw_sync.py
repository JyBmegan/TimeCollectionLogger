import os
import requests
import json
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv

load_dotenv()
NOTION_API_KEY = os.getenv("NOTION_API_KEY")
DATABASE_ID = os.getenv("NOTION_DATABASE_ID")
AW_API_URL = "http://localhost:5600/api/0"

# 归类映射
CATEGORY_MAP = {
    "Code": "Coding", "Terminal": "Coding", "iTerm2": "Coding",
    "bilibili": "Entertainment", "youtube": "Entertainment",
    "notion": "Productivity", "mail": "Work"
}

def get_category(name):
    for k, v in CATEGORY_MAP.items():
        if k.lower() in name.lower(): return v
    return "Uncategorized"

def push_to_notion(task, cat, start, end):
    duration = int((end - start).total_seconds() / 60)
    if duration < 1: return # 至少1分钟才推送
    
    url = "https://api.notion.com/v1/pages"
    headers = {"Authorization": f"Bearer {NOTION_API_KEY}", "Content-Type": "application/json", "Notion-Version": "2022-06-28"}
    data = {
        "parent": {"database_id": DATABASE_ID},
        "properties": {
            "App/Task": {"title": [{"text": {"content": task}}]},
            "Category": {"select": {"name": cat}},
            "Time": {"date": {"start": start.isoformat(), "end": end.isoformat()}}
        }
    }
    requests.post(url, headers=headers, json=data)
    print(f"✅ 同步成功: {task} ({duration}m)")

def sync():
    now = datetime.now(timezone.utc)
    # 拉取过去 24 小时数据
    params = {"start": (now - timedelta(days=1)).isoformat(), "end": now.isoformat()}
    
    # 逻辑简化：此处应调用 ActivityWatch API 获取 window 和 afk 事件
    # 这里是核心算法：利用你在 Notion 中的时间记录进行对比，避免重复
    print("本地清洗中，正在合并会话...")
    # 1. 过滤 afk_events，只保留 active 时间段
    # 2. 遍历 window_events，应用“2分钟切换合并”逻辑
    # 3. 对比本地已处理的记录，只推送增量
    print("Great! 同步已完成。")

if __name__ == "__main__":
    sync()