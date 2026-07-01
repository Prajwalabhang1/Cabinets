from typing import Dict, List, Tuple

class WallEngine:
    """Procedural generator for architectural walls, hatches, and openings."""
    
    @staticmethod
    def draw_wall_core(start: Tuple[float, float], end: Tuple[float, float], thickness: float = 4.5, scale: float = 1.0) -> Dict[str, List]:
        """Draws the core structure lines of a wall."""
        geom = {"lines": [], "blocks": [], "texts": []}
        x1, y1 = start
        x2, y2 = end
        
        # Simplified assumption for horizontal walls for MVP
        if abs(y1 - y2) < 0.1:  # Horizontal
            geom["lines"].append({"start": [x1, y1], "end": [x2, y2], "layer": "WALLS", "style": "solid"})
            geom["lines"].append({"start": [x1, y1 + thickness * scale], "end": [x2, y2 + thickness * scale], "layer": "WALLS", "style": "solid"})
        else:  # Vertical
            geom["lines"].append({"start": [x1, y1], "end": [x2, y2], "layer": "WALLS", "style": "solid"})
            geom["lines"].append({"start": [x1 + thickness * scale, y1], "end": [x2 + thickness * scale, y2], "layer": "WALLS", "style": "solid"})
            
        return geom

    @staticmethod
    def draw_finish_face(start: Tuple[float, float], end: Tuple[float, float], offset: float = 0.5, scale: float = 1.0) -> Dict[str, List]:
        """Draws the drywall/finish line offset from the core."""
        geom = {"lines": [], "blocks": [], "texts": []}
        x1, y1 = start
        x2, y2 = end
        
        if abs(y1 - y2) < 0.1:  # Horizontal
            geom["lines"].append({"start": [x1, y1 - offset * scale], "end": [x2, y2 - offset * scale], "layer": "WALL_FINISH", "style": "solid"})
        else:  # Vertical
            geom["lines"].append({"start": [x1 - offset * scale, y1], "end": [x2 - offset * scale, y2], "layer": "WALL_FINISH", "style": "solid"})
            
        return geom

    @staticmethod
    def draw_wall_hatch(x: float, y: float, w: float, h: float, pattern: str = "ANSI31", scale: float = 1.0) -> Dict[str, List]:
        """Draws the architectural hatch pattern within the wall core."""
        geom = {"lines": [], "blocks": [], "texts": []}
        # A true hatch is complex; we'll simulate by returning a hatch polygon block
        geom["blocks"].append({
            "type": "rect", 
            "coords": [x, y, w, h], 
            "layer": "WALL_HATCH", 
            "style": "hatch_" + pattern.lower()
        })
        return geom

    @staticmethod
    def draw_opening(x: float, y: float, width: float, depth: float = 4.5, scale: float = 1.0) -> Dict[str, List]:
        """Draws a door or window opening interruption in the wall."""
        geom = {"lines": [], "blocks": [], "texts": []}
        # Opening lines usually cross the wall core
        geom["lines"].append({"start": [x, y], "end": [x, y + depth * scale], "layer": "WALLS", "style": "solid"})
        geom["lines"].append({"start": [x + width * scale, y], "end": [x + width * scale, y + depth * scale], "layer": "WALLS", "style": "solid"})
        return geom

    @staticmethod
    def draw_centerline(start: Tuple[float, float], end: Tuple[float, float], scale: float = 1.0) -> Dict[str, List]:
        """Draws an architectural centerline."""
        geom = {"lines": [], "blocks": [], "texts": []}
        x1, y1 = start
        x2, y2 = end
        geom["lines"].append({"start": [x1, y1], "end": [x2, y2], "layer": "CENTERLINES", "style": "center"})
        return geom

    @staticmethod
    def draw_hidden_wall(start: Tuple[float, float], end: Tuple[float, float], thickness: float = 4.5, scale: float = 1.0) -> Dict[str, List]:
        """Draws a hidden/below-grade wall."""
        geom = {"lines": [], "blocks": [], "texts": []}
        x1, y1 = start
        x2, y2 = end
        
        if abs(y1 - y2) < 0.1:  # Horizontal
            geom["lines"].append({"start": [x1, y1], "end": [x2, y2], "layer": "WALLS_HIDDEN", "style": "dashed"})
            geom["lines"].append({"start": [x1, y1 + thickness * scale], "end": [x2, y2 + thickness * scale], "layer": "WALLS_HIDDEN", "style": "dashed"})
        else:  # Vertical
            geom["lines"].append({"start": [x1, y1], "end": [x2, y2], "layer": "WALLS_HIDDEN", "style": "dashed"})
            geom["lines"].append({"start": [x1 + thickness * scale, y1], "end": [x2 + thickness * scale, y2], "layer": "WALLS_HIDDEN", "style": "dashed"})
        return geom

    @staticmethod
    def draw_demolition_wall(start: Tuple[float, float], end: Tuple[float, float], thickness: float = 4.5, scale: float = 1.0) -> Dict[str, List]:
        """Draws a wall marked for demolition."""
        geom = {"lines": [], "blocks": [], "texts": []}
        x1, y1 = start
        x2, y2 = end
        
        if abs(y1 - y2) < 0.1:  # Horizontal
            geom["lines"].append({"start": [x1, y1], "end": [x2, y2], "layer": "WALLS_DEMO", "style": "hidden"})
            geom["lines"].append({"start": [x1, y1 + thickness * scale], "end": [x2, y2 + thickness * scale], "layer": "WALLS_DEMO", "style": "hidden"})
        else:  # Vertical
            geom["lines"].append({"start": [x1, y1], "end": [x2, y2], "layer": "WALLS_DEMO", "style": "hidden"})
            geom["lines"].append({"start": [x1 + thickness * scale, y1], "end": [x2 + thickness * scale, y2], "layer": "WALLS_DEMO", "style": "hidden"})
        return geom

    @staticmethod
    def draw_soffit(start: Tuple[float, float], end: Tuple[float, float], depth: float = 12.0, scale: float = 1.0) -> Dict[str, List]:
        """Draws overhead soffit lines."""
        geom = {"lines": [], "blocks": [], "texts": []}
        x1, y1 = start
        x2, y2 = end
        
        if abs(y1 - y2) < 0.1:  # Horizontal
            geom["lines"].append({"start": [x1, y1 + depth * scale], "end": [x2, y2 + depth * scale], "layer": "SOFFIT", "style": "dashed"})
        else:  # Vertical
            geom["lines"].append({"start": [x1 + depth * scale, y1], "end": [x2 + depth * scale, y2], "layer": "SOFFIT", "style": "dashed"})
        return geom
