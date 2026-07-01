from typing import Dict, List

class MicrowaveBlock:
    @staticmethod
    def elevation(x0: float, y0: float, width: float, height: float = 18.0, scale_x: float = 1.0, scale_y: float = 1.0) -> Dict[str, List]:
        geom = {"lines": [], "blocks": [], "texts": []}
        x1 = x0 + width * scale_x
        y1 = y0 + height * scale_y
        geom["blocks"].append({"type": "rect", "coords": [x0, y0, x1 - x0, y1 - y0], "id": "MW", "layer": "APPLIANCES", "style": "solid"})
        geom["texts"].append({"pos": [(x0 + x1) / 2, (y0 + y1) / 2], "text": "MW/HOOD", "size": 4.5, "layer": "TEXT"})
        return geom
        
    @staticmethod
    def plan(x0: float, y0: float, width: float, depth: float = 15.0, scale_x: float = 1.0, scale_y: float = 1.0) -> Dict[str, List]:
        geom = {"lines": [], "blocks": [], "texts": []}
        x1 = x0 + width * scale_x
        y1 = y0 + depth * scale_y
        geom["blocks"].append({"type": "rect", "coords": [x0, y0, x1 - x0, y1 - y0], "id": "MW", "layer": "APPLIANCES", "style": "dashed"})
        return geom
