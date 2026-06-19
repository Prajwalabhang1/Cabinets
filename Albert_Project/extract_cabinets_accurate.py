"""
===========================================================================
  ACCURATE Cabinet Extractor for Casa Familia
===========================================================================
  This script uses EXACT crop coordinates derived from deep PDF inspection
  to extract ONLY the correct elevation zones (not 24 random regions).
  
  Each unit plan PDF is ONE large page containing:
    - Kitchen Floor Plan (top section)
    - Kitchen Elevation A (bottom-left)  
    - Kitchen Elevation B (bottom-right)
    - Bathroom/Vanity Elevation (bottom section)
  
  We crop EXACTLY these zones and send to Groq Vision.
===========================================================================
"""
import fitz
import base64
import json
import time
import os
from pathlib import Path
from dotenv import load_dotenv
from groq import Groq

load_dotenv()

GROQ_CLIENT = Groq(api_key=os.getenv("GROQ_API_KEY"))
GROQ_MODEL = "meta-llama/llama-4-scout-17b-16e-instruct"

# ── EXACT crop zones per unit (in PDF points) ──────────────────────────────
UNIT_CROP_ZONES = {
    # Verified from visual inspection of Unit A1 PDF (A-6.00)
    # Page: 2592 x 1728 pts | Scale: 1/2"=1'-0"
    # Kitchen EL.1: Full-width elevation (DW, SINK, RANGE, MICROWAVE, upper cabs)
    # Kitchen EL.2: Corner/perpendicular elevation (REF., P.)
    "A1": {
        "kitchen_elevation_1": (1150, 870, 1840, 1160),   # Main kitchen elevation (DW,SINK,RANGE,MICROWAVE)
        "kitchen_elevation_2": (1230, 1230, 1700, 1530),  # Corner elevation (REF., Pantry)
    },
    "A2-ADA": {
        "kitchen_elevation_1": (1150, 870, 1840, 1160),
        "kitchen_elevation_2": (1230, 1230, 1700, 1530),
    },
    "A3": {
        "kitchen_elevation_1": (1150, 870, 1840, 1160),
        "kitchen_elevation_2": (1230, 1230, 1700, 1530),
    },
    "B1": {
        "kitchen_elevation_1": (1150, 870, 1840, 1160),
        "kitchen_elevation_2": (1230, 1230, 1700, 1530),
    },
    "B2-ADA": {
        "kitchen_elevation_1": (1150, 870, 1840, 1160),
        "kitchen_elevation_2": (1230, 1230, 1700, 1530),
    },
}

UNIT_PDFS = {
    "A1":     "Casa familia/01_Architectural_Drawings/Unit_Plans_FHA_ADA/A-6.00-FHA-UNIT-A1-FLOOR-PLAN-&-DETAILS-Rev.10.pdf",
    "A2-ADA": "Casa familia/01_Architectural_Drawings/Unit_Plans_FHA_ADA/A-6.01-ADA-UNIT-A2-FULLY-ACCESSIBLE-FLOOR-PLAN-&-DETAILS-Rev.10.pdf",
    "A3":     "Casa familia/01_Architectural_Drawings/Unit_Plans_FHA_ADA/A-6.02-FHA-UNIT-A3-FLOOR-PLAN-&-DETAILS-Rev.10.pdf",
    "B1":     "Casa familia/01_Architectural_Drawings/Unit_Plans_FHA_ADA/A-6.03-FHA-UNIT-B1-FLOOR-PLAN-&-DETAILS-Rev.10.pdf",
    "B2-ADA": "Casa familia/01_Architectural_Drawings/Unit_Plans_FHA_ADA/A-6.04-ADA-UNIT-B2-FULLY-ACCESSIBLE-FLOOR-PLAN-&-DETAILS-Rev.10.pdf",
}

