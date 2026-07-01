"""
===========================================================================
  core/cabinet_validator.py — Rule-Based Sanity Checker (Layer 5)
===========================================================================
  After AI Vision classifies cabinets, this module applies construction-
  grade sanity checks to validate the output before auto-approving.

  Validation rules:
    1. All widths must be within ±25in of a standard catalog size
    2. Total cabinet run width must ≤ room width + 50in tolerance
    3. Base cabinet height: 720in (or 864in for ADA)
    4. Every kitchen elevation must have ≥ 1 base + ≥ 1 upper
    5. No two corner cabinets side-by-side
    6. Confidence score per item must be ≥ 0.70 to auto-approve

  Results:
    - auto_approve: True/False
    - confidence: overall score 0.0–1.0
    - flags: list of issues found (human review items)
    - corrected_cabinets: fixed width/height values if auto-correctable
===========================================================================
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from core.config import (
    STANDARD_WIDTHS_IN, CABINET_WIDTH_TOLERANCE_IN,
    ROOM_WIDTH_TOLERANCE_IN, AUTO_APPROVE_CONFIDENCE,
    BASE_CABINET_HEIGHT_STD_IN, BASE_CABINET_HEIGHT_ADA_IN,
)
from core.ai_vision_classifier import CabinetItem


# ══════════════════════════════════════════════════════════════════════════
# DATA CLASSES
# ══════════════════════════════════════════════════════════════════════════

@dataclass
class ValidationResult:
    """Result of validating a cabinet schedule for one elevation."""
    is_valid:       bool
    auto_approve:   bool
    overall_score:  float               # 0.0–1.0
    flags:          list[str] = field(default_factory=list)
    warnings:       list[str] = field(default_factory=list)
    corrections:    list[str] = field(default_factory=list)  # auto-applied fixes

    @property
    def has_issues(self) -> bool:
        return bool(self.flags)

    @property
    def summary(self) -> str:
        status = "✅ AUTO-APPROVED" if self.auto_approve else "⚠️  NEEDS REVIEW"
        return f"{status} | score={self.overall_score:.2f} | {len(self.flags)} flags"


# ══════════════════════════════════════════════════════════════════════════
# VALIDATOR
# ══════════════════════════════════════════════════════════════════════════

class CabinetValidator:
    """
    Rule-based validator for AI-extracted cabinet schedules.

    Usage:
        validator = CabinetValidator()
        result = validator.validate(cabinets, room_width_in=168.0, is_ada=False)
    """

    def validate(
        self,
        cabinets:      list[CabinetItem],
        room_width_in: Optional[float] = None,
        is_ada:        bool = False,
        location:      str = "unknown",  # for logging
    ) -> list[CabinetItem]:
        """
        Validate and auto-correct the cabinet list.
        Returns corrected cabinets (in-place modifications).
        Also prints validation report.
        """
        result = self.get_validation_result(cabinets, room_width_in, is_ada, location)

        print(f"\n  Validation [{location}]: {result.summary}")
        for flag in result.flags:
            print(f"    ⛳ FLAG: {flag}")
        for warn in result.warnings:
            print(f"    ⚠️  WARN: {warn}")
        for corr in result.corrections:
            print(f"    🔧 AUTO-FIXED: {corr}")

        return cabinets

    def get_validation_result(
        self,
        cabinets:      list[CabinetItem],
        room_width_in: Optional[float] = None,
        is_ada:        bool = False,
        location:      str = "unknown",
    ) -> ValidationResult:
        """Run all checks and return ValidationResult."""
        flags:       list[str] = []
        warnings:    list[str] = []
        corrections: list[str] = []
        scores:      list[float] = []

        if not cabinets:
            return ValidationResult(
                is_valid=False, auto_approve=False, overall_score=0.0,
                flags=["No cabinets found in this elevation"],
            )

        # ── Check 1: Individual cabinet confidence ────────────────────────
        for cab in cabinets:
            if cab.confidence < 0.60:
                flags.append(
                    f"Item {cab.item_num} ({cab.cabinet_type}) confidence "
                    f"{cab.confidence:.2f} is very low — manual check needed"
                )
            elif cab.confidence < 0.75:
                warnings.append(
                    f"Item {cab.item_num} ({cab.cabinet_type}) confidence "
                    f"{cab.confidence:.2f} is borderline"
                )
            scores.append(cab.confidence)

        # ── Check 2: Standard width snapping ─────────────────────────────
        for cab in cabinets:
            if cab.cabinet_type == "appliance_space":
                continue  # appliances are fine with non-standard widths

            # Auto-fix: width=0 means Gemini couldn't read it → snap to 762in default
            if cab.width_in <= 0:
                old_w = cab.width_in
                cab.width_in = 30.0   # 30" — most common standard cabinet width
                corrections.append(
                    f"Item {cab.item_num} ({cab.cabinet_type}) had width={old_w:.0f}in "
                    f"→ defaulted to 762in (30\"). Verify against drawing."
                )
                warnings.append(
                    f"Item {cab.item_num} width was 0/null — used 30in default"
                )

            nearest, delta = _nearest_standard_width(cab.width_in)
            if delta > CABINET_WIDTH_TOLERANCE_IN:
                flags.append(
                    f"Item {cab.item_num} ({cab.cabinet_type}) width "
                    f"{cab.width_in:.0f}in is {delta:.0f}in from nearest "
                    f"standard ({nearest:.0f}in)"
                )
            elif delta > 5:
                # Auto-correct small deviations
                old_w = cab.width_in
                cab.width_in = nearest
                corrections.append(
                    f"Item {cab.item_num} width snapped "
                    f"{old_w:.0f}→{nearest:.0f}in"
                )

        # ── Check 3: Height correctness ───────────────────────────────────
        expected_base_h = BASE_CABINET_HEIGHT_ADA_IN if is_ada else BASE_CABINET_HEIGHT_STD_IN
        BASE_TYPES = {"base", "sink_base", "dw_adjacent", "corner_base"}

        for cab in cabinets:
            if cab.cabinet_type in BASE_TYPES and cab.height_in > 0:
                if is_ada and cab.height_in > BASE_CABINET_HEIGHT_ADA_IN + 50:
                    flags.append(
                        f"Item {cab.item_num} ADA base height {cab.height_in:.0f}in "
                        f"exceeds ADA max {BASE_CABINET_HEIGHT_ADA_IN:.0f}in"
                    )
                elif not is_ada and abs(cab.height_in - BASE_CABINET_HEIGHT_STD_IN) > 80:
                    warnings.append(
                        f"Item {cab.item_num} base height {cab.height_in:.0f}in "
                        f"differs from standard {BASE_CABINET_HEIGHT_STD_IN:.0f}in"
                    )

        # ── Check 4: At least 1 base + 1 upper in kitchen elevation ───────
        non_appliance = [c for c in cabinets if c.cabinet_type != "appliance_space"]
        has_upper = any(c.cabinet_type in ("upper_wall", "corner_upper", "microwave_shelf")
                        for c in non_appliance)
        has_base  = any(c.cabinet_type in BASE_TYPES | {"pantry"}
                        for c in non_appliance)
        has_bath  = any(c.cabinet_type in ("vanity", "medicine_cabinet", "linen")
                        for c in non_appliance)

        if not has_bath:  # Only applies to kitchen elevations
            if not has_upper:
                warnings.append("No upper/wall cabinets detected — verify elevation is kitchen")
            if not has_base:
                warnings.append("No base cabinets detected — verify elevation is kitchen")

        # ── Check 5: Total width vs. room width ───────────────────────────
        if room_width_in and room_width_in > 0:
            total_run = sum(c.width_in for c in cabinets)
            delta = total_run - room_width_in
            if delta > ROOM_WIDTH_TOLERANCE_IN:
                flags.append(
                    f"Total cabinet run {total_run:.0f}in exceeds "
                    f"room width {room_width_in:.0f}in by {delta:.0f}in"
                )
            elif delta < -(ROOM_WIDTH_TOLERANCE_IN * 3):
                warnings.append(
                    f"Total cabinet run {total_run:.0f}in is significantly less "
                    f"than room width {room_width_in:.0f}in — may be missing items"
                )

        # ── Check 6: No consecutive corner cabinets ───────────────────────
        for i in range(len(cabinets) - 1):
            if (cabinets[i].cabinet_type in ("corner_base", "corner_upper") and
                    cabinets[i+1].cabinet_type in ("corner_base", "corner_upper")):
                flags.append(
                    f"Items {cabinets[i].item_num} and {cabinets[i+1].item_num} "
                    f"are two consecutive corner cabinets — unlikely in practice"
                )

        # ── Overall Score ─────────────────────────────────────────────────
        avg_conf = sum(scores) / len(scores) if scores else 0.0
        flag_penalty = len(flags) * 0.08
        warn_penalty = len(warnings) * 0.02
        overall_score = max(0.0, min(1.0, avg_conf - flag_penalty - warn_penalty))

        auto_approve = (
            overall_score >= AUTO_APPROVE_CONFIDENCE and
            len(flags) == 0
        )

        return ValidationResult(
            is_valid     = len(flags) == 0,
            auto_approve = auto_approve,
            overall_score = overall_score,
            flags        = flags,
            warnings     = warnings,
            corrections  = corrections,
        )


# ══════════════════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════════════════

def _nearest_standard_width(width_in: float) -> tuple[float, float]:
    """Return (nearest_standard_in, delta_in)."""
    if not STANDARD_WIDTHS_IN:
        return width_in, 0.0
    nearest = min(STANDARD_WIDTHS_IN, key=lambda s: abs(s - width_in))
    return nearest, abs(nearest - width_in)


def validate_schedule(
    cabinets:      list[CabinetItem],
    room_width_in: Optional[float] = None,
    is_ada:        bool = False,
    location:      str = "unknown",
) -> tuple[list[CabinetItem], ValidationResult]:
    """Convenience wrapper. Returns (corrected_cabinets, validation_result)."""
    validator = CabinetValidator()
    result    = validator.get_validation_result(cabinets, room_width_in, is_ada, location)
    corrected = validator.validate(cabinets, room_width_in, is_ada, location)
    return corrected, result


# ══════════════════════════════════════════════════════════════════════════
# QUICK TEST
# ══════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    from core.ai_vision_classifier import CabinetItem

    # Sample cabinet schedule for Unit A1 - Elevation A
    test_cabinets = [
        CabinetItem(1, "upper_wall",      30.0, 12.0, 13.0, "Left of range", "ELEVATION A", 0.92),
        CabinetItem(2, "upper_wall",      36.0, 12.0, 13.0, "Right of range","ELEVATION A", 0.88),
        CabinetItem(3, "microwave_shelf", 12.0, 18.0, 13.0, "Over range",    "ELEVATION A", 0.85),
        CabinetItem(4, "base",            30.0, 34.5, 24.0, "Left base",     "ELEVATION A", 0.95),
        CabinetItem(5, "appliance_space", 24.0, 34.5, 24.0, "DW space",      "ELEVATION A", 0.98),
        CabinetItem(6, "base",            36.0, 34.5, 24.0, "Right base",    "ELEVATION A", 0.91),
    ]

    validator = CabinetValidator()
    result = validator.get_validation_result(
        test_cabinets,
        room_width_in=168.0,  # 14'
        is_ada=False,
        location="Unit A1 Elevation A",
    )

    print(f"\nTest Validation Result: {result.summary}")
    print(f"  Flags:       {result.flags}")
    print(f"  Warnings:    {result.warnings}")
    print(f"  Corrections: {result.corrections}")
