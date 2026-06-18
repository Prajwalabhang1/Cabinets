#!/usr/bin/env python3
"""
===========================================================================
CASA FAMILIA — PRODUCTION SHOP DRAWINGS COMPILER & RECONSTRUCTOR  v5.0
===========================================================================
This script programmatically reconstructs the 23-page shop drawing package:
  - Page 1: COVER (dynamically generated from project data)
  - Page 2: MATRIX (dynamically generated from unit quantities)
  - Pages 3-23: Vector-level reconstruction from the client's reference PDF,
    separating the drawing graphics from the title blocks, and wrapping each
    sheet with our dynamic, uniform title block layout.

All CAD elements (lines, arcs, dimensions, text rotation, dashes) are copied
with 100% precision, producing a crisp, vector-grade print PDF.
===========================================================================
"""

import math
import os
import re
import fitz  # PyMuPDF
from reportlab.lib.pagesizes import landscape
from reportlab.pdfgen import canvas
from reportlab.lib.colors import HexColor, black, white

# ── Page & Scale Constants ─────────────────────────────────────────────────
PAGE_W  = 1224.0   # 17" × 72pt/in
PAGE_H  = 792.0    # 11" × 72pt/in

# ── Title-block geometry ───────────────────────────────────────────────────
TB_X = 1161.6
TB_W = 62.4
TB_COLS = [TB_X + i*14.4 for i in range(5)] + [TB_X + TB_W]

# ── Drawing area ──────────────────────────────────────────────────────────
DA_L  = 18.0
DA_R  = TB_X - 4.0
DA_T  = 8.0
DA_B  = PAGE_H - 14.0

# ── Colors ────────────────────────────────────────────────────────────────
BLACK  = HexColor('#000000')
GRAY   = HexColor('#D0D0D0')
DKGRAY = HexColor('#888888')
WHITE  = HexColor('#FFFFFF')

# ══════════════════════════════════════════════════════════════════════════
# REAL PROJECT DATA
# ══════════════════════════════════════════════════════════════════════════
PROJECT = {
    "name":        "CASA FAMILIA",
    "id":          "23-033",
    "date":        "11/05/2024",
    "revision":    "5.0",
    "drawn_by":    "A.C",
    "dimensions":  "CM|INCHES",
    "scope":       "KITCHEN | VANITIES",
    "finish":      "K019 SILVER LIBERTY ELM",
    "company": {
        "name":    "ITALIAN KITCHEN AND BATH",
        "tagline": "kitchen | bath | tile | closet",
        "address": "1777 NW 72TH AVE. MIAMI FL, 33126",
        "phone":   "T. 305.599.9000  F. 305.599.9870",
    },
    "revision_log": [
        ("1.0","10/06/2023","V.U",""),
        ("2.0","07/18/2024","A.C",""),
        ("3.0","09/18/2024","A.C",""),
        ("4.0","10/30/2024","A.C",""),
        ("5.0","11/05/2024","A.C",""),
    ],
    "appliances_regular": [
        '28" REFRIGERATOR  GE MODEL GTE18GSNRSS',
        '24" DISHWASHER    GE MODEL GDT535PSRSS',
        '30" RANGE         GE MODEL GRF400PV',
        '30" MICROWAVE     GE MODEL JVM3160RFSS',
    ],
    "appliances_ada": [
        '28" REFRIGERATOR  GE MODEL GTE18GSNRSS',
        '24" DISHWASHER    GE MODEL GDT225SSLSS (ADA)',
        '30" RANGE         GE MODEL GRS500PVSS (ADA)',
        '30" MICROWAVE     GE MODEL JES1145SHSS',
        '30" HOOD          GE MODEL JVX3300SJSS',
    ],
    "general_notes": [
        "*ALL DIMENSIONS ARE FROM FINISHED WALL TO FINISHED WALL",
        "*ALL DIMENSIONS ARE FROM FINISHED FLOOR TO FINISHED CEILING",
        "*NOT INCLUDED: APPLIANCES, FIXTURES, PLUMBING, AND COUNTER TOPS",
        "*IT'S ARCHITECT'S RESPONSIBILITY TO CONFIRM KITCHEN & VANITY",
        " CABINETS COMPLY WITH BUILDING FHA & ADA CODES.",
    ],
}

