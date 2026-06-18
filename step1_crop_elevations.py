#!/usr/bin/env python3
"""
===========================================================================
  STEP 1A + 1B — ELEVATION REGION CROPPER + CABINET SCHEDULE EXTRACTOR
===========================================================================
  What this does:
    1. Opens Unit A1 architectural PDF
    2. Maps ALL text with exact (x,y) coordinates
    3. Detects elevation / kitchen / bath section boundaries
    4. Crops each region at 400 DPI → saves as PNG
    5. For each region, extracts ALL text + rectangles inside it
    6. Outputs a structured JSON:  cabinet_schedule_A1.json
       → ready to send to Claude/GPT-4o for classification

  Output files:
    CROP_kitchen_region.png      ← full kitchen area
    CROP_bath_region.png         ← full bathroom area
    CROP_elevation_*.png         ← individual elevation sections
    cabinet_extraction_A1.json   ← all extracted data structured
===========================================================================
"""
import sys, json, re, os
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
import fitz

# ── Paths ─────────────────────────────────────────────────────────────────
BASE     = r"C:\Users\prajw\OneDrive\Desktop\Albert\Albert_Project"
PDF_PATH = os.path.join(BASE,
    "Casa familia", "01_Architectural_Drawings", "Unit_Plans_FHA_ADA",
    "A-6.00-FHA-UNIT-A1-FLOOR-PLAN-&-DETAILS-Rev.10.pdf")
OUT_DIR  = os.path.join(BASE, "EXTRACTION_OUTPUT")
os.makedirs(OUT_DIR, exist_ok=True)

SEP  = "=" * 70
DASH = "-" * 50

# ── Patterns we look for ──────────────────────────────────────────────────
ELEVATION_LABELS = ["ELEVATION A", "ELEVATION B", "ELEVATION C",
                    "ELEV. A", "ELEV. B", "ELEV A", "ELEV B",
                    "EL. A", "EL. B",]
KITCHEN_LABELS   = ["KITCHEN", "KITCHEN ELEVATION", "KIT."]
BATH_LABELS      = ["BATHROOM", "BATH", "MASTER BATH", "MASTER BEDROOM BATH",
                    "VANITY", "BATH 2", "BATH 1"]
CABINET_KEYWORDS = ["DISHWASHER", "D/W", "DW", "REFRIGERATOR", "REF.",
                    "MICROWAVE", "M/W", "RANGE", "OVEN", "SINK",
                    "UPPER", "LOWER", "BASE", "WALL CAB", "PANTRY",
                    "TALL", "COUNTERTOP", "COUNTER", "CABINET",
                    "W.I.C", "CLOSET", "LINEN"]
DIM_METRIC_RE   = re.compile(r'\b(\d{1,4}(?:\.\d{1,2})?)\b')
DIM_IMPERIAL_RE = re.compile(r"""(\d+)[''][\s-]*(\d+)?[\s]*(\d+/\d+)?["\"]?|(\d+-\d+/\d+["\"])""")


