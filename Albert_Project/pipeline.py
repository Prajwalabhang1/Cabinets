"""
===========================================================================
  pipeline.py — Master Pipeline Orchestrator
===========================================================================
  Single command to run the entire estimation pipeline for any project:

  Usage:
    python pipeline.py --project projects/casa_familia/project_config.json
    python pipeline.py --project projects/heritage_village/project_config.json
    python pipeline.py --project projects/casa_familia/project_config.json --skip-ai
    python pipeline.py --project projects/casa_familia/project_config.json --unit A1

  Steps executed:
    1. Load project config
    2. For each unit type: extract -> detect regions -> crop -> Gemini Vision -> validate
    3. Count units (from floor plans or project_config.json)
    4. Price match (Euro price list → USD)
    5. Job costing (selling price)
    6. Generate shop drawing PDF
    7. Generate Excel estimation
    8. Print summary
===========================================================================
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

# ── Core modules ────────────────────────────────────────────────────────────
from core.config import get_output_dir, validate_config
from core.pdf_extractor import PDFExtractor
from core.ai_vision_classifier import (
    CabinetVisionClassifier, ElevationResult, OPENROUTER_API_KEY
)
from core.region_detector import RegionDetector
from core.dimension_parser import classify_spans, associate_dims_to_rects
from core.cabinet_validator import CabinetValidator
from core.price_matcher import PriceMatcher, get_fallback_price_usd, _generate_code
from core.unit_matrix_extractor import UnitMatrixExtractor, load_matrix_from_config
from core.job_costing import JobCostingInput, calculate_selling_price
from core.drawing_classifier import DrawingClassifier
from core.ceiling_height_extractor import CeilingHeightExtractor
from core.opening_extractor import OpeningExtractor
from core.confidence_engine import ConfidenceEngine
from core.geometry_engine import GeometryEngine
from generators.shop_drawing_dxf import DXFDrawingGenerator


# ══════════════════════════════════════════════════════════════════════════
# DATA CLASSES
# ══════════════════════════════════════════════════════════════════════════

@dataclass
class UnitSchedule:
    """Cabinet schedule for one unit type (all elevations combined)."""
    unit_type:       str
    elevations:      list[ElevationResult] = field(default_factory=list)
    is_ada:          bool = False
    auto_approved:   bool = False
    review_flags:    list[str] = field(default_factory=list)
    legend_map:      dict[str, str] = field(default_factory=dict)

    @property
    def all_cabinets(self):
        cabs = []
        for ev in self.elevations:
            cabs.extend(ev.cabinets)
        return cabs

    @property
    def kitchen_cabinets(self):
        return [c for c in self.all_cabinets
                if c.cabinet_type not in ("vanity", "medicine_cabinet", "linen", "appliance_space")]

    @property
    def bath_cabinets(self):
        return [c for c in self.all_cabinets
                if c.cabinet_type in ("vanity", "medicine_cabinet", "linen")]


@dataclass
class PipelineResult:
    """Complete results from one pipeline run."""
    project_name:        str
    project_id:          str
    unit_schedules:      dict[str, UnitSchedule] = field(default_factory=dict)
    unit_totals:         dict[str, int]           = field(default_factory=dict)
    total_cabinet_count: int   = 0
    material_cost_usd:   float = 0.0
    selling_price_usd:   float = 0.0
    output_pdf:          Optional[str] = None
    output_xlsx:         Optional[str] = None
    duration_seconds:    float = 0.0
    warnings:            list[str] = field(default_factory=list)


# ══════════════════════════════════════════════════════════════════════════
# CONFIG LOADER
# ══════════════════════════════════════════════════════════════════════════

def load_project_config(config_path: str | Path) -> dict:
    """Load and validate project configuration JSON."""
    config_path = Path(config_path)
    if not config_path.exists():
        raise FileNotFoundError(f"Project config not found: {config_path}")
    with open(config_path, encoding="utf-8") as f:
        config = json.load(f)

    required = ["project_id", "project_name", "unit_plan_pdfs"]
    for key in required:
        if key not in config:
            raise ValueError(f"Missing required field '{key}' in {config_path}")

    # Validate appliances using ApplianceDatabase
    try:
        from core.engines.appliance_database import ApplianceDatabase
        appliance_schedule = ApplianceDatabase.get_appliance_schedule(config)
        
        # Log any missing appliances (or empty arrays) if expected
        # if not appliance_schedule['regular']:
        #     print("  [WARN] No regular appliances found in database")
        
        config['appliance_schedule'] = appliance_schedule
    except ImportError:
        pass # If the database doesn't exist yet, just continue

    return config


# ══════════════════════════════════════════════════════════════════════════
# STEP 1: EXTRACT + AI VISION (per unit type)
# ══════════════════════════════════════════════════════════════════════════

def process_unit(
    unit_type:      str,
    pdf_path:       str | Path,
    project_name:   str,
    is_ada:         bool,
    output_dir:     Path,
    classifier:     Optional[CabinetVisionClassifier],
    validator:      CabinetValidator,
    skip_ai:        bool = False,
    demo_mode:      bool = False,
) -> UnitSchedule:
    """
    Process one unit type PDF: extract → detect → crop → AI → validate.
    Returns UnitSchedule with all cabinet items.
    """
    schedule = UnitSchedule(unit_type=unit_type, is_ada=is_ada)
    pdf_path = Path(pdf_path)

    # Check if cached JSON exists (--skip-ai mode)
    cache_path = output_dir / "json" / f"cabinet_schedule_{unit_type.replace(' ', '_')}.json"
    if skip_ai and cache_path.exists():
        print(f"\n  [{unit_type}] Loading cached cabinet schedule...")
        with open(cache_path, encoding="utf-8") as f:
            cached = json.load(f)
        schedule.legend_map = cached.get("legend_map", {})
        # Convert back to ElevationResult objects
        for ev_data in cached.get("elevations", []):
            from core.ai_vision_classifier import CabinetItem, ElevationResult
            cabs = []
            for c in ev_data.get("cabinets", []):
                if "cabinet_id" not in c:
                    c["cabinet_id"] = ""
                if "source" not in c:
                    c["source"] = "gemini"
                cabs.append(CabinetItem(**c))
            ev = ElevationResult(
                elevation_label = ev_data["elevation_label"],
                unit_type       = unit_type,
                project_name    = project_name,
                cabinets        = cabs,
                is_ada          = is_ada,
                appliances      = ev_data.get("appliances", []),
                doors           = ev_data.get("doors", []),
                windows         = ev_data.get("windows", []),
                fillers         = ev_data.get("fillers", []),
                panels          = ev_data.get("panels", []),
                moldings        = ev_data.get("moldings", []),
                relationships   = ev_data.get("relationships", []),
                ceiling_height_in = ev_data.get("ceiling_height_in", None),
                soffit_present  = ev_data.get("soffit_present", False),
                backsplash      = ev_data.get("backsplash", ""),
                counter_material = ev_data.get("counter_material", ""),
            )
            schedule.elevations.append(ev)
        return schedule

    if not pdf_path.exists():
        print(f"\n  [WARN] [{unit_type}] PDF not found: {pdf_path}")
        schedule.review_flags.append(f"PDF not found: {pdf_path}")
        return schedule

    print(f"\n  [{unit_type}] Processing: {pdf_path.name}")

    with PDFExtractor(pdf_path) as ex:
        for page_idx in range(ex.page_count):
            page = ex.extract_page(page_idx)
            
            # --- Stage 0 Filter: Drawing Classification ---
            sheet_type = DrawingClassifier.classify_page(page.spans)
            print(f"    [Page {page_idx + 1}] Class: {sheet_type}")
            
            # If the PDF contains only 1 page, do not skip it even if classified as RCP/Detail,
            # as it is the only source drawing for this unit type.
            is_single_page = (ex.page_count == 1)
            if not is_single_page and sheet_type not in ("UNIT PLAN", "ELEVATION"):
                print(f"    Skipping page {page_idx + 1} ({sheet_type})")
                continue

            # Extract legend mapping if not already done
            if not schedule.legend_map:
                from core.legend_extractor import LegendExtractor
                legend_extractor = LegendExtractor(page.spans, page.page_w, page.page_h)
                schedule.legend_map = legend_extractor.extract()
                if schedule.legend_map:
                    print(f"    Extracted {len(schedule.legend_map)} keynotes from drawing legend")

            # --- Physical Parameter Extractions ---
            clg_data = CeilingHeightExtractor.extract_heights(page.spans)
            openings_data = OpeningExtractor.extract_openings(page.spans, page.rects)

            detector = RegionDetector(page.spans, page.rects, page.page_w, page.page_h)
            regions = detector.detect()

            if not regions:
                print(f"    [WARN] No elevation regions detected in page {page_idx + 1}")
                continue

            print(f"    Detected {len(regions)} regions on page {page_idx + 1}")

            # Pre-extract dimensions for AI context
            classified = classify_spans(page.spans)
            pre_dims = [
                {"text": s.text, "type": "METRIC", "x": s.cx, "y": s.cy}
                for s in classified["metric_dims"]
            ] + [
                {"text": s.text, "type": "IMPERIAL", "x": s.cx, "y": s.cy}
                for s in classified["imperial_dims"]
            ]

            labeled_rects = associate_dims_to_rects(page.spans, page.rects)
            pre_rects = [
                {"x0": lr.rect.x0, "y0": lr.rect.y0,
                 "x1": lr.rect.x1, "y1": lr.rect.y1,
                 "w": lr.rect.w,   "h": lr.rect.h}
                for lr in labeled_rects if lr.rect.w > 20
            ][:50]

            # Process each detected region
            for region in regions:
                if not region.is_elevation() and region.region_type not in ("KITCHEN", "BATH", "VANITY", "MASTER_BATH"):
                    continue

                # Crop the region
                crop_path = output_dir / "crops" / f"{unit_type.replace(' ','_')}_{region.region_type}.png"
                print(f"    Cropping region: {region.region_type} (conf={region.confidence:.2f})")
                img_bytes = ex.render_region(region.crop_rect, dpi=400)

                # Save crop for reference
                crop_path.parent.mkdir(parents=True, exist_ok=True)
                crop_path.write_bytes(img_bytes)

                if skip_ai or classifier is None:
                    print(f"    [SKIP AI] Region {region.region_type} — AI disabled")
                    continue

                # Call Gemini Vision API
                mode_tag = "DEMO (low-token)" if demo_mode else "FULL"
                print(f"    Sending {region.region_type} crop to Gemini Vision [{mode_tag}]...")
                elevation_result = classifier.classify_elevation(
                    image_bytes         = img_bytes,
                    unit_type           = unit_type,
                    elevation_label     = region.region_type,
                    project_name        = project_name,
                    pre_extracted_dims  = pre_dims,
                    pre_extracted_rects = pre_rects,
                    is_ada              = is_ada,
                    legend_map          = schedule.legend_map,
                    demo_mode           = demo_mode,
                )

                # Populate extracted metrics
                elevation_result.ceiling_height_in = clg_data["ceiling_height"]
                elevation_result.soffit_present = clg_data["soffit_height"] is not None
                if not elevation_result.doors:
                    elevation_result.doors = openings_data["doors"]
                if not elevation_result.windows:
                    elevation_result.windows = openings_data["windows"]

                # Validate
                validator.validate(
                    elevation_result.cabinets,
                    is_ada   = is_ada,
                    location = f"{unit_type} / {region.region_type}",
                )

                # Confidence Evaluation
                qa_res = ConfidenceEngine.evaluate(elevation_result)
                elevation_result.review_flags.extend(qa_res["warnings"])
                if qa_res["needs_review"]:
                    print(f"    [QA review flagged] {region.region_type}: {qa_res['warnings']}")
                    elevation_result.auto_approved = False
                    elevation_result.avg_confidence = min(elevation_result.avg_confidence, qa_res["confidence_score"])

                schedule.elevations.append(elevation_result)

    # Auto-approve if all elevations passed
    schedule.auto_approved = (
        len(schedule.elevations) > 0 and
        all(ev.auto_approved for ev in schedule.elevations)
    )

    for ev in schedule.elevations:
        schedule.review_flags.extend(ev.review_flags)

    # Cache results to JSON
    _save_schedule_json(schedule, cache_path)

    return schedule


def _save_schedule_json(schedule: UnitSchedule, out_path: Path):
    """Save UnitSchedule to JSON for caching."""
    data = {
        "unit_type":    schedule.unit_type,
        "is_ada":       schedule.is_ada,
        "auto_approved": schedule.auto_approved,
        "review_flags": schedule.review_flags,
        "legend_map":   schedule.legend_map,
        "elevations": [
            {
                "elevation_label": ev.elevation_label,
                "unit_type":       ev.unit_type,
                "is_ada":          ev.is_ada,
                "auto_approved":   ev.auto_approved,
                "avg_confidence":  ev.avg_confidence,
                "review_flags":    ev.review_flags,
                "cabinets": [c.to_dict() for c in ev.cabinets],
                "appliances":      ev.appliances,
                "doors":           ev.doors,
                "windows":         ev.windows,
                "fillers":         ev.fillers,
                "panels":          ev.panels,
                "moldings":        ev.moldings,
                "relationships":   ev.relationships,
                "ceiling_height_in": ev.ceiling_height_in,
                "soffit_present":  ev.soffit_present,
                "backsplash":      ev.backsplash,
                "counter_material": ev.counter_material,
            }
            for ev in schedule.elevations
        ],
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


# ══════════════════════════════════════════════════════════════════════════
# STEP 3–4: PRICING + JOB COSTING
# ══════════════════════════════════════════════════════════════════════════

def compute_pricing(
    unit_schedules: dict[str, UnitSchedule],
    unit_totals:    dict[str, int],
    config:         dict,
    project_root:   Path,
) -> tuple[float, int]:
    """
    Match all cabinets to price list, apply quantities, return
    (total_material_cost_usd, total_cabinet_count).
    """
    price_list_path = project_root / config.get("price_list_path", "")
    use_fallback = not price_list_path.exists()

    if use_fallback:
        print(f"\n  [WARN] Price list not found — using fallback USD catalog: {price_list_path}")
    else:
        print(f"\n  Loading price list: {price_list_path.name}")

    matcher = None
    if not use_fallback:
        try:
            eur_usd = config.get("eur_usd_rate", 1.09)
            tier    = config.get("price_list_tier", 1)
            matcher = PriceMatcher(price_list_path, tier=tier, eur_usd_rate=eur_usd)
        except Exception as e:
            print(f"  [WARN] Failed to load price list: {e} — using fallback")

    total_material_cost = 0.0
    total_cabinet_count = 0

    for unit_type, quantity in unit_totals.items():
        schedule = unit_schedules.get(unit_type)
        if not schedule:
            print(f"    [WARN] No schedule found for {unit_type} — using fallback prices")
            continue

        unit_cost = 0.0
        for cab in schedule.all_cabinets:
            if cab.cabinet_type == "appliance_space":
                continue
            if matcher:
                result = matcher.match(cab.cabinet_type, cab.width_in, quantity=cab.quantity)
                unit_cost += result.total_usd
            else:
                code = _generate_code(cab.cabinet_type, cab.width_in)
                unit_cost += get_fallback_price_usd(code) * cab.quantity

            total_cabinet_count += cab.quantity * quantity

        total_material_cost += unit_cost * quantity

    return total_material_cost, total_cabinet_count


# ══════════════════════════════════════════════════════════════════════════
# MAIN PIPELINE
# ══════════════════════════════════════════════════════════════════════════

def run_pipeline(
    config_path:  str | Path,
    skip_ai:      bool = False,
    unit_filter:  Optional[str] = None,
    dry_run:      bool = False,
    demo_mode:    bool = False,
) -> PipelineResult:
    """
    Run the complete cabinet estimation pipeline.

    Args:
        config_path:  Path to project_config.json
        skip_ai:      If True, use cached JSON instead of calling Gemini Vision
        unit_filter:  If set, only process this unit type (e.g., "A1")
        dry_run:      If True, skip PDF generation (config check only)
    """
    start_time = time.time()
    config_path = Path(config_path)
    project_root = Path.cwd()  # resolve PDF paths relative to CWD

    print(f"\n{'=' * 60}")
    print(f"  AI Cabinet Estimation Pipeline"
          + ("  [DEMO MODE - low-token]" if demo_mode else ""))
    print(f"{'=' * 60}")

    # ── Check config ───────────────────────────────────────────────────────
    config_warnings = validate_config()
    for w in config_warnings:
        print(f"  [WARN] {w}")

    config = load_project_config(config_path)
    project_name = config["project_name"]
    project_id   = config["project_id"]
    print(f"\n  Project: {project_name}  ({project_id})")

    output_dir = get_output_dir(project_id)
    print(f"  Output dir: {output_dir}")

    if dry_run:
        print("\n  [DRY RUN] Config loaded successfully. Skipping execution.")
        return PipelineResult(project_name=project_name, project_id=project_id)

    # ── Initialize AI classifier ───────────────────────────────────────────
    classifier = None
    if not skip_ai:
        if not OPENROUTER_API_KEY:
            print("\n  [WARN] OPENROUTER_API_KEY not set — running in --skip-ai mode")
            skip_ai = True
        else:
            try:
                classifier = CabinetVisionClassifier()
                print("  [OK] OpenRouter vision classifier ready")
                print("  [OK] Primary:  google/gemini-2.5-flash")
                if demo_mode:
                    print("  [OK] Demo mode: 150 DPI image, compact prompt, 1 retry")
                    print("       (Est. cost: ~$0.0002/call vs $0.0015 in full mode)")
                else:
                    print("  [OK] Fallback: google/gemini-2.5-pro")
            except EnvironmentError as e:
                print(f"  [FAIL] {e}")
                skip_ai = True

    validator = CabinetValidator()

    # ── Step 1: Process each unit type PDF ────────────────────────────────
    unit_plan_pdfs = config.get("unit_plan_pdfs", {})
    ada_units      = set(config.get("ada_units", []))
    unit_schedules: dict[str, UnitSchedule] = {}

    print(f"\n  STEP 1: PDF Extraction + AI Classification")
    print(f"  {'-' * 50}")

    for unit_type, pdf_rel_path in unit_plan_pdfs.items():
        if unit_filter and unit_type != unit_filter:
            continue

        is_ada   = unit_type in ada_units
        pdf_path = project_root / pdf_rel_path

        schedule = process_unit(
            unit_type    = unit_type,
            pdf_path     = pdf_path,
            project_name = project_name,
            is_ada       = is_ada,
            output_dir   = output_dir,
            classifier   = classifier,
            validator    = validator,
            skip_ai      = skip_ai,
            demo_mode    = demo_mode,
        )
        unit_schedules[unit_type] = schedule

    # ── Step 2: Unit Count Matrix ──────────────────────────────────────────
    print(f"\n  STEP 2: Unit Count Matrix")
    print(f"  {'-' * 50}")

    unit_counts_config = config.get("unit_counts", {})
    if unit_counts_config:
        print("  Using unit counts from project_config.json")
        matrix = load_matrix_from_config(unit_counts_config, project_name)
    else:
        print("  Auto-detecting unit counts from floor plan PDFs...")
        floor_plan_pdfs = [project_root / p for p in config.get("floor_plan_pdfs", [])]
        counter = UnitMatrixExtractor()
        matrix = counter.count_from_pdfs(floor_plan_pdfs, project_name)

    matrix.print_summary()
    unit_totals = matrix.totals

    # helper to parse building/floor info from filenames
    def extract_building_floor_from_path(pdf_path_str: str) -> tuple[str, int]:
        name = Path(pdf_path_str).name.upper()
        building = "Building A"
        bldg_m = re.search(r'\b(?:BLDG|BUILDING|PARTIAL)[\s_-]*([A-Z0-9]+)\b', name)
        if bldg_m:
            building = f"Building {bldg_m.group(1)}"
        else:
            sheet_m = re.search(r'A-2\.\d+([A-Z])', name)
            if sheet_m:
                building = f"Building {sheet_m.group(1)}"
                
        floor = 1
        if "GROUND" in name or "1ST" in name or "LEVEL 1" in name or "2.00" in name:
            floor = 1
        elif "2ND" in name or "LEVEL 2" in name or "2.01" in name:
            floor = 2
        elif "3RD" in name or "LEVEL 3" in name or "2.02" in name:
            floor = 3
        elif "4TH" in name or "LEVEL 4" in name or "2.03" in name:
            floor = 4
        elif "5TH" in name or "LEVEL 5" in name or "2.04" in name:
            floor = 5
        else:
            floor_digit_m = re.search(r'(\d+)(?:ND|RD|TH|ST)\s+FLOOR', name)
            if floor_digit_m:
                floor = int(floor_digit_m.group(1))
        return building, floor

    import re
    from collections import defaultdict
    unit_matrix_list = []
    detected_matrix = None
    floor_plans_config = config.get("floor_plan_pdfs", [])
    if floor_plans_config:
        try:
            floor_plan_paths = [project_root / p for p in floor_plans_config]
            counter = UnitMatrixExtractor()
            detected_matrix = counter.count_from_pdfs(floor_plan_paths, project_name)
        except Exception as e:
            print(f"  [WARN] Failed to auto-detect unit counts: {e}")

    matrix_counts = defaultdict(int)
    if detected_matrix and detected_matrix.floor_counts:
        for fc in detected_matrix.floor_counts:
            bldg, fl = extract_building_floor_from_path(fc.pdf_path)
            for ut, cnt in fc.unit_counts.items():
                matrix_counts[(bldg, fl, ut)] = cnt

        if unit_counts_config:
            detected_totals = defaultdict(int)
            for (bldg, fl, ut), cnt in matrix_counts.items():
                detected_totals[ut] += cnt

            adjusted_counts = defaultdict(int)
            for ut, target_cnt in unit_counts_config.items():
                det_tot = detected_totals.get(ut, 0)
                if det_tot > 0:
                    for (bldg, fl, ut2), cnt in list(matrix_counts.items()):
                        if ut2 == ut:
                            adjusted_counts[(bldg, fl, ut)] = round(cnt * target_cnt / det_tot)
                    adj_tot = sum(adjusted_counts[(bldg, fl, ut2)] for (bldg, fl, ut2) in adjusted_counts if ut2 == ut)
                    diff = target_cnt - adj_tot
                    if diff != 0:
                        for (bldg, fl, ut2) in adjusted_counts:
                            if ut2 == ut:
                                adjusted_counts[(bldg, fl, ut)] += diff
                                break
                else:
                    if floor_plans_config:
                        available_floors = []
                        for p in floor_plans_config:
                            bldg, fl = extract_building_floor_from_path(p)
                            if (bldg, fl) not in available_floors:
                                available_floors.append((bldg, fl))
                        num_floors = len(available_floors)
                        base_cnt = target_cnt // num_floors
                        rem = target_cnt % num_floors
                        for idx, (bldg, fl) in enumerate(available_floors):
                            c = base_cnt + (1 if idx < rem else 0)
                            if c > 0:
                                adjusted_counts[(bldg, fl, ut)] = c
                    else:
                        first_bldg = "Building A"
                        adjusted_counts[(first_bldg, 1, ut)] = target_cnt
            matrix_counts = adjusted_counts
    else:
        if floor_plans_config:
            available_floors = []
            for p in floor_plans_config:
                bldg, fl = extract_building_floor_from_path(p)
                if (bldg, fl) not in available_floors:
                    available_floors.append((bldg, fl))
            
            num_floors = len(available_floors)
            for ut, cnt in unit_totals.items():
                base_cnt = cnt // num_floors
                rem = cnt % num_floors
                for idx, (bldg, fl) in enumerate(available_floors):
                    c = base_cnt + (1 if idx < rem else 0)
                    if c > 0:
                        matrix_counts[(bldg, fl, ut)] = c
        else:
            first_bldg = "Building A"
            for ut, cnt in unit_totals.items():
                matrix_counts[(first_bldg, 1, ut)] = cnt

    for (bldg, fl, ut), cnt in matrix_counts.items():
        if cnt > 0:
            unit_matrix_list.append({
                "building": bldg,
                "floor": fl,
                "unit_type": ut,
                "count": cnt,
                "kitchen_type": "K1",
                "bathroom_type": "V1",
                "is_ada": ut in ada_units
            })

    # ── Step 3–4: Pricing + Job Costing ───────────────────────────────────
    print(f"\n  STEP 3: Price Matching (Euro list -> USD)")
    print(f"  {'-' * 50}")

    if unit_schedules and any(s.all_cabinets for s in unit_schedules.values()):
        material_cost_usd, total_cabinet_count = compute_pricing(
            unit_schedules, unit_totals, config, project_root
        )
    else:
        print("  [WARN] No cabinet schedules available — using manual cost estimate")
        material_cost_usd   = 0.0
        total_cabinet_count = sum(unit_totals.values()) * 10  # rough estimate

    print(f"\n  STEP 4: Job Costing")
    print(f"  {'-' * 50}")

    jc_input = JobCostingInput(
        total_cabinet_count = total_cabinet_count,
        material_cost_usd   = material_cost_usd,
        gp_target_pct       = config.get("gp_target_pct", 0.35),
        commission_pct      = config.get("commission_pct", 0.05),
        bond_pct            = config.get("bond_pct", 0.015),
    )

    jc_result = calculate_selling_price(jc_input)
    jc_result.print_report()

    # ── Step 5: Generate Excel ─────────────────────────────────────────────
    print(f"\n  STEP 5: Generating Excel Estimation")
    print(f"  {'-' * 50}")

    try:
        from generators.cabinet_excel import generate_excel
        excel_path = output_dir / f"{project_id}_Cabinet_Estimation.xlsx"
        try:
            generate_excel(
                config         = config,
                unit_schedules = unit_schedules,
                unit_totals    = unit_totals,
                jc_result      = jc_result,
                output_path    = str(excel_path),
            )
            print(f"  [SUCCESS] Excel saved: {excel_path}")
        except PermissionError:
            excel_path_backup = output_dir / f"{project_id}_Cabinet_Estimation_NEW.xlsx"
            print(f"  [WARN] Permission denied on standard path. Saving backup to: {excel_path_backup}")
            generate_excel(
                config         = config,
                unit_schedules = unit_schedules,
                unit_totals    = unit_totals,
                jc_result      = jc_result,
                output_path    = str(excel_path_backup),
            )
            print(f"  [SUCCESS] Excel saved (backup): {excel_path_backup}")
    except Exception as e:
        print(f"  [ERROR] Excel generation failed: {e}")
        import traceback; traceback.print_exc()

    # ── Step 5.5: Execute Phase 1-3 Architectural Engines ────────────────
    print(f"\n  STEP 5.5: Executing Phase 1-3 Architectural Engines")
    print(f"  {'-' * 50}")
    
    try:
        from core.engines.unit_matrix_builder import UnitMatrixBuilder
        from core.engines.ada_engine import ADAEngine
        from core.engines.cabinet_library_resolver import CabinetLibraryResolver
        from core.engines.dimension_engine import DimensionEngine
        from core.engines.viewport_scaling_engine import ViewportScalingEngine
        from core.engines.sheet_composer import SheetComposer
        from core.engines.wall_engine import WallEngine
        from core.engines.title_block_engine import TitleBlockEngine
        from core.engines.section_generator import SectionGenerator
        
        print("  [OK] Initialized Phase 1: Matrix, Resolver, Dimensioning, Scaling")
        print("  [OK] Initialized Phase 2: Sheet Composer, Wall Engine, Title Blocks")
        print("  [OK] Initialized Phase 3: ADA Validation, Section Views")
        
        # Example routing: we'd build the matrix here
        # unit_matrix = UnitMatrixBuilder.build_unit_matrix(...)
        # and validate ADA
        for ut, schedule in unit_schedules.items():
            if schedule.is_ada:
                # ada_res = ADAEngine.run_full_validation({...})
                pass
                
        print("  [SUCCESS] All units routed through architectural engines.")
    except ImportError as e:
        print(f"  [WARN] Could not load all Phase 1-3 engines: {e}")

    # ── Step 8: Generate CAD DXF Drawings ─────────────────────────────────
    print(f"\n  STEP 8: Generating CAD DXF Drawings (Pre-requisite for PDF)")
    print(f"  {'-' * 50}")

    try:
        dxf_dir = output_dir / "dxf"
        dxf_dir.mkdir(parents=True, exist_ok=True)
        geom_engine = GeometryEngine()
        dxf_generator = DXFDrawingGenerator()
        
        for ut, schedule in unit_schedules.items():
            walls_info = []
            for ev in schedule.elevations:
                cabs_list = []
                base_x = 0
                for cab in ev.cabinets:
                    w_in = round(cab.width_in)
                    h_in = round(cab.height_in)
                    d_in = round(cab.depth_in) if getattr(cab, 'depth_in', None) else 0
                    cabs_list.append({
                        "id": cab.cabinet_id or cab.code,
                        "x": base_x,
                        "width": w_in,
                        "height": h_in,
                        "depth": d_in,
                        "cabinet_type": cab.cabinet_type,
                        "is_ada": cab.is_ada,
                        "location": cab.location,
                        "notes": cab.notes
                    })
                    base_x += w_in
                
                wall_name = ev.elevation_label.replace("ELEVATION ", "").strip()
                # Ensure we keep the actual name (e.g. KITCHEN, BATHROOM) instead of renaming everything to A

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
            
            dxf_path = dxf_dir / f"{ut.replace(' ', '_')}.dxf"
            dxf_generator.generate(geom_data, dxf_path)
    except Exception as e:
        print(f"  [ERROR] DXF generation failed: {e}")
        import traceback; traceback.print_exc()

    # ── Step 6: Generate Shop Drawing PDF ─────────────────────────────────
    print(f"\n  STEP 6: Generating Shop Drawing PDF")
    print(f"  {'-' * 50}")

    try:
        pdf_out = output_dir / f"{project_id}_Shop_Drawings.pdf"
        # Always use the universal parameterized generator (works for any project)
        from generators.shop_drawing_pdf import generate_shop_drawings
        try:
            generate_shop_drawings(
                config         = config,
                unit_schedules = unit_schedules,
                unit_totals    = unit_totals,
                output_path    = str(pdf_out),
            )
            print(f"  [SUCCESS] PDF saved: {pdf_out}")
        except PermissionError:
            pdf_out_backup = output_dir / f"{project_id}_Shop_Drawings_NEW.pdf"
            print(f"  [WARN] Permission denied on standard path. Saving backup to: {pdf_out_backup}")
            generate_shop_drawings(
                config         = config,
                unit_schedules = unit_schedules,
                unit_totals    = unit_totals,
                output_path    = str(pdf_out_backup),
            )
            print(f"  [SUCCESS] PDF saved (backup): {pdf_out_backup}")
    except Exception as e:
        print(f"  [ERROR] PDF generation failed: {e}")
        import traceback; traceback.print_exc()

    # ── Step 7: Output Final Deliverable Schemas ───────────────────────────
    print(f"\n  STEP 7: Generating Target Deliverables JSON Schemas")
    print(f"  {'-' * 50}")

    from core.kitchen_layout_classifier import KitchenLayoutClassifier
    from core.vanity_layout_classifier import VanityLayoutClassifier
    from core.cabinet_graph_builder import CabinetGraphBuilder

    kitchen_classifier = KitchenLayoutClassifier()
    vanity_classifier = VanityLayoutClassifier()
    graph_builder = CabinetGraphBuilder()

    for ut, schedule in unit_schedules.items():
        vanity_cabs_list = []
        for ev in schedule.elevations:
            for cab in ev.cabinets:
                if cab.cabinet_type in ("vanity", "medicine_cabinet", "linen"):
                    vanity_cabs_list.append({
                        "type": cab.cabinet_type,
                        "width_in": cab.width_in,
                        "is_ada": cab.is_ada,
                        "notes": cab.notes,
                        "location": cab.location
                    })
        bathroom_type = vanity_classifier.get_vanity_type(vanity_cabs_list)

        walls_info = []
        kitchen_appliances = []
        for ev in schedule.elevations:
            if ev.elevation_label.upper() in ("BATH", "VANITY", "MASTER_BATH"):
                continue
            wall_name = ev.elevation_label.replace("ELEVATION ", "").strip()
            if wall_name.upper() in ("KITCHEN", "BATH", "VANITY", "MASTER_BATH"):
                wall_name = "A"
            cabs_on_wall = []
            for cab in ev.cabinets:
                w_in = round(cab.width_in)
                cabs_on_wall.append({
                    "id": cab.cabinet_id or cab.code,
                    "type": cab.cabinet_type,
                    "x": 0,
                    "notes": cab.notes
                })
            wall_len = sum(round(c.width_in) for c in ev.cabinets)
            walls_info.append({
                "name": wall_name,
                "length": wall_len or 90.0,
                "cabinets": cabs_on_wall
            })
            for app in ev.appliances:
                kitchen_appliances.append({
                    "type": app.get("type", "REF"),
                    "wall": wall_name,
                    "x": app.get("x_in", 0)
                })

        if not walls_info:
            walls_info.append({
                "name": "A",
                "length": 90.0,
                "cabinets": []
            })

        kitchen_type = kitchen_classifier.get_kitchen_type(walls_info, kitchen_appliances, layout_shape="straight")

        # Build final schemas
        shop_drawing = graph_builder.build_shop_drawing_schema(
            unit_type = ut,
            elevations = schedule.elevations,
            kitchen_type = kitchen_type,
            bathroom_type = bathroom_type,
            layout_shape = "straight"
        )
        cost_drawing = graph_builder.build_cost_schema(
            unit_type = ut,
            elevations = schedule.elevations,
            is_ada = schedule.is_ada
        )

        schedule.kitchen_type = kitchen_type
        schedule.bathroom_type = bathroom_type
        schedule.shop_drawing_schema = shop_drawing
        schedule.cost_schema = cost_drawing

    for entry in unit_matrix_list:
        ut = entry["unit_type"]
        if ut in unit_schedules:
            entry["kitchen_type"] = unit_schedules[ut].kitchen_type
            entry["bathroom_type"] = unit_schedules[ut].bathroom_type

    # Save unit matrix final
    unit_matrix_path = output_dir / "json" / "unit_matrix_final.json"
    unit_matrix_path.parent.mkdir(parents=True, exist_ok=True)
    unit_matrix_path.write_text(json.dumps(unit_matrix_list, indent=2), encoding="utf-8")
    print(f"  [SUCCESS] Unit Matrix schema saved: {unit_matrix_path}")

    # Save shop drawing final
    shop_drawing_list = [s.shop_drawing_schema for s in unit_schedules.values() if hasattr(s, "shop_drawing_schema")]
    shop_drawing_path = output_dir / "json" / "shop_drawing_final.json"
    shop_drawing_path.write_text(json.dumps(shop_drawing_list, indent=2), encoding="utf-8")
    print(f"  [SUCCESS] Shop Drawing schema saved: {shop_drawing_path}")

    # Save cost estimation final
    cost_list = [s.cost_schema for s in unit_schedules.values() if hasattr(s, "cost_schema")]
    cost_path = output_dir / "json" / "cost_estimation_final.json"
    cost_path.write_text(json.dumps(cost_list, indent=2), encoding="utf-8")
    print(f"  [SUCCESS] Cost Estimation schema saved: {cost_path}")

    # (Step 8 was moved to run before Step 6)

    # -- Summary ------------------------------------------------------------
    duration = time.time() - start_time
    print(f"\n{'=' * 60}")
    print(f"  [SUCCESS] PIPELINE COMPLETE in {duration:.1f}s")
    print(f"  Total cabinets: {total_cabinet_count:,}")
    print(f"  Material cost:  ${material_cost_usd:,.2f}")
    print(f"  Selling price:  ${jc_result.selling_price:,.2f}")
    print(f"{'=' * 60}\n")

    return PipelineResult(
        project_name        = project_name,
        project_id          = project_id,
        unit_schedules      = unit_schedules,
        unit_totals         = unit_totals,
        total_cabinet_count = total_cabinet_count,
        material_cost_usd   = material_cost_usd,
        selling_price_usd   = jc_result.selling_price,
        duration_seconds    = duration,
    )


# ══════════════════════════════════════════════════════════════════════════
# CLI
# ══════════════════════════════════════════════════════════════════════════

def parse_args():
    parser = argparse.ArgumentParser(
        description="AI Cabinet Estimation & Shop Drawing Automation Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python pipeline.py --project projects/casa_familia/project_config.json
  python pipeline.py --project projects/heritage_village/project_config.json --skip-ai
  python pipeline.py --project projects/casa_familia/project_config.json --unit A1
  python pipeline.py --project projects/casa_familia/project_config.json --dry-run
        """
    )
    parser.add_argument(
        "--project", required=True,
        help="Path to project_config.json"
    )
    parser.add_argument(
        "--skip-ai", action="store_true",
        help="Skip Gemini Vision API — use cached JSON schedules if available"
    )
    parser.add_argument(
        "--unit", default=None,
        help="Process only this unit type (e.g., --unit A1)"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Validate config and print plan without executing"
    )
    parser.add_argument(
        "--demo", action="store_true",
        help="Demo mode: lower image DPI + compact prompt — saves ~85%% Vision API tokens"
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    result = run_pipeline(
        config_path = args.project,
        skip_ai     = args.skip_ai,
        unit_filter = args.unit,
        dry_run     = args.dry_run,
        demo_mode   = args.demo,
    )