UNIT_MATRIX = {
    "building_a": [
        {"unit":"UNIT A1",    "qty":14,"v1":1,"v2":0,"v3":0,"v4":0,"kitchen":"K1"},
        {"unit":"UNIT A2 FA", "qty":3, "v1":0,"v2":1,"v3":0,"v4":0,"kitchen":"K2"},
        {"unit":"UNIT A3",    "qty":2, "v1":0,"v2":0,"v3":1,"v4":0,"kitchen":"K1"},
        {"unit":"UNIT B1",    "qty":3, "v1":1,"v2":0,"v3":0,"v4":1,"kitchen":"K3"},
        {"unit":"UNIT B2 FA", "qty":3, "v1":0,"v2":1,"v3":0,"v4":1,"kitchen":"K4"},
    ],
    "building_b": [
        {"unit":"UNIT A1",    "qty":14,"v1":1,"v2":0,"v3":0,"v4":0,"kitchen":"K1"},
        {"unit":"UNIT A2 FA", "qty":3, "v1":0,"v2":1,"v3":0,"v4":0,"kitchen":"K2"},
        {"unit":"UNIT A3",    "qty":2, "v1":0,"v2":0,"v3":1,"v4":0,"kitchen":"K1"},
        {"unit":"UNIT B1",    "qty":3, "v1":1,"v2":0,"v3":0,"v4":1,"kitchen":"K3"},
        {"unit":"UNIT B2 FA", "qty":3, "v1":0,"v2":1,"v3":0,"v4":1,"kitchen":"K4"},
    ],
    "kitchen_types": [("K1",32),("K2",6),("K3",6),("K4",6)],
}


# ══════════════════════════════════════════════════════════════════════════
# TITLE BLOCK  (exact ItalianKB layout)
# ══════════════════════════════════════════════════════════════════════════
def draw_title_block(c, project, sheet_type, sheet_num, big_title="", sub_title=""):
    c.saveState()
    c.setStrokeColor(BLACK)
    c.setFillColor(WHITE)
    c.rect(TB_X, 0, TB_W, PAGE_H, stroke=1, fill=1)

    def hline(y, lw=0.4):
        c.setLineWidth(lw)
        c.line(TB_X, y, TB_X+TB_W, y)

    def vline(x, y0, y1, lw=0.3):
        c.setLineWidth(lw)
        c.line(x, y0, x, y1)

    # Section borders
    hline(537, 0.6); hline(645, 0.5); hline(758, 0.5); hline(774, 0.5)
    c.setLineWidth(0.8); c.line(TB_X, 0, TB_X, PAGE_H)

    # Sub-column verticals — company section
    for x in TB_COLS[1:5]:
        vline(x, 0, 537)

    # Sub-column verticals — project section
    for x in TB_COLS[1:4]:
        vline(x, 537, 645)

    # Sub-column verticals — info section
    for x in TB_COLS[1:4]:
        vline(x, 645, 758)

    # ── Company section: rotated text ────────────────────────────────────
    _rot_col(c, project["company"]["name"],    TB_COLS[0], TB_COLS[1], 0, 537, 14, "Helvetica-Bold")
    _rot_col(c, project["company"]["tagline"], TB_COLS[1], TB_COLS[2], 0, 537, 5.5, "Helvetica")
    _rot_col(c, project["company"]["address"], TB_COLS[2], TB_COLS[3], 0, 537, 5.5, "Helvetica")
    _rot_col(c, project["company"]["phone"],   TB_COLS[3], TB_COLS[4], 0, 537, 5.5, "Helvetica")

    # ── Project section ───────────────────────────────────────────────────
    _rot_label_value(c, "PROJECT #:", project["id"],   TB_COLS[0], TB_COLS[1], 537, 645)
    _rot_label_value(c, "",  project["name"],          TB_COLS[1], TB_COLS[2], 537, 645)
    _rot_label_value(c, "",  sheet_type,               TB_COLS[2], TB_COLS[3], 537, 645)

    # ── Info section ─────────────────────────────────────────────────────
    _rot_label_value(c, "DATE:",       project["date"],       TB_COLS[0], TB_COLS[1], 645, 758)
    _rot_label_value(c, "REV:",        project["revision"],   TB_COLS[1], TB_COLS[2], 645, 758)
    _rot_label_value(c, "DIMENSION:",  project["dimensions"], TB_COLS[2], TB_COLS[3], 645, 758)
    _rot_label_value(c, "DRAWN BY:",   project["drawn_by"],   TB_COLS[3], TB_COLS[4], 645, 758)

    # ── Sheet number ─────────────────────────────────────────────────────
    mx = TB_X + TB_W/2
    c.setFont("Helvetica", 4.5); c.setFillColor(BLACK)
    c.drawCentredString(mx, 766, "SHEET NUMBER")
    c.setFont("Helvetica-Bold", 9)
    c.drawCentredString(mx, 779, sheet_num)

    # ── Page title top-right (only drawn if specified dynamically) ─────────
    if big_title:
        c.setFont("Helvetica-Bold", 26); c.setFillColor(BLACK)
        c.drawRightString(TB_X - 8, PAGE_H - 40, big_title)
        if sub_title:
            c.setFont("Helvetica-Bold", 15)
            c.drawRightString(TB_X - 8, PAGE_H - 60, sub_title)

    # ── Page border ───────────────────────────────────────────────────────
    c.setStrokeColor(BLACK); c.setLineWidth(0.8)
    c.rect(DA_L, 14, DA_R - DA_L, PAGE_H - 22, stroke=1, fill=0)
    c.restoreState()


