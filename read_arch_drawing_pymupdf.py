#!/usr/bin/env python3
"""
===========================================================================
  ARCHITECTURAL DRAWING READER — PyMuPDF Demo
===========================================================================
  What this script does:
    1. Opens the real Unit A1 architectural PDF (Casa Familia)
    2. Extracts ALL text strings with their exact (x, y) coordinates
    3. Extracts ALL vector geometry (lines, rectangles, curves)
    4. Detects dimension strings (metric cm + imperial inches/feet)
    5. Renders a full HIGH-RES visual output PDF showing:
         - Page A: The raw architectural drawing (300 DPI render)
         - Page B: Annotated drawing — elevation regions highlighted
         - Page C: Text extraction map — every text string shown at its
                   true position with a colour-coded bounding box
         - Page D: Summary extraction report — all found dimensions,
                   cabinet-area geometry, and unit metadata

  Output: OUTPUT_ARCH_ANALYSIS.pdf  (same folder as this script)
===========================================================================
"""

import re
import math
import sys
import fitz          # PyMuPDF
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import landscape, letter, A3
from reportlab.lib.colors import HexColor, black, white, Color
from reportlab.lib.units import inch
import os

# Fix Windows console UTF-8 output
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# ── Paths ─────────────────────────────────────────────────────────────────
BASE = r"C:\Users\prajw\OneDrive\Desktop\Albert\Albert_Project"
ARCH_PDF = os.path.join(BASE, "Casa familia", "01_Architectural_Drawings",
                        "Unit_Plans_FHA_ADA",
                        "A-6.00-FHA-UNIT-A1-FLOOR-PLAN-&-DETAILS-Rev.10.pdf")
OUT_PDF  = os.path.join(BASE, "OUTPUT_ARCH_ANALYSIS.pdf")

# ── Output page size: 17×11 landscape ─────────────────────────────────────
PW, PH = 1224.0, 792.0   # points (17" × 11" @ 72pt/in)

# ── Colours ───────────────────────────────────────────────────────────────
C_BG        = HexColor("#F8F9FA")
C_BORDER    = HexColor("#1A1A2E")
C_ACCENT    = HexColor("#E94560")
C_BLUE      = HexColor("#0F3460")
C_GREEN     = HexColor("#16213E")
C_GOLD      = HexColor("#F5A623")
C_HIGHLIGHT = HexColor("#00B4D8")
C_DIM_BOX   = HexColor("#FF6B35")
C_CAB_BOX   = HexColor("#06D6A0")
C_TEXT_BOX  = HexColor("#118AB2")
C_TITLE_BAR = HexColor("#1A1A2E")

METRIC_RE   = re.compile(r'\b(\d{1,3}(?:\.\d{1,2})?)\b')
IMPERIAL_RE = re.compile(r"(\d+)'\s*-?\s*(\d+(?:\s+\d+/\d+)?)?\"?|(\d+)-(\d+/\d+)?\"")
FRACTION_RE = re.compile(r'\b(\d+\s*\d*/\d+)\b')


# ══════════════════════════════════════════════════════════════════════════
# UTILITIES
# ══════════════════════════════════════════════════════════════════════════
def py2rl(x, y, page_height=792.0):
    """Convert PyMuPDF coords (origin top-left) → ReportLab (origin bottom-left)"""
    return x, page_height - y

def hex_to_rl(r, g, b):
    return HexColor(f"#{int(r*255):02x}{int(g*255):02x}{int(b*255):02x}")

def header(c, title, subtitle="", page_num=""):
    """Draw a sleek dark header bar."""
    c.setFillColor(C_TITLE_BAR)
    c.rect(0, PH - 48, PW, 48, stroke=0, fill=1)
    c.setFont("Helvetica-Bold", 18)
    c.setFillColor(HexColor("#FFFFFF"))
    c.drawString(24, PH - 32, title)
    if subtitle:
        c.setFont("Helvetica", 11)
        c.setFillColor(HexColor("#AAAACC"))
        c.drawString(24, PH - 44, subtitle)
    if page_num:
        c.setFont("Helvetica-Bold", 11)
        c.setFillColor(C_ACCENT)
        c.drawRightString(PW - 20, PH - 30, page_num)
    # thin accent line
    c.setStrokeColor(C_ACCENT)
    c.setLineWidth(2)
    c.line(0, PH - 50, PW, PH - 50)

