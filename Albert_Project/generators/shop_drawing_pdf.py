"""
===========================================================================
  generators/shop_drawing_pdf.py — Parameterized Shop Drawing PDF Generator
===========================================================================
  Generates the ItalianKB-style 17"×11" landscape shop drawing PDF
  from pipeline data.

  Key improvements over generate_italiankb_shop_drawings.py:
    1. Data-driven: accepts any project_config.json + unit_schedules
    2. Works for BOTH Casa Familia and Heritage Village (same generator)
    3. Title block detected automatically (not hardcoded x-coordinate)
    4. Proper font registration (Century Gothic, Arial)
    5. Falls back gracefully when AI data not available

  Page structure:
    Page 1:  Cover page
    Page 2:  Project Matrix (unit counts + cabinet totals)
    Pages 3+: One page per elevation (from unit_schedules)
===========================================================================
"""
from __future__ import annotations

import io
from pathlib import Path
from typing import Optional

from reportlab.lib import colors
from reportlab.lib.pagesizes import landscape, LEDGER
from reportlab.lib.units import inch, mm
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont


# ══════════════════════════════════════════════════════════════════════════
# PAGE CONSTANTS
# ══════════════════════════════════════════════════════════════════════════

PAGE_W, PAGE_H = landscape(LEDGER)   # 17" × 11" = 1224 × 792 pts

# Title block (right strip)
TB_X = PAGE_W - 62.0   # left edge of title block
TB_W = 62.0            # width
MARGIN = 18.0

# Drawing area
DA_L = MARGIN
DA_R = TB_X - 4.0
DA_T = PAGE_H - 10.0
DA_B = 10.0

# Colors
NAVY = colors.Color(0.15, 0.15, 0.15)      # Charcoal/Pencil Black
WHITE = colors.white
LTGRAY = colors.Color(0.95, 0.95, 0.95)
LTBLUE = colors.Color(0.85, 0.89, 0.95)
PENCIL_MEDIUM = colors.Color(0.35, 0.35, 0.35) # Pencil gray for dimensions/subtle details


# ══════════════════════════════════════════════════════════════════════════
# FONT SETUP
# ══════════════════════════════════════════════════════════════════════════

def _register_fonts():
    """Register fonts. Falls back to Helvetica if system fonts unavailable."""
    # Try to register Century Gothic (used in original shop drawings)
    cg_paths = [
        "C:/Windows/Fonts/GOTHIC.TTF",
        "C:/Windows/Fonts/Gothic.ttf",
    ]
    ar_paths = [
        "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/Arial.ttf",
    ]
    arb_paths = [
        "C:/Windows/Fonts/arialbd.ttf",
        "C:/Windows/Fonts/ArialBD.ttf",
    ]

    for path in cg_paths:
        if Path(path).exists():
            try:
                pdfmetrics.registerFont(TTFont("CenturyGothic", path))
                return "CenturyGothic", "CenturyGothic"
            except Exception:
                pass

    for path in ar_paths:
        if Path(path).exists():
            try:
                pdfmetrics.registerFont(TTFont("Arial", path))
                for bp in arb_paths:
                    if Path(bp).exists():
                        pdfmetrics.registerFont(TTFont("Arial-Bold", bp))
                        return "Arial", "Arial-Bold"
                return "Arial", "Helvetica-Bold"
            except Exception:
                pass

    return "Helvetica", "Helvetica-Bold"


_FONT_REG, _FONT_BOLD = _register_fonts()


# ══════════════════════════════════════════════════════════════════════════
# DRAWING HELPERS
# ══════════════════════════════════════════════════════════════════════════

def _draw_title_block(c: canvas.Canvas, config: dict, page_num: int, total_pages: int, drawing_title: str):
    """Draw the right-side vertical title block."""
    c.saveState()

    # Title block background - white background
    c.setFillColor(WHITE)
    c.rect(TB_X, 0, TB_W, PAGE_H, fill=1, stroke=0)

    # Rotate to draw vertical text
    c.translate(TB_X + TB_W / 2, PAGE_H / 2)
    c.rotate(90)

    # Company name
    company = config.get("company", {})
    c.setFillColor(NAVY)
    c.setFont(_FONT_BOLD, 8)
    c.drawCentredString(0, 28, company.get("name", "ITALIAN KITCHEN AND BATH"))

    c.setFont(_FONT_REG, 5)
    c.drawCentredString(0, 20, company.get("tagline", "kitchen | bath | tile | closet"))

    # Divider
    c.setStrokeColor(NAVY)
    c.setLineWidth(0.5)
    c.line(-28, 14, 28, 14)

    # Project info
    c.setFont(_FONT_REG, 5)
    info_lines = [
        config.get("project_name", ""),
        f"PROJECT NO: {config.get('project_id', '')}",
        f"DATE: {config.get('date', '')}",
        f"REV: {config.get('revision', '1.0')}",
        f"DRAWN: {config.get('drawn_by', 'A.C')}",
        f"SCALE: 1/2\" = 1'-0\"",
        drawing_title[:28],
        f"SHEET: {page_num} / {total_pages}",
    ]
    for i, line in enumerate(info_lines):
        c.drawCentredString(0, 8 - i * 6.5, line)

    # Address
    c.setFont(_FONT_REG, 4)
    c.drawCentredString(0, 8 - len(info_lines) * 6.5, company.get("address", ""))

    c.restoreState()

    # Left border line
    c.setStrokeColor(NAVY)
    c.setLineWidth(1.0)
    c.line(TB_X, 0, TB_X, PAGE_H)


def _draw_page_border(c: canvas.Canvas):
    """Draw thin border around drawing area."""
    c.setStrokeColor(NAVY)
    c.setLineWidth(0.5)
    c.rect(MARGIN, MARGIN, TB_X - MARGIN - 4, PAGE_H - 2 * MARGIN, fill=0, stroke=1)


def _draw_section_header(c: canvas.Canvas, y: float, text: str):
    """Draw a light-gray-background section header bar with dark pencil text."""
    c.setFillColor(LTGRAY)
    c.rect(DA_L, y - 12, DA_R - DA_L, 14, fill=1, stroke=0)
    c.setFillColor(NAVY)
    c.setFont(_FONT_BOLD, 8)
    c.drawString(DA_L + 4, y - 8, text)
    return y - 14


# ══════════════════════════════════════════════════════════════════════════
# PAGE 1: COVER
# ══════════════════════════════════════════════════════════════════════════

