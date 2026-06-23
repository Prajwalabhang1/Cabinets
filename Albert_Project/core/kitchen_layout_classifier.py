"""
===========================================================================
  core/kitchen_layout_classifier.py — Kitchen Type Classifier
===========================================================================
  Generates a layout signature for a kitchen and maps it to a canonical
  kitchen type (e.g., K1, K2).
===========================================================================
"""
from __future__ import annotations

from typing import Any


class KitchenLayoutClassifier:
    """
    Classifies kitchen layouts and maps them to K-types.
    """

    def __init__(self):
        # Maps signature -> type name (e.g., "K1")
        self.signature_to_type: dict[str, str] = {}
        self.type_counter = 0

    def get_kitchen_type(self, walls: list[dict], appliances: list[dict], layout_shape: str) -> str:
        """
        Generate a unique signature and return the K-type (e.g. "K1").
        """
        # 1. Build appliance sequence
        # Group appliances and sink cabinets by wall and sort horizontally
        appliance_seqs = []
        for wall in walls:
            wall_name = wall["name"]
            wall_items = []
            
            # Find appliances on this wall
            for app in appliances:
                if app["wall"] == wall_name:
                    wall_items.append((app["x"], app["type"]))
            
            # Find sink base or range cabinets on this wall from cabinets
            for cab in wall.get("cabinets", []):
                # Check if it has a sink/range keyword or ID mapping
                cid = cab.get("id", "").upper()
                c_type = cab.get("type", "").lower()
                # Some cabinets are mapped to keynotes representing sinks/ranges
                if "SINK" in c_type or cid in ("U9", "U2"):  # U9/U2 are often sink/range in keynotes
                    wall_items.append((cab["x"], "SINK"))
            
            # Sort by x coordinate
            wall_items.sort(key=lambda item: item[0])
            seq = "-".join(item[1] for item in wall_items)
            if seq:
                appliance_seqs.append(f"Wall_{wall_name}:{seq}")

        appliance_seq_str = "; ".join(appliance_seqs) if appliance_seqs else "NONE"

        # 2. Wall lengths string
        lengths = []
        for wall in sorted(walls, key=lambda w: w["name"]):
            length_in = wall.get("length", 0)
            lengths.append(f"{wall['name']}:{length_in:.0f}\"")
        lengths_str = ", ".join(lengths)

        # 3. Form final signature
        signature = f"{appliance_seq_str} | {layout_shape} | {lengths_str}"

        # 4. Check/register signature
        if signature in self.signature_to_type:
            return self.signature_to_type[signature]
        else:
            self.type_counter += 1
            type_name = f"K{self.type_counter}"
            self.signature_to_type[signature] = type_name
            return type_name