SYSTEM_PROMPT = """You are an expert cabinet estimator reading kitchen and bathroom elevation drawings for US residential housing.

Your task: identify EVERY cabinet in this elevation drawing and return a JSON array.

CABINET TYPES:
- upper_wall: Wall cabinet above countertop
- base: Standard base cabinet  
- sink_base: Base cabinet under sink
- dw_adjacent: Base cabinet next to dishwasher
- microwave_shelf: Upper cabinet housing microwave
- pantry: Tall pantry cabinet (floor to ceiling)
- corner_upper: Corner wall cabinet
- corner_base: Corner base cabinet
- vanity: Bathroom vanity cabinet
- medicine_cabinet: Bathroom medicine cabinet/mirror
- linen: Linen closet cabinet
- appliance_space: Space for appliance (no cabinet) - include DW, fridge, range

RULES:
1. Count EVERY cabinet visible, left to right
2. Use dimensions shown in the drawing (inches or feet-inches)
3. Convert all widths to mm (1 inch = 25.4mm)
4. Mark appliances as appliance_space with name in notes
5. Return ONLY valid JSON array, no other text

OUTPUT FORMAT:
[
  {"item_num": 1, "cabinet_type": "upper_wall", "width_mm": 762, "height_mm": 720, "depth_mm": 330, 
   "location": "left of range", "elevation_ref": "ELEVATION A", "confidence": 0.90, 
   "quantity": 1, "is_ada": false, "notes": ""}
]"""


def crop_zone(pdf_path: str, x0: float, y0: float, x1: float, y1: float, dpi: int = 200) -> bytes:
    """Crop a specific zone from page 0 of a PDF and return PNG bytes."""
    doc = fitz.open(pdf_path)
    page = doc[0]
    clip = fitz.Rect(x0, y0, x1, y1)
    mat = fitz.Matrix(dpi / 72, dpi / 72)
    pix = page.get_pixmap(matrix=mat, clip=clip)
    png_bytes = pix.tobytes("png")
    doc.close()
    return png_bytes


def ask_groq_vision(image_bytes: bytes, zone_name: str, unit_type: str, is_ada: bool) -> list:
    """Send image to Groq Vision and get cabinet schedule. Auto-waits on rate limits."""
    ada_note = " (ADA ACCESSIBLE UNIT - countertop max 34\", base height max 864mm)" if is_ada else ""
    prompt = f"Unit Type: {unit_type}{ada_note}\nZone: {zone_name}\n\nIdentify all cabinets in this elevation drawing. Return ONLY the JSON array."

    b64 = base64.standard_b64encode(image_bytes).decode("utf-8")

    for attempt in range(6):  # more retries to handle rate-limit waits
        try:
            resp = GROQ_CLIENT.chat.completions.create(
                model=GROQ_MODEL,
                max_tokens=3000,
                temperature=0.1,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": [
                        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
                        {"type": "text", "text": prompt}
                    ]}
                ]
            )
            raw = resp.choices[0].message.content
            # Parse JSON
            import re
            raw = re.sub(r'^```(?:json)?\s*', '', raw.strip(), flags=re.MULTILINE)
            raw = re.sub(r'\s*```\s*$', '', raw.strip(), flags=re.MULTILINE)
            start, end = raw.find('['), raw.rfind(']')
            if start != -1 and end != -1:
                data = json.loads(raw[start:end+1])
                return data if isinstance(data, list) else []
            return []

        except Exception as e:
            err_str = str(e)
            # Handle rate limit — parse wait time from error message
            if '429' in err_str or 'rate_limit' in err_str.lower():
                import re as _re
                # Try to find "Please try again in Xs" or "Xm Ys"
                m = _re.search(r'try again in (\d+)m(\d+)', err_str)
                if m:
                    wait_secs = int(m.group(1)) * 60 + int(float(m.group(2))) + 5
                else:
                    m2 = _re.search(r'try again in (\d+\.?\d*)', err_str)
                    wait_secs = int(float(m2.group(1))) + 5 if m2 else 30
                print(f"    [RATE LIMIT] Waiting {wait_secs}s for quota to reset...")
                time.sleep(wait_secs)
            else:
                print(f"    [WARN] Attempt {attempt+1}/6 failed: {e}")
                if attempt < 5:
                    time.sleep(2 ** min(attempt, 3))
                else:
                    print("    [FAIL] All retries exhausted.")
    return []



