"""
===========================================================================
  core/cabinet_graph_builder.py — Spatial Layout Graph Builder
===========================================================================
  Constructs the spatial layout graph of cabinets, appliances, and openings.
  Calculates offsets, identifies adjacency, and builds the target schemas.
===========================================================================
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional
from core.ai_vision_classifier import CabinetItem, ElevationResult

class CabinetGraphBuilder:
    """
    Constructs spatial relationship graphs from elevation classification results
    and builds the standard deliverables.
    """

    def __init__(self):
        pass

    def build_shop_drawing_schema(
        self,
        unit_type: str,
        elevations: list[ElevationResult],
        kitchen_type: str,
        bathroom_type: str,
        layout_shape: str = "straight"
    ) -> dict:
        """
        Builds the shop drawing JSON schema.
        """
        walls_list = []
        appliances_list = []
        ceiling_height = 108.0

        for ev in elevations:
            # Standardize wall label name from elevation label
            wall_name = ev.elevation_label.replace("ELEVATION ", "").strip()
            # If the label is KITCHEN or BATH, use a friendly shorthand
            if wall_name.upper() in ("KITCHEN", "BATH", "VANITY", "MASTER_BATH"):
                wall_name = "A"

            # Parse ceiling height if reported
            if ev.ceiling_height_in is not None:
                ceiling_height = ev.ceiling_height_in

            # Build wall info
            # 1. Base run sequence
            # Standardize cabinet items
            base_items = []
            upper_items = []
            
            for cab in ev.cabinets:
                # convert width_mm to inches
                w_in = round(cab.width_mm / 25.4)
                h_in = round(cab.height_mm / 25.4)
                d_in = round(cab.depth_mm / 25.4)
                cid = cab.cabinet_id or cab.code

                cab_dict = {
                    "id": cid,
                    "type": cab.cabinet_type,
                    "width": w_in,
                    "height": h_in,
                    "depth": d_in,
                    "cabinet_type": cab.cabinet_type,
                    "notes": cab.notes,
                    "is_ada": cab.is_ada
                }
                
                if cab.cabinet_type in ("upper_wall", "microwave_shelf", "corner_upper", "medicine_cabinet"):
                    upper_items.append(cab_dict)
                else:
                    base_items.append(cab_dict)

            # Sequence base run
            base_x = 0
            sequenced_base_cabs = []
            for b in base_items:
                b["x"] = base_x
                sequenced_base_cabs.append(b)
                
                # If it's an appliance space, also add it to the appliances list
                if b["type"] == "appliance_space" or b["cabinet_type"] == "appliance_space":
                    # Determine type of appliance
                    app_type = "REF"
                    for t in ["REF", "DW", "RANGE", "MIC", "HOOD", "OVEN"]:
                        if t in b["notes"].upper() or t in b["id"].upper():
                            app_type = t
                            break
                    appliances_list.append({
                        "type": app_type,
                        "wall": wall_name,
                        "x": base_x,
                        "width": b["width"]
                    })
                base_x += b["width"]

            # Sequence upper run
            upper_x = 0
            sequenced_upper_cabs = []
            for u in upper_items:
                u["x"] = upper_x
                sequenced_upper_cabs.append(u)
                upper_x += u["width"]

            # Combine all sequenced cabinets
            # Standardize output cabinets format: id, x, width, height
            all_cabs_output = []
            for c in sequenced_base_cabs + sequenced_upper_cabs:
                if c["type"] != "appliance_space":
                    all_cabs_output.append({
                        "id": c["id"],
                        "x": c["x"],
                        "width": c["width"],
                        "height": c["height"]
                    })

            # Process openings
            doors_output = []
            for d in ev.doors:
                doors_output.append({
                    "x": d.get("x_in", 0),
                    "width": d.get("width_in", 36),
                    "height": d.get("height_in", 80)
                })

            windows_output = []
            for w in ev.windows:
                windows_output.append({
                    "x": w.get("x_in", 0),
                    "width": w.get("width_in", 36),
                    "height": w.get("height_in", 48),
                    "sill_height": w.get("sill_height_in", 36)
                })

            wall_length = max(base_x, upper_x)
            if wall_length == 0:
                wall_length = 90.0  # default wall length

            walls_list.append({
                "name": wall_name,
                "length": wall_length,
                "doors": doors_output,
                "windows": windows_output,
                "cabinets": all_cabs_output
            })

        # Try to parse appliances list directly from elevations if none added from base run
        if not appliances_list:
            for ev in elevations:
                wall_name = ev.elevation_label.replace("ELEVATION ", "").strip()
                if wall_name.upper() in ("KITCHEN", "BATH", "VANITY", "MASTER_BATH"):
                    wall_name = "A"
                for app in ev.appliances:
                    appliances_list.append({
                        "type": app.get("type", "REF"),
                        "wall": wall_name,
                        "x": app.get("x_in", 0),
                        "width": app.get("width_in", 36)
                    })

        # Normalize layout shape
        layout_map = {
            "K1": "single_wall",
            "K2": "l_shape",
            "K3": "galley"
        }
        layout_name = layout_map.get(kitchen_type, layout_shape.lower())

        return {
            "unit": unit_type,
            "kitchen_type": kitchen_type,
            "layout": layout_name,
            "ceiling_height": ceiling_height,
            "walls": walls_list,
            "appliances": appliances_list
        }

    def build_cost_schema(
        self,
        unit_type: str,
        elevations: list[ElevationResult],
        is_ada: bool = False
    ) -> dict:
        """
        Builds the cost estimation JSON schema.
        """
        cabinets_summary = {}
        fillers = []
        panels = []
        moldings = []
        special_items = []
        
        countertop_in = 0.0
        upper_cabinet_in = 0.0
        pantry_count = 0
        has_island = False

        for ev in elevations:
            # Aggregate cabinets count
            for cab in ev.cabinets:
                w_in = round(cab.width_mm / 25.4)
                cid = cab.cabinet_id or cab.code
                
                # Check for special properties
                if cab.cabinet_type == "pantry":
                    pantry_count += 1
                if "island" in cab.location.lower() or "island" in cab.notes.lower():
                    has_island = True

                # Skip appliance spaces and fillers in primary cabinet list
                if cab.cabinet_type == "appliance_space":
                    continue

                if cab.cabinet_type == "filler":
                    # track filler keynotes (e.g. F3)
                    fillers.append(cid)
                    continue

                cabinets_summary[cid] = cabinets_summary.get(cid, 0) + cab.quantity

                # Calculate linear feet dimensions
                if cab.cabinet_type in ("upper_wall", "microwave_shelf", "corner_upper"):
                    upper_cabinet_in += w_in * cab.quantity
                elif cab.cabinet_type in ("base", "sink_base", "dw_adjacent", "vanity"):
                    countertop_in += w_in * cab.quantity

            # Gather other filler/panel/molding lists from elevation metadata
            for f in ev.fillers:
                if f not in fillers:
                    fillers.append(f)
            for p in ev.panels:
                if p not in panels:
                    panels.append(p)
            for m in ev.moldings:
                if m not in moldings:
                    moldings.append(m)

        # Build final cabinet list format
        cabinets_list = [
            {"code": code, "qty": qty}
            for code, qty in sorted(cabinets_summary.items())
        ]

        # Calculate linear feet (inches / 12)
        countertop_lf = round(countertop_in / 12.0, 1)
        upper_cabinet_lf = round(upper_cabinet_in / 12.0, 1)

        # Detect special items
        if is_ada:
            special_items.append("ADA")
        if pantry_count > 0:
            special_items.append("Pantry")
        if has_island:
            special_items.append("Island")

        # Determine installation complexity
        total_boxes = sum(c["qty"] for c in cabinets_list)
        if has_island or (pantry_count > 0 and is_ada) or total_boxes > 15:
            complexity = "high"
        elif total_boxes >= 8 or is_ada:
            complexity = "medium"
        else:
            complexity = "low"

        return {
            "unit_type": unit_type,
            "cabinets": cabinets_list,
            "countertop_lf": countertop_lf,
            "upper_cabinet_lf": upper_cabinet_lf,
            "fillers": fillers,
            "panels": panels,
            "moldings": moldings,
            "special_items": special_items,
            "installation_complexity": complexity
        }
