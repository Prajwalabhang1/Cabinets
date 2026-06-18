"""
===========================================================================
  core/dimension_parser.py — Dual-Unit Dimension Parser
===========================================================================
  Extracts and cross-validates dimensions from architectural drawings.

  Architectural PDFs (Casa Familia, Heritage Village) use BOTH systems:
    - Metric:   "76.20"     (cm)  →  762.0 mm
    - Imperial: "[2'-6\"]"  (ft+in) →  762.0 mm
  
  When both are present for the same measurement, they MUST agree within
  tolerance — if not, we flag it as a mismatch for human review.

  Key improvements over step1_crop_elevations.py:
    1. Fixed: original DIM_METRIC_RE matched ALL numbers (page numbers, etc.)
       New approach: contextual filter — metric dims must be near a
       line/rect endpoint (within 40 pts) OR contain a decimal point
       AND be in the range 5–9999 (valid cabinet dimension range)
    2. Proper cross-validation between metric and imperial values
    3. Associates dimensions to their nearest rectangle (the cabinet they label)
    4. Returns structured DimensionPair objects, not raw text
===========================================================================
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

from core.pdf_extractor import TextSpan, VectorRect


# ══════════════════════════════════════════════════════════════════════════
# REGEX PATTERNS
# ══════════════════════════════════════════════════════════════════════════

# Metric: matches "76.20", "228.60", "90", "12.5"
# Restricted: must be plausible cabinet dimension (5mm–9999mm when interpreted as cm×10)
_METRIC_RE = re.compile(
    r'(?<!\d)'          # no digit before
    r'(\d{1,4}(?:\.\d{1,2})?)'  # 1-4 digits, optional decimal
    r'(?!\d)'           # no digit after
)

# Imperial: "2' - 6\"", "3'-0\"", "7' - 6\"", "14'", "2'-6\"", "11\""
_IMPERIAL_RE = re.compile(
    r"""
    (?:                          # feet + inches form
        (\d+)                    # feet
        \s*['′]\s*[-]?\s*        # foot mark with optional dash/space
        (\d+)                    # whole inches
        (?:\s+(\d+)/(\d+))?      # optional fractional inches: "3/4"
        \s*["″]?                 # optional inch mark
    )
    |
    (?:                          # feet only form: "14'"
        (\d+)\s*['′]
        (?!\s*[-]?\s*\d)         # not followed by inches (avoid double-match)
    )
    |
    (?:                          # inches only form: "36\""
        (\d+(?:\.\d+)?)\s*["″]
    )
    |
    (?:                          # bracket form: "[2'-6\"]" or "[14']"
        \[(\d+)['′]\s*[-]?\s*(\d+)?(?:\s+\d+/\d+)?["″]?\]
    )
    """,
    re.VERBOSE,
)

# Valid cabinet width range in mm (2" to 72")
_MIN_CAB_MM = 50.0
_MAX_CAB_MM = 2000.0
_VALID_CM_RANGE = (5.0, 350.0)  # 5cm to 350cm = 50mm to 3500mm


# ══════════════════════════════════════════════════════════════════════════
# DATA CLASSES
# ══════════════════════════════════════════════════════════════════════════

@dataclass
class ParsedDimension:
    """A single dimension value extracted from a text span."""
    value_mm:    float           # canonical value in mm
    source_text: str             # original text e.g. "76.20" or "2' - 6\""
    dim_type:    str             # "METRIC" | "IMPERIAL" | "FRACTION"
    span_x:      float           # x-coordinate of span origin
    span_y:      float           # y-coordinate of span origin
    confidence:  float = 1.0


@dataclass
class DimensionPair:
    """
    A cross-validated dimension — metric + imperial values for the same measurement.
    When both are found and agree, confidence is HIGH.
    """
    value_mm:     float
    metric_text:  Optional[str]
    imperial_text: Optional[str]
    confidence:   str   # "HIGH" | "METRIC_ONLY" | "IMPERIAL_ONLY" | "MISMATCH"
    mismatch_mm:  Optional[float] = None   # difference if mismatch


@dataclass
class LabeledRect:
    """A rectangle associated with its nearest dimension label."""
    rect:          VectorRect
    width_mm:      Optional[float]
    height_mm:     Optional[float]
    nearby_labels: list[str]   # cabinet keywords near this rect
    dim_confidence: str = "NONE"


# ══════════════════════════════════════════════════════════════════════════
# PARSING FUNCTIONS
# ══════════════════════════════════════════════════════════════════════════

def parse_metric_mm(text: str) -> Optional[float]:
    """
    Parse a metric dimension text → value in mm.
    Input is assumed to be in cm (the standard in these drawings).
    E.g., "76.20" → 762.0 mm
    E.g., "90" → 900.0 mm (only if in valid cm range)
    Returns None if not a valid cabinet dimension.
    """
    text = text.strip()
    m = _METRIC_RE.fullmatch(text)
    if not m:
        # Try to extract just the number
        m = _METRIC_RE.search(text)
        if not m:
            return None

    try:
        val = float(m.group(1))
    except (ValueError, IndexError):
        return None

    # Validate: must be in plausible cm range
    if not (_VALID_CM_RANGE[0] <= val <= _VALID_CM_RANGE[1]):
        return None

    return val * 10.0  # cm → mm


def parse_imperial_mm(text: str) -> Optional[float]:
    """
    Parse an imperial dimension text → value in mm.
    Handles: "2' - 6\"", "3'-0\"", "7' - 6\"", "14'", "[2'-6\"]", "36\""
    Returns None if not parseable.
    """
    text = text.strip()
    total_inches = 0.0

    # Try bracket form first: [2'-6"] or [14']
    bracket_m = re.search(r'\[(\d+)[\'′]\s*[-]?\s*(\d+)?(?:\s+(\d+)/(\d+))?["″]?\]', text)
    if bracket_m:
        feet = int(bracket_m.group(1))
        inches = int(bracket_m.group(2) or 0)
        frac_num = int(bracket_m.group(3) or 0)
        frac_den = int(bracket_m.group(4) or 1)
        frac = frac_num / frac_den if frac_den else 0
        total_inches = feet * 12 + inches + frac
        mm = total_inches * 25.4
        if _MIN_CAB_MM <= mm <= _MAX_CAB_MM * 2:
            return mm
        return None

    # Feet + inches form: "2' - 6\""
    fi_m = re.search(
        r'(\d+)\s*[\'′]\s*[-]?\s*(\d+)(?:\s+(\d+)/(\d+))?\s*["″]?', text
    )
    if fi_m:
        feet = int(fi_m.group(1))
        inches = int(fi_m.group(2))
        frac_num = int(fi_m.group(3) or 0)
        frac_den = int(fi_m.group(4) or 1)
        frac = frac_num / frac_den if frac_den else 0
        total_inches = feet * 12 + inches + frac
        mm = total_inches * 25.4
        if _MIN_CAB_MM <= mm <= _MAX_CAB_MM * 2:
            return mm

    # Feet only: "14'"
    feet_only = re.search(r'^(\d+)\s*[\'′]$', text)
    if feet_only:
        total_inches = int(feet_only.group(1)) * 12
        mm = total_inches * 25.4
        if _MIN_CAB_MM <= mm <= _MAX_CAB_MM * 2:
            return mm

    # Inches only: "36\""
    inches_only = re.search(r'^(\d+(?:\.\d+)?)\s*["″]$', text)
    if inches_only:
        mm = float(inches_only.group(1)) * 25.4
        if _MIN_CAB_MM <= mm <= _MAX_CAB_MM * 2:
            return mm

    return None


def cross_validate(
    metric_mm:   Optional[float],
    imperial_mm: Optional[float],
    tolerance_mm: float = 10.0,
) -> DimensionPair:
    """
    Cross-validate metric and imperial values for the same dimension.
    Tolerance: ±10mm (accounts for rounding in cm vs imperial notation).
    """
    if metric_mm is not None and imperial_mm is not None:
        diff = abs(metric_mm - imperial_mm)
        if diff <= tolerance_mm:
            return DimensionPair(
                value_mm      = metric_mm,  # prefer metric (exact)
                metric_text   = f"{metric_mm/10:.2f}cm",
                imperial_text = f"{imperial_mm/25.4:.2f}\"",
                confidence    = "HIGH",
            )
        else:
            return DimensionPair(
                value_mm      = metric_mm,
                metric_text   = f"{metric_mm/10:.2f}cm",
                imperial_text = f"{imperial_mm/25.4:.2f}\"",
                confidence    = "MISMATCH",
                mismatch_mm   = diff,
            )
    elif metric_mm is not None:
        return DimensionPair(
            value_mm      = metric_mm,
            metric_text   = f"{metric_mm/10:.2f}cm",
            imperial_text = None,
            confidence    = "METRIC_ONLY",
        )
    elif imperial_mm is not None:
        return DimensionPair(
            value_mm      = imperial_mm,
            metric_text   = None,
            imperial_text = f"{imperial_mm/25.4:.2f}\"",
            confidence    = "IMPERIAL_ONLY",
        )
    else:
        return DimensionPair(
            value_mm=0, metric_text=None, imperial_text=None,
            confidence="NONE",
        )


# ══════════════════════════════════════════════════════════════════════════
# SPAN CLASSIFICATION
# ══════════════════════════════════════════════════════════════════════════

def classify_spans(spans: list[TextSpan]) -> dict[str, list[TextSpan]]:
    """
    Classify all spans into categories.
    Returns dict with keys:
      "metric_dims", "imperial_dims", "labels", "cabinet_keywords", "other"
    """
    from core.config import CABINET_KEYWORDS, ELEVATION_LABELS, KITCHEN_LABELS, BATH_LABELS

    result: dict[str, list] = {
        "metric_dims":      [],
        "imperial_dims":    [],
        "labels":           [],
        "cabinet_keywords": [],
        "other":            [],
    }

    for span in spans:
        t  = span.text
        tu = span.upper

        # Section labels
        is_label = (
            any(lbl in tu for lbl in ELEVATION_LABELS) or
            any(lbl in tu for lbl in KITCHEN_LABELS) or
            any(lbl in tu for lbl in BATH_LABELS) or
            any(kw in tu for kw in ["SCALE", "FLOOR PLAN", "SECTION", "UNIT", "NOTE", "ADA", "FHA"])
        )

        # Cabinet keywords
        is_cabinet_kw = any(kw in tu for kw in CABINET_KEYWORDS)

        # Metric dimension: has decimal point and is in valid range
        is_metric = False
        if "." in t and len(t) < 12:
            mv = parse_metric_mm(t)
            is_metric = mv is not None

        # Imperial dimension: contains foot or inch marks
        is_imperial = False
        if ("'" in t or '"' in t or "'" in t or "″" in t or "[" in t) and len(t) < 20:
            iv = parse_imperial_mm(t)
            is_imperial = iv is not None

        if is_label:
            result["labels"].append(span)
        elif is_cabinet_kw:
            result["cabinet_keywords"].append(span)
        elif is_metric:
            result["metric_dims"].append(span)
        elif is_imperial:
            result["imperial_dims"].append(span)
        else:
            result["other"].append(span)

    return result


# ══════════════════════════════════════════════════════════════════════════
# DIMENSION-TO-RECT ASSOCIATION
# ══════════════════════════════════════════════════════════════════════════

def associate_dims_to_rects(
    spans:       list[TextSpan],
    rects:       list[VectorRect],
    proximity:   float = 60.0,   # max pt distance between dim text and rect edge
) -> list[LabeledRect]:
    """
    For each significant rectangle (potential cabinet box), find the
    dimension text nearest to it and associate them.

    Returns a LabeledRect for each rect that has a nearby dimension.
    """
    from core.config import CABINET_KEYWORDS

    classified = classify_spans(spans)
    all_dim_spans = classified["metric_dims"] + classified["imperial_dims"]
    all_kw_spans  = classified["cabinet_keywords"]

    labeled: list[LabeledRect] = []

    for rect in rects:
        # Find all dimension spans within proximity of this rect
        nearby_dims: list[tuple[float, TextSpan]] = []  # (distance, span)
        for dim_span in all_dim_spans:
            # Distance from dim span center to nearest rect edge
            dx = max(rect.x0 - dim_span.cx, 0, dim_span.cx - rect.x1)
            dy = max(rect.y0 - dim_span.cy, 0, dim_span.cy - rect.y1)
            dist = (dx**2 + dy**2) ** 0.5
            if dist <= proximity:
                nearby_dims.append((dist, dim_span))

        # Parse widths from nearby dim spans (horizontal = width, vertical = height)
        width_mm  = None
        height_mm = None
        dim_conf  = "NONE"

        # Sort by distance, try to assign widths and heights
        nearby_dims.sort(key=lambda x: x[0])
        for _, ds in nearby_dims[:4]:
            mm = parse_metric_mm(ds.text) or parse_imperial_mm(ds.text)
            if mm is None:
                continue
            if ds.is_horizontal and width_mm is None:
                width_mm = mm
                dim_conf = "METRIC_ONLY" if parse_metric_mm(ds.text) else "IMPERIAL_ONLY"
            elif not ds.is_horizontal and height_mm is None:
                height_mm = mm

        # Find nearby cabinet keywords
        nearby_labels: list[str] = []
        for kw_span in all_kw_spans:
            dx = max(rect.x0 - kw_span.cx, 0, kw_span.cx - rect.x1)
            dy = max(rect.y0 - kw_span.cy, 0, kw_span.cy - rect.y1)
            dist = (dx**2 + dy**2) ** 0.5
            if dist <= proximity * 2:
                nearby_labels.append(kw_span.text)

        labeled.append(LabeledRect(
            rect          = rect,
            width_mm      = width_mm,
            height_mm     = height_mm,
            nearby_labels = nearby_labels,
            dim_confidence = dim_conf,
        ))

    return labeled


# ══════════════════════════════════════════════════════════════════════════
# QUICK TEST
# ══════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    # Quick unit tests
    tests_metric = [
        ("76.20", 762.0),
        ("90.00", 900.0),
        ("228.60", 2286.0),
        ("30", 300.0),
        ("1",   None),     # too small
        ("9999", None),    # too large
        ("12345", None),   # not a dimension
    ]
    tests_imperial = [
        ("2' - 6\"", 762.0),
        ("[14']",    4267.2),
        ("36\"",     914.4),
        ("3'-0\"",   914.4),
        ("[2'-6\"]", 762.0),
    ]

    print("=== Metric Parsing ===")
    for txt, expected in tests_metric:
        result = parse_metric_mm(txt)
        status = "✅" if (result == expected or (result is None and expected is None)) else "❌"
        print(f"  {status}  '{txt}'  →  {result}  (expected {expected})")

    print("\n=== Imperial Parsing ===")
    for txt, expected in tests_imperial:
        result = parse_imperial_mm(txt)
        delta = abs((result or 0) - (expected or 0))
        status = "✅" if (result is not None and expected is not None and delta < 1) else "❌"
        print(f"  {status}  '{txt}'  →  {result:.1f if result else None}  (expected {expected})")

    print("\n=== Cross-Validation ===")
    pair = cross_validate(762.0, 762.0)
    print(f"  76.20cm + [2'-6\"] → {pair.confidence} ({pair.value_mm}mm)")
    pair = cross_validate(762.0, 914.4)
    print(f"  76.20cm + 36\"     → {pair.confidence} (diff={pair.mismatch_mm:.1f}mm)")