def footer(c, note=""):
    c.setFillColor(HexColor("#EEEEEE"))
    c.rect(0, 0, PW, 18, stroke=0, fill=1)
    c.setFont("Helvetica", 7)
    c.setFillColor(HexColor("#666666"))
    c.drawString(12, 5, "PyMuPDF Architectural Drawing Extractor  |  Casa Familia — Unit A1")
    if note:
        c.drawRightString(PW - 12, 5, note)

def label_box(c, text, x, y, bg=C_HIGHLIGHT, fg=white, size=7, padding=3):
    w = len(text) * size * 0.6 + padding * 2
    h = size + padding * 2
    c.setFillColor(bg)
    c.roundRect(x, y - h + padding, w, h, 2, stroke=0, fill=1)
    c.setFont("Helvetica-Bold", size)
    c.setFillColor(fg)
    c.drawString(x + padding, y - size + padding * 0.5, text)
    return w


# ══════════════════════════════════════════════════════════════════════════
# CORE EXTRACTION FUNCTIONS
# ══════════════════════════════════════════════════════════════════════════
def extract_all(arch_pdf_path):
    """Open the PDF and extract everything with PyMuPDF."""
    doc = fitz.open(arch_pdf_path)
    results = []
    for page_num, page in enumerate(doc):
        page_data = {
            "page_num":    page_num,
            "rect":        page.rect,
            "text_blocks": [],
            "text_spans":  [],
            "drawings":    [],
            "images":      page.get_images(),
            "dimensions":  [],
            "regions":     {},
        }

        # ── 1. Full text dict (every span with exact bbox + origin) ────────
        tdict = page.get_text("dict", flags=fitz.TEXT_PRESERVE_WHITESPACE)
        for block in tdict.get("blocks", []):
            if block.get("type") == 0:  # text block
                for line in block.get("lines", []):
                    for span in line.get("spans", []):
                        page_data["text_spans"].append({
                            "text":   span["text"].strip(),
                            "bbox":   span["bbox"],          # (x0,y0,x1,y1)
                            "origin": span["origin"],        # (x, y) baseline
                            "size":   span["size"],
                            "font":   span["font"],
                            "color":  span["color"],
                            "dir":    line.get("dir", (1,0)),
                        })

        # ── 2. Text blocks for region detection ────────────────────────────
        for b in page.get_text("blocks"):
            page_data["text_blocks"].append({
                "text": b[4].strip(),
                "bbox": (b[0], b[1], b[2], b[3]),
            })

        # ── 3. Vector drawings (lines, rects, curves) ─────────────────────
        for d in page.get_drawings():
            page_data["drawings"].append(d)

        # ── 4. Detect dimension strings in spans ───────────────────────────
        for span in page_data["text_spans"]:
            t = span["text"]
            is_metric   = bool(METRIC_RE.search(t)) and ("." in t or t.isdigit())
            is_imperial = bool(IMPERIAL_RE.search(t)) or ("'" in t and '"' in t)
            is_fraction = bool(FRACTION_RE.search(t))
            is_label    = any(kw in t.upper() for kw in [
                "ELEVATION", "KITCHEN", "BATH", "UNIT", "SCALE", "SECTION",
                "UPPER", "LOWER", "BASE", "WALL", "PANTRY", "VANITY",
                "DISHWASHER", "REFRIGERATOR", "MICROWAVE", "RANGE", "SINK",
                "COUNTERTOP", "CABINET", "ADA", "FHA", "FLOOR", "PLAN",
            ])
            if is_metric or is_imperial or is_fraction or is_label:
                page_data["dimensions"].append({
                    **span,
                    "is_metric":   is_metric,
                    "is_imperial": is_imperial,
                    "is_label":    is_label,
                    "is_fraction": is_fraction,
                })

        # ── 5. Detect regions by scanning for label text ───────────────────
        for span in page_data["text_spans"]:
            t = span["text"].upper()
            for kw in ["ELEVATION A", "ELEVATION B", "ELEVATION C",
                        "FLOOR PLAN", "KITCHEN", "BATH", "VANITY",
                        "SCALE", "GENERAL NOTES", "SECTION"]:
                if kw in t:
                    page_data["regions"].setdefault(kw, []).append(span["bbox"])

        results.append(page_data)
    doc.close()
    return results


