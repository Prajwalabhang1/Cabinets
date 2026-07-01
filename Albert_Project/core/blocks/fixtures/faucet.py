from typing import Dict, List

class FaucetBlock:
    @staticmethod
    def plan(x0: float, y0: float, scale_x: float = 1.0, scale_y: float = 1.0) -> Dict[str, List]:
        geom = {"lines": [], "blocks": [], "texts": []}
        # simple circle for base
        geom["blocks"].append({"type": "circle", "coords": [x0, y0, 1.0*scale_x], "layer": "FIXTURES", "style": "solid"})
        # spout line
        geom["lines"].append({"start": [x0, y0], "end": [x0, y0 - 4.0*scale_y], "layer": "FIXTURES", "style": "solid"})
        return geom
