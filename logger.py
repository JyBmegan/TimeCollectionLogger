import sys
import requests
from datetime import datetime, timedelta
from config import get_notion_api_key, get_notion_database_id

NOTION_API_KEY = get_notion_api_key()
DATABASE_ID = get_notion_database_id()

def push_to_notion(app_name, duration_minutes):
    url = "https://api.notion.com/v1/pages"
    headers = {
        "Authorization": f"Bearer {NOTION_API_KEY}",
        "Content-Type": "application/json",
        "Notion-Version": "2022-06-28"
    }

    # 自动计算这段时间跨度的起止时间
    end_time = datetime.now().astimezone()
    start_time = end_time - timedelta(minutes=int(duration_minutes))

    # 2. 组装发给 Notion 的结构化数据包
    data = {
        "parent": {"database_id": DATABASE_ID},
        "properties": {
            "App/Task": {
                "title": [{"text": {"content": app_name}}]
            },
            "Duration (mins)": {
                "number": int(duration_minutes)
            },
            "Time": {
                "date": {
                    "start": start_time.isoformat(),
                    "end": end_time.isoformat()
                }
            }
        }
    }

    # 3. 发送加密请求并返回结果
    response = requests.post(url, headers=headers, json=data)
    if response.status_code == 200:
        print(f"✅ 记录成功！[{app_name}] 专注了 {duration_minutes} 分钟，已安全同步至 Notion。")
    else:
        print(f"❌ 记录失败，错误信息：\n{response.text}")

if __name__ == "__main__":
    # 接收你在终端输入的指令
    if len(sys.argv) < 3:
        print("用法: uv run logger.py <软件名/任务> <分钟>")
        sys.exit(1)
        
    push_to_notion(sys.argv[1], sys.argv[2])