# ══════════════════════════════════════════════════════════════════════════
# PAGE A — Raw Architectural Drawing (300 DPI rendered)
# ══════════════════════════════════════════════════════════════════════════
def page_raw_render(c, arch_pdf_path):
    print("  [A] Rendering raw architectural drawing (300 DPI)...")
    doc = fitz.open(arch_pdf_path)
    page = doc[0]
    mat  = fitz.Matrix(300/72, 300/72)
    pix  = page.get_pixmap(matrix=mat, colorspace=fitz.csRGB)

    # Save as temp PNG then embed
    tmp_png = os.path.join(BASE, "_tmp_render.png")
    pix.save(tmp_png)

    header(c, "PAGE A — RAW ARCHITECTURAL DRAWING",
           f"Source: A-6.00-FHA-UNIT-A1  |  PyMuPDF fitz.get_pixmap(300 DPI)  |  "
           f"PDF size: {page.rect.width:.0f}×{page.rect.height:.0f} pts  |  "
           f"Image: {pix.width}×{pix.height}px",
           "1 / 4")

    # Fit the rendered PNG inside the drawing area (below header, above footer)
    img_area_w = PW - 40
    img_area_h = PH - 80
    ratio = min(img_area_w / pix.width, img_area_h / pix.height)
    dw = pix.width  * ratio
    dh = pix.height * ratio
    dx = (PW - dw) / 2
    dy = (PH - 50 - dh) / 2 + 18

    # Subtle shadow
    c.setFillColor(HexColor("#CCCCCC"))
    c.rect(dx + 4, dy - 4, dw, dh, stroke=0, fill=1)
    c.drawImage(tmp_png, dx, dy, width=dw, height=dh, preserveAspectRatio=True)

    # Border
    c.setStrokeColor(C_ACCENT)
    c.setLineWidth(1.5)
    c.rect(dx, dy, dw, dh, stroke=1, fill=0)

    footer(c, f"Image size: {pix.width}×{pix.height}px  |  Scale ratio: {ratio:.3f}")
    doc.close()
    os.remove(tmp_png)


