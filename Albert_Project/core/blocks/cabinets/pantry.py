from typing import Dict, List

class PantryBlock:
    @staticmethod
    def elevation(x0: float, y0: float, width: float, height: float = 84.0, scale_x: float = 1.0, scale_y: float = 1.0) -> Dict[str, List]:
        geom = {"lines": [], "blocks": [], "texts": []}
        x1 = x0 + width * scale_x
        y1 = y0 + height * scale_y
        
        geom["blocks"].append({"type": "rect", "coords": [x0, y0, x1 - x0, y1 - y0], "layer": "CABINETS_TALL", "style": "solid"})
        
        tk_h = 4.5 * scale_y
        geom["lines"].append({"start": [x0, y0 + tk_h], "end": [x1, y0 + tk_h], "layer": "CABINETS_TALL", "style": "solid"})
        
        # Split upper/lower doors at typical height
        split_y = y0 + 54.0 * scale_y
        if split_y < y1:
            geom["lines"].append({"start": [x0, split_y], "end": [x1, split_y], "layer": "CABINETS_TALL", "style": "solid"})
            
        return geom

    @staticmethod
    def plan(x0: float, y0: float, width: float, depth: float = 24.0, scale_x: float = 1.0, scale_y: float = 1.0) -> Dict[str, List]:
        geom = {"lines": [], "blocks": [], "texts": []}
        x1 = x0 + width * scale_x
        y1 = y0 + depth * scale_y
        geom["blocks"].append({"type": "rect", "coords": [x0, y0, x1 - x0, y1 - y0], "layer": "CABINETS_TALL", "style": "solid"})
        # Crossed lines to indicate tall
        geom["lines"].append({"start": [x0, y0], "end": [x1, y1], "layer": "CABINETS_TALL", "style": "solid"})
        geom["lines"].append({"start": [x1, y0], "end": [x0, y1], "layer": "CABINETS_TALL", "style": "solid"})
        return geom
