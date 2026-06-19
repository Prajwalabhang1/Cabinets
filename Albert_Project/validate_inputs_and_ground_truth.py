"""
Deep validation: Extract cabinet schedules from the REAL shop drawing PDFs
and compare against what our pipeline produces.

This tells us the accuracy gap.
"""
import fitz
import re
import json
from pathlib import Path

# ── Extract all dimensions and cabinet data from the REAL shop drawing ─────

def extract_real_schedule(pdf_path: str, project_name: str):
    """Extract every measurement and cabinet label from the real shop drawing PDF."""
    pdf = fitz.open(pdf_path)
    print(f"\n{'='*65}")
    print(f"  EXTRACTING GROUND TRUTH FROM: {project_name}")
    print(f"  Pages: {pdf.page_count}")
    print(f"{'='*65}")

    all_dims_metric  = []
    all_dims_imperial = []
    unit_pages = {}

    current_unit = "UNKNOWN"

    for pg in range(pdf.page_count):
        page = pdf[pg]
        blocks = page.get_text("blocks")
        full_text = ""
        for b in blocks:
            full_text += b[4].strip() + "\n"

        # Detect which unit this page is about
        unit_match = re.search(r'(?:UNIT\s+)?([A-D](?:-\d+[A-Za-z]*)?|ST-\d+[A-Za-z]*)\s*(?:TYP|FHA|ADA|ACC)?', full_text, re.IGNORECASE)
        page_title = ""
        for b in blocks[:5]:
            t = b[4].strip().replace('\n', ' ')
            if len(t) > 5:
                page_title += t[:60] + " | "

        # Find all metric dimensions (e.g. "76.20", "90.00", "152.40")
        metric_dims = re.findall(r'\b(\d{2,4}\.\d{1,2})\b', full_text)
        metric_dims = [float(d) for d in metric_dims if 50.0 <= float(d) <= 4000.0]

        # Find all imperial dimensions (e.g. [2'-6"], [3'-0"], [5'-0"])
        imperial_dims = re.findall(r"\[(\d+)'[\s-]*(\d+)(?:\s+\d+/\d+)?\"?\]|\[(\d+)'\]", full_text)

        # Convert to mm
        imperial_mm = []
        for m in imperial_dims:
            if m[0] and m[1]:
                mm = (int(m[0]) * 12 + int(m[1])) * 25.4
                imperial_mm.append(round(mm, 1))
            elif m[2]:
                mm = int(m[2]) * 12 * 25.4
                imperial_mm.append(round(mm, 1))

        print(f"\n  Page {pg+1:2d}: {page_title[:80]}")
        if metric_dims:
            print(f"    Metric dims (mm×10): {sorted(set(metric_dims))[:15]}")
            print(f"    → In mm: {sorted(set([d*10 for d in metric_dims]))[:15]}")
        if imperial_mm:
            print(f"    Imperial dims (mm): {sorted(set(imperial_mm))[:15]}")

        all_dims_metric.extend(metric_dims)
        all_dims_imperial.extend(imperial_mm)

    pdf.close()

    # Convert metric (the PDF stores in cm, ×10 gives mm)
    unique_metric_mm = sorted(set([d*10 for d in all_dims_metric if 150 <= d*10 <= 2500]))
    unique_imperial_mm = sorted(set([d for d in all_dims_imperial if 150 <= d <= 2500]))

    print(f"\n  SUMMARY — Unique Cabinet-Range Dimensions Found:")
    print(f"    Metric (×10 for mm):   {unique_metric_mm}")
    print(f"    Imperial (converted):  {unique_imperial_mm}")

    return unique_metric_mm, unique_imperial_mm


# ── Check: Do we have ALL required input files? ─────────────────────────────