# ══════════════════════════════════════════════════════════════════════════
# PAGE B — Annotated Drawing: Elevation Regions Highlighted
# ══════════════════════════════════════════════════════════════════════════
def page_annotated(c, arch_pdf_path, extracted):
    print("  [B] Building annotated drawing with region overlays...")
    doc = fitz.open(arch_pdf_path)
    page = doc[0]
    pw_orig, ph_orig = page.rect.width, page.rect.height

    # Render at lower DPI for this page (we'll overlay annotations)
    mat = fitz.Matrix(200/72, 200/72)
    pix = page.get_pixmap(matrix=mat, colorspace=fitz.csRGB)
    tmp = os.path.join(BASE, "_tmp_ann.png")
    pix.save(tmp)

    header(c, "PAGE B — ANNOTATED ELEVATION & REGION DETECTION",
           "PyMuPDF text search → ELEVATION A/B/C regions detected and colour-coded",
           "2 / 4")

    img_area_w = PW - 420
    img_area_h = PH - 80
    ratio = min(img_area_w / pix.width, img_area_h / pix.height)
    dw = pix.width  * ratio
    dh = pix.height * ratio
    dx = 20
    dy = (PH - 50 - dh) / 2 + 18

    c.drawImage(tmp, dx, dy, width=dw, height=dh, preserveAspectRatio=True)
    c.setStrokeColor(C_BORDER)
    c.setLineWidth(0.8)
    c.rect(dx, dy, dw, dh, stroke=1, fill=0)

    # ── Overlay coloured region boxes ─────────────────────────────────────
    region_colors = {
        "ELEVATION A":   HexColor("#FF6B35"),
        "ELEVATION B":   HexColor("#06D6A0"),
        "ELEVATION C":   HexColor("#118AB2"),
        "FLOOR PLAN":    HexColor("#FFD166"),
        "KITCHEN":       HexColor("#EF476F"),
        "BATH":          HexColor("#9B5DE5"),
        "VANITY":        HexColor("#F15BB5"),
        "SCALE":         HexColor("#00BBF9"),
        "GENERAL NOTES": HexColor("#9BDE5E"),
    }

    pdata = extracted[0]
    legend_y = PH - 80
    legend_x = PW - 390

    c.setFont("Helvetica-Bold", 11)
    c.setFillColor(C_BORDER)
    c.drawString(legend_x, legend_y, "DETECTED REGIONS")
    c.setLineWidth(0.5)
    c.setStrokeColor(C_BORDER)
    c.line(legend_x, legend_y - 4, legend_x + 360, legend_y - 4)
    legend_y -= 18

    found_any = False
    for kw, bboxes in pdata["regions"].items():
        clr = region_colors.get(kw, HexColor("#888888CC"))
        # convert PDF coords → screen coords
        for bbox in bboxes[:1]:  # just first occurrence per region
            x0, y0, x1, y1 = bbox
            # scale to rendered image space
            rx0 = dx + (x0 / pw_orig) * dw
            ry1 = dy + (1 - y0 / ph_orig) * dh
            rx1 = dx + (x1 / pw_orig) * dw
            ry0 = dy + (1 - y1 / ph_orig) * dh
            box_w = rx1 - rx0
            box_h = ry1 - ry0

            # Draw translucent highlight
            highlight = Color(clr.red, clr.green, clr.blue, alpha=0.3)
            c.setFillColor(highlight)
            c.setStrokeColor(clr)
            c.setLineWidth(1.5)
            c.rect(rx0, ry0, box_w, box_h, stroke=1, fill=1)

            # Label tag
            c.setFont("Helvetica-Bold", 7)
            c.setFillColor(clr)
            c.drawString(rx0 + 2, ry0 + 2, kw)

        # Legend entry
        c.setFillColor(clr)
        c.rect(legend_x, legend_y - 2, 12, 10, stroke=0, fill=1)
        c.setFont("Helvetica", 9)
        c.setFillColor(C_BORDER)
        count = len(bboxes)
        c.drawString(legend_x + 16, legend_y, f"{kw}  ({count} occurrence{'s' if count>1 else ''})")
        legend_y -= 16
        found_any = True

    if not found_any:
        c.setFont("Helvetica", 10)
        c.setFillColor(HexColor("#999999"))
        c.drawString(legend_x, legend_y, "(No labelled regions found on this page)")

    # ── Dimension annotations ──────────────────────────────────────────────
    dim_count = {"metric": 0, "imperial": 0, "label": 0}
    for dim in pdata["dimensions"][:80]:  # cap at 80 to avoid clutter
        x0, y0, x1, y1 = dim["bbox"]
        rx = dx + (x0 / pw_orig) * dw
        ry = dy + (1 - y1 / ph_orig) * dh
        if dim["is_label"]:
            dot_c = C_GOLD
            dim_count["label"] += 1
        elif dim["is_imperial"]:
            dot_c = C_ACCENT
            dim_count["imperial"] += 1
        else:
            dot_c = C_CAB_BOX
            dim_count["metric"] += 1
        c.setFillColor(dot_c)
        c.circle(rx, ry, 2, stroke=0, fill=1)

    # Dimension legend
    legend_y -= 20
    c.setFont("Helvetica-Bold", 10)
    c.setFillColor(C_BORDER)
    c.drawString(legend_x, legend_y, "DIMENSION MARKERS")
    c.line(legend_x, legend_y - 4, legend_x + 360, legend_y - 4)
    legend_y -= 18

    for color, label, count in [
        (C_CAB_BOX, "Metric (cm/mm)", dim_count["metric"]),
        (C_ACCENT,  "Imperial (ft/in)", dim_count["imperial"]),
        (C_GOLD,    "Location Labels", dim_count["label"]),
    ]:
        c.setFillColor(color)
        c.circle(legend_x + 6, legend_y + 4, 5, stroke=0, fill=1)
        c.setFont("Helvetica", 9)
        c.setFillColor(C_BORDER)
        c.drawString(legend_x + 16, legend_y, f"{label}: {count} found")
        legend_y -= 15

    footer(c, f"Total spans analysed: {len(pdata['text_spans'])}  |  "
              f"Dimension strings: {len(pdata['dimensions'])}")
    doc.close()
    os.remove(tmp)


