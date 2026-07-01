from typing import Dict, List

class RangeBlock:
    @staticmethod
    def elevation(x0: float, y0: float, width: float, height: float = 36.0, scale_x: float = 1.0, scale_y: float = 1.0) -> Dict[str, List]:
        geom = {"lines": [], "blocks": [], "texts": []}
        x1 = x0 + width * scale_x
        y1 = y0 + height * scale_y
        geom["blocks"].append({"type": "rect", "coords": [x0, y0, x1 - x0, y1 - y0], "id": "RANGE", "layer": "APPLIANCES", "style": "solid"})
        geom["texts"].append({"pos": [(x0 + x1) / 2, (y0 + y1) / 2], "text": "RANGE", "size": 4.5, "layer": "TEXT"})
        return geom

    @staticmethod
    def plan(x0: float, y0: float, width: float, depth: float = 25.0, scale_x: float = 1.0, scale_y: float = 1.0) -> Dict[str, List]:
        geom = {"lines": [], "blocks": [], "texts": []}
        x1 = x0 + width * scale_x
        y1 = y0 + depth * scale_y
        geom["blocks"].append({"type": "rect", "coords": [x0, y0, x1 - x0, y1 - y0], "id": "RANGE", "layer": "APPLIANCES", "style": "solid"})
        
        # Draw 4 burners
        r = 3.0 * scale_x
        cx1, cy1 = x0 + (width * 0.25) * scale_x, y0 + (depth * 0.3) * scale_y
        cx2, cy2 = x0 + (width * 0.75) * scale_x, y0 + (depth * 0.3) * scale_y
        cx3, cy3 = x0 + (width * 0.25) * scale_x, y0 + (depth * 0.7) * scale_y
        cx4, cy4 = x0 + (width * 0.75) * scale_x, y0 + (depth * 0.7) * scale_y
        for c in [(cx1, cy1), (cx2, cy2), (cx3, cy3), (cx4, cy4)]:
            geom["blocks"].append({"type": "circle", "coords": [c[0], c[1], r], "layer": "APPLIANCES", "style": "solid"})
            
        return geom