def check_inputs(project_name: str, unit_pdfs: list, floor_pdfs: list, price_list: str):
    print(f"\n{'='*65}")
    print(f"  INPUT FILE CHECK: {project_name}")
    print(f"{'='*65}")

    all_ok = True

    print(f"\n  Unit Plan PDFs ({len(unit_pdfs)} expected):")
    for path in unit_pdfs:
        exists = Path(path).exists()
        size = f"{Path(path).stat().st_size/1024:.0f} KB" if exists else "MISSING"
        mark = "[OK]" if exists else "[MISSING]"
        print(f"    {mark} {Path(path).name:<70} {size}")
        if not exists:
            all_ok = False

    print(f"\n  Floor Plan PDFs ({len(floor_pdfs)} expected):")
    for path in floor_pdfs:
        exists = Path(path).exists()
        size = f"{Path(path).stat().st_size/1024:.0f} KB" if exists else "MISSING"
        mark = "[OK]" if exists else "[MISSING]"
        print(f"    {mark} {Path(path).name:<70} {size}")
        if not exists:
            all_ok = False

    print(f"\n  Price List:")
    exists = Path(price_list).exists()
    size = f"{Path(price_list).stat().st_size/1024:.0f} KB" if exists else "MISSING"
    mark = "[OK]" if exists else "[MISSING]"
    print(f"    {mark} {Path(price_list).name} {size}")
    if not exists:
        all_ok = False

    print(f"\n  Status: {'ALL INPUTS PRESENT' if all_ok else 'SOME INPUTS MISSING'}")
    return all_ok


# ══════════════════════════════════════════════════════════════════════════
# CASA FAMILIA INPUT CHECK
# ══════════════════════════════════════════════════════════════════════════

cf_units = [
    r"Casa familia\01_Architectural_Drawings\Unit_Plans_FHA_ADA\A-6.00-FHA-UNIT-A1-FLOOR-PLAN-&-DETAILS-Rev.10.pdf",
    r"Casa familia\01_Architectural_Drawings\Unit_Plans_FHA_ADA\A-6.00A-FHA-UNIT-A1-FLOOR-PLAN-&-DETAILS-Rev.10.pdf",
    r"Casa familia\01_Architectural_Drawings\Unit_Plans_FHA_ADA\A-6.01-ADA-UNIT-A2-FULLY-ACCESSIBLE-FLOOR-PLAN-&-DETAILS-Rev.10.pdf",
    r"Casa familia\01_Architectural_Drawings\Unit_Plans_FHA_ADA\A-6.02-FHA-UNIT-A3-FLOOR-PLAN-&-DETAILS-Rev.10.pdf",
    r"Casa familia\01_Architectural_Drawings\Unit_Plans_FHA_ADA\A-6.03-FHA-UNIT-B1-FLOOR-PLAN-&-DETAILS-Rev.10.pdf",
    r"Casa familia\01_Architectural_Drawings\Unit_Plans_FHA_ADA\A-6.04-ADA-UNIT-B2-FULLY-ACCESSIBLE-FLOOR-PLAN-&-DETAILS-Rev.10.pdf",
]
cf_floors = [
    r"Casa familia\01_Architectural_Drawings\Floor_Plans\A-2.00-BLDG-A---GROUND-FLOOR-PLAN-Rev.10.pdf",
    r"Casa familia\01_Architectural_Drawings\Floor_Plans\A-2.01-BLDG-A---2ND-FLOOR-PLAN-Rev.10.pdf",
    r"Casa familia\01_Architectural_Drawings\Floor_Plans\A-2.02-BLDG-A---3RD-FLOOR-PLAN-Rev.10.pdf",
]
cf_price = r"Casa familia\02_Price_List\MS PRICE LIST LEVEL 1 -90CM.xlsx"
cf_real_output = r"Casa familia\03_Shop_Drawings\ITALIANKB SHOP DRAWINGS - 23-033 CASA FAMILIA - 03.04.2025 hatch corregido.pdf"

check_inputs("CASA FAMILIA", cf_units, cf_floors, cf_price)

# ══════════════════════════════════════════════════════════════════════════
# HERITAGE VILLAGE INPUT CHECK
# ══════════════════════════════════════════════════════════════════════════

