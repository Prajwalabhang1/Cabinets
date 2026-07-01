from typing import Dict, List, Any

class ApplianceLibrary:
    """Procedural generator for appliance CAD blocks."""
    
    @staticmethod
    def draw_refrigerator_elevation(x0: float, y0: float, width: float, scale_x: float = 4.0, scale_y: float = 3.0) -> Dict[str, List]:
        """Draws a refrigerator in elevation view."""
        geom = {"lines": [], "blocks": [], "texts": []}
        x1 = x0 + width * scale_x
        y1 = y0 + 72.0 * scale_y  # Ref height is typically 72"
        
        # Main body
        geom["blocks"].append({
            "type": "rect",
            "coords": [x0, y0, x1 - x0, y1 - y0],
            "id": "REF", "layer": "APPLIANCES", "style": "solid"
        })
        
        # Doors divide
        mid_x = x0 + (width / 2.0) * scale_x
        geom["lines"].append({"start": [mid_x, y0], "end": [mid_x, y1], "layer": "APPLIANCES", "style": "solid"})
        
        # Handles
        h_start_y = y0 + 30.0 * scale_y
        h_end_y = y0 + 48.0 * scale_y
        geom["lines"].append({"start": [mid_x - 1.5, h_start_y], "end": [mid_x - 1.5, h_end_y], "layer": "HANDLES", "style": "solid"})
        geom["lines"].append({"start": [mid_x + 1.5, h_start_y], "end": [mid_x + 1.5, h_end_y], "layer": "HANDLES", "style": "solid"})
        
        # Text
        geom["texts"].append({"pos": [(x0 + x1) / 2, (y0 + y1) / 2], "text": "REF", "size": 4.5, "layer": "TEXT"})
        
        return geom

    @staticmethod
    def draw_dishwasher_elevation(x0: float, y0: float, width: float, height: float, scale_x: float = 4.0, scale_y: float = 3.0) -> Dict[str, List]:
        geom = {"lines": [], "blocks": [], "texts": []}
        x1 = x0 + width * scale_x
        y1 = y0 + height * scale_y
        
        geom["blocks"].append({
            "type": "rect",
            "coords": [x0, y0, x1 - x0, y1 - y0],
            "id": "D/W", "layer": "APPLIANCES", "style": "solid"
        })
        
        # Control panel
        geom["lines"].append({"start": [x0, y1 - 4.0 * scale_y], "end": [x1, y1 - 4.0 * scale_y], "layer": "APPLIANCES", "style": "solid"})
        
        geom["texts"].append({"pos": [(x0 + x1) / 2, (y0 + y1) / 2 - 2.0 * scale_y], "text": "D/W\nS.S", "size": 4.5, "layer": "TEXT"})
        
        return geom

    @staticmethod
    def draw_range_elevation(x0: float, y0: float, width: float, scale_x: float = 4.0, scale_y: float = 3.0) -> Dict[str, List]:
        geom = {"lines": [], "blocks": [], "texts": []}
        x1 = x0 + width * scale_x
        y1_stove = y0 + 36.0 * scale_y
        
        # Main body
        geom["blocks"].append({
            "type": "rect",
            "coords": [x0, y0, x1 - x0, y1_stove - y0],
            "id": "STOVE", "layer": "APPLIANCES", "style": "solid"
        })
        # Bottom warming drawer
        geom["lines"].append({"start": [x0, y0 + 8.0 * scale_y], "end": [x1, y0 + 8.0 * scale_y], "layer": "APPLIANCES", "style": "solid"})
        
        # Glass window
        geom["blocks"].append({
            "type": "rect",
            "coords": [x0 + 4.0 * scale_x, y0 + 12.0 * scale_y, (width - 8.0) * scale_x, 14.0 * scale_y],
            "id": "", "layer": "APPLIANCES", "style": "solid"
        })
        
        # Control panel
        geom["lines"].append({"start": [x0, y1_stove - 4.0 * scale_y], "end": [x1, y1_stove - 4.0 * scale_y], "layer": "APPLIANCES", "style": "solid"})
        
        # Knobs
        for i in range(1, 5):
            kx = x0 + (width / 5.0 * i) * scale_x
            geom["blocks"].append({
                "type": "rect",
                "coords": [kx - 1.0, y1_stove - 3.0 * scale_y, 2.0, 2.0 * scale_y],
                "id": "", "layer": "APPLIANCES", "style": "solid"
            })
            
        return geom

    @staticmethod
    def draw_microwave_elevation(x0: float, y0: float, width: float, height: float, scale_x: float = 4.0, scale_y: float = 3.0) -> Dict[str, List]:
        geom = {"lines": [], "blocks": [], "texts": []}
        x1 = x0 + width * scale_x
        y1 = y0 + height * scale_y
        
        geom["blocks"].append({
            "type": "rect",
            "coords": [x0, y0, x1 - x0, y1 - y0],
            "id": "MW", "layer": "APPLIANCES", "style": "solid"
        })
        # Keypad
        geom["lines"].append({"start": [x1 - 6.0 * scale_x, y0], "end": [x1 - 6.0 * scale_x, y1], "layer": "APPLIANCES", "style": "solid"})
        geom["blocks"].append({
            "type": "rect",
            "coords": [x1 - 5.0 * scale_x, y0 + 2.0 * scale_y, 3.0 * scale_x, 6.0 * scale_y],
            "id": "", "layer": "APPLIANCES", "style": "solid"
        })
        # Window
        geom["blocks"].append({
            "type": "rect",
            "coords": [x0 + 2.0 * scale_x, y0 + 2.0 * scale_y, (width - 10.0) * scale_x, (height - 4.0) * scale_y],
            "id": "", "layer": "APPLIANCES", "style": "solid"
        })
        return geom

    @staticmethod
    def draw_sink_elevation(x0: float, y1: float, width: float, scale_x: float = 4.0, scale_y: float = 3.0) -> Dict[str, List]:
        """Draws dashed sink bowl in elevation behind base cabinets."""
        geom = {"lines": [], "blocks": [], "texts": []}
        x1 = x0 + width * scale_x
        sink_d = 8.0 * scale_y
        
        geom["lines"].append({"start": [x0 + 3.0 * scale_x, y1], "end": [x0 + 3.0 * scale_x, y1 - sink_d], "layer": "SINK", "style": "dashed"})
        geom["lines"].append({"start": [x0 + 3.0 * scale_x, y1 - sink_d], "end": [x1 - 3.0 * scale_x, y1 - sink_d], "layer": "SINK", "style": "dashed"})
        geom["lines"].append({"start": [x1 - 3.0 * scale_x, y1 - sink_d], "end": [x1 - 3.0 * scale_x, y1], "layer": "SINK", "style": "dashed"})
        return geom

    @staticmethod
    def draw_sink_plan(x0: float, y0: float, width: float, depth: float, scale_x: float = 4.0, scale_y: float = 4.0) -> Dict[str, List]:
        """Draws sink symbol in floor plan."""
        geom = {"lines": [], "blocks": [], "texts": []}
        x1 = x0 + width * scale_x
        
        # Center of sink
        cx = x0 + (width / 2.0) * scale_x
        cy = y0 + (depth / 2.0) * scale_y
        
        sink_w = min(width - 6.0, 24.0) * scale_x
        sink_h = 16.0 * scale_y
        
        # Outer rim
        geom["blocks"].append({
            "type": "rect",
            "coords": [cx - sink_w/2, cy - sink_h/2, sink_w, sink_h],
            "id": "SINK", "layer": "APPLIANCES", "style": "solid"
        })
        
        # Drain circle approximation (diamond for now)
        dx, dy = cx, cy + 2.0 * scale_y
        r = 1.0 * scale_x
        geom["lines"].append({"start": [dx-r, dy], "end": [dx, dy+r], "layer": "APPLIANCES", "style": "solid"})
        geom["lines"].append({"start": [dx, dy+r], "end": [dx+r, dy], "layer": "APPLIANCES", "style": "solid"})
        geom["lines"].append({"start": [dx+r, dy], "end": [dx, dy-r], "layer": "APPLIANCES", "style": "solid"})
        geom["lines"].append({"start": [dx, dy-r], "end": [dx-r, dy], "layer": "APPLIANCES", "style": "solid"})
        
        return geom

    @staticmethod
    def draw_range_plan(x0: float, y0: float, width: float, depth: float, scale_x: float = 4.0, scale_y: float = 4.0) -> Dict[str, List]:
        """Draws range symbol with 4 burners in floor plan."""
        geom = {"lines": [], "blocks": [], "texts": []}
        x1 = x0 + width * scale_x
        y1 = y0 + depth * scale_y
        
        geom["blocks"].append({
            "type": "rect",
            "coords": [x0, y0, width * scale_x, depth * scale_y],
            "id": "RANGE", "layer": "APPLIANCES", "style": "solid"
        })
        
        # 4 burners
        margin_x = 4.0 * scale_x
        margin_y = 4.0 * scale_y
        spacing_x = (width * scale_x - 2*margin_x)
        spacing_y = (depth * scale_y - 2*margin_y)
        
        for bx in [x0 + margin_x, x1 - margin_x]:
            for by in [y0 + margin_y, y1 - margin_y]:
                # Draw burner as a small box or cross
                geom["lines"].append({"start": [bx-2, by], "end": [bx+2, by], "layer": "APPLIANCES", "style": "solid"})
                geom["lines"].append({"start": [bx, by-2], "end": [bx, by+2], "layer": "APPLIANCES", "style": "solid"})
                
        return geom
