============================================================
  XP-236B LABEL STUDIO  —  Windows
============================================================

Same label designer as the Mac version (code + QR + logo +
text, English & Persian/Dari). This folder builds/runs it
on Windows.

------------------------------------------------------------
STEP 1 — INSTALL THE PRINTER (do this first)
------------------------------------------------------------
1. Download the XP-236B *Windows* driver from Xprinter
   (the "Seagull/Windows driver" for the XP-236 series), or
   use the CD that came with the printer.
2. Plug the printer in by USB, turn it on, run the driver
   installer, and finish the wizard.
3. Open  Settings > Bluetooth & devices > Printers & scanners
   and confirm a printer appears. If its name is exactly
   "XP-236B", great. If it's named differently, either:
     - rename it to  XP-236B  (right-click > Printer
       properties > change the name), OR
     - just make it your DEFAULT printer (the app falls
       back to the default printer automatically).
4. Right-click the printer > Printing preferences > set the
   PAPER / LABEL SIZE to your label (e.g. 40 x 30 mm). On
   Windows the label size comes from HERE, so set it to
   match the size you pick in the app.
   TIP: calibrate the roll on the printer — power OFF, hold
   FEED, power ON while holding, release after 1-2 blank
   labels feed.

------------------------------------------------------------
STEP 2 — GET THE APP RUNNING (pick ONE option)
------------------------------------------------------------
You need Python 3 installed either way:
  https://www.python.org/downloads/   (tick "Add Python to PATH")

OPTION A — just run it (easiest):
   Double-click   run-without-building.bat
   It installs what it needs and opens the designer in your
   browser. Keep the black window open while printing.

OPTION B — make a standalone .exe (to hand to someone with
           no Python):
   Double-click   build-windows.bat
   When it finishes, the app is in  dist\LabelStudio\ .
   Run  dist\LabelStudio\LabelStudio.exe  (or zip that
   folder and send it to a colleague).

------------------------------------------------------------
USING IT
------------------------------------------------------------
The browser shows the label designer at
   http://127.0.0.1:8236
Design your label, set Copies, click Print. Batch printing,
logo, QR, sizes and layouts all work the same as on Mac.

------------------------------------------------------------
IF PRINTING DOESN'T COME OUT RIGHT
------------------------------------------------------------
- Wrong size / squished: the printer's paper-size setting
  (Step 1.4) must match the size chosen in the app. On
  Windows the driver decides the physical size; the app
  scales its design to fill that page.
- Nothing prints: make sure the XP-236B is the default
  printer, or that its name is exactly  XP-236B .
- Persian/Arabic looks wrong: make sure Arial is present
  (it is, on every standard Windows install).

Questions: ask Rashid.
============================================================
