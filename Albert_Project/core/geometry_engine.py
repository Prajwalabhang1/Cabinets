"""
===========================================================================
  core/geometry_engine.py — High-Fidelity 2D CAD Layouts Engine
===========================================================================
  Translates sequenced cabinets, appliances, and openings into detailed
  architectural 2D lines, dimensions, texts, and swing annotations.
===========================================================================
"""
from __future__ import annotations

import math
from typing import List, Dict, Any, Optional
from fractions import Fraction

class GeometryEngine:
    """
    Builds plan views and detailed elevation views coordinates.
    All dimensions inside this engine use inches.
    """

    def __init__(self):
        # Coordinates offsets inside GeometryEngine space
        self.GE_PLAN_OX = 250.0
        self.GE_PLAN_OY = 450.0
        self.GE_ELEV_OX = 250.0
        self.GE_ELEV_OY = 150.0
        self.GE_SIDE_OX = 250.0
        self.GE_SIDE_OY = 150.0

    def _make_double_dim(self, inches: float) -> str:
        """Helper to format inches to Metric [Imperial] format (e.g. 76.20 [2'-6"])."""
        if inches <= 0.01:
            return ""
        # Convert inches to cm
        cm = inches * 2.54
        
        # Convert inches to feet and remainder inches
        feet = int(inches // 12)
        rem_inches = inches % 12
        
        # Round remainder inches to nearest 1/16
        rounded_rem = round(rem_inches * 16) / 16
        
        # Format imperial part
        if feet > 0:
            whole_in = int(rounded_rem)
            frac = rounded_rem - whole_in
            if frac < 0.01:
                imp_str = f"{feet}'-{whole_in}\"" if whole_in > 0 else f"{feet}'"
            else:
                frac_str = str(Fraction(frac))
                imp_str = f"{feet}'-{whole_in} {frac_str}\"" if whole_in > 0 else f"{feet}'-{frac_str}\""
        else:
            whole_in = int(rounded_rem)
            frac = rounded_rem - whole_in
            if frac < 0.01:
                imp_str = f"{whole_in}\""
            else:
                frac_str = str(Fraction(frac))
                imp_str = f"{whole_in} {frac_str}\"" if whole_in > 0 else f"{frac_str}\""
                
        return f"{cm:.2f} [{imp_str}]"

    def generate_layout_geometry(
        self,
        walls: list[dict],
        appliances: list[dict],
        ceiling_height: float = 108.0,
        soffit_height: float = 96.0
    ) -> dict:
        """
        Processes wall runs to generate plan and elevation geometries.
        Returns:
        {
          "plan": { "lines": [], "dimensions": [], "blocks": [], "texts": [] },
          "elevation": { "lines": [], "dimensions": [], "blocks": [], "texts": [] }
        }
        """
        plan_geom = {"lines": [], "dimensions": [], "blocks": [], "texts": []}
        elev_geom = {"lines": [], "dimensions": [], "blocks": [], "texts": []}
        side_geom = {"lines": [], "dimensions": [], "blocks": [], "texts": []}

        # Origin offsets
        plan_ox = self.GE_PLAN_OX
        plan_oy = self.GE_PLAN_OY
        elev_ox = self.GE_ELEV_OX
        elev_oy = self.GE_ELEV_OY
        side_ox = self.GE_SIDE_OX
        side_oy = self.GE_SIDE_OY

        for w_idx, wall in enumerate(walls):
            wall_name = wall.get("name", "A")
            wall_length = wall.get("length", 90.0)
            cabinets = wall.get("cabinets", [])
            
            if w_idx > 0:
                prev_length = walls[w_idx - 1].get("length", 90.0)
                offset_x = (prev_length * 4.0) + 100.0
                plan_ox += offset_x
                elev_ox += offset_x
                side_ox += offset_x
            
            # --- Plan View Construction ---
            # 1. Back wall line and solid thick wall + hatch pattern (6" depth)
            plan_geom["lines"].append({
                "start": [plan_ox, plan_oy],
                "end": [plan_ox + wall_length * 4.0, plan_oy],
                "layer": "WALLS",
                "style": "solid"
            })
            plan_geom["lines"].append({
                "start": [plan_ox, plan_oy + 6.0 * 4.0],
                "end": [plan_ox + wall_length * 4.0, plan_oy + 6.0 * 4.0],
                "layer": "WALLS",
                "style": "solid"
            })
            # Draw cross-hatches in wall cut
            for hx in range(0, int(wall_length), 4):
                plan_geom["lines"].append({
                    "start": [plan_ox + hx * 4.0, plan_oy],
                    "end": [plan_ox + (hx + 4) * 4.0, plan_oy + 6.0 * 4.0],
                    "layer": "WALLS_HATCH",
                    "style": "solid"
                })
                
            # 2. Countertop boundary (25" depth standard)
            ct_d = 25.0
            plan_geom["lines"].append({
                "start": [plan_ox, plan_oy - ct_d * 4.0],
                "end": [plan_ox + wall_length * 4.0, plan_oy - ct_d * 4.0],
                "layer": "COUNTERTOP",
                "style": "solid"
            })
            # Double line for front edge lip
            plan_geom["lines"].append({
                "start": [plan_ox, plan_oy - (ct_d - 1.0) * 4.0],
                "end": [plan_ox + wall_length * 4.0, plan_oy - (ct_d - 1.0) * 4.0],
                "layer": "COUNTERTOP",
                "style": "solid"
            })
            
            # 3. Draw cabinets in Plan
            for cab in cabinets:
                cab_x = cab.get("x", 0.0)
                cab_w = cab.get("width", 12.0)
                cab_id = cab.get("id", "CAB")
                cab_type = cab.get("cabinet_type", cab.get("type", "")).lower()
                
                is_upper = cab_id.upper().startswith("W") or "upper" in cab_type
                is_sink = "sink" in cab_type or cab_id.upper().startswith("SB")
                is_range = "range" in cab_type or "range" in cab_id.lower() or "cooktop" in cab_id.lower()
                is_ref = "ref" in cab_type or "refrigerator" in cab_id.lower() or "ref" in cab_id.lower()
                is_dw = "dw" in cab_type or "dishwasher" in cab_id.lower() or "dw" in cab_id.lower()

                depth = 12.0 if is_upper else (30.0 if is_ref else 24.0)
                layer = "CABINETS_UPPER" if is_upper else "CABINETS_BASE"
                style = "dashed" if is_upper else "solid"

                # Cabinet box
                x0 = plan_ox + cab_x * 4.0
                x1 = x0 + cab_w * 4.0
                y0 = plan_oy
                y1 = plan_oy - depth * 4.0

                plan_geom["blocks"].append({
                    "type": "rect",
                    "coords": [x0, y1, x1 - x0, y0 - y1],
                    "id": cab_id,
                    "layer": layer,
                    "style": style
                })

                # Visual Details
                if is_sink:
                    # Draw double sink bowl
                    sw = (cab_w - 6.0) * 4.0
                    sd = 15.0 * 4.0
                    sx0 = x0 + 3.0 * 4.0
                    sy0 = plan_oy - 4.0 * 4.0
                    # Outer bowl
                    plan_geom["blocks"].append({
                        "type": "rect",
                        "coords": [sx0, sy0 - sd, sw, sd],
                        "id": "",
                        "layer": "SINK",
                        "style": "solid"
                    })
                    # Double bowl separator
                    plan_geom["lines"].append({
                        "start": [sx0 + sw/2, sy0],
                        "end": [sx0 + sw/2, sy0 - sd],
                        "layer": "SINK",
                        "style": "solid"
                    })
                    # Faucet point
                    plan_geom["lines"].append({
                        "start": [sx0 + sw/2, sy0 + 1.0 * 4.0],
                        "end": [sx0 + sw/2, sy0 - 2.0 * 4.0],
                        "layer": "SINK",
                        "style": "solid"
                    })
                elif is_range:
                    # Draw 4 circles for cooktop burners
                    r_burner = 2.5 * 4.0
                    cx1 = x0 + (cab_w / 4.0) * 4.0
                    cx2 = x0 + (cab_w * 3.0 / 4.0) * 4.0
                    cy1 = plan_oy - 7.0 * 4.0
                    cy2 = plan_oy - 17.0 * 4.0
                    for cx, cy in [(cx1, cy1), (cx1, cy2), (cx2, cy1), (cx2, cy2)]:
                        # Represent circle via cross lines for standard compatibility
                        plan_geom["lines"].append({
                            "start": [cx - r_burner, cy], "end": [cx + r_burner, cy],
                            "layer": "BURNERS", "style": "solid"
                        })
                        plan_geom["lines"].append({
                            "start": [cx, cy - r_burner], "end": [cx, cy + r_burner],
                            "layer": "BURNERS", "style": "solid"
                        })
                elif is_ref:
                    # Draw refrigerator handles on the front edge
                    plan_geom["lines"].append({
                        "start": [x0 + 4.0, y1],
                        "end": [x1 - 4.0, y1],
                        "layer": "APPLIANCES",
                        "style": "solid"
                    })
                    plan_geom["texts"].append({
                        "pos": [(x0 + x1) / 2, (y0 + y1) / 2],
                        "text": "REFRIGERATOR",
                        "size": 4.5,
                        "layer": "TEXT"
                    })
                elif is_dw:
                    plan_geom["texts"].append({
                        "pos": [(x0 + x1) / 2, (y0 + y1) / 2],
                        "text": "DISHWASHER",
                        "size": 4.5,
                        "layer": "TEXT"
                    })

                # Dimension labels inside boxes
                if not is_ref and not is_dw:
                    plan_geom["texts"].append({
                        "pos": [(x0 + x1) / 2, (y0 + y1) / 2 - 2.0],
                        "text": f"{cab_id}\n{cab_w}\"",
                        "size": 4.0,
                        "layer": layer
                    })

            # Running dimension string at top of plan
            plan_geom["dimensions"].append({
                "start": [plan_ox, plan_oy + 14.0 * 4.0],
                "end": [plan_ox + wall_length * 4.0, plan_oy + 14.0 * 4.0],
                "text": self._make_double_dim(wall_length)
            })
            
            # --- Elevation View Construction ---
            # 1. Ground floor line
            elev_geom["lines"].append({
                "start": [elev_ox - 10.0, elev_oy],
                "end": [elev_ox + wall_length * 4.0 + 10.0, elev_oy],
                "layer": "GROUND",
                "style": "solid"
            })
            
            # 2. Toe kick line (4" height AFF)
            elev_geom["lines"].append({
                "start": [elev_ox, elev_oy + 4.0 * 3.0],
                "end": [elev_ox + wall_length * 4.0, elev_oy + 4.0 * 3.0],
                "layer": "CABINETS_BASE",
                "style": "solid"
            })
            
            # 3. Countertop lines (34.5" to 36.0" AFF)
            elev_geom["lines"].append({
                "start": [elev_ox, elev_oy + 34.5 * 3.0],
                "end": [elev_ox + wall_length * 4.0, elev_oy + 34.5 * 3.0],
                "layer": "COUNTERTOP",
                "style": "solid"
            })
            elev_geom["lines"].append({
                "start": [elev_ox, elev_oy + 36.0 * 3.0],
                "end": [elev_ox + wall_length * 4.0, elev_oy + 36.0 * 3.0],
                "layer": "COUNTERTOP",
                "style": "solid"
            })
            
            # 4. Ceiling line
            elev_geom["lines"].append({
                "start": [elev_ox - 10.0, elev_oy + ceiling_height * 3.0],
                "end": [elev_ox + wall_length * 4.0 + 10.0, elev_oy + ceiling_height * 3.0],
                "layer": "CEILING",
                "style": "solid"
            })

            # 5. Draw cabinets in Elevation
            for cab in cabinets:
                cab_x = cab.get("x", 0.0)
                cab_w = cab.get("width", 12.0)
                cab_h = cab.get("height", 30.0)
                cab_id = cab.get("id", "CAB")
                cab_type = cab.get("cabinet_type", cab.get("type", "")).lower()
                
                is_upper = cab_id.upper().startswith("W") or "upper" in cab_type
                is_pantry = cab_id.upper().startswith("T") or "pantry" in cab_type
                is_sink = "sink" in cab_type or cab_id.upper().startswith("SB")
                is_range = "range" in cab_type or "range" in cab_id.lower() or "cooktop" in cab_id.lower()
                is_ref = "ref" in cab_type or "refrigerator" in cab_id.lower() or "ref" in cab_id.lower()
                is_dw = "dw" in cab_type or "dishwasher" in cab_id.lower() or "dw" in cab_id.lower()
                is_drawer = "dwr" in cab_id.lower() or "drawer" in cab_type or "drawers" in cab.get("notes", "").lower()

                # Coordinate height offsets
                if is_pantry:
                    y0 = elev_oy + 4.0 * 3.0
                    y1 = elev_oy + cab_h * 3.0
                elif is_upper:
                    y0 = elev_oy + 54.0 * 3.0
                    y1 = y0 + cab_h * 3.0
                else:
                    # standard base cabinet starts above 4" toe kick, ends at 34.5" box height
                    y0 = elev_oy + 4.0 * 3.0
                    y1 = elev_oy + 34.5 * 3.0

                x0 = elev_ox + cab_x * 4.0
                x1 = x0 + cab_w * 4.0

                if is_ref:
                    # Refrigerator stands on floor and goes up to 72" AFF typically
                    y0_ref = elev_oy
                    y1_ref = elev_oy + 72.0 * 3.0
                    elev_geom["blocks"].append({
                        "type": "rect",
                        "coords": [x0, y0_ref, x1 - x0, y1_ref - y0_ref],
                        "id": cab_id,
                        "layer": "APPLIANCES",
                        "style": "solid"
                    })
                    # Refrigerator doors dividing vertical line
                    elev_geom["lines"].append({
                        "start": [x0 + (x1 - x0)/2, y0_ref],
                        "end": [x0 + (x1 - x0)/2, y1_ref],
                        "layer": "APPLIANCES",
                        "style": "solid"
                    })
                    # Refrigerator handles
                    elev_geom["lines"].append({
                        "start": [x0 + (x1 - x0)/2 - 1.5, y0_ref + 30.0 * 3.0],
                        "end": [x0 + (x1 - x0)/2 - 1.5, y0_ref + 48.0 * 3.0],
                        "layer": "APPLIANCES",
                        "style": "solid"
                    })
                    elev_geom["lines"].append({
                        "start": [x0 + (x1 - x0)/2 + 1.5, y0_ref + 30.0 * 3.0],
                        "end": [x0 + (x1 - x0)/2 + 1.5, y0_ref + 48.0 * 3.0],
                        "layer": "APPLIANCES",
                        "style": "solid"
                    })
                    elev_geom["texts"].append({
                        "pos": [(x0 + x1) / 2, (y0_ref + y1_ref) / 2],
                        "text": f"REFRIGERATOR\n{cab_w}\"W",
                        "size": 4.5,
                        "layer": "TEXT"
                    })
                elif is_dw:
                    # Dishwasher front panel
                    elev_geom["blocks"].append({
                        "type": "rect",
                        "coords": [x0, y0, x1 - x0, y1 - y0],
                        "id": "D/W",
                        "layer": "APPLIANCES",
                        "style": "solid"
                    })
                    # Control panel line at top of D/W
                    elev_geom["lines"].append({
                        "start": [x0, y1 - 4.0 * 3.0],
                        "end": [x1, y1 - 4.0 * 3.0],
                        "layer": "APPLIANCES",
                        "style": "solid"
                    })
                    elev_geom["texts"].append({
                        "pos": [(x0 + x1) / 2, (y0 + y1) / 2],
                        "text": f"D/W\n{cab_w}\"W",
                        "size": 4.5,
                        "layer": "TEXT"
                    })
                elif is_range:
                    # Cooktop / Range stove
                    # Draw stove box standing on ground Y=0, ending at Y=36 (counter level)
                    y1_stove = elev_oy + 36.0 * 3.0
                    elev_geom["blocks"].append({
                        "type": "rect",
                        "coords": [x0, elev_oy, x1 - x0, y1_stove - elev_oy],
                        "id": "STOVE",
                        "layer": "APPLIANCES",
                        "style": "solid"
                    })
                    # Oven glass window
                    elev_geom["blocks"].append({
                        "type": "rect",
                        "coords": [x0 + 4.0, elev_oy + 8.0 * 3.0, (cab_w - 8.0) * 4.0, 14.0 * 3.0],
                        "id": "",
                        "layer": "APPLIANCES",
                        "style": "solid"
                    })
                    # Dials/control panel line at top
                    elev_geom["lines"].append({
                        "start": [x0, y1_stove - 3.0 * 3.0],
                        "end": [x1, y1_stove - 3.0 * 3.0],
                        "layer": "APPLIANCES",
                        "style": "solid"
                    })
                    elev_geom["texts"].append({
                        "pos": [(x0 + x1) / 2, y1_stove - 1.5 * 3.0],
                        "text": "RANGE",
                        "size": 4.5,
                        "layer": "TEXT"
                    })
                elif is_drawer:
                    # Draw 3-drawer layout
                    elev_geom["blocks"].append({
                        "type": "rect",
                        "coords": [x0, y0, x1 - x0, y1 - y0],
                        "id": cab_id,
                        "layer": "CABINETS_BASE",
                        "style": "solid"
                    })
                    # Draw horizontal dividers
                    dy1 = y0 + 7.0 * 3.0
                    dy2 = y0 + 17.0 * 3.0
                    elev_geom["lines"].append({
                        "start": [x0, dy1], "end": [x1, dy1],
                        "layer": "CABINETS_BASE", "style": "solid"
                    })
                    elev_geom["lines"].append({
                        "start": [x0, dy2], "end": [x1, dy2],
                        "layer": "CABINETS_BASE", "style": "solid"
                    })
                    # Draw drawer handles
                    for h_y in [(y0 + dy1)/2, (dy1 + dy2)/2, (dy2 + y1)/2]:
                        elev_geom["lines"].append({
                            "start": [(x0 + x1)/2 - 3.0, h_y],
                            "end": [(x0 + x1)/2 + 3.0, h_y],
                            "layer": "HANDLES",
                            "style": "solid"
                        })
                else:
                    # Standard Cabinet Box
                    layer = "CABINETS_UPPER" if is_upper else "CABINETS_BASE"
                    elev_geom["blocks"].append({
                        "type": "rect",
                        "coords": [x0, y0, x1 - x0, y1 - y0],
                        "id": cab_id,
                        "layer": layer,
                        "style": "solid"
                    })

                    # Door divides and swing indicators (triangle dashes)
                    if cab_w > 21.0:
                        # Double door divide
                        xm = (x0 + x1) / 2
                        elev_geom["lines"].append({
                            "start": [xm, y0],
                            "end": [xm, y1],
                            "layer": layer,
                            "style": "solid"
                        })
                        # Left door swing triangle
                        elev_geom["lines"].append({
                            "start": [x0, y0], "end": [xm, (y0 + y1) / 2],
                            "layer": "SWING", "style": "dashed"
                        })
                        elev_geom["lines"].append({
                            "start": [x0, y1], "end": [xm, (y0 + y1) / 2],
                            "layer": "SWING", "style": "dashed"
                        })
                        # Right door swing triangle
                        elev_geom["lines"].append({
                            "start": [x1, y0], "end": [xm, (y0 + y1) / 2],
                            "layer": "SWING", "style": "dashed"
                        })
                        elev_geom["lines"].append({
                            "start": [x1, y1], "end": [xm, (y0 + y1) / 2],
                            "layer": "SWING", "style": "dashed"
                        })
                        # Handles in the center
                        elev_geom["lines"].append({
                            "start": [xm - 1.0, (y0 + y1)/2 - 3.0],
                            "end": [xm - 1.0, (y0 + y1)/2 + 3.0],
                            "layer": "HANDLES", "style": "solid"
                        })
                        elev_geom["lines"].append({
                            "start": [xm + 1.0, (y0 + y1)/2 - 3.0],
                            "end": [xm + 1.0, (y0 + y1)/2 + 3.0],
                            "layer": "HANDLES", "style": "solid"
                        })
                    else:
                        # Single door swing (left hinged hinge swing lines)
                        elev_geom["lines"].append({
                            "start": [x0, y0], "end": [x1, (y0 + y1) / 2],
                            "layer": "SWING", "style": "dashed"
                        })
                        elev_geom["lines"].append({
                            "start": [x0, y1], "end": [x1, (y0 + y1) / 2],
                            "layer": "SWING", "style": "dashed"
                        })
                        # Handle on the right side
                        elev_geom["lines"].append({
                            "start": [x1 - 1.5, (y0 + y1)/2 - 3.0],
                            "end": [x1 - 1.5, (y0 + y1)/2 + 3.0],
                            "layer": "HANDLES", "style": "solid"
                        })

                    # Label
                    elev_geom["texts"].append({
                        "pos": [(x0 + x1) / 2, (y0 + y1) / 2],
                        "text": f"{cab_id}\n{cab_w}\"x{cab_h}\"",
                        "size": 4.0,
                        "layer": "TEXT"
                    })

                # Dimension markers at bottom of cabinet box
                elev_geom["dimensions"].append({
                    "start": [x0, elev_oy - 10.0],
                    "end": [x1, elev_oy - 10.0],
                    "text": self._make_double_dim(cab_w)
                })

            # Running horizontal dimensions at top of elevation view
            elev_geom["dimensions"].append({
                "start": [elev_ox, elev_oy + (ceiling_height + 10.0) * 3.0],
                "end": [elev_ox + wall_length * 4.0, elev_oy + (ceiling_height + 10.0) * 3.0],
                "text": self._make_double_dim(wall_length)
            })

            # Vertical dimensions on the left of elevation
            v_dims = [
                (0.0, 4.0, "4\""),
                (4.0, 34.5, "30.5\""),
                (34.5, 36.0, "1.5\""),
                (36.0, 54.0, "18\""),
                (54.0, 54.0 + 30.0, "30\""), # assuming standard 30" upper
                (0.0, ceiling_height, f"{ceiling_height:.0f}\" clg")
            ]
            for start_aff, end_aff, dim_txt in v_dims:
                elev_geom["dimensions"].append({
                    "start": [elev_ox - 24.0, elev_oy + start_aff * 3.0],
                    "end": [elev_ox - 24.0, elev_oy + end_aff * 3.0],
                    "text": dim_txt
                })

            # --- Side View (Section) Construction ---
            # 1. Ground line (floor)
            side_geom["lines"].append({
                "start": [side_ox - 5.0 * 4.0, side_oy],
                "end": [side_ox + 35.0 * 4.0, side_oy],
                "layer": "GROUND",
                "style": "solid"
            })
            
            # 2. Back wall line
            side_geom["lines"].append({
                "start": [side_ox, side_oy],
                "end": [side_ox, side_oy + ceiling_height * 3.0],
                "layer": "WALLS",
                "style": "solid"
            })
            # Draw standard wall hatching on the left of the wall (e.g. from X=-6" to X=0)
            side_geom["lines"].append({
                "start": [side_ox - 6.0 * 4.0, side_oy],
                "end": [side_ox - 6.0 * 4.0, side_oy + ceiling_height * 3.0],
                "layer": "WALLS",
                "style": "solid"
            })
            for hx in range(0, int(ceiling_height), 12):
                side_geom["lines"].append({
                    "start": [side_ox - 6.0 * 4.0, side_oy + hx * 3.0],
                    "end": [side_ox, side_oy + (hx + 8) * 3.0],
                    "layer": "WALLS_HATCH",
                    "style": "solid"
                })
            
            # 3. Ceiling line
            side_geom["lines"].append({
                "start": [side_ox - 5.0 * 4.0, side_oy + ceiling_height * 3.0],
                "end": [side_ox + 35.0 * 4.0, side_oy + ceiling_height * 3.0],
                "layer": "CEILING",
                "style": "solid"
            })
            
            # 4. Check what cabinet types are on this wall
            has_base = False
            has_upper = False
            has_pantry = False
            has_vanity = False
            
            base_h = 34.5
            upper_h = 30.0
            pantry_h = 84.0
            vanity_h = 34.5
            
            for cab in cabinets:
                cab_id = cab.get("id", "").upper()
                cab_type = cab.get("type", "").lower() or cab.get("cabinet_type", "").lower()
                
                is_upper = cab_id.startswith("W") or "upper" in cab_type
                is_pantry = cab_id.startswith("T") or "pantry" in cab_type
                is_vanity = cab_id.startswith("VAN") or "vanity" in cab_type
                
                if is_pantry:
                    has_pantry = True
                    pantry_h = max(pantry_h, cab.get("height", 84.0))
                elif is_upper:
                    has_upper = True
                    upper_h = max(upper_h, cab.get("height", 30.0))
                elif is_vanity:
                    has_vanity = True
                    vanity_h = max(vanity_h, cab.get("height", 34.5))
                else:
                    has_base = True
                    base_h = max(base_h, cab.get("height", 34.5))
            
            # 5. Draw base cabinet or vanity section
            if has_vanity:
                van_d = 21.0
                # Draw vanity outline
                side_geom["blocks"].append({
                    "type": "rect",
                    "coords": [side_ox, side_oy + 4.0 * 3.0, van_d * 4.0, (vanity_h - 4.0) * 3.0],
                    "id": "",
                    "layer": "CABINETS_BASE",
                    "style": "solid"
                })
                # Toe kick (3" deep, 4" high)
                side_geom["lines"].append({
                    "start": [side_ox + (van_d - 3.0) * 4.0, side_oy],
                    "end": [side_ox + (van_d - 3.0) * 4.0, side_oy + 4.0 * 3.0],
                    "layer": "CABINETS_BASE",
                    "style": "solid"
                })
                side_geom["lines"].append({
                    "start": [side_ox + (van_d - 3.0) * 4.0, side_oy + 4.0 * 3.0],
                    "end": [side_ox + van_d * 4.0, side_oy + 4.0 * 3.0],
                    "layer": "CABINETS_BASE",
                    "style": "solid"
                })
                # Countertop (22" deep, 1.5" thickness)
                side_geom["blocks"].append({
                    "type": "rect",
                    "coords": [side_ox, side_oy + vanity_h * 3.0, (van_d + 1.0) * 4.0, 1.5 * 3.0],
                    "id": "",
                    "layer": "COUNTERTOP",
                    "style": "solid"
                })
                # Backsplash
                side_geom["blocks"].append({
                    "type": "rect",
                    "coords": [side_ox, side_oy + (vanity_h + 1.5) * 3.0, 0.75 * 4.0, 4.0 * 3.0],
                    "id": "",
                    "layer": "COUNTERTOP",
                    "style": "solid"
                })
            elif has_base:
                base_d = 24.0
                # Draw base outline
                side_geom["blocks"].append({
                    "type": "rect",
                    "coords": [side_ox, side_oy + 4.0 * 3.0, base_d * 4.0, (base_h - 4.0) * 3.0],
                    "id": "",
                    "layer": "CABINETS_BASE",
                    "style": "solid"
                })
                # Toe kick (3" deep, 4" high)
                side_geom["lines"].append({
                    "start": [side_ox + (base_d - 3.0) * 4.0, side_oy],
                    "end": [side_ox + (base_d - 3.0) * 4.0, side_oy + 4.0 * 3.0],
                    "layer": "CABINETS_BASE",
                    "style": "solid"
                })
                side_geom["lines"].append({
                    "start": [side_ox + (base_d - 3.0) * 4.0, side_oy + 4.0 * 3.0],
                    "end": [side_ox + base_d * 4.0, side_oy + 4.0 * 3.0],
                    "layer": "CABINETS_BASE",
                    "style": "solid"
                })
                # Countertop (25" deep, 1.5" thickness)
                side_geom["blocks"].append({
                    "type": "rect",
                    "coords": [side_ox, side_oy + base_h * 3.0, (base_d + 1.0) * 4.0, 1.5 * 3.0],
                    "id": "",
                    "layer": "COUNTERTOP",
                    "style": "solid"
                })
                # Backsplash
                side_geom["blocks"].append({
                    "type": "rect",
                    "coords": [side_ox, side_oy + (base_h + 1.5) * 3.0, 0.75 * 4.0, 18.0 * 3.0],
                    "id": "",
                    "layer": "COUNTERTOP",
                    "style": "solid"
                })
                
            # 6. Draw pantry/tall cabinet section
            if has_pantry:
                pantry_d = 24.0
                # Outline
                side_geom["blocks"].append({
                    "type": "rect",
                    "coords": [side_ox, side_oy + 4.0 * 3.0, pantry_d * 4.0, (pantry_h - 4.0) * 3.0],
                    "id": "",
                    "layer": "CABINETS_BASE",
                    "style": "solid"
                })
                # Toe kick (3" deep, 4" high)
                side_geom["lines"].append({
                    "start": [side_ox + (pantry_d - 3.0) * 4.0, side_oy],
                    "end": [side_ox + (pantry_d - 3.0) * 4.0, side_oy + 4.0 * 3.0],
                    "layer": "CABINETS_BASE",
                    "style": "solid"
                })
                side_geom["lines"].append({
                    "start": [side_ox + (pantry_d - 3.0) * 4.0, side_oy + 4.0 * 3.0],
                    "end": [side_ox + pantry_d * 4.0, side_oy + 4.0 * 3.0],
                    "layer": "CABINETS_BASE",
                    "style": "solid"
                })
                
            # 7. Draw upper cabinet section
            if has_upper:
                upper_d = 12.0
                # Outline
                side_geom["blocks"].append({
                    "type": "rect",
                    "coords": [side_ox, side_oy + 54.0 * 3.0, upper_d * 4.0, upper_h * 3.0],
                    "id": "",
                    "layer": "CABINETS_UPPER",
                    "style": "solid"
                })
                
            # 8. Add side view text labels
            side_geom["texts"].append({
                "pos": [side_ox + 15.0 * 4.0, side_oy - 15.0],
                "text": "SIDE SECTION",
                "size": 5.0,
                "layer": "TEXT"
            })
            
            # 9. Add dimension strings
            # Vertical dimension strings (left side of wall)
            # Toe kick: 4"
            side_geom["dimensions"].append({
                "start": [side_ox - 10.0, side_oy],
                "end": [side_ox - 10.0, side_oy + 4.0 * 3.0],
                "text": "4\""
            })
            # Base/Vanity cabinet box
            box_h = vanity_h if has_vanity else base_h
            side_geom["dimensions"].append({
                "start": [side_ox - 10.0, side_oy + 4.0 * 3.0],
                "end": [side_ox - 10.0, side_oy + box_h * 3.0],
                "text": f"{(box_h - 4.0):.1f}\""
            })
            # Countertop: 1.5"
            side_geom["dimensions"].append({
                "start": [side_ox - 10.0, side_oy + box_h * 3.0],
                "end": [side_ox - 10.0, side_oy + (box_h + 1.5) * 3.0],
                "text": "1 1/2\""
            })
            # Splash space: 18" (or 4" for vanity)
            splash_h = 4.0 if has_vanity else 18.0
            side_geom["dimensions"].append({
                "start": [side_ox - 10.0, side_oy + (box_h + 1.5) * 3.0],
                "end": [side_ox - 10.0, side_oy + (box_h + 1.5 + splash_h) * 3.0],
                "text": f"{splash_h:.0f}\""
            })
            # Upper box
            if has_upper:
                side_geom["dimensions"].append({
                    "start": [side_ox - 10.0, side_oy + 54.0 * 3.0],
                    "end": [side_ox - 10.0, side_oy + (54.0 + upper_h) * 3.0],
                    "text": f"{upper_h:.0f}\""
                })
            # Ceiling height total
            side_geom["dimensions"].append({
                "start": [side_ox - 22.0, side_oy],
                "end": [side_ox - 22.0, side_oy + ceiling_height * 3.0],
                "text": f"{ceiling_height:.0f}\" CLG"
            })
            
            # Horizontal depth dimensions
            if has_base:
                side_geom["dimensions"].append({
                    "start": [side_ox, side_oy + (base_h + 1.5) * 3.0 + 8.0],
                    "end": [side_ox + 25.0 * 4.0, side_oy + (base_h + 1.5) * 3.0 + 8.0],
                    "text": "25\""
                })
            if has_vanity:
                side_geom["dimensions"].append({
                    "start": [side_ox, side_oy + (vanity_h + 1.5) * 3.0 + 8.0],
                    "end": [side_ox + 22.0 * 4.0, side_oy + (vanity_h + 1.5) * 3.0 + 8.0],
                    "text": "22\""
                })
            if has_upper:
                side_geom["dimensions"].append({
                    "start": [side_ox, side_oy + (54.0 + upper_h) * 3.0 + 8.0],
                    "end": [side_ox + 12.0 * 4.0, side_oy + (54.0 + upper_h) * 3.0 + 8.0],
                    "text": "12\""
                })

        return {
            "plan": plan_geom,
            "elevation": elev_geom,
            "side": side_geom
        }
