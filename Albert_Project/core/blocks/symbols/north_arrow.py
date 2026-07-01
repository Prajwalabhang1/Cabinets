from typing import Dict, List

class NorthArrowBlock:
    @staticmethod
    def draw(x0: float, y0: float, scale: float = 1.0) -> Dict[str, List]:
        geom = {"lines": [], "blocks": [], "texts": []}
        r = 5.0 * scale
        geom["blocks"].append({"type": "circle", "coords": [x0, y0, r], "layer": "ANNOTATIONS", "style": "solid"})
        geom["lines"].append({"start": [x0, y0 - r], "end": [x0, y0 + r*1.5], "layer": "ANNOTATIONS", "style": "solid"})
        geom["texts"].append({"pos": [x0, y0 + r*2], "text": "N", "size": 5.0 * scale, "layer": "TEXT"})
        return geom