# ══════════════════════════════════════════════════════════════════════════
# STEP 1: FULL PAGE EXTRACTION
# ══════════════════════════════════════════════════════════════════════════
def full_extraction(pdf_path):
    print(f"\n{SEP}")
    print("  STEP 1 — Full Page Extraction")
    print(SEP)

    doc  = fitz.open(pdf_path)
    page = doc[0]

    # Page dimensions
    pw, ph = page.rect.width, page.rect.height
    print(f"  Page size : {pw:.0f} x {ph:.0f} pts  ({pw/72:.1f}\" x {ph/72:.1f}\")")

    # --- Extract ALL text spans with coordinates ---
    tdict      = page.get_text("dict", flags=fitz.TEXT_PRESERVE_WHITESPACE)
    all_spans  = []
    for block in tdict.get("blocks", []):
        if block.get("type") == 0:
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    text = span["text"].strip()
                    if text:
                        all_spans.append({
                            "text":   text,
                            "bbox":   list(span["bbox"]),
                            "origin": list(span["origin"]),
                            "size":   round(span["size"], 2),
                            "font":   span["font"],
                        })

    # --- Extract ALL vector drawings ---
    drawings = page.get_drawings()
    rects    = []
    for d in drawings:
        for item in d.get("items", []):
            if item[0] == "re":
                r = item[1]
                # Only keep rectangles with meaningful size (likely cabinet boxes)
                if r.width > 10 and r.height > 5:
                    rects.append({
                        "x0": round(r.x0, 2), "y0": round(r.y0, 2),
                        "x1": round(r.x1, 2), "y1": round(r.y1, 2),
                        "w":  round(r.width, 2), "h": round(r.height, 2),
                        "fill":   list(d.get("fill") or []),
                        "stroke": list(d.get("color") or []),
                    })

    print(f"  Text spans: {len(all_spans)}")
    print(f"  Rectangles: {len(rects)}")
    doc.close()
    return all_spans, rects, pw, ph


# ══════════════════════════════════════════════════════════════════════════
# STEP 2: DETECT REGIONS
# ══════════════════════════════════════════════════════════════════════════
def detect_regions(all_spans, pw, ph):
    print(f"\n{SEP}")
    print("  STEP 2 — Detect Elevation & Kitchen/Bath Regions")
    print(SEP)

    regions = []

    # Search all spans for matching labels
    for span in all_spans:
        t_up = span["text"].upper()
        x0, y0, x1, y1 = span["bbox"]

        # Check elevation labels
        for lbl in ELEVATION_LABELS:
            if lbl in t_up:
                regions.append({
                    "type":    "ELEVATION",
                    "label":   span["text"],
                    "bbox":    span["bbox"],
                    "origin":  span["origin"],
                    "size":    span["size"],
                })
                print(f"  ELEVATION  found: '{span['text']:30s}' @ ({x0:.0f}, {y0:.0f})")
                break

        # Check kitchen labels
        for lbl in KITCHEN_LABELS:
            if lbl in t_up:
                regions.append({
                    "type":    "KITCHEN",
                    "label":   span["text"],
                    "bbox":    span["bbox"],
                    "origin":  span["origin"],
                    "size":    span["size"],
                })
                print(f"  KITCHEN    found: '{span['text']:30s}' @ ({x0:.0f}, {y0:.0f})")
                break

        # Check bath labels
        for lbl in BATH_LABELS:
            if lbl in t_up:
                regions.append({
                    "type":    "BATH",
                    "label":   span["text"],
                    "bbox":    span["bbox"],
                    "origin":  span["origin"],
                    "size":    span["size"],
                })
                print(f"  BATH       found: '{span['text']:30s}' @ ({x0:.0f}, {y0:.0f})")
                break

    print(f"\n  Total keyword regions found: {len(regions)}")
    return regions


