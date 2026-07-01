from typing import Dict, List, Any
from core.engines.appliance_library import ApplianceLibrary
from core.engines.dimension_engine import DimensionEngine
from core.engines.cabinet_renderer import CabinetRendererFactory
from core.engines.cabinet_library_resolver import CabinetLibraryResolver

class ElevationGenerator:
    """Generates the Kitchen/Vanity Elevation geometry."""
    
    @staticmethod
    def generate(walls: List[Dict], start_ox: float, start_oy: float, ceiling_height: float = 108.0, scale_x: float = 4.0, scale_y: float = 3.0) -> Dict[str, List]:
        geom = {"lines": [], "blocks": [], "texts": [], "dimensions": []}
        
        elev_ox = start_ox
        elev_oy = start_oy
        
        for w_idx, wall in enumerate(walls):
            wall_length = wall.get("length", 90.0)
            cabinets = wall.get("cabinets", [])
            
            if w_idx > 0:
                prev_length = walls[w_idx - 1].get("length", 90.0)
                offset_x = (prev_length * scale_x) + 100.0
                elev_ox += offset_x
                
            # Label the elevation view
            geom["texts"].append({
                "pos": [elev_ox + wall_length/2.0 - 15.0, elev_oy - 20.0],
                "text": f"{wall.get('name', 'WALL')} ELEVATION VIEW",
                "layer": "TEXT"
            })
                
            wall_has_ada = any(cab.get("is_ada", False) for cab in cabinets)
            max_base_h = 32.5 if wall_has_ada else 34.5
            
            cab_x_curr = 0.0
            dim_items = []
            
            for cab in cabinets:
                cab_id = cab.get("cabinet_id", cab.get("id", "Cab"))
                
                # Normalize cabinet using Phase 1 Resolver
                resolved = CabinetLibraryResolver.resolve_cabinet(cab_id)
                
                # Prefer dimensions from the schedule
                cab_w = cab.get("width", cab.get("width_in", 0.0))
                if cab_w <= 0: cab_w = resolved["width"]
                
                cab_h = cab.get("height", cab.get("height_in", 0.0))
                if cab_h <= 0: cab_h = resolved["height"]
                
                family = resolved["family"]
                cab_type = cab.get("cabinet_type", cab.get("type", "")).lower()
                
                # Override family based on explicit cabinet_type
                if 'upper' in cab_type or 'wall' in cab_type:
                    family = 'UPPER'
                elif 'pantry' in cab_type or 'tall' in cab_type:
                    family = 'TALL'
                
                dim_items.append({"width": cab_w})
                
                is_upper = family == 'UPPER'
                is_pantry = family == 'TALL'
                is_sink = resolved["render_style"] == 'sink_base' or 'sink' in cab_type
                is_drawer = resolved["render_style"] == 'drawer_base' or 'drawer' in cab_type
                render_style = resolved["render_style"]
                
                # Appliances are still a bit hardcoded or can be resolved
                is_range = "range" in cab_type or "range" in cab_id.lower() or "cooktop" in cab_id.lower()
                is_ref = "ref" in cab_type or "refrigerator" in cab_id.lower() or "appliance" in cab_type
                is_dw = "dw" in cab_type or "dishwasher" in cab_id.lower()
                is_ada = cab.get("is_ada", False)
                
                x0 = elev_ox + cab_x_curr * scale_x
                x1 = x0 + cab_w * scale_x
                
                # Height positioning
                if is_pantry:
                    y0 = elev_oy + 4.0 * scale_y
                    y1 = elev_oy + cab_h * scale_y
                elif is_upper:
                    aff = 48.0 if is_ada else 54.0
                    y0 = elev_oy + aff * scale_y
                    y1 = y0 + cab_h * scale_y
                else:
                    actual_h = cab_h if cab_h > 0 else max_base_h
                    y0 = elev_oy + 4.0 * scale_y
                    y1 = elev_oy + actual_h * scale_y

                # Appliances vs Cabinets
                if is_ref:
                    app_geom = ApplianceLibrary.draw_refrigerator_elevation(x0, elev_oy, cab_w, scale_x, scale_y)
                    geom["blocks"].extend(app_geom["blocks"])
                    geom["lines"].extend(app_geom["lines"])
                    geom["texts"].extend(app_geom["texts"])
                elif is_dw:
                    app_geom = ApplianceLibrary.draw_dishwasher_elevation(x0, y0, cab_w, y1 - y0, scale_x, scale_y)
                    geom["blocks"].extend(app_geom["blocks"])
                    geom["lines"].extend(app_geom["lines"])
                    geom["texts"].extend(app_geom["texts"])
                elif is_range:
                    app_geom = ApplianceLibrary.draw_range_elevation(x0, elev_oy, cab_w, scale_x, scale_y)
                    geom["blocks"].extend(app_geom["blocks"])
                    geom["lines"].extend(app_geom["lines"])
                    geom["texts"].extend(app_geom["texts"])
                else:
                    cab_geom = CabinetRendererFactory.render_elevation(
                        cab, x0, y0, x1, y1, is_upper, is_pantry, is_drawer, render_style, scale_x, scale_y
                    )
                    geom["blocks"].extend(cab_geom["blocks"])
                    geom["lines"].extend(cab_geom["lines"])
                    geom["texts"].extend(cab_geom["texts"])
                    
                    if is_sink:
                        sink_geom = ApplianceLibrary.draw_sink_elevation(x0, y1, cab_w, scale_x, scale_y)
                        geom["lines"].extend(sink_geom["lines"])

                # Toe kicks for standard base cabinets (recessed by 3" on sides usually, but in elevation we just draw a box)
                if not is_upper and not is_pantry and not is_ref and not is_range and render_style != 'panel':
                    geom["blocks"].append({
                        "type": "rect",
                        "coords": [x0, elev_oy, x1 - x0, y0 - elev_oy],
                        "layer": "CABINETS_BASE",
                        "style": "solid"
                    })

                cab_x_curr += cab_w
                
            # Horizontal Dimensions
            geom["dimensions"].extend(DimensionEngine.generate_horizontal_chain(dim_items, elev_ox, elev_oy - 10.0, scale_x))
            geom["dimensions"].append(DimensionEngine.generate_overall_dimensions(
                [elev_ox, elev_oy + (ceiling_height + 10.0) * scale_y],
                [elev_ox + wall_length * scale_x, elev_oy + (ceiling_height + 10.0) * scale_y],
                wall_length
            ))
            
            # Thick Wall Border
            w_len_scale = wall_length * scale_x
            c_height_scale = ceiling_height * scale_y
            geom["lines"].append({"start": [elev_ox, elev_oy], "end": [elev_ox + w_len_scale, elev_oy], "layer": "WALLS", "style": "continuous"})
            geom["lines"].append({"start": [elev_ox + w_len_scale, elev_oy], "end": [elev_ox + w_len_scale, elev_oy + c_height_scale], "layer": "WALLS", "style": "continuous"})
            geom["lines"].append({"start": [elev_ox + w_len_scale, elev_oy + c_height_scale], "end": [elev_ox, elev_oy + c_height_scale], "layer": "WALLS", "style": "continuous"})
            geom["lines"].append({"start": [elev_ox, elev_oy + c_height_scale], "end": [elev_ox, elev_oy], "layer": "WALLS", "style": "continuous"})
            
        return geom