# ══════════════════════════════════════════════════════════════════════════
# PAGE C — Text Extraction Map
# ══════════════════════════════════════════════════════════════════════════
def page_text_map(c, extracted):
    print("  [C] Building text extraction map...")
    pdata = extracted[0]
    pw_orig = pdata["rect"].width
    ph_orig = pdata["rect"].height

    header(c, "PAGE C — TEXT EXTRACTION MAP",
           "Every text string extracted by PyMuPDF get_text('dict')  — "
           "showing exact (x,y) position and bounding box  |  "
           "Colour = text type",
           "3 / 4")

    # Drawing canvas area
    area_x, area_y = 20, 22
    area_w = PW - 280
    area_h = PH - 80

    # Background
    c.setFillColor(HexColor("#1E1E2E"))
    c.rect(area_x, area_y, area_w, area_h, stroke=0, fill=1)
    c.setStrokeColor(C_ACCENT)
    c.setLineWidth(1.2)
    c.rect(area_x, area_y, area_w, area_h, stroke=1, fill=0)

    scale_x = area_w / pw_orig
    scale_y = area_h / ph_orig

    # Draw ALL text spans
    FONT_SCALE = 0.75
    for span in pdata["text_spans"]:
        text = span["text"]
        if not text:
            continue

        # Colour by type
        t_up = text.upper()
        if any(kw in t_up for kw in ["ELEVATION", "FLOOR PLAN", "SECTION", "SCALE",
                                       "KITCHEN", "BATH", "VANITY"]):
            clr = C_GOLD
            show_box = True
        elif "'" in text or '"' in text:
            clr = C_ACCENT
            show_box = True
        elif METRIC_RE.search(text) and "." in text:
            clr = C_CAB_BOX
            show_box = True
        else:
            clr = HexColor("#AAAAAA")
            show_box = False

        x0, y0, x1, y1 = span["bbox"]
        ox, oy = span["origin"]
        rx  = area_x + ox * scale_x
        ry  = area_y + area_h - oy * scale_y
        sz  = max(4, span["size"] * scale_x * FONT_SCALE)

        # Draw bounding box for highlighted items
        if show_box:
            bx0 = area_x + x0 * scale_x
            by1 = area_y + area_h - y0 * scale_y
            bx1 = area_x + x1 * scale_x
            by0 = area_y + area_h - y1 * scale_y
            bw  = max(1, bx1 - bx0)
            bh  = max(1, by1 - by0)
            box_clr = Color(clr.red, clr.green, clr.blue, alpha=0.15)
            c.setFillColor(box_clr)
            c.setStrokeColor(clr)
            c.setLineWidth(0.4)
            c.rect(bx0, by0, bw, bh, stroke=1, fill=1)

        c.setFillColor(clr)
        c.setFont("Helvetica", min(sz, 10))
        try:
            c.drawString(rx, ry, text[:40])
        except Exception:
            pass

    # ── Right panel: stats ────────────────────────────────────────────────
    px = PW - 250
    py = PH - 80

    c.setFont("Helvetica-Bold", 12)
    c.setFillColor(C_BORDER)
    c.drawString(px, py, "EXTRACTION STATS")
    c.setLineWidth(0.8)
    c.setStrokeColor(C_BORDER)
    c.line(px, py - 4, px + 240, py - 4)
    py -= 22

    stats = [
        ("Total text spans",     str(len(pdata["text_spans"]))),
        ("Dimension strings",    str(len(pdata["dimensions"]))),
        ("Vector paths",         str(len(pdata["drawings"]))),
        ("Embedded images",      str(len(pdata["images"]))),
        ("Detected regions",     str(len(pdata["regions"]))),
        ("Page width (pts)",     f"{pdata['rect'].width:.1f}"),
        ("Page height (pts)",    f"{pdata['rect'].height:.1f}"),
        ("Page width (inches)",  f"{pdata['rect'].width/72:.2f}\""),
        ("Page height (inches)", f"{pdata['rect'].height/72:.2f}\""),
    ]
    for label, val in stats:
        c.setFont("Helvetica", 9)
        c.setFillColor(HexColor("#555555"))
        c.drawString(px, py, label)
        c.setFont("Helvetica-Bold", 9)
        c.setFillColor(C_BLUE)
        c.drawRightString(px + 240, py, val)
        py -= 14
        c.setStrokeColor(HexColor("#DDDDDD"))
        c.setLineWidth(0.3)
        c.line(px, py + 10, px + 240, py + 10)

    # Legend
    py -= 16
    c.setFont("Helvetica-Bold", 10)
    c.setFillColor(C_BORDER)
    c.drawString(px, py, "COLOUR LEGEND")
    c.line(px, py - 4, px + 240, py - 4)
    py -= 18

    legend = [
        (C_GOLD,      "Section / Elevation labels"),
        (C_ACCENT,    "Imperial dimensions (ft/in)"),
        (C_CAB_BOX,   "Metric dimensions (cm/mm)"),
        (HexColor("#AAAAAA"), "Other text"),
    ]
    for col, lbl in legend:
        c.setFillColor(col)
        c.rect(px, py - 2, 12, 10, stroke=0, fill=1)
        c.setFont("Helvetica", 9)
        c.setFillColor(C_BORDER)
        c.drawString(px + 16, py, lbl)
        py -= 15

    # Sample dimension values table
    py -= 20
    c.setFont("Helvetica-Bold", 10)
    c.setFillColor(C_BORDER)
    c.drawString(px, py, "SAMPLE DIMENSIONS FOUND")
    c.line(px, py - 4, px + 240, py - 4)
    py -= 16

    shown = 0
    for dim in pdata["dimensions"]:
        t = dim["text"]
        if not t or shown > 22:
            break
        tag = ""
        if dim["is_imperial"]: tag = "[IN]"
        elif dim["is_metric"]:  tag = "[CM]"
        elif dim["is_label"]:   tag = "[LBL]"
        if tag:
            c.setFont("Helvetica", 7.5)
            c.setFillColor(HexColor("#333333"))
            c.drawString(px, py, t[:28])
            c.setFont("Helvetica-Bold", 7)
            c.setFillColor(C_ACCENT if tag=="[IN]" else C_CAB_BOX if tag=="[CM]" else C_GOLD)
            c.drawRightString(px + 240, py, tag)
            py -= 12
            shown += 1

    footer(c, f"Spans rendered: {len(pdata['text_spans'])}")


