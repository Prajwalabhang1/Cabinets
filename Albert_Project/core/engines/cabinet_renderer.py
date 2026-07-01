from typing import Dict, List, Any

class CabinetRendererFactory:
    """Renders cabinet geometry based on type, producing detailed architectural graphics."""

    @staticmethod
    def render_elevation(cab: Dict[str, Any], x0: float, y0: float, x1: float, y1: float, is_upper: bool, is_pantry: bool, is_drawer: bool, render_style: str = 'standard', scale_x: float = 1.0, scale_y: float = 1.0) -> Dict[str, List]:
        geom = {"lines": [], "blocks": [], "texts": []}
        layer = "CABINETS_UPPER" if is_upper else "CABINETS_BASE"
        cab_w = (x1 - x0) / scale_x
        cab_h = (y1 - y0) / scale_y
        
        # 1. Outer box (Face frame / carcass)
        geom["blocks"].append({
            "type": "rect",
            "coords": [x0, y0, x1 - x0, y1 - y0],
            "id": cab.get("cabinet_id", ""),
            "layer": layer,
            "style": "solid"
        })
        
        if render_style in ('filler', 'panel'):
            # Just return the solid box for a filler or panel, no doors/drawers
            return geom
            
        # 1.5 Face Frame Inner Edge (1.5" frame width)
        frame_w = 1.5 * scale_x
        geom["blocks"].append({
            "type": "rect",
            "coords": [x0 + frame_w, y0 + frame_w, (x1 - x0) - 2*frame_w, (y1 - y0) - 2*frame_w],
            "layer": layer,
            "style": "solid"
        })

        if is_drawer:
            # 3-drawer stack with fronts
            drawers = 3
            drawer_h = ((y1 - y0) - 2*frame_w) / drawers
            for i in range(drawers):
                dy_bottom = y0 + frame_w + i * drawer_h
                dy_top = dy_bottom + drawer_h
                
                # Drawer front gap (1/8")
                gap = 0.125 * scale_x
                geom["blocks"].append({
                    "type": "rect",
                    "coords": [x0 + frame_w + gap, dy_bottom + gap, (x1 - x0) - 2*(frame_w + gap), drawer_h - 2*gap],
                    "layer": "DOOR_PANEL",
                    "style": "solid"
                })
                
                # Handle
                hy = dy_bottom + drawer_h / 2
                geom["lines"].append({
                    "start": [(x0 + x1)/2 - 3.0 * scale_x, hy],
                    "end": [(x0 + x1)/2 + 3.0 * scale_x, hy],
                    "layer": "HANDLES", "style": "solid"
                })
                geom["blocks"].append({
                    "type": "circle",
                    "coords": [(x0 + x1)/2 - 3.0 * scale_x, hy, 0.2 * scale_x],
                    "layer": "HANDLES", "style": "solid"
                })
                geom["blocks"].append({
                    "type": "circle",
                    "coords": [(x0 + x1)/2 + 3.0 * scale_x, hy, 0.2 * scale_x],
                    "layer": "HANDLES", "style": "solid"
                })
        else:
            y1_door = y1 - frame_w
            
            # Top drawer for base cabinets
            drawer_h = 6.0 * scale_y
            if not is_upper and not is_pantry and cab_h > drawer_h + 3.0:
                dy_drawer = y1 - frame_w - drawer_h
                gap = 0.125 * scale_x
                
                # Drawer Front
                geom["blocks"].append({
                    "type": "rect",
                    "coords": [x0 + frame_w + gap, dy_drawer + gap, (x1 - x0) - 2*(frame_w + gap), drawer_h - 2*gap],
                    "layer": "DOOR_PANEL",
                    "style": "solid"
                })
                # Drawer Handle
                hy = dy_drawer + drawer_h/2
                geom["lines"].append({
                    "start": [(x0 + x1)/2 - 3.0 * scale_x, hy],
                    "end": [(x0 + x1)/2 + 3.0 * scale_x, hy],
                    "layer": "HANDLES", "style": "solid"
                })
                
                # Drawer separator line
                geom["lines"].append({"start": [x0 + frame_w, dy_drawer], "end": [x1 - frame_w, dy_drawer], "layer": layer, "style": "solid"})
                y1_door = dy_drawer
                
            # Doors
            gap = 0.125 * scale_x
            if cab_w > 21.0:
                # Double door
                xm = (x0 + x1) / 2
                # Left Door
                geom["blocks"].append({
                    "type": "rect",
                    "coords": [x0 + frame_w + gap, y0 + frame_w + gap, (xm - x0) - frame_w - 2*gap, (y1_door - y0) - frame_w - 2*gap],
                    "layer": "DOOR_PANEL", "style": "solid"
                })
                # Right Door
                geom["blocks"].append({
                    "type": "rect",
                    "coords": [xm + gap, y0 + frame_w + gap, (x1 - xm) - frame_w - 2*gap, (y1_door - y0) - frame_w - 2*gap],
                    "layer": "DOOR_PANEL", "style": "solid"
                })
                
                # Swings (Left Door)
                geom["lines"].append({"start": [x0 + frame_w, (y0 + y1_door) / 2], "end": [xm, y0 + frame_w], "layer": "SWING", "style": "dashed"})
                geom["lines"].append({"start": [x0 + frame_w, (y0 + y1_door) / 2], "end": [xm, y1_door - gap], "layer": "SWING", "style": "dashed"})
                # Swings (Right Door)
                geom["lines"].append({"start": [x1 - frame_w, (y0 + y1_door) / 2], "end": [xm, y0 + frame_w], "layer": "SWING", "style": "dashed"})
                geom["lines"].append({"start": [x1 - frame_w, (y0 + y1_door) / 2], "end": [xm, y1_door - gap], "layer": "SWING", "style": "dashed"})
                
                # Handles
                if is_upper:
                    geom["lines"].append({"start": [xm - 1.5 * scale_x, y0 + frame_w + 2.0 * scale_y], "end": [xm - 1.5 * scale_x, y0 + frame_w + 7.0 * scale_y], "layer": "HANDLES", "style": "solid"})
                    geom["lines"].append({"start": [xm + 1.5 * scale_x, y0 + frame_w + 2.0 * scale_y], "end": [xm + 1.5 * scale_x, y0 + frame_w + 7.0 * scale_y], "layer": "HANDLES", "style": "solid"})
                else:
                    geom["lines"].append({"start": [xm - 1.5 * scale_x, y1_door - 7.0 * scale_y], "end": [xm - 1.5 * scale_x, y1_door - 2.0 * scale_y], "layer": "HANDLES", "style": "solid"})
                    geom["lines"].append({"start": [xm + 1.5 * scale_x, y1_door - 7.0 * scale_y], "end": [xm + 1.5 * scale_x, y1_door - 2.0 * scale_y], "layer": "HANDLES", "style": "solid"})
            else:
                # Single door
                geom["blocks"].append({
                    "type": "rect",
                    "coords": [x0 + frame_w + gap, y0 + frame_w + gap, (x1 - x0) - 2*frame_w - 2*gap, (y1_door - y0) - frame_w - 2*gap],
                    "layer": "DOOR_PANEL", "style": "solid"
                })
                geom["lines"].append({"start": [x0 + frame_w, (y0 + y1_door) / 2], "end": [x1 - frame_w, y0 + frame_w], "layer": "SWING", "style": "dashed"})
                geom["lines"].append({"start": [x0 + frame_w, (y0 + y1_door) / 2], "end": [x1 - frame_w, y1_door - gap], "layer": "SWING", "style": "dashed"})
                
                if is_upper:
                    geom["lines"].append({"start": [x1 - frame_w - 1.5 * scale_x, y0 + frame_w + 2.0 * scale_y], "end": [x1 - frame_w - 1.5 * scale_x, y0 + frame_w + 7.0 * scale_y], "layer": "HANDLES", "style": "solid"})
                else:
                    geom["lines"].append({"start": [x1 - frame_w - 1.5 * scale_x, y1_door - 7.0 * scale_y], "end": [x1 - frame_w - 1.5 * scale_x, y1_door - 2.0 * scale_y], "layer": "HANDLES", "style": "solid"})

            # Shelves (visible as dashed lines representing internal shelves)
            if is_pantry or is_upper:
                num_shelves = 4 if is_pantry else 2
                for i in range(1, num_shelves + 1):
                    sy = y0 + (y1 - y0) * (i / (num_shelves + 1))
                    geom["lines"].append({"start": [x0 + frame_w, sy], "end": [x1 - frame_w, sy], "layer": "CABINETS_UPPER", "style": "dashed"})

        return geom
