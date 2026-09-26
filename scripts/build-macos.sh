#!/bin/bash
# Rebuild the macOS Label Studio app and assemble the distributable zip.
# Requires: python3 with pillow qrcode arabic-reshaper python-bidi pyinstaller.
set -e
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT/labelapp"

echo "== Building LabelStudio.app (onedir) =="
rm -rf build dist
python3 -m PyInstaller --onedir --name LabelStudio \
  --collect-data arabic_reshaper --noconfirm server.py

echo "== Assembling bundle =="
BUNDLE="$ROOT/XP236B-Label-Studio"
rm -rf "$BUNDLE/app"
cp -R dist/LabelStudio "$BUNDLE/app"
chmod +x "$BUNDLE/app/LabelStudio" "$BUNDLE"/*.command

echo "== Zipping =="
cd "$ROOT"
rm -f XP236B-Label-Studio-macOS.zip
zip -r -y -X "XP236B-Label-Studio-macOS.zip" "XP236B-Label-Studio" >/dev/null
echo "Done -> $ROOT/XP236B-Label-Studio-macOS.zip"
