#!/bin/bash
# One-time setup: installs the Xprinter driver and creates the print queue.
DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"

echo "======================================================"
echo "   XP-236B Label Studio — Setup"
echo "======================================================"
echo

# 0) Remove the macOS 'downloaded from internet' quarantine on this folder
xattr -dr com.apple.quarantine "$DIR" 2>/dev/null || true

# 1) Make sure the Xprinter driver is installed
if [ -f /usr/libexec/cups/filter/rastertosnailtspl-xp ]; then
  echo "[1/3] Xprinter driver already installed. Good."
else
  echo "!! The Xprinter macOS driver is not installed yet."
  echo "   Download it from Xprinter's website (model XP-236B, macOS driver):"
  echo "       https://www.xprintertech.com/  ->  Support / Download"
  echo "   Install the .pkg, then run this Setup again."
  echo "   (If someone gave you a folder that included the driver .pkg, just"
  echo "    double-click that .pkg first, then run this Setup again.)"
  read -r -p "Press Return to close."; exit 1
fi
echo

# 2) Detect the XP-236B on USB (each printer has its own serial number)
echo "[2/3] Looking for the XP-236B on USB..."
URI="$(/usr/libexec/cups/backend/usb 2>/dev/null | grep -i 'XP-236B' | head -1 | awk '{print $2}')"
if [ -z "$URI" ]; then
  echo
  echo "!! XP-236B was not found."
  echo "   -> Connect it by USB, turn it ON, then run this Setup again."
  read -r -p "Press Return to close."; exit 1
fi
echo "      Found printer: $URI"
echo

# 3) Create / update the print queue with the right label settings
echo "[3/3] Creating the print queue 'XP-236B'..."
PPD=/Library/Printers/PPDs/Contents/Resources/XP-236B.ppd
lpadmin -p XP-236B -v "$URI" -P "$PPD" -E \
  -o printer-is-shared=false \
  -o PaperType=LabelGaps -o PostAction=TearOff -o Darkness=8 \
  -o PageSize=Custom.48x40mm 2>/dev/null && echo "      Queue ready." || {
    echo "!! Could not create the queue."; read -r -p "Press Return to close."; exit 1; }

echo
echo "======================================================"
echo "   Setup complete!"
echo "   Now double-click:  2. Start Label Studio"
echo "======================================================"
echo
echo "TIP for the label roll: power the printer OFF, hold the FEED"
echo "button, power it ON while holding, and release after it feeds"
echo "1-2 blank labels. That calibrates the label size."
echo
read -r -p "Press Return to close this window."
