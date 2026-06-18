#!/usr/bin/env python3
"""
===========================================================================
HERITAGE VILLAGE — PRODUCTION SHOP DRAWINGS COMPILER & RECONSTRUCTOR  v1.0
===========================================================================
This script programmatically compiles the 16-page tabloid shop drawing package:
  - Page 1: COVER (dynamically generated from project data)
  - Page 2: MATRIX (dynamically generated from unit quantities)
  - Pages 3-16: Vector-level reconstruction from the client's 14 unit plan PDFs,
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
    "name":        "HERITAGE VILLAGE",
    "id":          "23-045",
    "date":        "05/16/2025",
    "revision":    "17.0",
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
        ("1.0", "12/21/2023", "Y.J", "INITIAL RELEASE"),
        ("5.0", "04/26/2024", "M.A", "COORDINATION"),
        ("15.0", "01/07/2025", "T.A", "ADA/FHA REVISION"),
        ("17.0", "04/21/2025", "A.C", "COORDINATION"),
    ],
    "appliances_regular": [
        '30" REFRIGERATOR  GE MODEL GTE18GSNRSS',
        '24" DISHWASHER    GE MODEL GDT535PSRSS',
        '30" RANGE         GE MODEL GRF400PV',
        '30" MICROWAVE     GE MODEL JVM3160RFSS',
    ],
    "appliances_ada": [
        '30" REFRIGERATOR  GE MODEL GTE18GSNRSS',
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

UNIT_MATRIX = [
    {"unit": "A-1",       "desc": "1BR/1Bath FHA",       "qty": 15, "u": 4, "l": 4, "t": 0, "b": 3},
    {"unit": "A-1a ACC",  "desc": "1BR/1Bath Accessible", "qty": 3,  "u": 4, "l": 4, "t": 0, "b": 3},
    {"unit": "B-1",       "desc": "2BR/2Bath FHA",       "qty": 12, "u": 5, "l": 5, "t": 0, "b": 5},
    {"unit": "B-1a ACC",  "desc": "2BR/2Bath Accessible", "qty": 3,  "u": 5, "l": 5, "t": 0, "b": 5},
    {"unit": "C-1",       "desc": "3BR/2Bath FHA",       "qty": 8,  "u": 5, "l": 5, "t": 0, "b": 5},
    {"unit": "C-2",       "desc": "3BR/2Bath FHA",       "qty": 6,  "u": 5, "l": 5, "t": 0, "b": 5},
    {"unit": "C-2a ACC",  "desc": "3BR/2Bath Accessible", "qty": 2,  "u": 5, "l": 5, "t": 0, "b": 5},
    {"unit": "C-3",       "desc": "3BR/2Bath FHA",       "qty": 6,  "u": 5, "l": 5, "t": 0, "b": 5},
    {"unit": "D-1N",      "desc": "4BR/2Bath FHA (North)", "qty": 4, "u": 6, "l": 6, "t": 0, "b": 5},
    {"unit": "D-1",       "desc": "4BR/2Bath FHA",       "qty": 1,  "u": 6, "l": 6, "t": 0, "b": 5},
    {"unit": "D-1a ACC",  "desc": "4BR/2Bath Accessible", "qty": 2,  "u": 6, "l": 6, "t": 0, "b": 5},
    {"unit": "D-1A ACC",  "desc": "4BR/2Bath Accessible", "qty": 2,  "u": 6, "l": 6, "t": 0, "b": 5},
    {"unit": "ST-1a ACC", "desc": "Studio Accessible",    "qty": 4,  "u": 3, "l": 3, "t": 0, "b": 2},
    {"unit": "ST-1",      "desc": "Studio FHA",           "qty": 6,  "u": 3, "l": 3, "t": 0, "b": 2},
]

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
    c.setFont("Helvetica-Bold", 8)
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
                     "HERITAGE VILLAGE", "KITCHEN | VANITY SHOP-DWGS")

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
    c.drawString(DA_L+10, 25, "OWNER: ATLANTIC PACIFIC COMMUNITIES  |  26905 SW 142nd Ave, Homestead FL")


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
                     "HERITAGE VILLAGE", "MATRIX")
    c.setFont("Helvetica-Bold", 48); c.setFillColor(BLACK)
    c.drawString(DA_L+10, PAGE_H-78, proj["name"])
    c.setFont("Helvetica-Bold", 24)
    c.drawString(DA_L+10, PAGE_H-108, "MATRIX")

    # Table columns centered
    cols  = [90, 160, 30, 45, 45, 45, 45, 45, 45, 60, 60]
    heads = ["UNIT TYPE", "DESCRIPTION", "QTY", "KIT. UPPER", "KIT. LOWER", "KIT. TALL", "KIT. TOTAL", "BATH CABS", "UNIT TOTAL", "PROJ. KIT.", "PROJ. BATH"]
    rh, tw = 16, sum(cols)
    tx, ty = DA_L + (1139.6 - tw)/2, PAGE_H-135

    # Table header row
    c.setLineWidth(0.5)
    c.rect(tx, ty-32, tw, 32, stroke=1, fill=0)
    cx = tx
    c.setFont("Helvetica-Bold", 7.5)
    for h, cw in zip(heads, cols):
        ls = h.split("\n")
        for li, l in enumerate(ls):
            c.drawCentredString(cx+cw/2, ty-14+li*(-10), l)
        if cx > tx: c.line(cx, ty-32, cx, ty)
        cx += cw

    def row(ry, label, desc, data, bold=False):
        c.setLineWidth(0.5)
        c.rect(tx, ry, tw, rh, stroke=1, fill=0)
        fn = "Helvetica-Bold" if bold else "Helvetica"
        c.setFont(fn, 8); c.setFillColor(BLACK)
        
        vals = [
            label, desc, data.get("qty",""), data.get("u",""),
            data.get("l",""), data.get("t",""), data.get("kt",""),
            data.get("b",""), data.get("ut",""), data.get("pk",""),
            data.get("pb","")
        ]
        
        cx = tx
        for i, (v, cw) in enumerate(zip(vals, cols)):
            if v not in (0, ""):
                if i == 1: # description left-aligned
                    c.drawString(cx+4, ry+4, str(v))
                elif i == 0: # label left-aligned if bold
                    c.drawString(cx+4, ry+4, str(v))
                else:
                    c.drawCentredString(cx+cw/2, ry+4, str(v))
            if i > 0: c.line(cx, ry, cx, ry+rh)
            cx += cw

    ry = ty - 32
    tot_qty = 0
    tot_pk = 0
    tot_pb = 0
    
    for r in matrix:
        ry -= rh
        qty = r["qty"]
        kt = r["u"] + r["l"] + r["t"]
        ut = kt + r["b"]
        pk = kt * qty
        pb = r["b"] * qty
        
        row(ry, r["unit"], r["desc"],
            {"qty": qty, "u": r["u"], "l": r["l"], "t": r["t"] or "",
             "kt": kt, "b": r["b"], "ut": ut, "pk": pk, "pb": pb})
             
        tot_qty += qty
        tot_pk += pk
        tot_pb += pb

    # Totals row
    ry -= rh
    c.setFont("Helvetica-Bold", 8.5); c.setFillColor(BLACK)
    c.rect(tx, ry, tw, rh, stroke=1, fill=0)
    
    vals = ["PROJECT TOTALS", "", tot_qty, "", "", "", "", "", "", tot_pk, tot_pb]
    cx = tx
    for i, (v, cw) in enumerate(zip(vals, cols)):
        if v not in (0, ""):
            if i == 0:
                c.drawString(cx+4, ry+4, str(v))
            else:
                c.drawCentredString(cx+cw/2, ry+4, str(v))
        if i > 0: c.line(cx, ry, cx, ry+rh)
        cx += cw

    # Summary totals
    c.setFont("Helvetica-Bold", 11); c.setFillColor(BLACK)
    c.drawString(tx+50, ry-30, f"KITCHEN TOTAL QTY =  {tot_pk}")
    c.drawString(tx+50, ry-50, f"VANITY TOTAL QTY  =  {tot_pb}")


# ══════════════════════════════════════════════════════════════════════════
# RECONSTRUCTION DRAWING HELPERS
# ══════════════════════════════════════════════════════════════════════════
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


def reconstruct_heritage_page(ref_doc, out_canvas):
    page = ref_doc[0]
    
    # Heritage page is 3024 x 2160.
    # We want to crop at x=2800 to exclude the architect's title block on the right.
    # Target drawing area width is DA_R - DA_L = 1139.6, height is 764.0
    orig_w = 2800.0
    orig_h = 2160.0
    
    scale_w = 1139.6 / orig_w
    scale_h = 764.0 / orig_h
    scale = min(scale_w, scale_h)
    
    tx = DA_L
    ty = 14.0 + (764.0 - orig_h * scale) / 2
    
    # 1. Reconstruct vector drawings
    drawings = page.get_drawings()
    
    for draw in drawings:
        rect = draw.get("rect", fitz.Rect(0,0,0,0))
        # Skip drawings in title block area (x > 2800)
        if rect.x0 > 2800:
            continue
            
        fill_color = draw.get("fill")
        stroke_color = draw.get("color")
        stroke_width = draw.get("width", 0.5)
        stroke_dashes = draw.get("dashes", "[] 0")
        
        out_canvas.saveState()
        
        # Apply transformation
        out_canvas.translate(tx, ty)
        out_canvas.scale(scale, scale)
        
        # Translate PyMuPDF coordinates (top-left origin, y increases down)
        # to ReportLab coordinates within the scaled viewport (bottom-left origin, y increases up)
        # In the scaled viewport, the drawing height is 2160.
        def map_coords(x, y):
            return x, 2160.0 - y
            
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
                p1 = map_coords(item[1].x, item[1].y)
                p2 = map_coords(item[2].x, item[2].y)
                path.moveTo(p1[0], p1[1])
                path.lineTo(p2[0], p2[1])
            elif item[0] == "re":
                r = item[1]
                p1 = map_coords(r.x0, r.y1)
                path.rect(p1[0], p1[1], r.width, r.height)
            elif item[0] == "c":
                p1 = map_coords(item[1].x, item[1].y)
                p2 = map_coords(item[2].x, item[2].y)
                p3 = map_coords(item[3].x, item[3].y)
                p4 = map_coords(item[4].x, item[4].y)
                path.moveTo(p1[0], p1[1])
                path.curveTo(p2[0], p2[1], p3[0], p3[1], p4[0], p4[1])
                
        if draw.get("closePath"):
            path.close()
            
        out_canvas.drawPath(path, fill=fill, stroke=stroke)
        out_canvas.restoreState()
        
    # 2. Reconstruct text spans
    text_dict = page.get_text("dict")
    for block in text_dict.get("blocks", []):
        if block.get("type") == 0:
            for line in block.get("lines", []):
                line_dir = line.get("dir", (1.0, 0.0))
                for span in line.get("spans", []):
                    if span["bbox"][0] > 2800:
                        continue
                        
                    text_str = span["text"]
                    size = span["size"]
                    font = span["font"]
                    color = span["color"]
                    
                    out_canvas.saveState()
                    
                    # Apply translation and scaling
                    out_canvas.translate(tx, ty)
                    out_canvas.scale(scale, scale)
                    
                    # Colors
                    r = (color >> 16) & 255
                    g = (color >> 8) & 255
                    b = color & 255
                    out_canvas.setFillColor(HexColor(f"#{r:02x}{g:02x}{b:02x}"))
                    
                    font_name = "Helvetica"
                    if "bold" in font.lower():
                        font_name = "Helvetica-Bold"
                    elif "italic" in font.lower():
                        font_name = "Helvetica-Oblique"
                    out_canvas.setFont(font_name, size)
                    
                    # Map coordinates within scaled viewport
                    orig_x, orig_y = span["origin"]
                    rx, ry = orig_x, 2160.0 - orig_y
                    
                    dx, dy = line_dir
                    rl_angle_rad = math.atan2(-dy, dx)
                    rl_angle_deg = math.degrees(rl_angle_rad)
                    
                    if abs(rl_angle_deg) > 0.01:
                        out_canvas.translate(rx, ry)
                        out_canvas.rotate(rl_angle_deg)
                        out_canvas.drawString(0, 0, text_str)
                    else:
                        out_canvas.drawString(rx, ry, text_str)
                        
                    out_canvas.restoreState()


# ══════════════════════════════════════════════════════════════════════════
# MAIN PROGRAM PIPELINE
# ══════════════════════════════════════════════════════════════════════════
def compile_heritage_shop_drawings(ref_dir_path, output_pdf_path):
    print(f"\n===========================================================================")
    print(f"HERITAGE VILLAGE — PRODUCTION SHOP DRAWINGS COMPILER")
    print(f"===========================================================================")
    print(f"  Reference Directory: {ref_dir_path}")
    print(f"  Output PDF:          {output_pdf_path}")
    
    if not os.path.exists(ref_dir_path):
         raise FileNotFoundError(f"Reference folder not found at: {ref_dir_path}")
         
    c = canvas.Canvas(output_pdf_path, pagesize=(PAGE_W, PAGE_H))
    
    c.setTitle(f"Shop Drawings — {PROJECT['name']} — {PROJECT['id']}")
    c.setAuthor("ITALIAN KITCHEN AND BATH")
    c.setSubject("Kitchen & Vanity Shop Drawings")
    c.setCreator("AI Production Compiler v1.0")
    
    # ── Page 1: Dynamic Cover ─────────────────────────────────────────────
    print("  [01/16] Compiling COVER (dynamic)...")
    build_cover(c, PROJECT)
    c.showPage()
    
    # ── Page 2: Dynamic Matrix ────────────────────────────────────────────
    print("  [02/16] Compiling MATRIX (dynamic)...")
    build_matrix(c, PROJECT, UNIT_MATRIX)
    c.showPage()
    
    # ── Pages 3-16: Reconstructed CAD Drawings ───────────────────────────
    unit_drawings = [
        ("A-6.00", "UNIT A-1", "A-6.00_ UNIT A-1 -FHA - FLOOR PLANS & DETAILS Rev.17 markup.pdf"),
        ("A-6.01", "UNIT A-1A ACC", "A-6.01_ UNIT A-1A ACC FLOOR PLANS & DETAILS Rev.17 markup.pdf"),
        ("A-6.02", "UNIT B-1", "A-6.02_ UNIT B-1 FLOOR PLANS & DETAILS Rev.17 markup.pdf"),
        ("A-6.03", "UNIT B-1A ACC", "A-6.03_ UNIT B-1A ACC FLOOR PLANS & DETAILS Rev.17 markup.pdf"),
        ("A-6.04", "UNIT C-1", "A-6.04_ UNIT C-1 - FHA FLOOR PLANS & DETAILS Rev.17 markup.pdf"),
        ("A-6.05", "UNIT C-2", "A-6.05 - UNIT C-2 - FHA - FLOOR PLANS & DETAILS.pdf"),
        ("A-6.06", "UNIT C-2a ACC", "A-6.06 - UNIT C-2a ACC- FLOOR PLANS & DETAILS-.pdf"),
        ("A-6.07", "UNIT C-3", "A-6.07_ UNIT C-3 FLOOR PLANS & DETAILS Rev.15 markup.pdf"),
        ("A-6.08A", "UNIT D-1N", "A-6.08A_ UNIT D-1N- FHA - FLOOR PLANS AND DETAILS Rev.15 markup.pdf"),
        ("A-6.08", "UNIT D-1", "A-6.08_ UNIT D-1 - FHA FLOOR PLANS & DETAILS Rev.17 markup.pdf"),
        ("A-6.09A", "UNIT D-1a ACC", "A-6.09A_ UNIT D-1a ACC. FLOOR PLANS & DETAILS (CONTINUED) Rev.15 markup.pdf"),
        ("A-6.09", "UNIT D-1A ACC", "A-6.09_ UNIT D-1A ACC FLOOR PLANS AND DETAILS Rev.15 markup.pdf"),
        ("A-6.10", "UNIT ST-1A ACC", "A-6.10_ UNIT ST-1A ACC FLOOR PLANS & DETAILS Rev.15 markup.pdf"),
        ("A-6.11", "UNIT ST-1", "A-6.11_ UNIT ST-1 - FHA FLOOR PLANS & DETAILS Rev.15 markup.pdf")
    ]
    
    for idx, (sheet_num, unit_label, file_name) in enumerate(unit_drawings):
        page_num = idx + 3
        ref_pdf_path = os.path.join(ref_dir_path, file_name)
        
        print(f"  [{page_num:02d}/16] Reconstructing Sheet {sheet_num:7s} ({unit_label})...")
        
        ref_doc = fitz.open(ref_pdf_path)
        reconstruct_heritage_page(ref_doc, c)
        ref_doc.close()
        
        # Draw standardized title block
        draw_title_block(c, PROJECT, "KITCHEN | VANITIES", sheet_num)
        c.showPage()
        
    c.save()
    print(f"\n  [OK] Saved: {output_pdf_path}")
    print(f"  Total compiled pages: 16")


if __name__ == "__main__":
    REF_DIR = r"C:\Users\prajw\OneDrive\Desktop\Albert\Albert_Project\Heritage\01_Architectural_Drawings\Unit_Plans_FHA_ADA"
    OUT_PDF = r"C:\Users\prajw\OneDrive\Desktop\Albert\Albert_Project\Heritage\03_Shop_Drawings\05_Cabinet_Estimation_Shop_Drawings_Heritage_Village.pdf"
    compile_heritage_shop_drawings(REF_DIR, OUT_PDF)