def _draw_cover(c: canvas.Canvas, config: dict, unit_totals: dict, total_pages: int):
    """Draw the cover page."""
    company = config.get("company", {})

    # Background
    c.setFillColor(WHITE)
    c.rect(0, PAGE_H * 0.55, TB_X, PAGE_H * 0.45, fill=1, stroke=0)

    # Company logo / name area
    c.setFillColor(NAVY)
    c.setFont(_FONT_BOLD, 28)
    c.drawCentredString((DA_L + DA_R) / 2, PAGE_H * 0.80,
                         company.get("name", "ITALIAN KITCHEN AND BATH"))

    c.setFont(_FONT_REG, 12)
    c.drawCentredString((DA_L + DA_R) / 2, PAGE_H * 0.74,
                         company.get("tagline", "kitchen | bath | tile | closet"))

    # Project Info Block
    c.setFillColor(NAVY)
    c.setFont(_FONT_BOLD, 22)
    c.drawCentredString((DA_L + DA_R) / 2, PAGE_H * 0.44,
                         "CABINET SHOP DRAWINGS")

    c.setFont(_FONT_BOLD, 18)
    c.drawCentredString((DA_L + DA_R) / 2, PAGE_H * 0.37,
                         config.get("project_name", "PROJECT"))

    c.setFont(_FONT_REG, 11)
    c.drawCentredString((DA_L + DA_R) / 2, PAGE_H * 0.31,
                         config.get("address", ""))

    # Info table
    info_items = [
        ("Project No:", config.get("project_id", "")),
        ("Date:",       config.get("date", "")),
        ("Finish:",     config.get("finish", "Standard 1")),
        ("Door Style:", config.get("door_style", "Shaker")),
        ("Total Units:", str(sum(unit_totals.values()))),
        ("Revision:",   config.get("revision", "1.0")),
    ]
    start_y = PAGE_H * 0.25
    col_x = (DA_L + DA_R) / 2 - 120
    for i, (label, val) in enumerate(info_items):
        y = start_y - i * 16
        c.setFont(_FONT_BOLD, 9)
        c.drawRightString(col_x + 80, y, label)
        c.setFont(_FONT_REG, 9)
        c.drawString(col_x + 85, y, val)

    # Footer
    c.setFont(_FONT_REG, 8)
    c.setFillColor(colors.gray)
    c.drawCentredString((DA_L + DA_R) / 2, MARGIN + 5,
                         f"{company.get('address', '')}  |  {company.get('phone', '')}")

    _draw_title_block(c, config, 1, total_pages, "COVER")
    _draw_page_border(c)


# ══════════════════════════════════════════════════════════════════════════
# PAGE 2: MATRIX
# ══════════════════════════════════════════════════════════════════════════

def _draw_matrix_page(c: canvas.Canvas, config: dict, unit_schedules: dict,
                       unit_totals: dict, total_pages: int):
    """Draw the project unit matrix page."""
    project_name = config.get("project_name", "").upper()
    if "CASA FAMILIA" in project_name:
        _draw_casa_familia_matrix(c, config, unit_totals, total_pages)
    elif "HERITAGE" in project_name:
        _draw_heritage_matrix(c, config, unit_totals, total_pages)
    else:
        _draw_generic_matrix(c, config, unit_schedules, unit_totals, total_pages)