# ══════════════════════════════════════════════════════════════════════════
# PAGE D — Full Extraction Report
# ══════════════════════════════════════════════════════════════════════════
def page_report(c, arch_pdf_path, extracted):
    print("  [D] Building extraction report...")
    pdata = extracted[0]

    header(c, "PAGE D — FULL EXTRACTION REPORT",
           "All dimension strings, cabinet labels, and geometry summary extracted by PyMuPDF",
           "4 / 4")

    # Two columns
    col1_x = 24
    col2_x = PW // 2 + 10
    y_start = PH - 68
    col_w = PW // 2 - 34

    # ── Column 1: All Dimension & Label strings ───────────────────────────
    c.setFont("Helvetica-Bold", 11)
    c.setFillColor(C_BLUE)
    c.drawString(col1_x, y_start, "ALL EXTRACTED TEXT STRINGS (Type-Classified)")
    c.setLineWidth(1)
    c.setStrokeColor(C_BLUE)
    c.line(col1_x, y_start - 4, col1_x + col_w, y_start - 4)

    y = y_start - 18
    row_h = 11
    c.setFont("Helvetica-Bold", 8)
    c.setFillColor(HexColor("#444444"))
    for lbl, x_off, w in [("#", 0, 22), ("TEXT", 26, 140), ("TYPE", 172, 50),
                            ("X", 228, 35), ("Y", 268, 35), ("SIZE", 308, 30)]:
        c.drawString(col1_x + x_off, y, lbl)
    y -= 2
    c.setStrokeColor(HexColor("#CCCCCC"))
    c.setLineWidth(0.4)
    c.line(col1_x, y, col1_x + col_w, y)
    y -= row_h

    shown = 0
    for i, dim in enumerate(pdata["dimensions"]):
        if y < 30 or shown > 52:
            break
        tag  = "LABEL" if dim["is_label"] else "IMPERIAL" if dim["is_imperial"] else "METRIC"
        clr  = C_GOLD if tag=="LABEL" else C_ACCENT if tag=="IMPERIAL" else C_CAB_BOX
        text = dim["text"][:22]
        ox, oy = dim["origin"]

        if i % 2 == 0:
            c.setFillColor(HexColor("#F5F5F5"))
            c.rect(col1_x, y - 1, col_w, row_h, stroke=0, fill=1)

        c.setFont("Helvetica", 7.5)
        c.setFillColor(HexColor("#666666"))
        c.drawString(col1_x,      y, str(i+1))
        c.setFillColor(HexColor("#111111"))
        c.drawString(col1_x + 26, y, text)
        c.setFillColor(clr)
        c.setFont("Helvetica-Bold", 7)
        c.drawString(col1_x + 172, y, tag)
        c.setFont("Helvetica", 7.5)
        c.setFillColor(HexColor("#888888"))
        c.drawString(col1_x + 228, y, f"{ox:.1f}")
        c.drawString(col1_x + 268, y, f"{oy:.1f}")
        c.drawString(col1_x + 308, y, f"{dim['size']:.1f}")

        y -= row_h
        shown += 1

    if len(pdata["dimensions"]) > shown:
        c.setFont("Helvetica-Oblique", 8)
        c.setFillColor(HexColor("#999999"))
        c.drawString(col1_x, y, f"... and {len(pdata['dimensions'])-shown} more strings")

    # ── Column 2: Geometry Summary + Regions ─────────────────────────────
    y = y_start
    c.setFont("Helvetica-Bold", 11)
    c.setFillColor(C_BLUE)
    c.drawString(col2_x, y, "GEOMETRY & VECTOR PATHS SUMMARY")
    c.setLineWidth(1)
    c.setStrokeColor(C_BLUE)
    c.line(col2_x, y - 4, col2_x + col_w, y - 4)
    y -= 22

    # Geometry stats
    drawings = pdata["drawings"]
    lines    = sum(1 for d in drawings for item in d.get("items", []) if item[0] == "l")
    rects    = sum(1 for d in drawings for item in d.get("items", []) if item[0] == "re")
    curves   = sum(1 for d in drawings for item in d.get("items", []) if item[0] == "c")

    geo_stats = [
        ("Total vector paths",       len(drawings)),
        ("  → Line segments",        lines),
        ("  → Rectangles",           rects),
        ("  → Bezier curves",        curves),
        ("Text spans extracted",     len(pdata["text_spans"])),
        ("Dimension/label strings",  len(pdata["dimensions"])),
        ("Embedded images",          len(pdata["images"])),
        ("Detected keyword regions", len(pdata["regions"])),
    ]
    for label, val in geo_stats:
        c.setFont("Helvetica", 9)
        c.setFillColor(HexColor("#333333"))
        c.drawString(col2_x, y, label)
        c.setFont("Helvetica-Bold", 9)
        c.setFillColor(C_BLUE)
        c.drawRightString(col2_x + col_w, y, str(val))
        y -= 14

    y -= 10
    c.setFont("Helvetica-Bold", 11)
    c.setFillColor(C_ACCENT)
    c.drawString(col2_x, y, "DETECTED KEYWORD REGIONS")
    c.setStrokeColor(C_ACCENT)
    c.setLineWidth(0.8)
    c.line(col2_x, y - 4, col2_x + col_w, y - 4)
    y -= 18

    for kw, bboxes in pdata["regions"].items():
        c.setFont("Helvetica-Bold", 9)
        c.setFillColor(C_ACCENT)
        c.drawString(col2_x, y, f"  {kw}")
        c.setFont("Helvetica", 8)
        c.setFillColor(HexColor("#555555"))
        c.drawRightString(col2_x + col_w, y, f"{len(bboxes)} occurrence(s)")
        y -= 12
        for bbox in bboxes[:2]:
            x0,y0,x1,y1 = bbox
            c.setFont("Helvetica", 7.5)
            c.setFillColor(HexColor("#888888"))
            c.drawString(col2_x + 14, y,
                         f"    bbox: ({x0:.0f},{y0:.0f}) → ({x1:.0f},{y1:.0f})  "
                         f"[{x1-x0:.0f}×{y1-y0:.0f} pts]")
            y -= 11
        y -= 3

    # ── Cabinet extraction preview box ────────────────────────────────────
    y -= 10
    c.setFont("Helvetica-Bold", 11)
    c.setFillColor(C_CAB_BOX)
    c.drawString(col2_x, y, "CABINET KEYWORD HITS")
    c.setStrokeColor(C_CAB_BOX)
    c.line(col2_x, y - 4, col2_x + col_w, y - 4)
    y -= 18

    cab_keywords = ["DISHWASHER", "REFRIGERATOR", "MICROWAVE", "RANGE",
                    "SINK", "UPPER", "LOWER", "BASE", "PANTRY", "COUNTERTOP",
                    "CABINET", "VANITY", "CLOSET"]
    for span in pdata["text_spans"]:
        t = span["text"].upper()
        for kw in cab_keywords:
            if kw in t and y > 30:
                c.setFont("Helvetica-Bold", 8)
                c.setFillColor(C_CAB_BOX)
                c.drawString(col2_x, y, f"  >>  {span['text'][:40]}")
                ox, oy = span["origin"]
                c.setFont("Helvetica", 7.5)
                c.setFillColor(HexColor("#888888"))
                c.drawRightString(col2_x + col_w, y, f"@ ({ox:.0f}, {oy:.0f})")
                y -= 12
                break

    footer(c, "PyMuPDF v" + fitz.__version__ + "  |  fitz.open() → get_text('dict') + get_drawings()")