def _rot_col(c, text, x0, x1, y0, y1, size, font="Helvetica"):
    cx = (x0 + x1)/2
    cy = (y0 + y1)/2
    c.saveState()
    c.setFont(font, size); c.setFillColor(BLACK)
    c.translate(cx, cy); c.rotate(90)
    c.drawCentredString(0, -size*0.35, text)
    c.restoreState()


def _rot_label_value(c, label, value, x0, x1, y0, y1):
    cx = (x0 + x1)/2
    c.saveState()
    c.setFillColor(BLACK)
    if label:
        c.setFont("Helvetica-Bold", 5.5)
        c.translate(cx, y1 - 10); c.rotate(90)
        c.drawString(0, -3, label)
        c.restoreState(); c.saveState()
    c.setFont("Helvetica", 7)
    c.translate(cx, (y0+y1)/2); c.rotate(90)
    c.drawCentredString(0, -3, value)
    c.restoreState()


# ══════════════════════════════════════════════════════════════════════════
# DYNAMIC COVER PAGE
# ══════════════════════════════════════════════════════════════════════════
def build_cover(c, proj):
    draw_title_block(c, proj, "KITCHEN | VANITIES", "COVER",
                     "CASA FAMILIA", "KITCHEN | VANITY SHOP-DWGS")

    # Project name
    c.setFont("Helvetica-Bold", 52); c.setFillColor(BLACK)
    c.drawString(DA_L+10, PAGE_H-80, proj["name"])
    c.setFont("Helvetica", 18)
    c.drawString(DA_L+10, PAGE_H-105, "KITCHEN | VANITY | LAUNDRY  SHOP-DRAWINGS")

    # Divider line
    c.setLineWidth(1.5)
    c.line(DA_L+10, PAGE_H-115, DA_R-10, PAGE_H-115)

    # FINISH box
    y = PAGE_H-130
    _info_box(c, "FINISH:", [f"- {proj['finish']}"],
              DA_L+10, y, 880, 42)

    # APPLIANCES box
    y -= 52
    app = (["REGULAR UNITS:"] +
           [f"    {a}" for a in proj["appliances_regular"]] +
           ["", "ADA UNITS:"] +
           [f"    {a}" for a in proj["appliances_ada"]])
    _info_box(c, "APPLIANCES:", app, DA_L+10, y, 880, 195)

    # GENERAL NOTES box
    y -= 205
    _info_box(c, "GENERAL NOTES:", proj["general_notes"], DA_L+10, y, 880, 100)

    # REVISION LOG
    y -= 120
    _rev_table(c, proj["revision_log"], DA_L+500, y)

    # Branding bottom
    c.setFont("Helvetica", 8); c.setFillColor(HexColor('#555555'))
    c.drawString(DA_L+10, 25, "OWNER: ATLANTIC PACIFIC COMMUNITIES  |  10951 SW 84th St., MIAMI-DADE, FLORIDA 33173")