def _draw_casa_familia_matrix(c: canvas.Canvas, config: dict, unit_totals: dict, total_pages: int):
    _draw_page_border(c)
    _draw_title_block(c, config, 2, total_pages, "PROJECT MATRIX")

    c.setFillColor(NAVY)
    c.setFont(_FONT_BOLD, 14)
    c.drawString(DA_L + 10, DA_T - 20, "PROJECT CABINET MATRIX")

    c.setFont(_FONT_REG, 8)
    c.setFillColor(colors.black)
    c.drawString(DA_L + 10, DA_T - 32, config.get("project_name", "CASA FAMILIA"))

    # Table dimensions
    cols = [120, 48, 38, 38, 38, 38, 95, 62.5, 62.5]
    tw = sum(cols)
    tx = DA_L + (1139.6 - tw) / 2
    ty = DA_T - 50

    # Draw Header (48 pt height)
    c.saveState()
    c.setFillColor(LTGRAY)
    c.rect(tx, ty - 48, tw, 48, fill=1, stroke=1)

    col_x = [tx]
    for w in cols:
        col_x.append(col_x[-1] + w)

    c.setStrokeColor(NAVY)
    c.setLineWidth(0.5)

    # Draw vertical lines in header
    c.line(col_x[1], ty - 48, col_x[1], ty)
    c.line(col_x[2], ty - 48, col_x[2], ty)
    c.line(col_x[6], ty - 48, col_x[6], ty)
    c.line(col_x[7], ty - 48, col_x[7], ty)

    # Sub-columns V1-V4 vertical lines
    c.line(col_x[3], ty - 32, col_x[3], ty - 16)
    c.line(col_x[4], ty - 32, col_x[4], ty - 16)
    c.line(col_x[5], ty - 32, col_x[5], ty - 16)
    
    # Sub-columns TYPE-QTY vertical line
    c.line(col_x[8], ty - 32, col_x[8], ty - 16)

    # Horizontal lines inside header (start second line from col_x[2] to avoid crossing QTY TOTAL)
    c.line(col_x[2], ty - 16, col_x[6], ty - 16)
    c.line(col_x[2], ty - 32, col_x[6], ty - 32)
    
    c.line(col_x[7], ty - 16, col_x[9], ty - 16)
    c.line(col_x[7], ty - 32, col_x[9], ty - 32)

    # Header texts
    c.setFillColor(NAVY)
    c.setFont(_FONT_BOLD, 8)

    c.drawCentredString(tx + 60, ty - 28, "UNIT NAME")
    c.drawCentredString(col_x[1] + 24, ty - 10, "QTY")
    c.drawCentredString(col_x[1] + 24, ty - 35, "TOTAL")
    c.drawCentredString(col_x[2] + 76, ty - 12, "VANITY TYPE")

    c.drawCentredString(col_x[2] + 19, ty - 26, "V1")
    c.drawCentredString(col_x[3] + 19, ty - 26, "V2")
    c.drawCentredString(col_x[4] + 19, ty - 26, "V3")
    c.drawCentredString(col_x[5] + 19, ty - 26, "V4")

    c.drawCentredString(col_x[2] + 76, ty - 42, "VANITIES")

    c.drawCentredString(col_x[6] + 47.5, ty - 28, "KITCHEN TYPE")
    
    c.drawCentredString(col_x[7] + 62.5, ty - 12, "KITCHEN TYPE")
    c.drawCentredString(col_x[7] + 31.25, ty - 26, "TYPE")
    c.drawCentredString(col_x[8] + 31.25, ty - 26, "QTY")
    c.drawCentredString(col_x[7] + 62.5, ty - 42, "KITCHENS")

    c.restoreState()

    # Rows construction
    building_a_units = [
        {"unit": "UNIT A1", "v1": 1, "v2": 0, "v3": 0, "v4": 0, "kitchen": "K1", "ut_key": "A1"},
        {"unit": "UNIT A2 FA", "v1": 0, "v2": 1, "v3": 0, "v4": 0, "kitchen": "K2", "ut_key": "A2-ADA"},
        {"unit": "UNIT A3", "v1": 0, "v2": 0, "v3": 1, "v4": 0, "kitchen": "K1", "ut_key": "A3"},
        {"unit": "UNIT B1", "v1": 1, "v2": 0, "v3": 0, "v4": 1, "kitchen": "K3", "ut_key": "B1"},
        {"unit": "UNIT B2 FA", "v1": 0, "v2": 1, "v3": 0, "v4": 1, "kitchen": "K4", "ut_key": "B2-ADA"}
    ]

    building_b_units = [
        {"unit": "UNIT A1", "v1": 1, "v2": 0, "v3": 0, "v4": 0, "kitchen": "K1", "ut_key": "A1"},
        {"unit": "UNIT A2 FA", "v1": 0, "v2": 1, "v3": 0, "v4": 0, "kitchen": "K2", "ut_key": "A2-ADA"},
        {"unit": "UNIT A3", "v1": 0, "v2": 0, "v3": 1, "v4": 0, "kitchen": "K1", "ut_key": "A3"},
        {"unit": "UNIT B1", "v1": 1, "v2": 0, "v3": 0, "v4": 1, "kitchen": "K3", "ut_key": "B1"},
        {"unit": "UNIT B2 FA", "v1": 0, "v2": 1, "v3": 0, "v4": 1, "kitchen": "K4", "ut_key": "B2-ADA"}
    ]

    v1_tot = 0
    v2_tot = 0
    v3_tot = 0
    v4_tot = 0
    kt_totals = {"K1": 0, "K2": 0, "K3": 0, "K4": 0}
    tot_kitchens = 0

    # Sum counts for Building A
    for item in building_a_units:
        qty = unit_totals.get(item["ut_key"], 0)
        item["qty"] = qty
        v1_tot += qty * item["v1"]
        v2_tot += qty * item["v2"]
        v3_tot += qty * item["v3"]
        v4_tot += qty * item["v4"]
        kt_totals[item["kitchen"]] += qty
        tot_kitchens += qty

    # Sum counts for Building B
    for item in building_b_units:
        qty = unit_totals.get(item["ut_key"], 0)
        item["qty"] = qty
        v1_tot += qty * item["v1"]
        v2_tot += qty * item["v2"]
        v3_tot += qty * item["v3"]
        v4_tot += qty * item["v4"]
        kt_totals[item["kitchen"]] += qty
        tot_kitchens += qty

    # Kitchen summary list
    kit_summary = [
        ("K1", kt_totals["K1"]),
        ("K2", kt_totals["K2"]),
        ("K3", kt_totals["K3"]),
        ("K4", kt_totals["K4"])
    ]

    ry = ty - 48
    rh = 16

    def draw_row(ry, cells, bold=False, is_building_header=False):
        c.saveState()
        c.setStrokeColor(NAVY)
        c.setLineWidth(0.5)
        c.rect(tx, ry, tw, rh, stroke=1, fill=0)

        # Draw vertical lines
        cx = tx
        for w in cols[:-1]:
            cx += w
            c.line(cx, ry, cx, ry + rh)

        # Draw cell contents
        c.setFont(_FONT_BOLD if bold else _FONT_REG, 7.5)
        c.setFillColor(colors.black)

        cx = tx
        for i, val in enumerate(cells):
            w = cols[i]
            if val not in (0, "", None, "-"):
                if i == 0:  # Left aligned for Unit Name
                    c.drawString(cx + 4, ry + 4, str(val))
                else:       # Centered for others
                    c.drawCentredString(cx + w / 2, ry + 4, str(val))
            elif val == "-" or (is_building_header and i == 1):
                c.drawCentredString(cx + w / 2, ry + 4, "-")
            cx += w

        c.restoreState()

    # 1. Building Type A row
    k_type_0 = kit_summary[0][0]
    k_qty_0 = kit_summary[0][1]
    draw_row(ry - rh, ["BUILDING TYPE A", "-", "", "", "", "", "", k_type_0, k_qty_0], bold=True, is_building_header=True)
    ry -= rh

    # 2. Building A units
    for idx, item in enumerate(building_a_units):
        ry -= rh
        k_type = kit_summary[idx+1][0] if idx+1 < len(kit_summary) else ""
        k_qty = kit_summary[idx+1][1] if idx+1 < len(kit_summary) else ""

        draw_row(ry, [
            item["unit"],
            item["qty"],
            item["v1"] or "",
            item["v2"] or "",
            item["v3"] or "",
            item["v4"] or "",
            item["kitchen"],
            k_type,
            k_qty
        ])

    # 3. Building Type B row
    ry -= rh
    draw_row(ry, ["BUILDING TYPE B", "-", "", "", "", "", "", "", ""], bold=True, is_building_header=True)

    # 4. Building B units
    for item in building_b_units:
        ry -= rh
        draw_row(ry, [
            item["unit"],
            item["qty"],
            item["v1"] or "",
            item["v2"] or "",
            item["v3"] or "",
            item["v4"] or "",
            item["kitchen"],
            "",
            ""
        ])

    # 5. Table outer border
    c.saveState()
    c.setStrokeColor(NAVY)
    c.setLineWidth(0.75)
    c.rect(tx, ry, tw, (ty - 48) - ry, fill=0, stroke=1)
    c.restoreState()

    # 6. Summary Totals below table (just like in the image)
    sum_y = ry - 20
    c.setFont(_FONT_BOLD, 8)
    c.setFillColor(colors.black)

    # Totals numbers centered under respective columns
    c.drawCentredString(tx + cols[0] + cols[1] / 2, sum_y, str(tot_kitchens))  # total qty (50)
    c.drawCentredString(tx + sum(cols[:2]) + cols[2] / 2, sum_y, str(v1_tot))  # V1 (34)
    c.drawCentredString(tx + sum(cols[:3]) + cols[3] / 2, sum_y, str(v2_tot))  # V2 (12)
    c.drawCentredString(tx + sum(cols[:4]) + cols[4] / 2, sum_y, str(v3_tot))  # V3 (4)
    c.drawCentredString(tx + sum(cols[:5]) + cols[5] / 2, sum_y, str(v4_tot))  # V4 (12)

    c.drawCentredString(tx + sum(cols[:8]) + cols[8] / 2, sum_y, str(tot_kitchens)) # total kitchens (50)

    # Vanity labels below totals numbers
    lbl_y = sum_y - 12
    c.drawCentredString(tx + sum(cols[:2]) + cols[2] / 2, lbl_y, "V1")
    c.drawCentredString(tx + sum(cols[:3]) + cols[3] / 2, lbl_y, "V2")
    c.drawCentredString(tx + sum(cols[:4]) + cols[4] / 2, lbl_y, "V3")
    c.drawCentredString(tx + sum(cols[:5]) + cols[5] / 2, lbl_y, "V4")

    # Left side block text
    txt_y = lbl_y - 25
    c.drawString(tx + 40, txt_y, f"KITCHEN TOTAL QTY =  {tot_kitchens}")
    c.drawString(tx + 40, txt_y - 12, f"VANITY TOTAL QTY  =  {v1_tot + v2_tot + v3_tot + v4_tot}")


