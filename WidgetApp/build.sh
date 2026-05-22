#!/bin/bash
set -e
cd "$(dirname "$0")"
SDK=$(xcrun --sdk macosx --show-sdk-path)

echo "编译 SwiftUI..."
swiftc -parse-as-library -sdk "$SDK" \
  -framework SwiftUI -framework AppKit -framework CoreGraphics \
  -o TimeWidget \
  Sources/DataModel.swift Sources/TimelineView.swift Sources/main.swift

echo "打包 .app..."
rm -rf TimeWidget.app
mkdir -p TimeWidget.app/Contents/MacOS
cp TimeWidget TimeWidget.app/Contents/MacOS/
cp Info.plist TimeWidget.app/Contents/

# 临时签名（避免 Gatekeeper 拦截）
codesign --force --deep -s - TimeWidget.app 2>/dev/null || true

echo "完成: $(pwd)/TimeWidget.app"
echo ""
echo "启动方式:"
echo "  open TimeWidget.app"
echo "  或双击 Finder 中的 TimeWidget.app"
