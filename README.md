# TimeCollectionLogger

Mac-native time tracking with ActivityWatch + Notion + desktop widget. Supports multi-Mac sync via iCloud.

## How It Works

```
ActivityWatch (local) → aw_sync.py daemon → Notion (cloud)
                                                    ↓
Desktop Widget (SwiftUI) ← widget_data.json ← widget_export.py
                                                    ↓
                                          iCloud: rules.json (shared)
```

- **aw_sync.py** runs as a background daemon (launchd). Every 5 min it fetches new window events from ActivityWatch, filters, merges, classifies, and pushes sessions to Notion.
- **widget_export.py** runs every 3 min, pulls the week's entries from Notion, writes a local JSON cache.
- **TimeWidget.app** (SwiftUI) reads the cache, renders a transparent desktop timeline. Click any block to open Notion.
- **rules.json** is symlinked to iCloud Drive — both Macs share the same classification rules.

---

## First-Time Setup (Primary Mac)

### 1. Prerequisites
- [ActivityWatch](https://activitywatch.net/) installed and running
- Chrome extension: `aw-watcher-web` (for browser URL tracking)
- Notion integration with API key (https://www.notion.so/my-integrations)
- Notion database with these columns (exact names required):

| Property | Type |
|---|---|
| `App/Task` | Title |
| `Category` | Select |
| `Project` | Select |
| `Duration` | Number |
| `Time` | Date (with time) |

### 2. Clone & Install
```bash
git clone git@github.com:JyBmegan/TimeCollectionLogger.git ~/TimeCollectionLogger
cd ~/TimeCollectionLogger
uv sync
```

### 3. Store Secrets in Keychain
```bash
security add-generic-password -a "$USER" -s "TimeCollectionLogger_NotionKey" -w "ntn_你的api_key"
security add-generic-password -a "$USER" -s "TimeCollectionLogger_NotionDB" -w "你的database_id"
```

### 4. Link Rules to iCloud
```bash
ICLOUD="$HOME/Library/Mobile Documents/com~apple~CloudDocs/TimeLogger"
mkdir -p "$ICLOUD"
mv rules.json "$ICLOUD/"
ln -s "$ICLOUD/rules.json" rules.json
```

### 5. Build Desktop Widget
```bash
cd WidgetApp
bash build.sh
open TimeWidget.app
# Manually add to System Settings → General → Login Items (开机自启)
```

### 6. Start Background Daemon
```bash
mkdir -p logs
cp com.timecollectionlogger.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.timecollectionlogger.plist
# Auto-starts on login. Check status: bash tcl.sh status
```

---

## Multi-Mac Sync (Mac mini, etc.)

### Step 1: Install ActivityWatch
On the second Mac, download and install ActivityWatch from https://activitywatch.net/downloads. Also install the Chrome `aw-watcher-web` extension.

### Step 2: Clone the Code
```bash
git clone git@github.com:JyBmegan/TimeCollectionLogger.git ~/TimeCollectionLogger
cd ~/TimeCollectionLogger
uv sync
```

### Step 3: Import Secrets
Use the SAME Notion API key and database ID as the primary Mac:
```bash
security add-generic-password -a "$USER" -s "TimeCollectionLogger_NotionKey" -w "ntn_你的api_key"
security add-generic-password -a "$USER" -s "TimeCollectionLogger_NotionDB" -w "你的database_id"
```

### Step 4: Link the Shared Rules
This connects to the same iCloud rules.json as your primary Mac:
```bash
rm ~/TimeCollectionLogger/rules.json
ln -s "$HOME/Library/Mobile Documents/com~apple~CloudDocs/TimeLogger/rules.json" ~/TimeCollectionLogger/rules.json
```
Now any new classification you make on either Mac is instantly shared.

### Step 5: Build Widget + Start Daemon
```bash
cd ~/TimeCollectionLogger/WidgetApp
bash build.sh
open TimeWidget.app
# Add to Login Items for auto-start

cd ~/TimeCollectionLogger
mkdir -p logs
cp com.timecollectionlogger.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.timecollectionlogger.plist
```

---

## What Syncs Automatically

| Data | How |
|---|---|
| **Notion entries** | Cloud — all Macs read/write the same Notion database. Edit from any device, changes appear everywhere. |
| **Classification rules** | iCloud Drive — symlinked rules.json shared between Macs |
| **Widget display** | Reads from Notion (refreshed every ~3 min), same on both Macs |

## Managing Entries

All changes are made in Notion and sync across every Mac automatically.

### Edit an entry (category / project / name)

Open Notion → edit the cell directly. Widget picks up changes within ~3 min.
Daemon also learns from your edits every 30 min to improve future auto-classification.

### Delete an entry

**Important:** Notion's "Delete" only moves items to Trash — the API still sees them, so the desktop widget won't remove them.

Two ways to fully delete:

```bash
# Option A: Delete in Notion, then empty Trash (Notion sidebar → Trash → Empty)
# Option B: Archive via API (single command)
uv run aw_sync.py --delete-from-notion "关键词"
```

### Ignore an app entirely

```bash
uv run aw_sync.py --set-rule "应用名" "IGNORE" "IGNORE"
```

### Classification rules

```bash
uv run aw_sync.py --list-rules                # See all rules
uv run aw_sync.py --set-rule "微信" "Entertainment" "WeChat"
uv run aw_sync.py --delete-rule "zoom.us"     # Force re-classify next time
uv run aw_sync.py --sync-rules-from-notion    # Learn from manual edits in Notion
```

### Daemon control

```bash
bash tcl.sh status   # Check if daemon is running
bash tcl.sh logs     # Watch live daemon logs
bash tcl.sh restart  # Restart after code changes
```

---

## What Needs Manual Sync

| Item | How |
|---|---|
| **Code updates** | `git pull` on both Macs, then rebuild Widget (`bash build.sh`) |
| **ActivityWatch data** | Each Mac records independently; data is local, not synced |

## Troubleshooting

**iCloud Drive is full?** Rules.json is only ~4KB. If iCloud is truly full, you can use Git instead:
```bash
# On MacBook after changes:
git add rules.json && git commit -m "Update rules" && git push
# On Mac mini:
git pull
```

**Widget not showing new data?** Force refresh:
```bash
uv run python3 widget_export.py
kill $(pgrep -f TimeWidget); sleep 1; open WidgetApp/TimeWidget.app
```

**Daemon not running?**
```bash
launchctl list | grep timecollection
# If missing:
launchctl load ~/Library/LaunchAgents/com.timecollectionlogger.plist
```