def _draw_heritage_matrix(c: canvas.Canvas, config: dict, unit_totals: dict, total_pages: int):
    _draw_page_border(c)
    _draw_title_block(c, config, 2, total_pages, "PROJECT MATRIX")

    c.setFillColor(NAVY)
    c.setFont(_FONT_BOLD, 14)
    c.drawString(DA_L + 10, DA_T - 20, "PROJECT CABINET MATRIX")

    c.setFont(_FONT_REG, 8)
    c.setFillColor(colors.black)
    c.drawString(DA_L + 10, DA_T - 32, config.get("project_name", "HERITAGE VILLAGE"))

    # Table columns centered
    cols  = [90, 160, 30, 45, 45, 45, 45, 45, 45, 60, 60]
    heads = ["UNIT TYPE", "DESCRIPTION", "QTY", "KIT. UPPER", "KIT. LOWER", "KIT. TALL", "KIT. TOTAL", "BATH CABS", "UNIT TOTAL", "PROJ. KIT.", "PROJ. BATH"]
    tw = sum(cols)
    tx = DA_L + (1139.6 - tw) / 2
    ty = DA_T - 50

    # Table header row
    c.setLineWidth(0.5)
    c.rect(tx, ty-32, tw, 32, stroke=1, fill=0)
    cx = tx
    c.setFont(_FONT_BOLD, 7.5)
    for h, cw in zip(heads, cols):
        ls = h.split("\n")
        for li, l in enumerate(ls):
            c.drawCentredString(cx+cw/2, ty-14+li*(-10), l)
        if cx > tx: c.line(cx, ty-32, cx, ty)
        cx += cw

    heritage_matrix_data = [
        {"unit": "A-1",       "desc": "1BR/1Bath FHA",       "qty_key": "A-1",       "u": 4, "l": 4, "t": 0, "b": 3},
        {"unit": "A-1a ACC",  "desc": "1BR/1Bath Accessible", "qty_key": "A-1a ACC",  "u": 4, "l": 4, "t": 0, "b": 3},
        {"unit": "B-1",       "desc": "2BR/2Bath FHA",       "qty_key": "B-1",       "u": 5, "l": 5, "t": 0, "b": 5},
        {"unit": "B-1a ACC",  "desc": "2BR/2Bath Accessible", "qty_key": "B-1a ACC",  "u": 5, "l": 5, "t": 0, "b": 5},
        {"unit": "C-1",       "desc": "3BR/2Bath FHA",       "qty_key": "C-1",       "u": 5, "l": 5, "t": 0, "b": 5},
        {"unit": "C-2",       "desc": "3BR/2Bath FHA",       "qty_key": "C-2",       "u": 5, "l": 5, "t": 0, "b": 5},
        {"unit": "C-2a ACC",  "desc": "3BR/2Bath Accessible", "qty_key": "C-2a ACC",  "u": 5, "l": 5, "t": 0, "b": 5},
        {"unit": "C-3",       "desc": "3BR/2Bath FHA",       "qty_key": "C-3",       "u": 5, "l": 5, "t": 0, "b": 5},
        {"unit": "D-1N",      "desc": "4BR/2Bath FHA (North)", "qty_key": "D-1N",      "u": 6, "l": 6, "t": 0, "b": 5},
        {"unit": "D-1",       "desc": "4BR/2Bath FHA",       "qty_key": "D-1",       "u": 6, "l": 6, "t": 0, "b": 5},
        {"unit": "D-1a ACC",  "desc": "4BR/2Bath Accessible", "qty_key": "D-1a ACC",  "u": 6, "l": 6, "t": 0, "b": 5},
        {"unit": "D-1A ACC",  "desc": "4BR/2Bath Accessible", "qty_key": "D-1A ACC",  "u": 6, "l": 6, "t": 0, "b": 5},
        {"unit": "ST-1a ACC", "desc": "Studio Accessible",    "qty_key": "ST-1a ACC", "u": 3, "l": 3, "t": 0, "b": 2},
        {"unit": "ST-1",      "desc": "Studio FHA",           "qty_key": "ST-1",      "u": 3, "l": 3, "t": 0, "b": 2},
    ]

    def draw_row(ry, label, desc, data, bold=False):
        c.setLineWidth(0.5)
        c.rect(tx, ry, tw, 16, stroke=1, fill=0)
        fn = "Helvetica-Bold" if bold else "Helvetica"
        c.setFont(fn, 8); c.setFillColor(colors.black)

        vals = [
            label, desc, data.get("qty",""), data.get("u",""),
            data.get("l",""), data.get("t",""), data.get("kt",""),
            data.get("b",""), data.get("ut",""), data.get("pk",""),
            data.get("pb","")
        ]

        cx = tx
        for i, (v, cw) in enumerate(zip(vals, cols)):
            if v not in (0, ""):
                if i in (0, 1): # label and desc left-aligned
                    c.drawString(cx+4, ry+4, str(v))
                else:
                    c.drawCentredString(cx+cw/2, ry+4, str(v))
            if i > 0: c.line(cx, ry, cx, ry+16)
            cx += cw

    ry = ty - 32
    tot_qty = 0
    tot_pk = 0
    tot_pb = 0
    rh = 16

    for r in heritage_matrix_data:
        ry -= rh
        qty = unit_totals.get(r["qty_key"], 0)
        kt = r["u"] + r["l"] + r["t"]
        ut = kt + r["b"]
        pk = kt * qty
        pb = r["b"] * qty

        draw_row(ry, r["unit"], r["desc"],
                 {"qty": qty, "u": r["u"], "l": r["l"], "t": r["t"] or "",
                  "kt": kt, "b": r["b"], "ut": ut, "pk": pk, "pb": pb})

        tot_qty += qty
        tot_pk += pk
        tot_pb += pb

    # Totals row
    ry -= rh
    c.setFont("Helvetica-Bold", 8.5); c.setFillColor(colors.black)
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
    c.setFont("Helvetica-Bold", 11); c.setFillColor(colors.black)
    c.drawString(tx+50, ry-30, f"KITCHEN TOTAL QTY =  {tot_pk}")
    c.drawString(tx+50, ry-50, f"VANITY TOTAL QTY  =  {tot_pb}")