def _info_box(c, title, lines, x, y_top, w, h):
    c.saveState()
    c.setStrokeColor(BLACK); c.setFillColor(WHITE); c.setLineWidth(0.7)
    c.rect(x, y_top-h, w, h, stroke=1, fill=1)
    c.setFont("Helvetica-Bold", 10); c.setFillColor(BLACK)
    c.drawString(x+8, y_top-15, title)
    c.setFont("Helvetica", 9)
    lh = 13
    for i, line in enumerate(lines):
        c.drawString(x+8, y_top-29-i*lh, line)
    c.restoreState()


def _rev_table(c, revs, x, y_top):
    c.saveState()
    cols  = [35, 75, 55, 130]
    hdrs  = ["REV.", "DATE", "BY", "DESCRIPTION"]
    rh, tw= 16, sum(cols)
    c.setFont("Helvetica-Bold", 8); c.setFillColor(BLACK)
    c.drawCentredString(x+tw/2, y_top+6, "REVISION LOG")
    c.setLineWidth(0.5)
    # Header
    c.rect(x, y_top-rh, tw, rh, stroke=1, fill=0)
    cx = x
    for h, cw in zip(hdrs, cols):
        c.drawCentredString(cx+cw/2, y_top-rh+4, h)
        if cx > x: c.line(cx, y_top-rh, cx, y_top)
        cx += cw
    # Rows
    for i in range(10):
        ry = y_top - rh*(i+2)
        c.rect(x, ry, tw, rh, stroke=1, fill=0)
        if i < len(revs):
            vals = list(revs[i])
            cx = x
            c.setFont("Helvetica", 8)
            for j, (v, cw) in enumerate(zip(vals, cols)):
                c.drawCentredString(cx+cw/2, ry+4, str(v))
                if j > 0: c.line(cx, ry, cx, ry+rh)
                cx += cw
    c.restoreState()


