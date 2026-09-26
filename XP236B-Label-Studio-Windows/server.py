#!/usr/bin/env python3
"""
XP-236B Label Studio — a tiny local web app to design & print 48x40mm labels.

Renders the label on the server (Pillow) so the on-screen preview is byte-for-byte
what gets printed. Prints via CUPS `lp` to the XP-236B queue.

Run:  python3 server.py   then open http://127.0.0.1:8236
"""
import io, json, subprocess, tempfile, os, html, base64, sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from PIL import Image, ImageDraw, ImageFont, ImageOps, ImageOps
import re
import qrcode

# optional Arabic/Persian shaping (joining + right-to-left)
try:
    import arabic_reshaper
    from bidi.algorithm import get_display
    _SHAPE = True
except Exception:
    _SHAPE = False

_ARABIC_RE = re.compile(r"[؀-ۿݐ-ݿࢠ-ࣿﭐ-﷿ﹰ-﻿]")

def has_arabic(s):
    return bool(s) and bool(_ARABIC_RE.search(s))

def prep(s):
    """Return display-ready text: shape+reorder Arabic/Persian, leave the rest."""
    if _SHAPE and has_arabic(s):
        return get_display(arabic_reshaper.reshape(s))
    return s

PRINTER = "XP-236B"
LOGO_PATH = os.path.expanduser("~/.xp236b_label_logo.png")  # stable per-user, survives bundling
DPI = 203
PORT = 8236
HEAD_MAX_MM = 48       # print head physical width limit

# Selectable label rolls. print_w = printable width (capped at the 48mm head);
# label_w is the physical roll width (only used for the on-screen note).
SIZES = {
    "60x40": {"name": "60 × 40 mm", "label_w": 60, "print_w": 48, "h": 40},
    "40x30": {"name": "40 × 30 mm", "label_w": 40, "print_w": 40, "h": 30},
}
DEFAULT_SIZE = "60x40"

def mm(v):  # mm -> px at 203 dpi
    return int(round(v / 25.4 * DPI))

def size_cfg(key):
    s = SIZES.get(key, SIZES[DEFAULT_SIZE])
    return mm(s["print_w"]), mm(s["h"]), f"Custom.{s['print_w']}x{s['h']}mm"

# ---- fonts -------------------------------------------------------------
# Arial carries both Latin AND Arabic-presentation-form glyphs, so a single font
# renders mixed Persian+Latin (e.g. "اتاق پشتیبانی (32)") without tofu boxes.
# Each entry is a list of candidate paths tried in order (per-OS), first hit wins.
if sys.platform == "win32":
    FONT_PATHS = {
        "bold":    [r"C:\Windows\Fonts\arialbd.ttf", r"C:\Windows\Fonts\tahomabd.ttf"],
        "regular": [r"C:\Windows\Fonts\arial.ttf",   r"C:\Windows\Fonts\tahoma.ttf"],
    }
elif sys.platform == "darwin":
    FONT_PATHS = {
        "bold":    ["/System/Library/Fonts/Supplemental/Arial Bold.ttf"],
        "regular": ["/System/Library/Fonts/Supplemental/Arial.ttf"],
    }
else:  # linux
    FONT_PATHS = {
        "bold":    ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"],
        "regular": ["/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"],
    }

def font(kind, size, arabic=False):
    for p in FONT_PATHS.get(kind, FONT_PATHS["regular"]):
        try:
            return ImageFont.truetype(p, size)
        except Exception:
            continue
    return ImageFont.load_default()

def text_w(d, s, f):
    b = d.textbbox((0, 0), s, font=f)
    return b[2] - b[0]

def fit_font(d, s, kind, max_w, start, min_size=12, arabic=False):
    """Largest font size (<= start) that fits display-string s within max_w px."""
    size = start
    while size > min_size:
        f = font(kind, size, arabic)
        if text_w(d, s, f) <= max_w:
            return f
        size -= 2
    return font(kind, min_size, arabic)

# ---- label rendering ---------------------------------------------------
def render_qr(value, px):
    qr = qrcode.QRCode(border=0, box_size=10,
                       error_correction=qrcode.constants.ERROR_CORRECT_M)
    qr.add_data(value)
    qr.make(fit=True)
    q = qr.make_image(fill_color="black", back_color="white").convert("RGB")
    return q.resize((px, px), Image.NEAREST)