hv_units = [
    r"Heritage\01_Architectural_Drawings\Unit_Plans_FHA_ADA\A-6.00_ UNIT A-1 -FHA - FLOOR PLANS & DETAILS Rev.17 markup.pdf",
    r"Heritage\01_Architectural_Drawings\Unit_Plans_FHA_ADA\A-6.01_ UNIT A-1A ACC FLOOR PLANS & DETAILS Rev.17 markup.pdf",
    r"Heritage\01_Architectural_Drawings\Unit_Plans_FHA_ADA\A-6.02_ UNIT B-1 FLOOR PLANS & DETAILS Rev.17 markup.pdf",
    r"Heritage\01_Architectural_Drawings\Unit_Plans_FHA_ADA\A-6.03_ UNIT B-1A ACC FLOOR PLANS & DETAILS Rev.17 markup.pdf",
    r"Heritage\01_Architectural_Drawings\Unit_Plans_FHA_ADA\A-6.04_ UNIT C-1 - FHA FLOOR PLANS & DETAILS Rev.17 markup.pdf",
    r"Heritage\01_Architectural_Drawings\Unit_Plans_FHA_ADA\A-6.05 - UNIT C-2 - FHA - FLOOR PLANS & DETAILS.pdf",
    r"Heritage\01_Architectural_Drawings\Unit_Plans_FHA_ADA\A-6.06 - UNIT C-2a ACC- FLOOR PLANS & DETAILS-.pdf",
    r"Heritage\01_Architectural_Drawings\Unit_Plans_FHA_ADA\A-6.07_ UNIT C-3 FLOOR PLANS & DETAILS Rev.15 markup.pdf",
    r"Heritage\01_Architectural_Drawings\Unit_Plans_FHA_ADA\A-6.08A_ UNIT D-1N- FHA - FLOOR PLANS AND DETAILS Rev.15 markup.pdf",
    r"Heritage\01_Architectural_Drawings\Unit_Plans_FHA_ADA\A-6.08_ UNIT D-1 - FHA FLOOR PLANS & DETAILS Rev.17 markup.pdf",
    r"Heritage\01_Architectural_Drawings\Unit_Plans_FHA_ADA\A-6.09A_ UNIT D-1a ACC. FLOOR PLANS & DETAILS (CONTINUED) Rev.15 markup.pdf",
    r"Heritage\01_Architectural_Drawings\Unit_Plans_FHA_ADA\A-6.09_ UNIT D-1A ACC FLOOR PLANS AND DETAILS Rev.15 markup.pdf",
    r"Heritage\01_Architectural_Drawings\Unit_Plans_FHA_ADA\A-6.10_ UNIT ST-1A ACC FLOOR PLANS & DETAILS Rev.15 markup.pdf",
    r"Heritage\01_Architectural_Drawings\Unit_Plans_FHA_ADA\A-6.11_ UNIT ST-1 - FHA FLOOR PLANS & DETAILS Rev.15 markup.pdf",
]
hv_floors = [
    r"Heritage\01_Architectural_Drawings\Floor_Plans\A-2.00C - PARTIAL C- GROUND LEVEL FLOOR PLAN.pdf",
    r"Heritage\01_Architectural_Drawings\Floor_Plans\A-2.01C - PARTIAL C- 2ND LEVEL FLOOR PLAN.pdf",
    r"Heritage\01_Architectural_Drawings\Floor_Plans\A-2.02C - PARTIAL C- 3RD LEVEL FLOOR PLAN.pdf",
]
hv_price = r"Heritage\02_Price_List\MS PRICE LIST LEVEL 1 -90CM.xlsx"
hv_real_output = r"Heritage\03_Shop_Drawings\05_Cabinet_Estimation_Shop_Drawings_Heritage_Village.pdf"

check_inputs("HERITAGE VILLAGE", hv_units, hv_floors, hv_price)

# ══════════════════════════════════════════════════════════════════════════
# EXTRACT GROUND TRUTH FROM REAL OUTPUTS
# ══════════════════════════════════════════════════════════════════════════

print(f"\n\n{'#'*65}")
print("  GROUND TRUTH EXTRACTION FROM REAL SHOP DRAWINGS")
print(f"{'#'*65}")

cf_metric, cf_imperial = extract_real_schedule(cf_real_output, "CASA FAMILIA")
hv_metric, hv_imperial = extract_real_schedule(hv_real_output, "HERITAGE VILLAGE")

# Save ground truth
ground_truth = {
    "casa_familia": {
        "source": cf_real_output,
        "unique_cabinet_widths_mm_metric": cf_metric,
        "unique_cabinet_widths_mm_imperial": cf_imperial,
    },
    "heritage_village": {
        "source": hv_real_output,
        "unique_cabinet_widths_mm_metric": hv_metric,
        "unique_cabinet_widths_mm_imperial": hv_imperial,
    }
}

out = Path("outputs/ground_truth.json")
out.parent.mkdir(exist_ok=True)
out.write_text(json.dumps(ground_truth, indent=2))
print(f"\n\nGround truth saved to: {out}")