def extract_all_units(output_dir: str = "outputs/23-033", save_images: bool = True):
    """Extract cabinet schedules for all 5 unit types."""
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    crops_dir = Path(output_dir) / "crops_v2"
    crops_dir.mkdir(exist_ok=True)
    json_dir = Path(output_dir) / "json_v2"
    json_dir.mkdir(exist_ok=True)

    all_results = {}

    for unit_type, pdf_rel in UNIT_PDFS.items():
        print(f"\n{'='*55}")
        print(f"  UNIT: {unit_type}")
        print(f"{'='*55}")
        
        pdf_path = str(Path(pdf_rel))
        if not Path(pdf_path).exists():
            print(f"  [ERROR] PDF not found: {pdf_path}")
            continue

        is_ada = "ADA" in unit_type
        zones = UNIT_CROP_ZONES[unit_type]
        unit_schedule = {"unit_type": unit_type, "is_ada": is_ada, "elevations": []}

        for zone_name, (x0, y0, x1, y1) in zones.items():
            if zone_name == "kitchen_plan":
                # Skip the floor plan — we only want elevations
                continue

            print(f"\n  Zone: {zone_name}")
            print(f"  Crop: ({x0},{y0}) → ({x1},{y1})")

            # Crop the image
            img_bytes = crop_zone(pdf_path, x0, y0, x1, y1, dpi=200)
            print(f"  Image: {len(img_bytes):,} bytes")

            # Save crop image
            if save_images:
                img_path = crops_dir / f"{unit_type}_{zone_name}.png"
                img_path.write_bytes(img_bytes)

            # Call Groq Vision
            print(f"  → Calling Groq Vision...")
            cabinets = ask_groq_vision(img_bytes, zone_name, unit_type, is_ada)
            
            real_cabs = [c for c in cabinets if c.get("cabinet_type") != "appliance_space"]
            appl_cabs = [c for c in cabinets if c.get("cabinet_type") == "appliance_space"]
            
            print(f"  ✓ Found: {len(real_cabs)} cabinets, {len(appl_cabs)} appliance spaces")
            for c in cabinets:
                w = c.get("width_mm", 0)
                w_in = round(w / 25.4)
                marker = "[APPL]" if c.get("cabinet_type") == "appliance_space" else "      "
                print(f"      {marker} {c.get('item_num',0):2d}. {c.get('cabinet_type','?'):20s}  "
                      f"{w:.0f}mm ({w_in}\")  conf={c.get('confidence',0):.0%}")

            unit_schedule["elevations"].append({
                "elevation_label": zone_name,
                "cabinets": cabinets,
                "cabinet_count": len(real_cabs),
                "appliance_count": len(appl_cabs),
            })

        # Save JSON
        json_path = json_dir / f"cabinet_schedule_{unit_type}.json"
        json_path.write_text(json.dumps(unit_schedule, indent=2, ensure_ascii=False))
        all_results[unit_type] = unit_schedule

        total = sum(e["cabinet_count"] for e in unit_schedule["elevations"])
        print(f"\n  ━━ UNIT {unit_type} TOTAL: {total} cabinets ━━")

    # Final summary
    print(f"\n{'='*55}")
    print("  EXTRACTION COMPLETE — SUMMARY")
    print(f"{'='*55}")
    for unit_type, sched in all_results.items():
        total = sum(e["cabinet_count"] for e in sched["elevations"])
        print(f"  {unit_type:10s}: {total:3d} cabinets")

    # Save combined results
    combined_path = Path(output_dir) / "json_v2" / "_all_units.json"
    combined_path.write_text(json.dumps(all_results, indent=2, ensure_ascii=False))
    print(f"\n  Saved: {combined_path}")
    return all_results


if __name__ == "__main__":
    results = extract_all_units()
