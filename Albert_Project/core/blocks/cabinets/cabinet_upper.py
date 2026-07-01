from typing import Dict, List

class CabinetUpperBlock:
    @staticmethod
    def elevation(x0: float, y0: float, width: float, height: float = 30.0, doors: int = 1, scale_x: float = 1.0, scale_y: float = 1.0) -> Dict[str, List]:
        geom = {"lines": [], "blocks": [], "texts": []}
        x1 = x0 + width * scale_x
        y1 = y0 + height * scale_y
        
        geom["blocks"].append({"type": "rect", "coords": [x0, y0, x1 - x0, y1 - y0], "layer": "CABINETS_UPPER", "style": "solid"})
        
        if doors > 1:
            w_door = (width / doors) * scale_x
            for i in range(1, doors):
                dx = x0 + w_door * i
                geom["lines"].append({"start": [dx, y0], "end": [dx, y1], "layer": "CABINETS_UPPER", "style": "solid"})
                
        # Swing diagonals (dashed)
        if doors == 1:
            geom["lines"].append({"start": [x0, y0], "end": [x1, y1], "layer": "CABINETS_UPPER", "style": "dashed"})
            geom["lines"].append({"start": [x1, y0], "end": [x0, y1], "layer": "CABINETS_UPPER", "style": "dashed"})
            
        return geom

    @staticmethod
    def plan(x0: float, y0: float, width: float, depth: float = 12.0, scale_x: float = 1.0, scale_y: float = 1.0) -> Dict[str, List]:
        geom = {"lines": [], "blocks": [], "texts": []}
        x1 = x0 + width * scale_x
        y1 = y0 + depth * scale_y
        geom["blocks"].append({"type": "rect", "coords": [x0, y0, x1 - x0, y1 - y0], "layer": "CABINETS_UPPER", "style": "dashed"})
        return geom