def center(d, y, s, f, W):
    w = text_w(d, s, f)
    d.text(((W - w) // 2, y), s, font=f, fill="black")

def process_logo(raw_bytes):
    """Convert any uploaded image to trimmed grayscale for crisp B/W thermal print."""
    im = Image.open(io.BytesIO(raw_bytes))
    if im.mode in ("RGBA", "LA", "P"):
        im = im.convert("RGBA")
        bg = Image.new("RGBA", im.size, (255, 255, 255, 255))
        bg.alpha_composite(im)
        im = bg.convert("L")
    else:
        im = im.convert("L")
    im = ImageOps.autocontrast(im)
    # trim surrounding white
    inv = ImageOps.invert(im)
    bbox = inv.getbbox()
    if bbox:
        im = im.crop(bbox)
    im.save(LOGO_PATH, "PNG")
    return im.size

def load_logo(max_w, max_h):
    """Return a black/white RGB logo scaled to fit (max_w,max_h), or None."""
    if not os.path.exists(LOGO_PATH):
        return None
    try:
        im = Image.open(LOGO_PATH).convert("L")
    except Exception:
        return None
    scale = min(max_w / im.width, max_h / im.height)
    nw, nh = max(1, int(im.width * scale)), max(1, int(im.height * scale))
    im = im.resize((nw, nh), Image.LANCZOS)
    im = im.point(lambda p: 0 if p < 140 else 255).convert("1")  # crisp B/W
    return im.convert("RGB")

def _th(d, s, f):  # text height
    return d.textbbox((0, 0), s, font=f)[3]

def render_label(data):
    """Asset tag. layout='stacked' (code/QR over each other) or 'side' (code+QR next to each other)."""
    W, H, _ = size_cfg(data.get("size"))
    img = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(img)

    layout = data.get("layout") or "stacked"
    code   = (data.get("code")   or "").strip()
    line2  = (data.get("line2")  or "").strip()
    line3  = (data.get("line3")  or "").strip()
    footer  = (data.get("footer")  or "").strip()
    footer2 = (data.get("footer2") or "").strip()
    # QR encodes the ORIGINAL logical text (never the reshaped display form)
    qr_val = (data.get("qr_value") or "").strip() or code or footer

    code_d, code_ar = prep(code),  has_arabic(code)
    l2_d,   l2_ar   = prep(line2), has_arabic(line2)
    l3_d,   l3_ar   = prep(line3), has_arabic(line3)
    show_logo = bool(data.get("logo"))

    pad = mm(2)
    # footer (1 or 2 lines) is shared by both layouts, pinned to the bottom
    foot_gap = mm(0.6)
    foot_items = []  # (display, font, height)
    for txt in (footer, footer2):
        if not txt:
            continue
        f = fit_font(d, prep(txt), "regular", W - mm(4), mm(3.8), min_size=11, arabic=has_arabic(txt))
        disp = prep(txt)
        foot_items.append((disp, f, _th(d, disp, f)))
    h_foot_total = sum(h for _, _, h in foot_items) + foot_gap * max(0, len(foot_items) - 1)
    bottom_pad = mm(1.5)
    h_foot = (h_foot_total + mm(2)) if foot_items else 0
    content_bottom = H - h_foot - bottom_pad

    if layout == "side":
        # ---- QR on the left, text column on the right ----
        avail_h = content_bottom - pad
        gap = mm(1.2)

        def build_blocks(tw):
            blocks = []
            if show_logo:
                lg = load_logo(tw, int(H * 0.24))
                if lg: blocks.append(("logo", lg))
            if code:
                f = fit_font(d, code_d, "bold", tw, mm(6), min_size=13, arabic=code_ar)
                blocks.append(("text", code_d, f))
            if line2:
                f = fit_font(d, l2_d, "regular", tw, mm(4), min_size=11, arabic=l2_ar)
                blocks.append(("text", l2_d, f))
            if line3:
                f = fit_font(d, l3_d, "regular", tw, mm(3.4), min_size=10, arabic=l3_ar)
                blocks.append(("text", l3_d, f))
            hs = [b[1].height if b[0] == "logo" else _th(d, b[1], b[2]) for b in blocks]
            total = sum(hs) + gap * max(0, len(blocks) - 1)
            return blocks, hs, total

        # pass 1: estimate text height, then size the QR to match it
        _, _, text_h = build_blocks(W - 2 * pad - mm(15) - mm(2))
        qpx = max(mm(11), min(text_h, avail_h)) if qr_val else 0  # match text, keep scannable

        tx0 = pad
        if qpx > mm(6):
            img.paste(render_qr(qr_val, qpx), (pad, pad + (avail_h - qpx) // 2))
            tx0 = pad + qpx + mm(2)

        # pass 2: lay out text in the real remaining width, centered on the QR
        blocks, heights, total = build_blocks(W - pad - tx0)
        by = pad + max(0, (avail_h - total) // 2)
        for b, hh in zip(blocks, heights):
            if b[0] == "logo":
                img.paste(b[1], (tx0, by))
            else:
                d.text((tx0, by), b[1], font=b[2], fill="black")
            by += hh + gap
    else:
        # ---- stacked: logo+code on top, line2, then QR centered below ----
        y = pad
        logo = load_logo(int(W * 0.42), int(H * 0.28)) if show_logo else None
        if logo:
            gap = mm(1.5)
            cmax = W - mm(3) - logo.width - gap
            f = fit_font(d, code_d, "bold", max(mm(6), cmax), mm(6), min_size=14, arabic=code_ar) if code else None
            cw = text_w(d, code_d, f) if code else 0
            ch = _th(d, code_d, f) if code else 0
            band_h = max(logo.height, ch)
            block_w = logo.width + (gap + cw if code else 0)
            x0 = (W - block_w) // 2
            img.paste(logo, (x0, y + (band_h - logo.height) // 2))
            if code:
                d.text((x0 + logo.width + gap, y + (band_h - ch) // 2), code_d, font=f, fill="black")
            y += band_h + mm(1.5)
        elif code:
            f = fit_font(d, code_d, "bold", W - mm(6), mm(7), min_size=18, arabic=code_ar)
            center(d, y, code_d, f, W)
            y += _th(d, code_d, f) + mm(1.2)
        if line2:
            f = fit_font(d, l2_d, "regular", W - mm(6), mm(4), min_size=12, arabic=l2_ar)
            center(d, y, l2_d, f, W)
            y += _th(d, l2_d, f) + mm(1.0)
        if line3:
            f = fit_font(d, l3_d, "regular", W - mm(6), mm(3.4), min_size=10, arabic=l3_ar)
            center(d, y, l3_d, f, W)
            y += _th(d, l3_d, f) + mm(1.0)
        avail_h = content_bottom - y
        if qr_val and avail_h > mm(6):
            qpx = min(avail_h, W - mm(6))
            img.paste(render_qr(qr_val, qpx), ((W - qpx) // 2, y))

    # footer lines, stacked and pinned to the bottom (both layouts)
    if foot_items:
        fy = H - bottom_pad - h_foot_total
        for disp, f, h in foot_items:
            center(d, fy, disp, f, W)
            fy += h + foot_gap

    # horizontal calibration nudge (mm): negative = shift content left
    try:
        nudge = float(data.get("nudge") or 0)
    except (TypeError, ValueError):
        nudge = 0
    if nudge:
        dx = int(round(nudge / 25.4 * DPI))
        shifted = Image.new("RGB", (W, H), "white")
        shifted.paste(img, (dx, 0))
        img = shifted

    return img

# ---- batch / sequential ------------------------------------------------
BATCH_CAP = 500

def parse_code(s):
    """Split a code into (prefix, digits, suffix), e.g. 'CH-00001' -> ('CH-','00001','')."""
    m = re.search(r"^(.*?)(\d+)(\D*)$", (s or "").strip())
    return (m.group(1), m.group(2), m.group(3)) if m else None

def expand_range(from_code, to_code):
    """Inclusive list of codes from 'from_code' to 'to_code', preserving prefix + zero-pad."""
    a = parse_code(from_code)
    if not a:
        return None, "Start code must contain a number (e.g. CH-00001)."
    pre, dig, suf = a
    start, width = int(dig), len(dig)
    b = parse_code(to_code)
    if b:
        end = int(b[1])
    else:
        try: end = int((to_code or "").strip())
        except ValueError: end = start
    if end < start:
        start, end = end, start
    n = end - start + 1
    if n > BATCH_CAP:
        return None, f"Range is {n} labels — max {BATCH_CAP} per batch."
    return [f"{pre}{str(i).zfill(width)}{suf}" for i in range(start, end + 1)], None

# ---- print -------------------------------------------------------------
def print_label(img, copies=1, media="Custom.48x40mm"):
    if sys.platform == "win32":
        return _print_windows(img, copies)
    return _print_cups(img, copies, media)

def _print_cups(img, copies, media):
    """macOS / Linux: send the PNG through CUPS `lp` at the exact media size."""
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tf:
        path = tf.name
    img.save(path, "PNG")
    try:
        r = subprocess.run(
            ["lp", "-d", PRINTER, "-n", str(copies), "-o", f"media={media}", path],
            capture_output=True, text=True, timeout=30)
        out = (r.stdout + r.stderr).strip()
        return r.returncode == 0, out
    finally:
        try: os.unlink(path)
        except Exception: pass

def _print_windows(img, copies):
    """Windows: draw the label to the printer DC, scaled to its printable area.
    The label size comes from the printer's own paper setting in the driver —
    set the XP-236B default paper to match the size chosen in the app."""
    try:
        import win32print, win32ui
        from PIL import ImageWin
    except Exception:
        return False, "Windows printing needs pywin32 (pip install pywin32)."
    name = PRINTER
    try:
        h = win32print.OpenPrinter(name)
        win32print.ClosePrinter(h)
    except Exception:
        # fall back to the system default printer if XP-236B isn't the exact name
        try:
            name = win32print.GetDefaultPrinter()
        except Exception:
            return False, "No printer named 'XP-236B' and no default printer set."
    try:
        hDC = win32ui.CreateDC()
        hDC.CreatePrinterDC(name)
        pw = hDC.GetDeviceCaps(8)   # HORZRES  (printable width, px)
        ph = hDC.GetDeviceCaps(10)  # VERTRES  (printable height, px)
        dib = ImageWin.Dib(img.convert("RGB"))
        for _ in range(max(1, copies)):
            hDC.StartDoc("Label")
            hDC.StartPage()
            dib.draw(hDC.GetHandleOutput(), (0, 0, pw, ph))
            hDC.EndPage()
            hDC.EndDoc()
        hDC.DeleteDC()
        return True, f"sent to {name}"
    except Exception as e:
        return False, f"Windows print error: {e}"

# ---- HTTP --------------------------------------------------------------
PAGE = r"""<!doctype html><html><head><meta charset=utf-8>
<meta name=viewport content="width=device-width,initial-scale=1">
<title>XP-236B Label Studio</title>
<style>
 :root{--bg:#0f1115;--card:#181b22;--line:#2a2f3a;--fg:#e8eaed;--mut:#9aa4b2;--acc:#4c8dff}
 @media(prefers-color-scheme:light){:root{--bg:#f4f5f7;--card:#fff;--line:#e2e5ea;--fg:#1a1c20;--mut:#5b6472;--acc:#2f6bff}}
 *{box-sizing:border-box}body{margin:0;font:15px/1.4 -apple-system,system-ui,sans-serif;background:var(--bg);color:var(--fg)}
 .wrap{max-width:900px;margin:0 auto;padding:24px}
 h1{font-size:20px;margin:0 0 2px}.sub{color:var(--mut);font-size:13px;margin:0 0 20px}
 .grid{display:grid;grid-template-columns:1fr 360px;gap:24px}@media(max-width:760px){.grid{grid-template-columns:1fr}}
 .card{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:18px}
 label{display:block;font-size:12px;color:var(--mut);margin:12px 0 4px;text-transform:uppercase;letter-spacing:.04em}
 input,select{width:100%;padding:9px 11px;border:1px solid var(--line);border-radius:9px;background:var(--bg);color:var(--fg);font-size:15px}
 .row{display:flex;gap:10px;align-items:center}.row input[type=checkbox]{width:auto}
 .row label{margin:0;text-transform:none;letter-spacing:0;font-size:14px;color:var(--fg)}
 .half{display:grid;grid-template-columns:1fr 1fr;gap:10px}
 button{margin-top:18px;width:100%;padding:12px;border:0;border-radius:10px;background:var(--acc);color:#fff;font-size:16px;font-weight:600;cursor:pointer}
 button:active{transform:translateY(1px)}
 .preview{display:flex;flex-direction:column;align-items:center;gap:10px;position:sticky;top:24px}
 .paper{background:#fff;border-radius:6px;box-shadow:0 6px 24px rgba(0,0,0,.25);padding:0;overflow:hidden}
 .paper img{display:block;image-rendering:pixelated}
 .dim{color:var(--mut);font-size:12px}
 .status{margin-top:12px;font-size:13px;min-height:18px}
 .ok{color:#3fb950}.err{color:#f85149}
 .copies{display:grid;grid-template-columns:1fr auto;gap:10px;align-items:end}
 .logorow{display:grid;grid-template-columns:1fr auto;gap:10px;align-items:center;margin-bottom:6px}
 .ghost{margin:0;background:transparent;border:1px solid var(--line);color:var(--fg);width:auto;padding:8px 14px;font-size:14px;cursor:pointer}
 .batchbox{margin-top:20px;padding-top:16px;border-top:1px dashed var(--line)}
 .batchhead{font-size:13px;font-weight:600;margin-bottom:10px}
</style></head><body><div class=wrap>
 <h1>XP-236B Label Studio</h1>
 <p class=sub>203&nbsp;dpi &nbsp;•&nbsp; prints straight to your Xprinter</p>
 <div class=grid>
  <div class=card>
   <label>Label size</label>
   <select id=size>
     <option value=60x40 selected>60 × 40 mm roll  (48 mm printable)</option>
     <option value=40x30>40 × 30 mm roll  (full width)</option>
   </select>
   <label>Shift left / right <span class=dim>(mm — negative = left, to remove left margin)</span></label>
   <div class=row><input id=nudge type=range min=-8 max=8 step=0.5 value=0 style=flex:1><span id=nudgeval class=dim style=min-width:52px>0.0 mm</span></div>
   <div class=row style="margin:14px 0 4px"><input type=checkbox id=logo><label for=logo>Show company logo</label></div>
   <div class=logorow>
     <input id=logofile type=file accept="image/*" style="padding:6px">
     <button type=button id=clearlogo class=ghost>Clear</button>
   </div>
   <label>Layout</label>
   <select id=layout>
     <option value=stacked selected>Stacked — code &amp; QR over each other</option>
     <option value=side>Side by side — code &amp; QR next to each other</option>
   </select>
   <label>Code</label><input id=code placeholder="IT-00393" value="IT-00393">
   <label>Second line <span class=dim>(optional)</span></label><input id=line2 placeholder="e.g. Dept / model" value="">
   <label>Third line <span class=dim>(optional)</span></label><input id=line3 placeholder="e.g. date / serial" value="">
   <label>QR encodes <span class=dim>(leave blank = same as code)</span></label>
   <input id=qr_value placeholder="IT-00393 (or a URL)" value="">
   <label>Footer line 1</label><input id=footer value="Property of the Hamagan">
   <label>Footer line 2 <span class=dim>(optional)</span></label><input id=footer2 placeholder="اتاق پشتیبانی (32)" value="">
   <div class=copies>
     <div><label>Copies</label><input id=copies type=number min=1 max=200 value=1></div>
     <button id=print style=margin:0>🖨️ Print one</button>
   </div>
   <div class=status id=status></div>

   <div class=batchbox>
    <div class=batchhead>Sequential batch <span class=dim>— increments the number, everything else stays the same</span></div>
    <div class=half>
      <div><label>From code</label><input id=from_code placeholder="CH-00001"></div>
      <div><label>To code</label><input id=to_code placeholder="CH-00099"></div>
    </div>
    <button id=printbatch class=ghost style="margin-top:14px;width:100%">🖨️ Print batch — <span id=batchcount>0</span> labels</button>
    <div class=status id=batchstatus></div>
   </div>
  </div>
  <div class=preview>
   <div class=paper><img id=prev src=""></div>
   <div class=dim>live preview • actual size 48×40mm</div>
  </div>
 </div>
</div>
<script>
 const ids=['size','layout','code','line2','line3','qr_value','footer','footer2','copies','logo','nudge'];
 const SCALE=6; // screen px per mm
 const DIMS={'60x40':[48,40],'40x30':[40,30]};
 const g=id=>document.getElementById(id);
 function data(){return{size:g('size').value,layout:g('layout').value,code:g('code').value,line2:g('line2').value,line3:g('line3').value,qr_value:g('qr_value').value,footer:g('footer').value,footer2:g('footer2').value,logo:g('logo').checked,nudge:parseFloat(g('nudge').value)||0};}
 function sizePreview(){const[w,h]=DIMS[g('size').value]||[48,40];const im=g('prev');im.style.width=(w*SCALE)+'px';im.style.height=(h*SCALE)+'px';
   g('nudgeval').textContent=(parseFloat(g('nudge').value)||0).toFixed(1)+' mm';
   localStorage.setItem('nudge',g('nudge').value);}
 // logo upload
 g('logofile').addEventListener('change',async e=>{
   const file=e.target.files[0]; if(!file)return;
   const r=await fetch('/upload_logo',{method:'POST',body:file});
   const j=await r.json();
   if(j.ok){g('logo').checked=true; refresh();}
   else{g('status').textContent='✗ logo: '+(j.msg||'error'); g('status').className='status err';}
 });
 g('clearlogo').addEventListener('click',async()=>{
   await fetch('/clear_logo',{method:'POST'}); g('logo').checked=false; g('logofile').value=''; refresh();
 });
 let t;
 function refresh(){sizePreview();clearTimeout(t);t=setTimeout(async()=>{
   const r=await fetch('/preview',{method:'POST',body:JSON.stringify(data())});
   if(r.ok){const b=await r.blob();g('prev').src=URL.createObjectURL(b);}
 },200);}
 const savedNudge=localStorage.getItem('nudge'); if(savedNudge!==null)g('nudge').value=savedNudge;
 ids.forEach(id=>{const el=g(id);el&&el.addEventListener('input',refresh);el&&el.addEventListener('change',refresh);});
 g('print').addEventListener('click',async()=>{
   const s=g('status');s.textContent='Printing…';s.className='status';
   const body=data();body.copies=parseInt(g('copies').value)||1;
   const r=await fetch('/print',{method:'POST',body:JSON.stringify(body)});
   const j=await r.json();
   s.textContent=j.ok?('✓ Sent to printer '+(j.msg||'')):('✗ '+(j.msg||'print failed'));
   s.className='status '+(j.ok?'ok':'err');
 });
 // ---- batch ----
 function batchCount(){
   const pa=g('from_code').value.match(/(\d+)\D*$/);
   if(!pa)return 0;
   let a=parseInt(pa[1]);
   const pb=g('to_code').value.match(/(\d+)\D*$/);
   let b=pb?parseInt(pb[1]):(g('to_code').value.trim()!==''?parseInt(g('to_code').value):a);
   if(isNaN(a))return 0; if(isNaN(b))b=a;
   return Math.abs(b-a)+1;
 }
 function updBatch(){g('batchcount').textContent=batchCount();}
 ['from_code','to_code'].forEach(id=>{
   g(id).addEventListener('input',()=>{updBatch();
     if(id==='from_code'&&g('from_code').value.trim()){g('code').value=g('from_code').value;refresh();}});
 });
 g('printbatch').addEventListener('click',async()=>{
   const n=batchCount(); const s=g('batchstatus');
   if(n<1){s.textContent='✗ Enter a valid From code (with a number).';s.className='status err';return;}
   if(!confirm('Print '+n+' labels from '+g('from_code').value+' to '+g('to_code').value+'?'))return;
   s.textContent='Printing '+n+' labels…';s.className='status';
   const body=data();body.from_code=g('from_code').value;body.to_code=g('to_code').value;
   const r=await fetch('/print_batch',{method:'POST',body:JSON.stringify(body)});
   const j=await r.json();
   s.textContent=(j.ok?'✓ ':'✗ ')+(j.msg||'');s.className='status '+(j.ok?'ok':'err');
 });
 updBatch();
 refresh();
</script>
</body></html>"""

class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def _body(self):
        n = int(self.headers.get("content-length", 0))
        try: return json.loads(self.rfile.read(n) or b"{}")
        except Exception: return {}
    def do_GET(self):
        if self.path in ("/", "/index.html"):
            b = PAGE.encode()
            self.send_response(200); self.send_header("content-type","text/html; charset=utf-8")
            self.send_header("content-length",str(len(b))); self.end_headers(); self.wfile.write(b)
        else:
            self.send_response(404); self.end_headers()
    def do_POST(self):
        if self.path == "/preview":
            img = render_label(self._body())
            bio = io.BytesIO(); img.save(bio,"PNG"); b=bio.getvalue()
            self.send_response(200); self.send_header("content-type","image/png")
            self.send_header("content-length",str(len(b))); self.end_headers(); self.wfile.write(b)
        elif self.path == "/upload_logo":
            n = int(self.headers.get("content-length", 0))
            raw = self.rfile.read(n)
            try:
                size = process_logo(raw)
                b = json.dumps({"ok": True, "w": size[0], "h": size[1]}).encode()
            except Exception as e:
                b = json.dumps({"ok": False, "msg": str(e)}).encode()
            self.send_response(200); self.send_header("content-type","application/json")
            self.send_header("content-length",str(len(b))); self.end_headers(); self.wfile.write(b)
        elif self.path == "/clear_logo":
            try: os.path.exists(LOGO_PATH) and os.unlink(LOGO_PATH)
            except Exception: pass
            b = b'{"ok":true}'
            self.send_response(200); self.send_header("content-type","application/json")
            self.send_header("content-length",str(len(b))); self.end_headers(); self.wfile.write(b)
        elif self.path == "/print":
            d = self._body(); copies = max(1, min(200, int(d.get("copies",1) or 1)))
            _, _, media = size_cfg(d.get("size"))
            img = render_label(d); ok,msg = print_label(img, copies, media)
            b = json.dumps({"ok":ok,"msg":msg}).encode()
            self.send_response(200); self.send_header("content-type","application/json")
            self.send_header("content-length",str(len(b))); self.end_headers(); self.wfile.write(b)
        elif self.path == "/print_batch":
            d = self._body()
            codes, err = expand_range(d.get("from_code",""), d.get("to_code",""))
            if err:
                b = json.dumps({"ok":False,"msg":err}).encode()
            else:
                _, _, media = size_cfg(d.get("size"))
                sent, fail_msg = 0, ""
                for c in codes:
                    dd = dict(d); dd["code"] = c
                    ok, m = print_label(render_label(dd), 1, media)
                    if ok: sent += 1
                    else:  fail_msg = m; break
                if fail_msg:
                    b = json.dumps({"ok":False,"msg":f"Sent {sent}/{len(codes)} then failed: {fail_msg}"}).encode()
                else:
                    b = json.dumps({"ok":True,"msg":f"{sent} labels sent ({codes[0]} → {codes[-1]})"}).encode()
            self.send_response(200); self.send_header("content-type","application/json")
            self.send_header("content-length",str(len(b))); self.end_headers(); self.wfile.write(b)
        else:
            self.send_response(404); self.end_headers()

def _open_browser():
    import time, webbrowser
    time.sleep(1.0)
    webbrowser.open(f"http://127.0.0.1:{PORT}/")

if __name__ == "__main__":
    url = f"http://127.0.0.1:{PORT}/"
    try:
        srv = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    except OSError:
        # already running (port busy) — just open the browser to it
        print(f"Label Studio already running → {url}")
        import webbrowser; webbrowser.open(url)
        raise SystemExit(0)
    import threading
    threading.Thread(target=_open_browser, daemon=True).start()
    print(f"XP-236B Label Studio → {url}   (close this window to quit)")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