# ══════════════════════════════════════════════════════════════════════════
# STEP 3: BUILD CROP ZONES
# ══════════════════════════════════════════════════════════════════════════
def build_crop_zones(regions, all_spans, pw, ph):
    """
    Strategy:
    - Group label hits by their x-coordinate clusters
    - Each cluster = one section (elevation A, elevation B, etc.)
    - Crop zone = from label down to next section boundary
    """
    print(f"\n{SEP}")
    print("  STEP 3 — Building Crop Zones from Region Labels")
    print(SEP)

    # Sort all KITCHEN/ELEVATION/BATH labels by Y position (top to bottom)
    sorted_regions = sorted(regions, key=lambda r: r["origin"][1])

    # Also collect all CABINET keyword hits
    cab_hits = []
    for span in all_spans:
        t_up = span["text"].upper()
        for kw in CABINET_KEYWORDS:
            if kw in t_up:
                cab_hits.append({**span, "keyword": kw})
                break

    print(f"  Cabinet keyword hits: {len(cab_hits)}")
    for h in cab_hits[:20]:
        x0,y0,x1,y1 = h["bbox"]
        print(f"    [{h['keyword']:15s}] '{h['text'][:35]:35s}' @ ({x0:.0f}, {y0:.0f})")

    # Build simple crop zones: use page quadrants
    # Architectural drawings typically:
    #   - Floor plan: left/center area
    #   - Elevations: right side or bottom
    # We build zones around each detected label with generous padding

    crop_zones = []
    seen = set()

    for region in sorted_regions:
        key = region["type"] + "_" + region["label"][:10]
        if key in seen:
            continue
        seen.add(key)

        ox, oy = region["origin"]
        # Crop window: 600 pts wide, 400 pts tall centered on label
        x0_crop = max(0,  ox - 50)
        y0_crop = max(0,  oy - 80)
        x1_crop = min(pw, ox + 650)
        y1_crop = min(ph, oy + 450)

        crop_zones.append({
            "label":  region["label"],
            "type":   region["type"],
            "origin": region["origin"],
            "crop_rect": [x0_crop, y0_crop, x1_crop, y1_crop],
        })

    # Add large section crops: split page into quadrants
    # Q1 = top-left (floor plan), Q2 = top-right, Q3 = bottom-left, Q4 = bottom-right
    quadrants = [
        {"label": "TOP_LEFT",     "type": "QUADRANT", "crop_rect": [0,    0,    pw/2, ph/2]},
        {"label": "TOP_RIGHT",    "type": "QUADRANT", "crop_rect": [pw/2, 0,    pw,   ph/2]},
        {"label": "BOTTOM_LEFT",  "type": "QUADRANT", "crop_rect": [0,    ph/2, pw/2, ph  ]},
        {"label": "BOTTOM_RIGHT", "type": "QUADRANT", "crop_rect": [pw/2, ph/2, pw,   ph  ]},
        {"label": "FULL_PAGE",    "type": "FULL",     "crop_rect": [0,    0,    pw,   ph  ]},
    ]
    crop_zones.extend(quadrants)

    print(f"\n  Crop zones to export: {len(crop_zones)}")
    for z in crop_zones:
        r = z["crop_rect"]
        print(f"    [{z['type']:12s}] {z['label'][:30]:30s}  rect=({r[0]:.0f},{r[1]:.0f})->({r[2]:.0f},{r[3]:.0f})")

    return crop_zones, cab_hits


# ══════════════════════════════════════════════════════════════════════════
# STEP 4: CROP & SAVE PNGS AT 400 DPI
# ══════════════════════════════════════════════════════════════════════════
def crop_and_save(pdf_path, crop_zones, out_dir):
    print(f"\n{SEP}")
    print("  STEP 4 — Cropping Regions at 400 DPI")
    print(SEP)

    doc  = fitz.open(pdf_path)
    page = doc[0]
    DPI  = 400
    mat  = fitz.Matrix(DPI/72, DPI/72)

    saved = []
    for zone in crop_zones:
        r    = zone["crop_rect"]
        clip = fitz.Rect(r[0], r[1], r[2], r[3])

        # Render only the clipped region
        pix  = page.get_pixmap(matrix=mat, clip=clip, colorspace=fitz.csRGB)

        safe_label = re.sub(r'[^A-Za-z0-9_]', '_', zone["label"])[:40]
        fname      = f"CROP_{zone['type']}_{safe_label}.png"
        fpath      = os.path.join(out_dir, fname)
        pix.save(fpath)

        size_kb = os.path.getsize(fpath) // 1024
        print(f"  Saved: {fname:55s}  {pix.width}x{pix.height}px  {size_kb} KB")
        saved.append({**zone, "file": fpath, "filename": fname,
                      "px_w": pix.width, "px_h": pix.height})

    doc.close()
    print(f"\n  {len(saved)} crop images saved to: {out_dir}")
    return saved


