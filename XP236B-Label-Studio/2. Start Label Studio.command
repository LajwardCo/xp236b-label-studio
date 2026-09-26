#!/bin/bash
# Starts Label Studio and opens it in your browser.
DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"

# If it's already running, just open the browser to it.
if curl -s -m 2 -o /dev/null http://127.0.0.1:8236/ ; then
  open "http://127.0.0.1:8236/"
  exit 0
fi

echo "Starting Label Studio…"
echo "(The very first time can take ~15 seconds while macOS checks the app."
echo " After that it opens instantly.)"
echo
echo "Keep THIS window open while you print. Closing it quits Label Studio."
echo

# Launch the app (it opens your browser automatically once ready).
xattr -dr com.apple.quarantine "$DIR/app" 2>/dev/null || true
exec "$DIR/app/LabelStudio"
