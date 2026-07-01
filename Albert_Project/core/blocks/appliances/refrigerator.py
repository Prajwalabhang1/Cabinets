from typing import Dict, List

class RefrigeratorBlock:
    """Modular block definition for Refrigerator geometry."""
    
    @staticmethod
    def elevation(x0: float, y0: float, width: float, height: float = 72.0, scale_x: float = 1.0, scale_y: float = 1.0) -> Dict[str, List]:
        geom = {"lines": [], "blocks": [], "texts": []}
        x1 = x0 + width * scale_x
        y1 = y0 + height * scale_y
        
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
        geom["lines"].append({"start": [mid_x - 1.5 * scale_x, h_start_y], "end": [mid_x - 1.5 * scale_x, h_end_y], "layer": "FIXTURES", "style": "solid"})
        geom["lines"].append({"start": [mid_x + 1.5 * scale_x, h_start_y], "end": [mid_x + 1.5 * scale_x, h_end_y], "layer": "FIXTURES", "style": "solid"})
        
        # Text
        geom["texts"].append({"pos": [(x0 + x1) / 2, (y0 + y1) / 2], "text": "REF", "size": 4.5, "layer": "TEXT"})
        
        return geom

    @staticmethod
    def plan(x0: float, y0: float, width: float, depth: float = 30.0, scale_x: float = 1.0, scale_y: float = 1.0) -> Dict[str, List]:
        geom = {"lines": [], "blocks": [], "texts": []}
        x1 = x0 + width * scale_x
        y1 = y0 + depth * scale_y
        
        # Main body
        geom["blocks"].append({
            "type": "rect",
            "coords": [x0, y0, x1 - x0, y1 - y0],
            "id": "REF", "layer": "APPLIANCES", "style": "solid"
        })
        
        # Door thickness indication in plan
        geom["lines"].append({"start": [x0, y0 + 2.0 * scale_y], "end": [x1, y0 + 2.0 * scale_y], "layer": "APPLIANCES", "style": "solid"})
        
        # Text
        geom["texts"].append({"pos": [(x0 + x1) / 2, (y0 + y1) / 2], "text": "REF", "size": 4.5, "layer": "TEXT"})
        
        return geom
