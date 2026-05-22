# TimeCollectionLogger

A privacy-first, automated time-tracking system that captures your computer activity and syncs it seamlessly to [Notion](https://notion.so/), with a native macOS desktop widget for at-a-glance time visualization.

## 1. Features
- **Desktop Widget**: A native SwiftUI widget that renders your daily timeline directly on the desktop, with clickable blocks linking to your Notion workspace.
- **Privacy-Centric**: All raw data stays locally on your machine. No third-party servers involved.
- **Automated Sync**: Leverages `ActivityWatch` for passive monitoring.
- **Intelligent Cleaning**: 
  - Filters out background noise and idle time.
  - **Smart Merge**: Category-aware gap merging — Research/Exploration/Work sessions within 30 minutes are merged; Entertainment/Web within 5 minutes; everything else within 10 minutes. Merging scans *all* existing entries (not just the last one) to handle reordered events.
  - **Two-Step Classification Dialog**: When an unknown app is detected, a native macOS dialog guides you through picking a high-level category first, then a specific project name — making classification faster and more consistent.
- **Customizable Rules**: Classification rules stored in `rules.json` — persist your decisions so the same app always maps to the same category and project.
- **Notion Integration**: Beautifully logs your work sessions into your Notion Database.

## 2. Tech Stack
- **Data Collection**: [ActivityWatch](https://activitywatch.net/)
- **Desktop Widget**: Swift + SwiftUI (native macOS widget app)
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

