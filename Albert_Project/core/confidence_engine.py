"""
===========================================================================
  core/confidence_engine.py — QA Confidence Engine
===========================================================================
  Runs rule-based validation checks on extracted metadata models to calculate
  overall QA score and list warning items.
===========================================================================
"""
from __future__ import annotations

from typing import List, Dict, Any
from core.ai_vision_classifier import CabinetItem, ElevationResult

class ConfidenceEngine:
    """
    Computes quality metrics and reports warning flags on takeoff outcomes.
    """

    @staticmethod
    def evaluate(elevation: ElevationResult) -> dict:
        """
        Runs checks and returns:
        {
          "confidence_score": 0.85,
          "needs_review": False,
          "warnings": []
        }
        """
        warnings = []
        cabinets = elevation.cabinets

        # 1. Base confidence
        base_confidence = elevation.avg_confidence if cabinets else 1.0
        
        # 2. Check: Duplicate keynote ID
        ids = [c.cabinet_id for c in cabinets if c.cabinet_id]
        if len(ids) != len(set(ids)):
            warnings.append("Duplicate keynote ID detected in same elevation run")
            base_confidence -= 0.1

        # 3. Check: Base/Upper alignment
        base_count = sum(1 for c in cabinets if c.cabinet_type in ("base", "sink_base", "dw_adjacent"))
        upper_count = sum(1 for c in cabinets if c.cabinet_type in ("upper_wall", "microwave_shelf"))
        if base_count == 0 and upper_count > 0:
            warnings.append("Elevation has upper cabinets but no matching base run support")
            base_confidence -= 0.15

        # 4. Check: ADA constraints
        if elevation.is_ada:
            for cab in cabinets:
                if cab.cabinet_type in ("base", "sink_base", "vanity") and cab.height_mm > 864:
                    warnings.append(f"ADA Unit contains cabinet {cab.code} exceeding 864mm height limit")
                    base_confidence -= 0.1

        # 5. Check: Sink/Range matching
        sink_count = sum(1 for c in cabinets if c.cabinet_type == "sink_base")
        if sink_count > 1:
            warnings.append("Multiple sink base cabinets found in single run")
            base_confidence -= 0.05

        final_score = max(0.0, min(1.0, base_confidence))
        needs_review = final_score < 0.80 or len(warnings) > 0

        return {
            "confidence_score": round(final_score, 2),
            "needs_review": needs_review,
            "warnings": warnings
        }
