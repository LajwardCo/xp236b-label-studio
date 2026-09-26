# XP‑236B Label Studio

A tiny local web app to design and print asset/inventory labels on the
**Xprinter XP‑236B** thermal label printer (2‑inch / 48 mm head, 203 dpi).

Everything runs locally on the machine the printer is plugged into — the label
is rendered on the server with Pillow, so the on‑screen preview is exactly what
prints.

## Features
- **Code + QR** asset tags (QR encodes the code by default)
- **Layouts:** stacked (code over QR) or side‑by‑side (QR beside text)
- **Up to 3 text lines** + **two footer lines**
- **Company logo** (auto‑converted to crisp black & white)
- **Any language** — Latin *and* Arabic/Persian/Dari/Pashto (auto‑shaped,
  right‑to‑left), including mixed strings like `اتاق پشتیبانی (No: 30)`
- **Label sizes:** 60×40 mm (48 mm printable) and 40×30 mm
- **Horizontal nudge** to fine‑tune print alignment
- **Sequential batch printing** — e.g. `CH‑00001 → CH‑00099` in one run
- Single local page at <http://127.0.0.1:8236>

## Online version
A browser‑based designer is deployed with GitHub Pages — no install needed to
**design** labels: **https://lajwardco.github.io/xp236b-label-studio/**
Printing from the web page goes through the browser's print dialog (Ctrl/Cmd‑P →
pick the XP‑236B). For exact sizing and one‑click batch runs, use the desktop app.

## Repository layout
| Path | What |
|------|------|
| `docs/index.html` | The **web** designer (GitHub Pages) |
| `labelapp/server.py` | The desktop app (cross‑platform: macOS/Linux via CUPS `lp`, Windows via GDI) |
| `XP236B-Label-Studio/` | macOS distributable template (setup + launcher `.command` scripts, README) |
| `XP236B-Label-Studio-Windows/` | Windows build kit (source + `.bat` scripts + README) |
| `scripts/build-macos.sh` | Rebuilds the macOS app + bundle zip |

> **Downloads:** ready‑to‑run desktop bundles are attached to each
> [GitHub Release](../../releases) — not committed to git.
>
> **Printer driver is not included** (it's Xprinter's proprietary software).
> Get the XP‑236B driver from <https://www.xprintertech.com/> — macOS `.pkg`
> or the Windows driver — and install it before first use.

## Build

### macOS (Apple Silicon)
```bash
./scripts/build-macos.sh
```
Produces `XP236B-Label-Studio-macOS.zip`. Recipient: unzip → right‑click
*“1. Setup (run first)”* → *“2. Start Label Studio”*.

### Windows
Copy `XP236B-Label-Studio-Windows/` to a Windows PC with Python 3, then either
double‑click `run-without-building.bat` (just runs it) or `build-windows.bat`
(produces a standalone `LabelStudio.exe`). See `README-WINDOWS.txt`.

## Requirements
- **Printer:** Xprinter XP‑236B on USB, with its vendor driver installed
  (download from <https://www.xprintertech.com/> for macOS or Windows).
- **Build tooling:** Python 3 + `pillow qrcode arabic-reshaper python-bidi
  pyinstaller` (plus `pywin32` on Windows).
