"""
Validation tests for all core modules.
Run: python test_all.py
"""
import sys
sys.stdout.reconfigure(encoding="utf-8")

PASS = "[PASS]"
FAIL = "[FAIL]"

def check(label, condition, info=""):
    status = PASS if condition else FAIL
    print(f"  {status}  {label}  {info}")
    return condition

all_ok = True

# ════════════════════════════════════════════════════
print("=" * 55)
print("  Albert Project — Core Module Validation Tests")
print("=" * 55)

# ── Test 1: Config ───────────────────────────────────
print("\n[1] Config")
try:
    from core.config import PROJECT_ROOT, EUR_USD_RATE, ANTHROPIC_API_KEY, STANDARD_WIDTHS_MM
    check("PROJECT_ROOT exists", PROJECT_ROOT.exists(), str(PROJECT_ROOT))
    check("EUR_USD_RATE valid", EUR_USD_RATE > 0, str(EUR_USD_RATE))
    check("STANDARD_WIDTHS_MM populated", len(STANDARD_WIDTHS_MM) > 10, f"{len(STANDARD_WIDTHS_MM)} widths")
    check("API key (optional)", True, f"{'SET' if ANTHROPIC_API_KEY else 'NOT SET (skip-ai mode)'}")
except Exception as e:
    print(f"  {FAIL}  Config import failed: {e}")
    all_ok = False

# ── Test 2: Dimension Parser ─────────────────────────
print("\n[2] Dimension Parser")
try:
    from core.dimension_parser import parse_metric_mm, parse_imperial_mm, cross_validate

    # Metric
    tests_m = [
        ("76.20", 762.0),
        ("90.00", 900.0),
        ("228.60", 2286.0),
        ("30", 300.0),
        ("1", None),
        ("9999", None),
    ]
    for txt, expected in tests_m:
        result = parse_metric_mm(txt)
        ok = (result == expected) or (result is None and expected is None)
        check(f"metric({txt!r})", ok, f"-> {result} (exp {expected})")
        all_ok = all_ok and ok

    # Imperial
    tests_i = [
        ("36\"",   914.4),
        ("3'-0\"", 914.4),
        ("[14']",  4267.2),
    ]
    for txt, expected in tests_i:
        result = parse_imperial_mm(txt)
        result_str = f"{result:.1f}" if result is not None else "None"
        ok = result is not None and abs(result - expected) < 1.5
        check(f"imperial({txt!r})", ok, f"-> {result_str} (exp {expected})")
        all_ok = all_ok and ok

    # Cross-validation
    pair = cross_validate(762.0, 762.0)
    check("cross_validate(762,762)", pair.confidence == "HIGH", pair.confidence)

    pair_mis = cross_validate(762.0, 914.4)
    check("cross_validate mismatch", pair_mis.confidence == "MISMATCH", pair_mis.confidence)

except Exception as e:
    print(f"  {FAIL}  dimension_parser error: {e}")
    import traceback; traceback.print_exc()
    all_ok = False

# ── Test 3: Job Costing ──────────────────────────────
print("\n[3] Job Costing")
try:
    from core.job_costing import JobCostingInput, calculate_selling_price

    inp = JobCostingInput(total_cabinet_count=630, material_cost_usd=95_000.0)
    res = calculate_selling_price(inp)

    ok_gp   = abs(res.gp_check_pct - 0.35) < 0.001
    ok_pos  = res.selling_price > 0
    ok_math = abs(res.pre_margin_total / (1 - 0.35 - 0.05 - 0.015) - res.selling_price) < 1.0

    check("GP% verification", ok_gp, f"{res.gp_check_pct:.4f} (exp 0.35)")
    check("Selling price > 0", ok_pos, f"${res.selling_price:,.2f}")
    check("Algebraic formula", ok_math, f"pre-margin/denom = ${res.selling_price:,.2f}")
    check("Containers needed", res.containers_needed == 3, f"{res.containers_needed} containers")

    all_ok = all_ok and ok_gp and ok_pos and ok_math

except Exception as e:
    print(f"  {FAIL}  job_costing error: {e}")
    import traceback; traceback.print_exc()
    all_ok = False

# ── Test 4: AI Vision JSON Parser ────────────────────
print("\n[4] AI Vision Classifier (JSON parser, no API key needed)")
try:
    from core.ai_vision_classifier import CabinetVisionClassifier, _normalize_cabinet_type, _default_height

    # Test JSON parsing without creating full object
    c = object.__new__(CabinetVisionClassifier)
    sample_json = '''[
      {"item_num": 1, "cabinet_type": "upper_wall", "width_mm": 762, "height_mm": 300,
       "depth_mm": 330, "location": "Left of range", "elevation_ref": "ELEV A",
       "confidence": 0.92, "quantity": 1, "is_ada": false, "notes": ""},
      {"item_num": 2, "cabinet_type": "base", "width_mm": 900, "height_mm": 720,
       "depth_mm": 600, "location": "Sink base", "elevation_ref": "ELEV A",
       "confidence": 0.88, "quantity": 1, "is_ada": false, "notes": "sink base"},
      {"item_num": 3, "cabinet_type": "appliance_space", "width_mm": 610, "height_mm": 720,
       "depth_mm": 600, "location": "DW", "elevation_ref": "ELEV A",
       "confidence": 0.98, "quantity": 1, "is_ada": false, "notes": "dishwasher"}
    ]'''
    cabs = c._parse_cabinet_json(sample_json, "ELEV A")

    check("Parsed 3 items", len(cabs) == 3, f"{len(cabs)} items")
    check("First item width=762mm", cabs[0].width_mm == 762, str(cabs[0].width_mm))
    check("First item code contains W30", "W30" in cabs[0].code, cabs[0].code)
    check("Third item = appliance_space", cabs[2].cabinet_type == "appliance_space", cabs[2].cabinet_type)

    # Test type normalization
    check("normalize 'wall'", _normalize_cabinet_type("wall") == "upper_wall")
    check("normalize 'dishwasher'", _normalize_cabinet_type("dishwasher") == "appliance_space")

    # Test default heights
    check("pantry height=2130", _default_height("pantry") == 2130.0)
    check("base height=720", _default_height("base") == 720.0)

    all_ok = all_ok and len(cabs) == 3

