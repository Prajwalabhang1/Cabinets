from typing import Dict, List

class SectionMarkerBlock:
    @staticmethod
    def draw(x0: float, y0: float, direction: str = "UP", label: str = "A", scale: float = 1.0) -> Dict[str, List]:
        geom = {"lines": [], "blocks": [], "texts": []}
        r = 4.0 * scale
        geom["blocks"].append({"type": "circle", "coords": [x0, y0, r], "layer": "SECTION_MARKERS", "style": "solid"})
        
        # Line cutting through
        geom["lines"].append({"start": [x0 - r*2, y0], "end": [x0 + r*2, y0], "layer": "SECTION_MARKERS", "style": "solid"})
        
        # Triangle pointer
        if direction == "UP":
            geom["lines"].append({"start": [x0 - r, y0], "end": [x0, y0 + r*1.5], "layer": "SECTION_MARKERS", "style": "solid"})
            geom["lines"].append({"start": [x0, y0 + r*1.5], "end": [x0 + r, y0], "layer": "SECTION_MARKERS", "style": "solid"})
            
        geom["texts"].append({"pos": [x0, y0 - r*0.5], "text": label, "size": 4.5 * scale, "layer": "TEXT"})
        return geom
