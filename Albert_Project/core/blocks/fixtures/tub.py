from typing import Dict, List

class TubBlock:
    @staticmethod
    def plan(x0: float, y0: float, width: float = 60.0, depth: float = 30.0, scale_x: float = 1.0, scale_y: float = 1.0) -> Dict[str, List]:
        geom = {"lines": [], "blocks": [], "texts": []}
        x1 = x0 + width * scale_x
        y1 = y0 + depth * scale_y
        geom["blocks"].append({"type": "rect", "coords": [x0, y0, x1 - x0, y1 - y0], "id": "TUB", "layer": "FIXTURES", "style": "solid"})
        geom["texts"].append({"pos": [(x0 + x1) / 2, (y0 + y1) / 2], "text": "TUB", "size": 4.5, "layer": "TEXT"})
        return geom
