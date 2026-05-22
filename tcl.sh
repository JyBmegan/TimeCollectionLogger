#!/bin/bash
# TimeCollectionLogger 后台管理脚本
# 用法: bash tcl.sh [start|stop|restart|status|logs]

PROJECT_DIR="/Users/Megan/0_MyFolders/0_Projects/TimeCollectionLogger"
PLIST_NAME="com.timecollectionlogger.plist"
PLIST_PATH="$HOME/Library/LaunchAgents/$PLIST_NAME"

case "${1:-status}" in
  start)
    cp "$PROJECT_DIR/$PLIST_NAME" "$PLIST_PATH"
    launchctl load "$PLIST_PATH"
    echo "已启动 TimeCollectionLogger 后台守护。"
    ;;
  stop)
    launchctl unload "$PLIST_PATH" 2>/dev/null
    rm -f "$PLIST_PATH"
    echo "已停止。"
    ;;
  restart)
    launchctl unload "$PLIST_PATH" 2>/dev/null
    sleep 1
    cp "$PROJECT_DIR/$PLIST_NAME" "$PLIST_PATH"
    launchctl load "$PLIST_PATH"
    echo "已重启。"
    ;;
  status)
    if launchctl list | grep -q timecollection; then
      echo "● 运行中"
      echo "--- 最近日志 ---"
      tail -8 "$PROJECT_DIR/logs/daemon.log" 2>/dev/null
    else
      echo "○ 未运行"
    fi
    ;;
  logs)
    tail -f "$PROJECT_DIR/logs/daemon.log"
    ;;
  *)
    echo "用法: bash tcl.sh [start|stop|restart|status|logs]"
    ;;
esac