# ══════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════
def main():
    print("=" * 70)
    print("  ARCHITECTURAL DRAWING READER — PyMuPDF")
    print("=" * 70)
    print(f"  Input PDF : {os.path.basename(ARCH_PDF)}")
    print(f"  Output PDF: {os.path.basename(OUT_PDF)}")
    print()

    if not os.path.exists(ARCH_PDF):
        print(f"  ERROR: Input PDF not found at:\n  {ARCH_PDF}")
        return

    # ── Extract everything from the PDF ───────────────────────────────────
    print("  Extracting text, geometry, and dimensions from PDF...")
    extracted = extract_all(ARCH_PDF)
    pdata = extracted[0]
    print(f"  ✓ Text spans:    {len(pdata['text_spans'])}")
    print(f"  ✓ Vector paths:  {len(pdata['drawings'])}")
    print(f"  ✓ Dim strings:   {len(pdata['dimensions'])}")
    print(f"  ✓ Regions found: {list(pdata['regions'].keys())}")
    print()

    # ── Build 4-page output PDF ───────────────────────────────────────────
    c = canvas.Canvas(OUT_PDF, pagesize=(PW, PH))
    c.setTitle("Architectural Drawing Extraction — Casa Familia Unit A1")
    c.setAuthor("PyMuPDF Extraction Demo")
    c.setSubject("AI Cabinet Estimation System — Input PDF Analysis")

    print("  Building output PDF (4 pages)...")

    page_raw_render(c, ARCH_PDF)
    c.showPage()

    page_annotated(c, ARCH_PDF, extracted)
    c.showPage()

    page_text_map(c, extracted)
    c.showPage()

    page_report(c, ARCH_PDF, extracted)
    c.showPage()

    c.save()
    print()
    print(f"  ✓ Done! Output saved to:")
    print(f"    {OUT_PDF}")
    print()
    print("  What each page shows:")
    print("    Page A — Raw 300 DPI render of the architectural PDF")
    print("    Page B — Same drawing with ELEVATION/KITCHEN/BATH regions highlighted")
    print("    Page C — Text extraction map: every string at its exact position")
    print("    Page D — Full report: dimensions, geometry counts, cabinet keywords")
    print("=" * 70)


if __name__ == "__main__":
    main()
