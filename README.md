# TimeCollectionLogger

A privacy-first, automated time-tracking system that captures your computer activity and syncs it seamlessly to [Notion](https://notion.so/).

## 1. Features
- **Privacy-Centric**: All raw data stays locally on your machine. No third-party servers involved.
- **Automated Sync**: Leverages `ActivityWatch` for passive monitoring.
- **Intelligent Cleaning**: 
  - Filters out background noise and idle time.
  - Automatically merges short task switches (e.g., checking messages) to maintain focus integrity.
  - Smart categorization based on customizable rules.
- **Notion Integration**: Beautifully logs your work sessions into your Notion Database.

## 2. Tech Stack
- **Data Collection**: [ActivityWatch](https://activitywatch.net/)
- **Core Engine**: Python (managed via `uv`)
- **Backend Sync**: Notion API
- **Task Scheduling**: macOS `launchd`

## 3. Getting Started

### 3.1 Prerequisites
- Install [ActivityWatch](https://activitywatch.net/) on your Mac.
- Get a Notion API Key and a Database ID.

### 3.2 Setup
Clone the repository and set up your environment:
```bash
git clone [https://github.com/yourusername/TimeCollectionLogger.git](https://github.com/yourusername/TimeCollectionLogger.git)
cd TimeCollectionLogger
uv sync
```


### 3.3 Configuration

Create a `.env` file in the project root:

```env
NOTION_API_KEY=your_integration_token
NOTION_DATABASE_ID=your_database_id
```

### 3.4 Running the Sync

You can test the synchronization manually:

```bash
uv run aw_sync_v2.py
```

## 4. Privacy Notice

Your usage data is personal. This project is built under the principle of "Local-First". The Python scripts process your logs locally, ensuring that only the summarized and sanitized data you choose is sent to the cloud.

