from typing import Dict, List

class SinkBlock:
    @staticmethod
    def plan(x0: float, y0: float, width: float = 30.0, depth: float = 18.0, scale_x: float = 1.0, scale_y: float = 1.0) -> Dict[str, List]:
        geom = {"lines": [], "blocks": [], "texts": []}
        x1 = x0 + width * scale_x
        y1 = y0 + depth * scale_y
        geom["blocks"].append({"type": "rect", "coords": [x0, y0, x1 - x0, y1 - y0], "id": "SINK", "layer": "FIXTURES", "style": "solid"})
        
        # Inner bowl
        geom["blocks"].append({"type": "rect", "coords": [x0 + 1.5*scale_x, y0 + 1.5*scale_y, (width-3)*scale_x, (depth-3)*scale_y], "layer": "FIXTURES", "style": "solid"})
        
        # Drain
        geom["blocks"].append({"type": "circle", "coords": [(x0+x1)/2, (y0+y1)/2, 1.5*scale_x], "layer": "FIXTURES", "style": "solid"})
        return geom