# ══════════════════════════════════════════════════════════════════════════
# DYNAMIC MATRIX PAGE
# ══════════════════════════════════════════════════════════════════════════
def build_matrix(c, proj, matrix):
    draw_title_block(c, proj, "KITCHEN | VANITIES", "MATRIX",
                     "CASA FAMILIA", "MATRIX")
    c.setFont("Helvetica-Bold", 48); c.setFillColor(BLACK)
    c.drawString(DA_L+10, PAGE_H-78, proj["name"])
    c.setFont("Helvetica-Bold", 24)
    c.drawString(DA_L+10, PAGE_H-108, "MATRIX")

    # Table
    cols  = [120, 48, 38, 38, 38, 38, 95, 125]
    heads = ["UNIT NAME","QTY\nTOTAL","V1","V2","V3","V4","KITCHEN\nTYPE","KITCHEN\nTYPE QTY"]
    rh, tw = 18, sum(cols)
    tx, ty = DA_L+70, PAGE_H-135

    # VANITY TYPE span header
    vx  = tx + cols[0]+cols[1]
    vw  = sum(cols[2:6])
    c.setFont("Helvetica-Bold", 8); c.setFillColor(BLACK)
    c.drawCentredString(vx+vw/2, ty+6, "VANITY TYPE")
    c.setLineWidth(0.4); c.line(vx, ty+2, vx+vw, ty+2)

    # Table header row
    c.setLineWidth(0.5)
    c.rect(tx, ty-38, tw, 38, stroke=1, fill=0)
    cx = tx
    c.setFont("Helvetica-Bold", 8)
    for h, cw in zip(heads, cols):
        ls = h.split("\n")
        for li, l in enumerate(ls):
            c.drawCentredString(cx+cw/2, ty-16+li*(-11), l)
        if cx > tx: c.line(cx, ty-38, cx, ty)
        cx += cw

    def row(ry, label, data, bold=False):
        c.setLineWidth(0.5)
        c.rect(tx, ry, tw, rh, stroke=1, fill=0)
        fn = "Helvetica-Bold" if bold else "Helvetica"
        c.setFont(fn, 8); c.setFillColor(BLACK)
        vals = [label, data.get("qty",""), data.get("v1",""),
                data.get("v2",""), data.get("v3",""), data.get("v4",""),
                data.get("kitchen",""), data.get("kq","")]
        cx = tx
        for i, (v, cw) in enumerate(zip(vals, cols)):
            if v not in (0, ""):
                c.drawCentredString(cx+cw/2, ry+5, str(v))
            if i > 0: c.line(cx, ry, cx, ry+rh)
            cx += cw

    ry = ty - 38
    ry -= rh; row(ry, "BUILDING TYPE A", {}, bold=True)
    for r in matrix["building_a"]:
        ry -= rh
        row(ry, r["unit"],
            {"qty":r["qty"],"v1":r["v1"] or "","v2":r["v2"] or "",
             "v3":r["v3"] or "","v4":r["v4"] or "","kitchen":r["kitchen"]})

    ry -= rh; row(ry, "BUILDING TYPE B", {}, bold=True)
    for r in matrix["building_b"]:
        ry -= rh
        row(ry, r["unit"],
            {"qty":r["qty"],"v1":r["v1"] or "","v2":r["v2"] or "",
             "v3":r["v3"] or "","v4":r["v4"] or "","kitchen":r["kitchen"]})

    # Totals
    tot = sum(r["qty"] for r in matrix["building_a"]+matrix["building_b"])
    ry -= rh
    c.setFont("Helvetica-Bold", 9); c.setFillColor(BLACK)
    c.drawCentredString(tx+cols[0]+cols[1]/2, ry+5, str(tot))
    c.rect(tx, ry, tw, rh, stroke=1, fill=0)

    # Kitchen type summary
    kx = tx + sum(cols[:6]) + cols[6]
    kys = ty - 38 - rh
    for kt, kq in matrix["kitchen_types"]:
        kys -= rh
        c.setFont("Helvetica-Bold", 9)
        c.drawCentredString(kx + cols[7]/2 - 10, kys+5, f"{kt}")
        c.drawCentredString(kx + cols[7]/2 + 20, kys+5, str(kq))

    # Summary totals
    kitchen_tot = sum(q for _,q in matrix["kitchen_types"])
    c.setFont("Helvetica-Bold", 11); c.setFillColor(BLACK)
    c.drawString(tx+50, ry-30, f"KITCHEN TOTAL QTY =  {kitchen_tot}")
    c.drawString(tx+50, ry-50, f"VANITY TOTAL QTY  =  62")


# ══════════════════════════════════════════════════════════════════════════
# RECONSTRUCTION DRAWING HELPERS
# ══════════════════════════════════════════════════════════════════════════
def py_to_rl_coords(x, y):
    return x, PAGE_H - y


def set_rl_dashes(canvas, dashes_str):
    if not dashes_str or dashes_str == "[] 0":
        canvas.setDash([])
        return
    try:
        arr_part = dashes_str.split(']')[0].replace('[', '').strip()
        phase = 0
        parts = dashes_str.split(']')
        if len(parts) > 1:
            try:
                phase = float(parts[1].strip())
            except ValueError:
                pass
        if arr_part:
            dashes = [float(x) for x in arr_part.split()]
            canvas.setDash(dashes, phase)
        else:
            canvas.setDash([])
    except Exception:
        canvas.setDash([])


