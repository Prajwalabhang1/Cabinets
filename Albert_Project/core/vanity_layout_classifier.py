"""
===========================================================================
  core/vanity_layout_classifier.py — Vanity Type Classifier
===========================================================================
  Generates a layout signature for a bathroom vanity and maps it to a
  canonical bathroom type (e.g., V1, V2).
===========================================================================
"""
from __future__ import annotations


class VanityLayoutClassifier:
    """
    Classifies vanity layouts and maps them to V-types.
    """

    def __init__(self):
        # Maps signature -> type name (e.g., "V1")
        self.signature_to_type: dict[str, str] = {}
        self.type_counter = 0

    def get_vanity_type(self, cabinets: list[dict], room_width_mm: float = 0.0) -> str:
        """
        Generate a unique signature and return the V-type (e.g. "V1").
        """
        # Find vanity cabinets and sum their widths
        vanity_cabs = [
            c for c in cabinets 
            if c.get("type") == "vanity" or "vanity" in c.get("type", "").lower()
        ]
        
        vanity_width_in = 0.0
        num_sinks = 0
        is_ada = False

        for vc in vanity_cabs:
            w_in = vc.get("width_mm", vc.get("width", 0) * 25.4) / 25.4
            vanity_width_in += w_in
            if vc.get("is_ada"):
                is_ada = True
            # Double vanity check from keynote or notes
            if "double" in vc.get("notes", "").lower() or "double" in vc.get("location", "").lower():
                num_sinks = 2

        if not vanity_cabs:
            # Fallback if no explicit vanity cabinets are detected
            signature = "NO_VANITY"
        else:
            if num_sinks == 0:
                num_sinks = 2 if vanity_width_in >= 48 else 1
            ada_str = "ADA" if is_ada else "STD"
            signature = f"VANITY | {vanity_width_in:.0f}\" | {num_sinks}SINK | {ada_str}"

        if signature in self.signature_to_type:
            return self.signature_to_type[signature]
        else:
            self.type_counter += 1
            type_name = f"V{self.type_counter}"
            self.signature_to_type[signature] = type_name
            return type_name
