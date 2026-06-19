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
NAVY = colors.Color(0.106, 0.212, 0.365)   # #1B365D
WHITE = colors.white
LTGRAY = colors.Color(0.95, 0.95, 0.95)
LTBLUE = colors.Color(0.85, 0.89, 0.95)


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

    # Title block background
    c.setFillColor(NAVY)
    c.rect(TB_X, 0, TB_W, PAGE_H, fill=1, stroke=0)

    # Rotate to draw vertical text
    c.translate(TB_X + TB_W / 2, PAGE_H / 2)
    c.rotate(90)

    # Company name
    company = config.get("company", {})
    c.setFillColor(WHITE)
    c.setFont(_FONT_BOLD, 8)
    c.drawCentredString(0, 28, company.get("name", "ITALIAN KITCHEN AND BATH"))

    c.setFont(_FONT_REG, 5)
    c.drawCentredString(0, 20, company.get("tagline", "kitchen | bath | tile | closet"))

    # Divider
    c.setStrokeColor(WHITE)
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
    """Draw a navy-background section header bar."""
    c.setFillColor(NAVY)
    c.rect(DA_L, y - 12, DA_R - DA_L, 14, fill=1, stroke=0)
    c.setFillColor(WHITE)
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
    c.setFillColor(NAVY)
    c.rect(0, PAGE_H * 0.55, TB_X, PAGE_H * 0.45, fill=1, stroke=0)

    # Company logo / name area
    c.setFillColor(WHITE)
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
    c.setFillColor(NAVY)
    c.rect(table_x, table_y - 14, sum(col_widths), 14, fill=1, stroke=0)
    c.setFillColor(WHITE)
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
    c.drawString(DA_L + 4, DA_T - 18, f"UNIT {unit_type} — CABINET SCHEDULE")

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
        c.drawString(DA_L + 4, y, label)
        c.setFont(_FONT_REG, 7)
        c.drawString(DA_L + 55, y, val)
        y -= 10

    # Cabinet table
    col_widths = [25, 60, 180, 70, 40, 40, 40, 30, 60, 110]
    headers    = ["#", "Code", "Description", "Type",
                  "W(in)", "H(in)", "D(in)", "Qty", "Elev.", "Location"]
    table_x = DA_L + 4
    table_y = y - 8

    # Header row
    c.setFillColor(NAVY)
    c.rect(table_x, table_y - 12, sum(col_widths), 12, fill=1, stroke=0)
    c.setFillColor(WHITE)
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
        # Section label
        y -= 14
        c.setFillColor(LTBLUE)
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
                break  # Don't overflow page

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