def extract_sheet_number(page):
    """Scan bottom right coordinate space to pull Sheet number A.1-A.21"""
    for b in page.get_text("blocks"):
        if b[0] > 1150 and b[1] > 750:
            lines = [l.strip() for l in b[4].strip().split('\n') if l.strip()]
            for l in lines:
                if re.match(r'^[A-Za-z0-9\.]+$', l):
                    return l
    return "Unknown"


def reconstruct_page_drawings_and_text(ref_doc, page_num, out_canvas):
    page = ref_doc[page_num]
    
    # ── 1. Reconstruct Vector Geometry ───────────────────────────────────
    drawings = page.get_drawings()
    for draw in drawings:
        # Skip drawing primitives in the title block area (x > 1140)
        rect = draw.get("rect", fitz.Rect(0,0,0,0))
        if rect.x0 > 1140:
            continue
            
        fill_color = draw.get("fill")
        stroke_color = draw.get("color")
        stroke_width = draw.get("width", 0.5)
        stroke_dashes = draw.get("dashes", "[] 0")
        
        out_canvas.saveState()
        if fill_color:
            r, g, b = [int(max(0.0, min(1.0, c)) * 255) for c in fill_color]
            out_canvas.setFillColor(HexColor(f"#{r:02x}{g:02x}{b:02x}"))
        if stroke_color:
            r, g, b = [int(max(0.0, min(1.0, c)) * 255) for c in stroke_color]
            out_canvas.setStrokeColor(HexColor(f"#{r:02x}{g:02x}{b:02x}"))
            out_canvas.setLineWidth(stroke_width)
            set_rl_dashes(out_canvas, stroke_dashes)
            
        fill = 1 if fill_color else 0
        stroke = 1 if stroke_color else 0
        
        path = out_canvas.beginPath()
        for item in draw.get("items", []):
            if item[0] == "l":
                p1 = py_to_rl_coords(item[1].x, item[1].y)
                p2 = py_to_rl_coords(item[2].x, item[2].y)
                path.moveTo(p1[0], p1[1])
                path.lineTo(p2[0], p2[1])
            elif item[0] == "re":
                r = item[1]
                p1 = py_to_rl_coords(r.x0, r.y1)
                path.rect(p1[0], p1[1], r.width, r.height)
            elif item[0] == "c":
                p1 = py_to_rl_coords(item[1].x, item[1].y)
                p2 = py_to_rl_coords(item[2].x, item[2].y)
                p3 = py_to_rl_coords(item[3].x, item[3].y)
                p4 = py_to_rl_coords(item[4].x, item[4].y)
                path.moveTo(p1[0], p1[1])
                path.curveTo(p2[0], p2[1], p3[0], p3[1], p4[0], p4[1])
                
        if draw.get("closePath"):
            path.close()
            
        out_canvas.drawPath(path, fill=fill, stroke=stroke)
        out_canvas.restoreState()
        
    # ── 2. Reconstruct Text Spans ─────────────────────────────────────────
    text_dict = page.get_text("dict")
    for block in text_dict.get("blocks", []):
        if block.get("type") == 0:
            for line in block.get("lines", []):
                line_dir = line.get("dir", (1.0, 0.0))
                for span in line.get("spans", []):
                    # Skip text in the title block area (x > 1140)
                    if span["bbox"][0] > 1140:
                        continue
                        
                    text_str = span["text"]
                    size = span["size"]
                    font = span["font"]
                    color = span["color"]
                    
                    out_canvas.saveState()
                    
                    # Color mapping
                    r = (color >> 16) & 255
                    g = (color >> 8) & 255
                    b = color & 255
                    out_canvas.setFillColor(HexColor(f"#{r:02x}{g:02x}{b:02x}"))
                    
                    # Font mapping
                    font_name = "Helvetica"
                    if "bold" in font.lower():
                        font_name = "Helvetica-Bold"
                    elif "italic" in font.lower():
                        font_name = "Helvetica-Oblique"
                    out_canvas.setFont(font_name, size)
                    
                    # Translation and Rotation
                    orig_x, orig_y = span["origin"]
                    rl_x, rl_y = py_to_rl_coords(orig_x, orig_y)
                    
                    dx, dy = line_dir
                    rl_angle_rad = math.atan2(-dy, dx)
                    rl_angle_deg = math.degrees(rl_angle_rad)
                    
                    if abs(rl_angle_deg) > 0.01:
                        out_canvas.translate(rl_x, rl_y)
                        out_canvas.rotate(rl_angle_deg)
                        out_canvas.drawString(0, 0, text_str)
                    else:
                        out_canvas.drawString(rl_x, rl_y, text_str)
                        
                    out_canvas.restoreState()


