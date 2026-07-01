from typing import Dict, List, Any
from core.engines.appliance_library import ApplianceLibrary
from core.engines.dimension_engine import DimensionEngine

class FloorPlanGenerator:
    """Generates the Kitchen/Vanity Floor Plan geometry."""
    
    @staticmethod
    def generate(walls: List[Dict], start_ox: float, start_oy: float, scale_factor: float = 4.0) -> Dict[str, List]:
        geom = {"lines": [], "blocks": [], "texts": [], "dimensions": []}
        
        plan_ox = start_ox
        plan_oy = start_oy
        
        for w_idx, wall in enumerate(walls):
            wall_length = wall.get("length", 90.0)
            cabinets = wall.get("cabinets", [])
            
            if w_idx > 0:
                prev_length = walls[w_idx - 1].get("length", 90.0)
                offset_x = (prev_length * scale_factor) + 100.0
                plan_ox += offset_x
                
            # Draw wall with thickness
            wall_depth = 6.0 * scale_factor
            wall_len = wall_length * scale_factor
            
            geom["blocks"].append({
                "type": "rect",
                "coords": [plan_ox, plan_oy, wall_len, wall_depth],
                "id": "", "layer": "WALLS", "style": "solid"
            })
            
            # Label the wall plan view
            geom["texts"].append({
                "pos": [plan_ox + wall_len/2.0 - 15.0, plan_oy - 20.0],
                "text": f"{wall.get('name', 'WALL')} PLAN VIEW",
                "layer": "TEXT"
            })
            
            # TODO: Wall Hatch can be represented by diagonal lines
            # For now, just thick outline is drawn above
            
            cab_x_curr = 0.0
            dim_items = []
            
            for cab in cabinets:
                cab_id = cab.get("cabinet_id", "Cab")
                cab_type = cab.get("cabinet_type", cab.get("type", "")).lower()
                cab_w = cab.get("width", 0.0)
                cab_d = cab.get("depth", 24.0)
                if cab_d <= 0:
                    cab_d = 24.0
                    
                is_upper = cab_id.upper().startswith("W") or "upper" in cab_type
                is_sink = "sink" in cab_type or cab_id.upper().startswith("SB")
                is_range = "range" in cab_type or "range" in cab_id.lower() or "cooktop" in cab_id.lower()
                is_ref = "ref" in cab_type or "refrigerator" in cab_id.lower()
                is_dw = "dw" in cab_type or "dishwasher" in cab_id.lower()
                
                dim_items.append({"width": cab_w})
                
                x0 = plan_ox + cab_x_curr * scale_factor
                y0 = plan_oy + wall_depth
                
                if is_upper:
                    # Draw dashed hidden overhead footprint
                    geom["blocks"].append({
                        "type": "rect",
                        "coords": [x0, y0, cab_w * scale_factor, cab_d * scale_factor],
                        "id": cab_id, "layer": "CABINETS_UPPER", "style": "dashed"
                    })
                else:
                    # Base footprint
                    geom["blocks"].append({
                        "type": "rect",
                        "coords": [x0, y0, cab_w * scale_factor, cab_d * scale_factor],
                        "id": cab_id, "layer": "CABINETS_BASE", "style": "solid"
                    })
                    
                    if is_sink:
                        sink_geom = ApplianceLibrary.draw_sink_plan(x0, y0, cab_w, cab_d, scale_factor, scale_factor)
                        geom["blocks"].extend(sink_geom["blocks"])
                        geom["lines"].extend(sink_geom["lines"])
                    elif is_range:
                        rng_geom = ApplianceLibrary.draw_range_plan(x0, y0, cab_w, cab_d, scale_factor, scale_factor)
                        geom["blocks"].extend(rng_geom["blocks"])
                        geom["lines"].extend(rng_geom["lines"])
                    elif is_ref:
                        geom["texts"].append({"pos": [x0 + (cab_w*scale_factor)/2, y0 + (cab_d*scale_factor)/2], "text": "REF", "size": 4.0, "layer": "TEXT"})
                    elif is_dw:
                        geom["texts"].append({"pos": [x0 + (cab_w*scale_factor)/2, y0 + (cab_d*scale_factor)/2], "text": "D/W", "size": 4.0, "layer": "TEXT"})
                
                cab_x_curr += cab_w
                
            # Add Horizontal Chain Dimension
            chain_dims = DimensionEngine.generate_horizontal_chain(dim_items, plan_ox, plan_oy + wall_depth + 30.0 * scale_factor, scale_factor)
            geom["dimensions"].extend(chain_dims)
            
            # Add Overall Dimension
            geom["dimensions"].append(DimensionEngine.generate_overall_dimensions(
                [plan_ox, plan_oy + wall_depth + 38.0 * scale_factor],
                [plan_ox + wall_length * scale_factor, plan_oy + wall_depth + 38.0 * scale_factor],
                wall_length
            ))

        return geom