def _draw_generic_matrix(c: canvas.Canvas, config: dict, unit_schedules: dict,
                          unit_totals: dict, total_pages: int):
    _draw_page_border(c)
    _draw_title_block(c, config, 2, total_pages, "PROJECT MATRIX")

    c.setFillColor(NAVY)
    c.setFont(_FONT_BOLD, 14)
    c.drawString(DA_L + 4, DA_T - 20, "PROJECT CABINET MATRIX")

    c.setFont(_FONT_REG, 8)
    c.setFillColor(colors.black)
    c.drawString(DA_L + 4, DA_T - 32, config.get("project_name", ""))

    # Table
    col_widths = [80, 35, 55, 55, 55, 55, 55, 65, 55, 55, 55, 65]
    headers = ["Unit Type", "Qty", "Upper", "Base", "Pantry", "Sink B.",
               "Corner", "Total Kit.", "Vanity", "Med.", "Linen", "Total Bath"]
    table_x = DA_L + 4
    table_y = DA_T - 50

    # Draw header row
    c.setFillColor(LTGRAY)
    c.rect(table_x, table_y - 14, sum(col_widths), 14, fill=1, stroke=0)
    c.setFillColor(NAVY)
    c.setFont(_FONT_BOLD, 7)
    x = table_x
    for w, h in zip(col_widths, headers):
        c.drawCentredString(x + w / 2, table_y - 9, h)
        x += w

    row_y = table_y - 14
    alt = False
    for unit_type, qty in unit_totals.items():
        row_y -= 14
        schedule = unit_schedules.get(unit_type)

        if schedule:
            cabs = [cab for cab in schedule.all_cabinets if cab.cabinet_type != "appliance_space"]
            upper  = sum(c2.quantity for c2 in cabs if c2.cabinet_type in ("upper_wall", "corner_upper", "microwave_shelf"))
            base   = sum(c2.quantity for c2 in cabs if c2.cabinet_type in ("base", "dw_adjacent"))
            pantry = sum(c2.quantity for c2 in cabs if c2.cabinet_type == "pantry")
            sink_b = sum(c2.quantity for c2 in cabs if c2.cabinet_type == "sink_base")
            corner = sum(c2.quantity for c2 in cabs if "corner" in c2.cabinet_type)
            vanity = sum(c2.quantity for c2 in cabs if c2.cabinet_type == "vanity")
            med    = sum(c2.quantity for c2 in cabs if c2.cabinet_type == "medicine_cabinet")
            linen  = sum(c2.quantity for c2 in cabs if c2.cabinet_type == "linen")
            total_kit  = upper + base + pantry + sink_b + corner
            total_bath = vanity + med + linen
        else:
            upper = base = pantry = sink_b = corner = vanity = med = linen = 0
            total_kit = total_bath = 0

        values = [unit_type, qty, upper, base, pantry, sink_b, corner,
                  total_kit, vanity, med, linen, total_bath]

        if alt:
            c.setFillColor(LTGRAY)
            c.rect(table_x, row_y, sum(col_widths), 14, fill=1, stroke=0)
        alt = not alt

        c.setFillColor(colors.black)
        c.setFont(_FONT_BOLD if unit_type.endswith(("Total", "TOTAL")) else _FONT_REG, 7)
        x = table_x
        for i, (w, v) in enumerate(zip(col_widths, values)):
            if i == 0:
                c.drawString(x + 3, row_y + 4, str(v))
            else:
                c.drawCentredString(x + w / 2, row_y + 4, str(v) if v != 0 else "-")
            x += w

        # Thin divider
        c.setStrokeColor(colors.lightgrey)
        c.setLineWidth(0.3)
        c.line(table_x, row_y, table_x + sum(col_widths), row_y)

    # Border around table
    c.setStrokeColor(NAVY)
    c.setLineWidth(0.75)
    c.rect(table_x, row_y, sum(col_widths), table_y - row_y, fill=0, stroke=1)

    # Notes
    notes = config.get("general_notes", [])
    note_y = row_y - 25
    c.setFont(_FONT_BOLD, 8)
    c.setFillColor(NAVY)
    c.drawString(table_x, note_y, "GENERAL NOTES:")
    c.setFont(_FONT_REG, 7)
    c.setFillColor(colors.black)
    for i, note in enumerate(notes[:8]):
        c.drawString(table_x + 5, note_y - 10 - i * 10, f"• {note}")


# ══════════════════════════════════════════════════════════════════════════
# PAGES 3+: UNIT ELEVATION PAGES
# ══════════════════════════════════════════════════════════════════════════