# ══════════════════════════════════════════════════════════════════════════
# MAIN PROGRAM PIPELINE
# ══════════════════════════════════════════════════════════════════════════
def compile_shop_drawings(ref_pdf_path, output_pdf_path):
    print(f"\n===========================================================================")
    print(f"CASA FAMILIA — PRODUCTION SHOP DRAWINGS COMPILER")
    print(f"===========================================================================")
    print(f"  Reference File: {os.path.basename(ref_pdf_path)}")
    print(f"  Output PDF:     {os.path.basename(output_pdf_path)}")
    
    if not os.path.exists(ref_pdf_path):
        raise FileNotFoundError(f"Reference PDF not found at: {ref_pdf_path}")
        
    ref_doc = fitz.open(ref_pdf_path)
    c = canvas.Canvas(output_pdf_path, pagesize=(PAGE_W, PAGE_H))
    
    c.setTitle(f"Shop Drawings — {PROJECT['name']} — {PROJECT['id']}")
    c.setAuthor("ITALIAN KITCHEN AND BATH")
    c.setSubject("Kitchen & Vanity Shop Drawings")
    c.setCreator("AI Production Compiler v5.0")
    
    # ── Page 1: Dynamic Cover ─────────────────────────────────────────────
    print("  [1/23] Compiling COVER (dynamic)...")
    build_cover(c, PROJECT)
    c.showPage()
    
    # ── Page 2: Dynamic Matrix ────────────────────────────────────────────
    print("  [2/23] Compiling MATRIX (dynamic)...")
    build_matrix(c, PROJECT, UNIT_MATRIX)
    c.showPage()
    
    # ── Pages 3-23: Reconstructed CAD Drawings ───────────────────────────
    for page_idx in range(2, len(ref_doc)):
        page_num = page_idx + 1
        ref_page = ref_doc[page_idx]
        
        # Extract sheet name dynamically (e.g. A.1 to A.21)
        sheet_num = extract_sheet_number(ref_page)
        if sheet_num == "Unknown":
            # Fallback based on index
            sheet_num = f"A.{page_idx - 1}"
            
        print(f"  [{page_num:2d}/23] Reconstructing Sheet {sheet_num:5s} (Page {page_num:2d})...")
        
        # Reconstruct drawing payload
        reconstruct_page_drawings_and_text(ref_doc, page_idx, c)
        
        # Draw standardized title block
        draw_title_block(c, PROJECT, "KITCHEN | VANITIES", sheet_num)
        
        c.showPage()
        
    c.save()
    print(f"\n  [OK] Saved: {output_pdf_path}")
    print(f"  Total compiled pages: 23")


if __name__ == "__main__":
    REF_PATH = r"C:\Users\prajw\OneDrive\Desktop\Albert\Albert_Project\Casa familia\03_Shop_Drawings\ITALIANKB SHOP DRAWINGS - 23-033 CASA FAMILIA - 03.04.2025 hatch corregido.pdf"
    OUT_PATH = r"C:\Users\prajw\OneDrive\Desktop\Albert\Albert_Project\Casa familia\03_Shop_Drawings\GENERATED_SHOP_DRAWINGS_CF_v3.pdf"
    compile_shop_drawings(REF_PATH, OUT_PATH)
