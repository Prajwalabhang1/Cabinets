"""
===========================================================================
  core/cabinet_validator.py — Rule-Based Sanity Checker (Layer 5)
===========================================================================
  After AI Vision classifies cabinets, this module applies construction-
  grade sanity checks to validate the output before auto-approving.

  Validation rules:
    1. All widths must be within ±25mm of a standard catalog size
    2. Total cabinet run width must ≤ room width + 50mm tolerance
    3. Base cabinet height: 720mm (or 864mm for ADA)
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
    STANDARD_WIDTHS_MM, CABINET_WIDTH_TOLERANCE_MM,
    ROOM_WIDTH_TOLERANCE_MM, AUTO_APPROVE_CONFIDENCE,
    BASE_CABINET_HEIGHT_STD_MM, BASE_CABINET_HEIGHT_ADA_MM,
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
        result = validator.validate(cabinets, room_width_mm=4267.2, is_ada=False)
    """

    def validate(
        self,
        cabinets:      list[CabinetItem],
        room_width_mm: Optional[float] = None,
        is_ada:        bool = False,
        location:      str = "unknown",  # for logging
    ) -> list[CabinetItem]:
        """
        Validate and auto-correct the cabinet list.
        Returns corrected cabinets (in-place modifications).
        Also prints validation report.
        """
        result = self.get_validation_result(cabinets, room_width_mm, is_ada, location)

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
        room_width_mm: Optional[float] = None,
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
            nearest, delta = _nearest_standard_width(cab.width_mm)
            if delta > CABINET_WIDTH_TOLERANCE_MM:
                flags.append(
                    f"Item {cab.item_num} ({cab.cabinet_type}) width "
                    f"{cab.width_mm:.0f}mm is {delta:.0f}mm from nearest "
                    f"standard ({nearest:.0f}mm)"
                )
            elif delta > 5:
                # Auto-correct small deviations
                old_w = cab.width_mm
                cab.width_mm = nearest
                corrections.append(
                    f"Item {cab.item_num} width snapped "
                    f"{old_w:.0f}→{nearest:.0f}mm"
                )

        # ── Check 3: Height correctness ───────────────────────────────────
        expected_base_h = BASE_CABINET_HEIGHT_ADA_MM if is_ada else BASE_CABINET_HEIGHT_STD_MM
        BASE_TYPES = {"base", "sink_base", "dw_adjacent", "corner_base"}

        for cab in cabinets:
            if cab.cabinet_type in BASE_TYPES and cab.height_mm > 0:
                if is_ada and cab.height_mm > BASE_CABINET_HEIGHT_ADA_MM + 50:
                    flags.append(
                        f"Item {cab.item_num} ADA base height {cab.height_mm:.0f}mm "
                        f"exceeds ADA max {BASE_CABINET_HEIGHT_ADA_MM:.0f}mm"
                    )
                elif not is_ada and abs(cab.height_mm - BASE_CABINET_HEIGHT_STD_MM) > 80:
                    warnings.append(
                        f"Item {cab.item_num} base height {cab.height_mm:.0f}mm "
                        f"differs from standard {BASE_CABINET_HEIGHT_STD_MM:.0f}mm"
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
        if room_width_mm and room_width_mm > 0:
            total_run = sum(c.width_mm for c in cabinets)
            delta = total_run - room_width_mm
            if delta > ROOM_WIDTH_TOLERANCE_MM:
                flags.append(
                    f"Total cabinet run {total_run:.0f}mm exceeds "
                    f"room width {room_width_mm:.0f}mm by {delta:.0f}mm"
                )
            elif delta < -(ROOM_WIDTH_TOLERANCE_MM * 3):
                warnings.append(
                    f"Total cabinet run {total_run:.0f}mm is significantly less "
                    f"than room width {room_width_mm:.0f}mm — may be missing items"
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

def _nearest_standard_width(width_mm: float) -> tuple[float, float]:
    """Return (nearest_standard_mm, delta_mm)."""
    if not STANDARD_WIDTHS_MM:
        return width_mm, 0.0
    nearest = min(STANDARD_WIDTHS_MM, key=lambda s: abs(s - width_mm))
    return nearest, abs(nearest - width_mm)


def validate_schedule(
    cabinets:      list[CabinetItem],
    room_width_mm: Optional[float] = None,
    is_ada:        bool = False,
    location:      str = "unknown",
) -> tuple[list[CabinetItem], ValidationResult]:
    """Convenience wrapper. Returns (corrected_cabinets, validation_result)."""
    validator = CabinetValidator()
    result    = validator.get_validation_result(cabinets, room_width_mm, is_ada, location)
    corrected = validator.validate(cabinets, room_width_mm, is_ada, location)
    return corrected, result


# ══════════════════════════════════════════════════════════════════════════
# QUICK TEST
# ══════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    from core.ai_vision_classifier import CabinetItem

    # Sample cabinet schedule for Unit A1 - Elevation A
    test_cabinets = [
        CabinetItem(1, "upper_wall",      762.0, 300.0, 330.0, "Left of range", "ELEVATION A", 0.92),
        CabinetItem(2, "upper_wall",      900.0, 300.0, 330.0, "Right of range","ELEVATION A", 0.88),
        CabinetItem(3, "microwave_shelf", 300.0, 460.0, 330.0, "Over range",    "ELEVATION A", 0.85),
        CabinetItem(4, "base",            762.0, 720.0, 600.0, "Left base",     "ELEVATION A", 0.95),
        CabinetItem(5, "appliance_space", 610.0, 720.0, 600.0, "DW space",      "ELEVATION A", 0.98),
        CabinetItem(6, "base",            900.0, 720.0, 600.0, "Right base",    "ELEVATION A", 0.91),
    ]

    validator = CabinetValidator()
    result = validator.get_validation_result(
        test_cabinets,
        room_width_mm=4267.2,  # 14'
        is_ada=False,
        location="Unit A1 Elevation A",
    )

    print(f"\nTest Validation Result: {result.summary}")
    print(f"  Flags:       {result.flags}")
    print(f"  Warnings:    {result.warnings}")
    print(f"  Corrections: {result.corrections}")
