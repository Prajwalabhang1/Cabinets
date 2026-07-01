from typing import Dict, List

class CabinetBaseBlock:
    @staticmethod
    def elevation(x0: float, y0: float, width: float, height: float = 34.5, depth: float = 24.0, doors: int = 1, drawers: int = 1, scale_x: float = 1.0, scale_y: float = 1.0) -> Dict[str, List]:
        geom = {"lines": [], "blocks": [], "texts": []}
        x1 = x0 + width * scale_x
        y1 = y0 + height * scale_y
        
        # Main box
        geom["blocks"].append({"type": "rect", "coords": [x0, y0, x1 - x0, y1 - y0], "layer": "CABINETS_BASE", "style": "solid"})
        
        # Toe kick
        tk_h = 4.5 * scale_y
        geom["lines"].append({"start": [x0, y0 + tk_h], "end": [x1, y0 + tk_h], "layer": "CABINETS_BASE", "style": "solid"})
        
        # Drawer section
        dr_h = 6.0 * scale_y
        if drawers > 0:
            geom["lines"].append({"start": [x0, y1 - dr_h], "end": [x1, y1 - dr_h], "layer": "CABINETS_BASE", "style": "solid"})
            
        # Door splits
        if doors > 1:
            w_door = (width / doors) * scale_x
            for i in range(1, doors):
                dx = x0 + w_door * i
                geom["lines"].append({"start": [dx, y0 + tk_h], "end": [dx, y1 - dr_h if drawers > 0 else y1], "layer": "CABINETS_BASE", "style": "solid"})
                
        # Swing diagonals
        if doors == 1:
            geom["lines"].append({"start": [x0, y0 + tk_h], "end": [x1, y1 - dr_h if drawers > 0 else y1], "layer": "CABINETS_BASE", "style": "dashed"})
            geom["lines"].append({"start": [x1, y0 + tk_h], "end": [x0, y1 - dr_h if drawers > 0 else y1], "layer": "CABINETS_BASE", "style": "dashed"})
            
        return geom

    @staticmethod
    def plan(x0: float, y0: float, width: float, depth: float = 24.0, scale_x: float = 1.0, scale_y: float = 1.0) -> Dict[str, List]:
        geom = {"lines": [], "blocks": [], "texts": []}
        x1 = x0 + width * scale_x
        y1 = y0 + depth * scale_y
        geom["blocks"].append({"type": "rect", "coords": [x0, y0, x1 - x0, y1 - y0], "layer": "CABINETS_BASE", "style": "solid"})
        return geom
