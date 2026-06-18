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
    2. For each unit type: extract → detect regions → crop → Claude AI → validate
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
from core.config import get_output_dir, validate_config, ANTHROPIC_API_KEY
from core.pdf_extractor import PDFExtractor
from core.region_detector import RegionDetector
from core.dimension_parser import classify_spans, associate_dims_to_rects
from core.ai_vision_classifier import CabinetVisionClassifier, ElevationResult
from core.cabinet_validator import CabinetValidator
from core.price_matcher import PriceMatcher, get_fallback_price_usd, _generate_code
from core.unit_counter import UnitCounter, load_matrix_from_config
from core.job_costing import JobCostingInput, calculate_selling_price


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
        # Convert back to ElevationResult objects
        for ev_data in cached.get("elevations", []):
            from core.ai_vision_classifier import CabinetItem, ElevationResult
            cabs = []
            for c in ev_data.get("cabinets", []):
                cabs.append(CabinetItem(**c))
            ev = ElevationResult(
                elevation_label = ev_data["elevation_label"],
                unit_type       = unit_type,
                project_name    = project_name,
                cabinets        = cabs,
                is_ada          = is_ada,
            )
            schedule.elevations.append(ev)
        return schedule

    if not pdf_path.exists():
        print(f"\n  ⚠️  [{unit_type}] PDF not found: {pdf_path}")
        schedule.review_flags.append(f"PDF not found: {pdf_path}")
        return schedule

    print(f"\n  [{unit_type}] Processing: {pdf_path.name}")

    with PDFExtractor(pdf_path) as ex:
        page = ex.extract_page(0)
        detector = RegionDetector(page.spans, page.rects, page.page_w, page.page_h)
        regions = detector.detect()

        if not regions:
            print(f"    ⚠️  No elevation regions detected in {pdf_path.name}")
            schedule.review_flags.append("No elevation regions detected")
            return schedule

        print(f"    Detected {len(regions)} regions")

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

            # Call Claude Vision API
            print(f"    Calling Claude Vision for {region.region_type}...")
            elevation_result = classifier.classify_elevation(
                image_bytes         = img_bytes,
                unit_type           = unit_type,
                elevation_label     = region.region_type,
                project_name        = project_name,
                pre_extracted_dims  = pre_dims,
                pre_extracted_rects = pre_rects,
                is_ada              = is_ada,
            )

            # Validate
            validator.validate(
                elevation_result.cabinets,
                is_ada   = is_ada,
                location = f"{unit_type} / {region.region_type}",
            )

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
        "elevations": [
            {
                "elevation_label": ev.elevation_label,
                "unit_type":       ev.unit_type,
                "is_ada":          ev.is_ada,
                "auto_approved":   ev.auto_approved,
                "avg_confidence":  ev.avg_confidence,
                "review_flags":    ev.review_flags,
                "cabinets": [c.to_dict() for c in ev.cabinets],
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
        print(f"\n  ⚠️  Price list not found — using fallback USD catalog: {price_list_path}")
    else:
        print(f"\n  Loading price list: {price_list_path.name}")

    matcher = None
    if not use_fallback:
        try:
            eur_usd = config.get("eur_usd_rate", 1.09)
            tier    = config.get("price_list_tier", 1)
            matcher = PriceMatcher(price_list_path, tier=tier, eur_usd_rate=eur_usd)
        except Exception as e:
            print(f"  ⚠️  Failed to load price list: {e} — using fallback")

    total_material_cost = 0.0
    total_cabinet_count = 0

    for unit_type, quantity in unit_totals.items():
        schedule = unit_schedules.get(unit_type)
        if not schedule:
            print(f"    ⚠️  No schedule found for {unit_type} — using fallback prices")
            continue

        unit_cost = 0.0
        for cab in schedule.all_cabinets:
            if cab.cabinet_type == "appliance_space":
                continue
            if matcher:
                result = matcher.match(cab.cabinet_type, cab.width_mm, quantity=cab.quantity)
                unit_cost += result.total_usd
            else:
                code = _generate_code(cab.cabinet_type, cab.width_mm)
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
) -> PipelineResult:
    """
    Run the complete cabinet estimation pipeline.

    Args:
        config_path:  Path to project_config.json
        skip_ai:      If True, use cached JSON instead of calling Claude
        unit_filter:  If set, only process this unit type (e.g., "A1")
        dry_run:      If True, skip PDF generation (config check only)
    """
    start_time = time.time()
    config_path = Path(config_path)
    project_root = Path.cwd()  # resolve PDF paths relative to CWD

    print(f"\n{'═' * 60}")
    print(f"  AI Cabinet Estimation Pipeline")
    print(f"{'═' * 60}")

    # ── Check config ───────────────────────────────────────────────────────
    config_warnings = validate_config()
    for w in config_warnings:
        print(f"  ⚠️  {w}")

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
        if not ANTHROPIC_API_KEY:
            print("\n  ⚠️  ANTHROPIC_API_KEY not set — running in --skip-ai mode")
            skip_ai = True
        else:
            try:
                classifier = CabinetVisionClassifier(use_gpt4o_backup=False)
                print("  ✅ Claude Vision classifier ready")
            except EnvironmentError as e:
                print(f"  ❌ {e}")
                skip_ai = True

    validator = CabinetValidator()

    # ── Step 1: Process each unit type PDF ────────────────────────────────
    unit_plan_pdfs = config.get("unit_plan_pdfs", {})
    ada_units      = set(config.get("ada_units", []))
    unit_schedules: dict[str, UnitSchedule] = {}

    print(f"\n  STEP 1: PDF Extraction + AI Classification")
    print(f"  {'─' * 50}")

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
        )
        unit_schedules[unit_type] = schedule

    # ── Step 2: Unit counts ────────────────────────────────────────────────
    print(f"\n  STEP 2: Unit Count Matrix")
    print(f"  {'─' * 50}")

    unit_counts_config = config.get("unit_counts", {})
    if unit_counts_config:
        print("  Using unit counts from project_config.json")
        matrix = load_matrix_from_config(unit_counts_config, project_name)
    else:
        print("  Auto-detecting unit counts from floor plan PDFs...")
        floor_plan_pdfs = [project_root / p for p in config.get("floor_plan_pdfs", [])]
        counter = UnitCounter()
        matrix = counter.count_from_pdfs(floor_plan_pdfs, project_name)

    matrix.print_summary()
    unit_totals = matrix.totals

    # ── Step 3–4: Pricing + Job Costing ───────────────────────────────────
    print(f"\n  STEP 3: Price Matching (Euro list → USD)")
    print(f"  {'─' * 50}")

    if unit_schedules and any(s.all_cabinets for s in unit_schedules.values()):
        material_cost_usd, total_cabinet_count = compute_pricing(
            unit_schedules, unit_totals, config, project_root
        )
    else:
        print("  ⚠️  No cabinet schedules available — using manual cost estimate")
        material_cost_usd   = 0.0
        total_cabinet_count = sum(unit_totals.values()) * 10  # rough estimate

    print(f"\n  STEP 4: Job Costing")
    print(f"  {'─' * 50}")

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
    print(f"  {'─' * 50}")

    try:
        from generators.cabinet_excel import generate_excel
        excel_path = output_dir / f"{project_id}_Cabinet_Estimation.xlsx"
        generate_excel(
            config         = config,
            unit_schedules = unit_schedules,
            unit_totals    = unit_totals,
            jc_result      = jc_result,
            output_path    = str(excel_path),
        )
        print(f"  ✅ Excel saved: {excel_path}")
    except Exception as e:
        print(f"  ❌ Excel generation failed: {e}")
        import traceback; traceback.print_exc()

    # ── Step 6: Generate Shop Drawing PDF ─────────────────────────────────
    print(f"\n  STEP 6: Generating Shop Drawing PDF")
    print(f"  {'─' * 50}")

    try:
        from generators.shop_drawing_pdf import generate_shop_drawings
        pdf_out = output_dir / f"{project_id}_Shop_Drawings.pdf"
        generate_shop_drawings(
            config         = config,
            unit_schedules = unit_schedules,
            unit_totals    = unit_totals,
            output_path    = str(pdf_out),
        )
        print(f"  ✅ PDF saved: {pdf_out}")
    except Exception as e:
        print(f"  ❌ PDF generation failed: {e}")
        import traceback; traceback.print_exc()

    # ── Summary ────────────────────────────────────────────────────────────
    duration = time.time() - start_time
    print(f"\n{'═' * 60}")
    print(f"  ✅ PIPELINE COMPLETE in {duration:.1f}s")
    print(f"  Total cabinets: {total_cabinet_count:,}")
    print(f"  Material cost:  ${material_cost_usd:,.2f}")
    print(f"  Selling price:  ${jc_result.selling_price:,.2f}")
    print(f"{'═' * 60}\n")

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
        help="Skip Claude Vision API — use cached JSON schedules if available"
    )
    parser.add_argument(
        "--unit", default=None,
        help="Process only this unit type (e.g., --unit A1)"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Validate config and print plan without executing"
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    result = run_pipeline(
        config_path = args.project,
        skip_ai     = args.skip_ai,
        unit_filter = args.unit,
        dry_run     = args.dry_run,
    )
