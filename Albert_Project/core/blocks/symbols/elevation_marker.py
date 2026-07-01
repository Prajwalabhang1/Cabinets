from typing import Dict, List

class ElevationMarkerBlock:
    @staticmethod
    def draw(x0: float, y0: float, label: str = "1", scale: float = 1.0) -> Dict[str, List]:
        geom = {"lines": [], "blocks": [], "texts": []}
        r = 3.0 * scale
        geom["blocks"].append({"type": "circle", "coords": [x0, y0, r], "layer": "ANNOTATIONS", "style": "solid"})
        geom["texts"].append({"pos": [x0, y0], "text": label, "size": 4.0 * scale, "layer": "TEXT"})
        return geom