except Exception as e:
    print(f"  {FAIL}  ai_vision_classifier error: {e}")
    import traceback; traceback.print_exc()
    all_ok = False

# ── Test 5: Cabinet Validator ────────────────────────
print("\n[5] Cabinet Validator")
try:
    from core.cabinet_validator import CabinetValidator
    from core.ai_vision_classifier import CabinetItem

    test_cabs = [
        CabinetItem(1, "upper_wall",    762.0, 300.0, 330.0, "Left",  "ELEV A", 0.92),
        CabinetItem(2, "base",          900.0, 720.0, 600.0, "Base",  "ELEV A", 0.88),
        CabinetItem(3, "appliance_space", 610.0, 720.0, 600.0, "DW", "ELEV A", 0.98),
    ]
    validator = CabinetValidator()
    result = validator.get_validation_result(test_cabs, room_width_mm=None, is_ada=False)

    check("Score > 0.8", result.overall_score > 0.8, f"{result.overall_score:.2f}")
    check("No critical flags", len(result.flags) == 0, f"{len(result.flags)} flags")

    # ADA test
    ada_cabs = [
        CabinetItem(1, "base", 900.0, 1000.0, 600.0, "ADA Base", "ELEV A", 0.9),
    ]
    ada_result = validator.get_validation_result(ada_cabs, is_ada=True)
    check("ADA height flag detected", len(ada_result.flags) > 0, f"{ada_result.flags}")

    all_ok = all_ok and result.overall_score > 0.8

except Exception as e:
    print(f"  {FAIL}  cabinet_validator error: {e}")
    import traceback; traceback.print_exc()
    all_ok = False

# ── Test 6: Price Matcher Fallback ───────────────────
print("\n[6] Price Matcher (fallback catalog)")
try:
    from core.price_matcher import get_fallback_price_usd, _generate_code

    check("B36 fallback", get_fallback_price_usd("B36") == 139.0, str(get_fallback_price_usd("B36")))
    check("VAN60 fallback", get_fallback_price_usd("VAN60") == 379.0, str(get_fallback_price_usd("VAN60")))
    check("unknown fallback", get_fallback_price_usd("XYZ999") == 100.0, str(get_fallback_price_usd("XYZ999")))

    code = _generate_code("base", 914.0)
    check("base 914mm code = B36", code == "B36", code)
    code2 = _generate_code("vanity", 762.0)
    check("vanity 762mm code = VAN30", code2 == "VAN30", code2)

except Exception as e:
    print(f"  {FAIL}  price_matcher error: {e}")
    import traceback; traceback.print_exc()
    all_ok = False

# ── Test 7: Unit Counter (manual mode) ───────────────
print("\n[7] Unit Counter (manual override)")
try:
    from core.unit_counter import load_matrix_from_config
    matrix = load_matrix_from_config({"A1": 14, "B1": 6}, "Test Project")
    check("Totals loaded", matrix.totals == {"A1": 14, "B1": 6})
    check("Confidence = 1.0", matrix.confidence == 1.0)
    check("Needs review = False", not matrix.needs_review)
except Exception as e:
    print(f"  {FAIL}  unit_counter error: {e}")
    all_ok = False

# ── Test 8: PDF Extractor (basic import) ─────────────
print("\n[8] PDF Extractor (import test)")
try:
    from core.pdf_extractor import PDFExtractor, TextSpan, VectorRect, PageData
    check("PDFExtractor imported", True)
    check("TextSpan imported", True)
    check("VectorRect imported", True)
except Exception as e:
    print(f"  {FAIL}  pdf_extractor import error: {e}")
    all_ok = False

# ── Test 9: Region Detector (basic import) ───────────
print("\n[9] Region Detector (import test)")
try:
    from core.region_detector import RegionDetector, DetectedRegion
    check("RegionDetector imported", True)
    check("DetectedRegion imported", True)
except Exception as e:
    print(f"  {FAIL}  region_detector import error: {e}")
    all_ok = False

# ── Summary ───────────────────────────────────────────
print("\n" + "=" * 55)
if all_ok:
    print("  ALL TESTS PASSED")
else:
    print("  SOME TESTS FAILED - see above")
print("=" * 55)
sys.exit(0 if all_ok else 1)