# ══════════════════════════════════════════════════════════════════════════
# STEP 5: BUILD STRUCTURED JSON FOR AI
# ══════════════════════════════════════════════════════════════════════════
def build_structured_json(all_spans, rects, crop_zones, cab_hits, saved_crops):
    print(f"\n{SEP}")
    print("  STEP 5 — Building Structured JSON for AI Classification")
    print(SEP)

    # Classify each span
    dimension_spans = []
    label_spans     = []
    other_spans     = []

    for span in all_spans:
        t = span["text"]
        t_up = t.upper()

        # Is it a cabinet keyword?
        is_cab  = any(kw in t_up for kw in CABINET_KEYWORDS)
        # Is it a section label?
        is_lbl  = any(kw in t_up for kw in
                      ["ELEVATION", "KITCHEN", "BATH", "VANITY", "SCALE",
                       "FLOOR PLAN", "SECTION", "UNIT", "NOTE"])
        # Is it a metric dimension?
        is_metric = (DIM_METRIC_RE.search(t) and
                     ("." in t or len(re.findall(r'\d+', t)) >= 1) and
                     len(t) < 15)
        # Is it an imperial dimension?
        is_imp  = (("'" in t or '"' in t) and len(t) < 20)

        entry = {**span, "is_cabinet_kw": is_cab, "is_label": is_lbl,
                 "is_metric_dim": is_metric, "is_imperial_dim": is_imp}

        if is_cab or is_lbl:
            label_spans.append(entry)
        elif is_metric or is_imp:
            dimension_spans.append(entry)
        else:
            other_spans.append(entry)

    # Large rectangles are likely cabinet boxes (filter by size)
    cabinet_rects = [r for r in rects if r["w"] > 20 and r["h"] > 10]

    print(f"  Label / cabinet spans : {len(label_spans)}")
    print(f"  Dimension spans       : {len(dimension_spans)}")
    print(f"  Cabinet-sized rects   : {len(cabinet_rects)}")

    # Print label spans
    print(f"\n  --- All Label / Cabinet keyword spans ---")
    for s in label_spans:
        x0,y0 = s["bbox"][0], s["bbox"][1]
        print(f"    [{x0:7.1f}, {y0:7.1f}]  '{s['text'][:50]}'")

    # Print dimension spans sample
    print(f"\n  --- Sample Dimension spans (first 30) ---")
    for s in dimension_spans[:30]:
        x0,y0 = s["bbox"][0], s["bbox"][1]
        tag = "[METRIC]" if s["is_metric_dim"] else "[IMPERIAL]"
        print(f"    {tag:10s}  [{x0:7.1f}, {y0:7.1f}]  '{s['text']}'")

    # Build final JSON
    output = {
        "project":        "Casa Familia",
        "unit_type":      "A1 (1BR FHA)",
        "pdf_source":     os.path.basename(PDF_PATH),
        "extraction_summary": {
            "total_text_spans":   len(all_spans),
            "label_spans":        len(label_spans),
            "dimension_spans":    len(dimension_spans),
            "cabinet_rects":      len(cabinet_rects),
            "crop_images_saved":  len(saved_crops),
        },
        "label_spans":       label_spans,
        "dimension_spans":   dimension_spans,
        "cabinet_rects":     cabinet_rects[:200],   # top 200 by size
        "crop_images": [
            {"label": s["label"], "type": s["type"],
             "filename": s["filename"], "size_px": f"{s['px_w']}x{s['px_h']}"}
            for s in saved_crops
        ],
        "next_step": {
            "action":   "Send crop images + dimension_spans + cabinet_rects to Claude Vision",
            "prompt":   (
                "You are an expert cabinet estimator. "
                "I am showing you a section of an architectural elevation drawing. "
                "The pre-extracted text dimensions are provided. "
                "Identify every cabinet in this elevation: "
                "type (upper_wall/base/sink_base/dw_adjacent/pantry/vanity), "
                "width_mm, height_mm, depth_mm, location note, confidence score. "
                "Return a JSON array of cabinets."
            ),
            "images_to_send": [s["filename"] for s in saved_crops
                               if s["type"] in ("KITCHEN","BATH","ELEVATION","QUADRANT")],
        }
    }

    json_path = os.path.join(OUT_DIR, "cabinet_extraction_A1.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"\n  JSON saved: {json_path}")
    print(f"  JSON size : {os.path.getsize(json_path) // 1024} KB")
    return output


# ══════════════════════════════════════════════════════════════════════════
# STEP 6: PRINT WHAT TO SEND TO AI
# ══════════════════════════════════════════════════════════════════════════
def print_ai_ready_summary(output, out_dir):
    print(f"\n{SEP}")
    print("  STEP 6 — AI-Ready Summary")
    print(SEP)
    ns = output["next_step"]

    print(f"\n  WHAT TO SEND TO CLAUDE / GPT-4o:")
    print(f"  --------------------------------")
    print(f"\n  1. Images (one per elevation section):")
    for f in ns["images_to_send"]:
        fpath = os.path.join(out_dir, f)
        sz    = os.path.getsize(fpath) // 1024 if os.path.exists(fpath) else 0
        print(f"     - {f}  ({sz} KB)")

    print(f"\n  2. Prompt:")
    print(f"     \"{ns['prompt']}\"")

    print(f"\n  3. Pre-extracted dimensions to include in prompt:")
    dims = output["dimension_spans"][:20]
    for d in dims:
        tag = "METRIC" if d["is_metric_dim"] else "IMPERIAL"
        print(f"     [{tag:8s}] '{d['text']:15s}' @ x={d['bbox'][0]:.0f}, y={d['bbox'][1]:.0f}")

    print(f"\n  4. Expected output from AI (JSON array):")
    print("""
     [
       {
         "item": 1,
         "type": "upper_wall",
         "width_mm": 762,
         "height_mm": 720,
         "depth_mm": 330,
         "location": "Left of range, Elevation A",
         "confidence": 0.92
       },
       {
         "item": 2,
         "type": "base",
         "width_mm": 900,
         "height_mm": 720,
         "depth_mm": 610,
         "location": "Sink base, Elevation A",
         "confidence": 0.88
       },
       ...
     ]
    """)

    print(f"\n  OUTPUT FILES IN: {out_dir}")
    for f in os.listdir(out_dir):
        fpath = os.path.join(out_dir, f)
        sz    = os.path.getsize(fpath) // 1024
        print(f"    {f:55s}  {sz:5d} KB")


# ══════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════
def main():
    print(SEP)
    print("  STEP 1A + 1B — ELEVATION CROPPER + CABINET EXTRACTOR")
    print(f"  Input: {os.path.basename(PDF_PATH)}")
    print(f"  Output: {OUT_DIR}")
    print(SEP)

    if not os.path.exists(PDF_PATH):
        print(f"  ERROR: PDF not found: {PDF_PATH}")
        return

    # Run pipeline
    all_spans, rects, pw, ph = full_extraction(PDF_PATH)
    regions                   = detect_regions(all_spans, pw, ph)
    crop_zones, cab_hits      = build_crop_zones(regions, all_spans, pw, ph)
    saved_crops               = crop_and_save(PDF_PATH, crop_zones, OUT_DIR)
    output                    = build_structured_json(all_spans, rects, crop_zones, cab_hits, saved_crops)
    print_ai_ready_summary(output, OUT_DIR)

    print(f"\n{SEP}")
    print("  DONE — Next action: send crop images to Claude Vision API")
    print(f"  JSON ready at: cabinet_extraction_A1.json")
    print(SEP)


if __name__ == "__main__":
    main()