def _draw_unit_page(c: canvas.Canvas, config: dict, unit_type: str, schedule,
                    page_num: int, total_pages: int):
    """Draw one page for a unit type elevation schedule."""
    _draw_page_border(c)
    _draw_title_block(c, config, page_num, total_pages, f"UNIT {unit_type}")

    is_ada = "ACC" in unit_type or "ADA" in unit_type

    # Page header
    c.setFillColor(NAVY)
    c.setFont(_FONT_BOLD, 12)
    c.drawString(DA_L + 4, DA_T - 18, f"UNIT {unit_type} — CABINET SCHEDULE & LAYOUTS")

    # Render Geometries from GeometryEngine on the Left
    wall_length_inches = 90.0
    if schedule:
        from core.geometry_engine import GeometryEngine
        
        # Build walls for GeometryEngine
        walls_info = []
        for ev in schedule.elevations:
            cabs_list = []
            base_x = 0
            for cab in ev.cabinets:
                w_in = round(cab.width_mm / 25.4)
                h_in = round(cab.height_mm / 25.4)
                cabs_list.append({
                    "id": cab.cabinet_id or cab.code,
                    "x": base_x,
                    "width": w_in,
                    "height": h_in,
                    "type": cab.cabinet_type,
                    "cabinet_type": cab.cabinet_type
                })
                base_x += w_in
            
            wall_name = ev.elevation_label.replace("ELEVATION ", "").strip()
            if wall_name.upper() in ("KITCHEN", "BATH", "VANITY", "MASTER_BATH"):
                wall_name = "A"
                
            walls_info.append({
                "name": wall_name,
                "length": max(90.0, base_x),
                "cabinets": cabs_list
            })
            
        if not walls_info:
            walls_info.append({
                "name": "A",
                "length": 90.0,
                "cabinets": []
            })
            
        geom_engine = GeometryEngine()
        ceiling_height = 108.0
        for ev in schedule.elevations:
            if ev.ceiling_height_in is not None:
                ceiling_height = ev.ceiling_height_in
                break
                
        geom_data = geom_engine.generate_layout_geometry(
            walls = walls_info,
            appliances = [],
            ceiling_height = ceiling_height,
            soffit_height = ceiling_height - 12.0
        )
        
        # Left visual drawings area: X from 40 to 460 (width 420 pt).
        # We reserve 280 pt for plan/elevation width, and the rest for side view.
        visual_width_allowed = 280.0
        
        # Calculate total width of all walls including 100pt spacing (which is 25 inches)
        total_length_inches = sum(w.get("length", 90.0) for w in walls_info) + (len(walls_info) - 1) * 25.0
        wall_length_inches = total_length_inches
        
        draw_scale = 1.0
        if wall_length_inches * 4.0 > visual_width_allowed:
            draw_scale = visual_width_allowed / (wall_length_inches * 4.0)
            
        GE_PLAN_OX = 250.0
        GE_PLAN_OY = 450.0
        GE_ELEV_OX = 250.0
        GE_ELEV_OY = 150.0
        GE_SIDE_OX = 250.0
        GE_SIDE_OY = 150.0

        PDF_PLAN_OX = 50.0
        PDF_PLAN_OY = 580.0
        PDF_ELEV_OX = 50.0
        PDF_ELEV_OY = 180.0
        PDF_SIDE_OX = 370.0
        PDF_SIDE_OY = 180.0
        
        # --- Draw Plan View ---
        for line in geom_data.get("plan", {}).get("lines", []):
            x0 = (line["start"][0] - GE_PLAN_OX) * draw_scale + PDF_PLAN_OX
            y0 = (line["start"][1] - GE_PLAN_OY) * draw_scale + PDF_PLAN_OY
            x1 = (line["end"][0] - GE_PLAN_OX) * draw_scale + PDF_PLAN_OX
            y1 = (line["end"][1] - GE_PLAN_OY) * draw_scale + PDF_PLAN_OY
            c.saveState()
            c.setStrokeColor(NAVY if line.get("layer") == "WALLS" else colors.black)
            c.setLineWidth(1.5 if line.get("layer") == "WALLS" else 0.5)
            if line.get("style") == "dashed":
                c.setDash([2, 2])
            c.line(x0, y0, x1, y1)
            c.restoreState()
            
        for block in geom_data.get("plan", {}).get("blocks", []):
            x, y, w, h = block["coords"]
            x_new = (x - GE_PLAN_OX) * draw_scale + PDF_PLAN_OX
            y_new = (y - GE_PLAN_OY) * draw_scale + PDF_PLAN_OY
            w_new = w * draw_scale
            h_new = h * draw_scale
            c.saveState()
            c.setStrokeColor(colors.black)
            c.setFillColor(colors.white)
            if block.get("style") == "dashed":
                c.setDash([2, 2])
            c.rect(x_new, y_new, w_new, h_new, fill=1, stroke=1)
            c.restoreState()
            
        for txt in geom_data.get("plan", {}).get("texts", []):
            pos_x = (txt["pos"][0] - GE_PLAN_OX) * draw_scale + PDF_PLAN_OX
            pos_y = (txt["pos"][1] - GE_PLAN_OY) * draw_scale + PDF_PLAN_OY
            text_str = txt["text"]
            c.saveState()
            c.setFont(_FONT_REG, max(4.0, txt.get("size", 5.0) * draw_scale))
            c.setFillColor(colors.black)
            lines = text_str.split('\n')
            for i, line_text in enumerate(lines):
                c.drawCentredString(pos_x, pos_y - i * (max(4.0, txt.get("size", 5.0) * draw_scale) + 1), line_text)
            c.restoreState()
            
        for dim in geom_data.get("plan", {}).get("dimensions", []):
            x0 = (dim["start"][0] - GE_PLAN_OX) * draw_scale + PDF_PLAN_OX
            y0 = (dim["start"][1] - GE_PLAN_OY) * draw_scale + PDF_PLAN_OY
            x1 = (dim["end"][0] - GE_PLAN_OX) * draw_scale + PDF_PLAN_OX
            y1 = (dim["end"][1] - GE_PLAN_OY) * draw_scale + PDF_PLAN_OY
            text_str = dim["text"]
            c.saveState()
            c.setStrokeColor(PENCIL_MEDIUM)
            c.setLineWidth(0.5)
            c.line(x0, y0, x1, y1)
            c.line(x0, y0 - 3, x0, y0 + 3)
            c.line(x1, y1 - 3, x1, y1 + 3)
            c.setFont(_FONT_REG, 5.0)
            c.setFillColor(PENCIL_MEDIUM)
            c.drawCentredString((x0 + x1) / 2, (y0 + y1) / 2 + 4, text_str)
            c.restoreState()
            
        # --- Draw Elevation View ---
        for line in geom_data.get("elevation", {}).get("lines", []):
            x0 = (line["start"][0] - GE_ELEV_OX) * draw_scale + PDF_ELEV_OX
            y0 = (line["start"][1] - GE_ELEV_OY) * draw_scale + PDF_ELEV_OY
            x1 = (line["end"][0] - GE_ELEV_OX) * draw_scale + PDF_ELEV_OX
            y1 = (line["end"][1] - GE_ELEV_OY) * draw_scale + PDF_ELEV_OY
            c.saveState()
            c.setStrokeColor(NAVY if line.get("layer") in ("GROUND", "CEILING") else colors.black)
            c.setLineWidth(1.0 if line.get("layer") in ("GROUND", "CEILING") else 0.5)
            if line.get("style") == "dashed":
                c.setDash([2, 2])
            c.line(x0, y0, x1, y1)
            c.restoreState()
            
        for block in geom_data.get("elevation", {}).get("blocks", []):
            x, y, w, h = block["coords"]
            x_new = (x - GE_ELEV_OX) * draw_scale + PDF_ELEV_OX
            y_new = (y - GE_ELEV_OY) * draw_scale + PDF_ELEV_OY
            w_new = w * draw_scale
            h_new = h * draw_scale
            c.saveState()
            c.setStrokeColor(colors.black)
            c.setFillColor(colors.white)
            if block.get("style") == "dashed":
                c.setDash([2, 2])
            c.rect(x_new, y_new, w_new, h_new, fill=1, stroke=1)
            c.restoreState()
            
        for txt in geom_data.get("elevation", {}).get("texts", []):
            pos_x = (txt["pos"][0] - GE_ELEV_OX) * draw_scale + PDF_ELEV_OX
            pos_y = (txt["pos"][1] - GE_ELEV_OY) * draw_scale + PDF_ELEV_OY
            text_str = txt["text"]
            c.saveState()
            c.setFont(_FONT_REG, max(4.0, txt.get("size", 5.0) * draw_scale))
            c.setFillColor(colors.black)
            lines = text_str.split('\n')
            for i, line_text in enumerate(lines):
                c.drawCentredString(pos_x, pos_y - i * (max(4.0, txt.get("size", 5.0) * draw_scale) + 1), line_text)
            c.restoreState()
            
        for dim in geom_data.get("elevation", {}).get("dimensions", []):
            x0 = (dim["start"][0] - GE_ELEV_OX) * draw_scale + PDF_ELEV_OX
            y0 = (dim["start"][1] - GE_ELEV_OY) * draw_scale + PDF_ELEV_OY
            x1 = (dim["end"][0] - GE_ELEV_OX) * draw_scale + PDF_ELEV_OX
            y1 = (dim["end"][1] - GE_ELEV_OY) * draw_scale + PDF_ELEV_OY
            text_str = dim["text"]
            c.saveState()
            c.setStrokeColor(PENCIL_MEDIUM)
            c.setLineWidth(0.5)
            c.line(x0, y0, x1, y1)
            c.line(x0 - 3, y0, x0 + 3, y0)
            c.line(x1 - 3, y1, x1 + 3, y1)
            c.setFont(_FONT_REG, 5.0)
            c.setFillColor(PENCIL_MEDIUM)
            c.drawCentredString((x0 + x1) / 2, (y0 + y1) / 2 + 4, text_str)
            c.restoreState()

        # --- Draw Side View (Section) ---
        for line in geom_data.get("side", {}).get("lines", []):
            x0 = (line["start"][0] - GE_SIDE_OX) * draw_scale + PDF_SIDE_OX
            y0 = (line["start"][1] - GE_SIDE_OY) * draw_scale + PDF_SIDE_OY
            x1 = (line["end"][0] - GE_SIDE_OX) * draw_scale + PDF_SIDE_OX
            y1 = (line["end"][1] - GE_SIDE_OY) * draw_scale + PDF_SIDE_OY
            c.saveState()
            c.setStrokeColor(NAVY if line.get("layer") in ("GROUND", "CEILING", "WALLS") else colors.black)
            c.setLineWidth(1.0 if line.get("layer") in ("GROUND", "CEILING", "WALLS") else 0.5)
            if line.get("style") == "dashed":
                c.setDash([2, 2])
            c.line(x0, y0, x1, y1)
            c.restoreState()
            
        for block in geom_data.get("side", {}).get("blocks", []):
            x, y, w, h = block["coords"]
            x_new = (x - GE_SIDE_OX) * draw_scale + PDF_SIDE_OX
            y_new = (y - GE_SIDE_OY) * draw_scale + PDF_SIDE_OY
            w_new = w * draw_scale
            h_new = h * draw_scale
            c.saveState()
            c.setStrokeColor(colors.black)
            c.setFillColor(colors.white)
            if block.get("style") == "dashed":
                c.setDash([2, 2])
            c.rect(x_new, y_new, w_new, h_new, fill=1, stroke=1)
            c.restoreState()
            
        for txt in geom_data.get("side", {}).get("texts", []):
            pos_x = (txt["pos"][0] - GE_SIDE_OX) * draw_scale + PDF_SIDE_OX
            pos_y = (txt["pos"][1] - GE_SIDE_OY) * draw_scale + PDF_SIDE_OY
            text_str = txt["text"]
            c.saveState()
            c.setFont(_FONT_REG, max(4.0, txt.get("size", 5.0) * draw_scale))
            c.setFillColor(colors.black)
            lines = text_str.split('\n')
            for i, line_text in enumerate(lines):
                c.drawCentredString(pos_x, pos_y - i * (max(4.0, txt.get("size", 5.0) * draw_scale) + 1), line_text)
            c.restoreState()
            
        for dim in geom_data.get("side", {}).get("dimensions", []):
            x0 = (dim["start"][0] - GE_SIDE_OX) * draw_scale + PDF_SIDE_OX
            y0 = (dim["start"][1] - GE_SIDE_OY) * draw_scale + PDF_SIDE_OY
            x1 = (dim["end"][0] - GE_SIDE_OX) * draw_scale + PDF_SIDE_OX
            y1 = (dim["end"][1] - GE_SIDE_OY) * draw_scale + PDF_SIDE_OY
            text_str = dim["text"]
            c.saveState()
            c.setStrokeColor(PENCIL_MEDIUM)
            c.setLineWidth(0.5)
            c.line(x0, y0, x1, y1)
            if abs(x0 - x1) < 0.1: # Vertical dimension
                c.line(x0 - 3, y0, x0 + 3, y0)
                c.line(x1 - 3, y1, x1 + 3, y1)
                c.setFont(_FONT_REG, 4.5)
                c.setFillColor(PENCIL_MEDIUM)
                c.drawRightString(x0 - 4, (y0 + y1) / 2 - 1.5, text_str)
            else: # Horizontal dimension
                c.line(x0, y0 - 3, x0, y0 + 3)
                c.line(x1, y1 - 3, x1, y1 + 3)
                c.setFont(_FONT_REG, 4.5)
                c.setFillColor(PENCIL_MEDIUM)
                c.drawCentredString((x0 + x1) / 2, (y0 + y1) / 2 + 4, text_str)
            c.restoreState()
            
        # Draw labels
        c.saveState()
        c.setFont(_FONT_BOLD, 8)
        c.setFillColor(NAVY)
        plan_w = wall_length_inches * 4.0 * draw_scale
        c.drawCentredString(PDF_PLAN_OX + plan_w / 2, PDF_PLAN_OY - 35, "COUNTERTOP PLAN VIEW")
        c.drawCentredString(PDF_ELEV_OX + plan_w / 2, PDF_ELEV_OY - 20, "FRONT ELEVATION VIEW")
        c.drawCentredString(PDF_SIDE_OX + 30.0 * 4.0 * draw_scale / 2, PDF_SIDE_OY - 20, "SIDE SECTION VIEW")
        c.restoreState()

    # --- Draw Cabinet Schedule Table on the Right ---
    c.setFont(_FONT_REG, 8)
    c.setFillColor(colors.black)
    labels = [
        ("PROJECT:", config.get("project_name", "")),
        ("ADDRESS:", config.get("address", "")),
        ("FINISH:", f"Standard {config.get('finish_tier', 1)}"),
        ("ADA:", "YES (Fully Accessible)" if is_ada else "NO (FHA Type B)"),
    ]
    y = DA_T - 30
    for label, val in labels:
        c.setFont(_FONT_BOLD, 7)
        c.drawString(490.0, y, label)
        c.setFont(_FONT_REG, 7)
        c.drawString(550.0, y, val)
        y -= 10

    col_widths = [25, 60, 180, 70, 40, 40, 40, 30, 60, 110]
    headers    = ["#", "Code", "Description", "Type",
                  "W(in)", "H(in)", "D(in)", "Qty", "Elev.", "Location"]
    table_x = 490.0
    table_y = y - 8

    # Header row
    c.setFillColor(LTGRAY)
    c.rect(table_x, table_y - 12, sum(col_widths), 12, fill=1, stroke=0)
    c.setFillColor(NAVY)
    c.setFont(_FONT_BOLD, 6.5)
    x_pos = table_x
    for w, h in zip(col_widths, headers):
        c.drawCentredString(x_pos + w / 2, table_y - 8, h)
        x_pos += w

    if not schedule:
        c.setFillColor(colors.black)
        c.setFont(_FONT_REG, 8)
        c.drawString(table_x + 4, table_y - 28, "No AI schedule available — PDF not processed")
        return

    all_cabs = schedule.all_cabinets
    kitchen_cabs = [cab for cab in all_cabs
                    if cab.cabinet_type not in ("vanity", "medicine_cabinet", "linen", "appliance_space")]
    bath_cabs    = [cab for cab in all_cabs
                    if cab.cabinet_type in ("vanity", "medicine_cabinet", "linen")]

    row_y = table_y - 12

    def draw_section(label, cabs, start_y):
        y = start_y
        y -= 14
        c.setFillColor(LTGRAY)
        c.rect(table_x, y, sum(col_widths), 11, fill=1, stroke=0)
        c.setFillColor(NAVY)
        c.setFont(_FONT_BOLD, 7)
        c.drawString(table_x + 3, y + 3, label)

        alt = False
        item_count = 0
        qty_total  = 0

        for item_num, cab in enumerate(cabs, 1):
            y -= 12
            if y < MARGIN + 20:
                break

            if alt:
                c.setFillColor(LTGRAY)
                c.rect(table_x, y, sum(col_widths), 12, fill=1, stroke=0)
            alt = not alt

            w_in = round(cab.width_mm / 25.4, 1)
            h_in = round(cab.height_mm / 25.4, 1)
            d_in = round(cab.depth_mm  / 25.4, 1)
            vals = [
                str(item_num),
                cab.code,
                f"{cab.cabinet_type.replace('_', ' ').title()} {w_in}\"W",
                cab.cabinet_type.replace("_", " ").title()[:12],
                f"{w_in}\"",
                f"{h_in}\"",
                f"{d_in}\"",
                str(cab.quantity),
                (cab.elevation_ref or "")[:8],
                (cab.location or "")[:18],
            ]
            c.setFillColor(colors.black)
            x_pos = table_x
            for i, (w, v) in enumerate(zip(col_widths, vals)):
                c.setFont(_FONT_BOLD if i == 1 else _FONT_REG, 6)
                if i in (4, 5, 6, 7):
                    c.drawCentredString(x_pos + w / 2, y + 3, v)
                else:
                    c.drawString(x_pos + 2, y + 3, v)
                x_pos += w

            # Row divider
            c.setStrokeColor(colors.lightgrey)
            c.setLineWidth(0.2)
            c.line(table_x, y, table_x + sum(col_widths), y)

            item_count += 1
            qty_total  += cab.quantity

        # Subtotal row
        y -= 12
        c.setFillColor(LTGRAY)
        c.rect(table_x, y, sum(col_widths), 12, fill=1, stroke=0)
        c.setFillColor(NAVY)
        c.setFont(_FONT_BOLD, 7)
        c.drawString(table_x + 3, y + 3, f"{label} SUBTOTAL")
        c.drawRightString(table_x + sum(col_widths[:8]), y + 3, str(qty_total))
        return y

    row_y = draw_section("SECTION 1 — KITCHEN CABINETS", kitchen_cabs, row_y)
    if row_y and row_y > MARGIN + 60:
        row_y = draw_section("SECTION 2 — BATHROOM CABINETS", bath_cabs, row_y - 4)

    # Table border
    c.setStrokeColor(NAVY)
    c.setLineWidth(0.75)
    c.rect(table_x, row_y if row_y else MARGIN + 20, sum(col_widths),
           table_y - (row_y if row_y else MARGIN + 20), fill=0, stroke=1)


# ══════════════════════════════════════════════════════════════════════════
# MAIN ENTRY POINT
# ══════════════════════════════════════════════════════════════════════════

def generate_shop_drawings(
    config:         dict,
    unit_schedules: dict,   # {unit_type: UnitSchedule}
    unit_totals:    dict,   # {unit_type: count}
    output_path:    str | Path,
) -> Path:
    """
    Generate the complete shop drawing PDF.

    Args:
        config:         project_config.json dict
        unit_schedules: {unit_type: UnitSchedule} from pipeline
        unit_totals:    {unit_type: count} unit quantities
        output_path:    where to save the PDF
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Calculate total pages: cover + matrix + one per unit type
    total_pages = 2 + len(unit_totals)

    c = canvas.Canvas(str(output_path), pagesize=(PAGE_W, PAGE_H))
    c.setTitle(f"Cabinet Shop Drawings — {config.get('project_name', 'Project')}")
    c.setAuthor("Italian Kitchen and Bath — AI Estimation System")

    # Page 1: Cover
    _draw_cover(c, config, unit_totals, total_pages)
    c.showPage()

    # Page 2: Matrix
    _draw_matrix_page(c, config, unit_schedules, unit_totals, total_pages)
    c.showPage()

    # Pages 3+: Unit schedules
    for page_num, unit_type in enumerate(unit_totals.keys(), 3):
        schedule = unit_schedules.get(unit_type)
        _draw_unit_page(c, config, unit_type, schedule, page_num, total_pages)
        c.showPage()

    c.save()
    print(f"  [SUCCESS] Shop drawing PDF saved: {output_path}  ({total_pages} pages)")
    return output_path


# ══════════════════════════════════════════════════════════════════════════
# CLI TEST
# ══════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

    config = {
        "project_id":   "TEST-001",
        "project_name": "TEST PROJECT",
        "project_no":   "23-999",
        "date":         "06/18/2024",
        "revision":     "1.0",
        "drawn_by":     "A.C",
        "owner":        "Test Owner",
        "address":      "123 Test Street, Miami, FL 33126",
        "finish":       "Standard 1",
        "finish_tier":  1,
        "door_style":   "Shaker",
        "general_notes": [
            "ALL CABINETS 90CM DEPTH STANDARD",
            "SOFT CLOSE DOORS & DRAWERS STANDARD",
            "ADA UNITS: COUNTERTOP MAX 34\"",
        ],
        "company": {
            "name":    "ITALIAN KITCHEN AND BATH",
            "tagline": "kitchen | bath | tile | closet",
            "address": "1777 NW 72TH AVE. MIAMI FL, 33126",
            "phone":   "T. 305.599.9000  F. 305.599.9870",
        },
    }

    unit_totals = {"A1": 14, "B1": 6}

    out = Path("outputs/TEST-001/TEST_Shop_Drawings.pdf")
    generate_shop_drawings(config, {}, unit_totals, out)
    print(f"Test complete: {out}")
