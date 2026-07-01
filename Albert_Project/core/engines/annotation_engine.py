from typing import Dict, List, Any

class AnnotationEngine:
    """Handles textual and symbol annotations like callouts, labels, and tags."""

    @staticmethod
    def draw_cabinet_tag(x: float, y: float, text: str, scale: float = 1.0) -> Dict[str, List]:
        """Draws a standard hexagonal or circular cabinet tag."""
        geom = {"lines": [], "blocks": [], "texts": []}
        
        # Hexagon tag
        r = 3.0 * scale
        pts = []
        import math
        for i in range(6):
            angle_deg = 60 * i
            angle_rad = math.pi / 180 * angle_deg
            pts.append([x + r * math.cos(angle_rad), y + r * math.sin(angle_rad)])
            
        geom["blocks"].append({
            "type": "polygon",
            "points": pts,
            "layer": "ANNOTATION",
            "style": "solid"
        })
        
        geom["texts"].append({
            "pos": [x, y],
            "text": text,
            "size": 2.5 * scale,
            "layer": "ANNOTATION_TEXT",
            "align": "CENTER"
        })
        
        return geom

    @staticmethod
    def draw_leader_callout(start_pt: List[float], end_pt: List[float], text: str, scale: float = 1.0) -> Dict[str, List]:
        """Draws a leader line pointing from an object to a text note."""
        geom = {"lines": [], "blocks": [], "texts": []}
        x1, y1 = start_pt
        x2, y2 = end_pt
        
        # Leader line
        geom["lines"].append({"start": [x1, y1], "end": [x2, y2], "layer": "ANNOTATION", "style": "solid"})
        
        # Leader shoulder (horizontal landing)
        shoulder_len = 5.0 * scale
        direction = 1 if x2 > x1 else -1
        x3 = x2 + (shoulder_len * direction)
        geom["lines"].append({"start": [x2, y2], "end": [x3, y2], "layer": "ANNOTATION", "style": "solid"})
        
        # Text
        geom["texts"].append({
            "pos": [x3 + (1.0 * direction * scale), y2 + (1.0 * scale)],
            "text": text,
            "size": 3.0 * scale,
            "layer": "ANNOTATION_TEXT",
            "align": "LEFT" if direction == 1 else "RIGHT"
        })
        
        return geom

    @staticmethod
    def draw_elevation_marker(x: float, y: float, view_name: str, sheet_num: str, scale: float = 1.0) -> Dict[str, List]:
        """Draws a standard elevation target marker (circle with an arrow)."""
        geom = {"lines": [], "blocks": [], "texts": []}
        r = 4.0 * scale
        
        # Circle
        geom["blocks"].append({
            "type": "circle",
            "center": [x, y],
            "radius": r,
            "layer": "ANNOTATION",
            "style": "solid"
        })
        
        # Split line
        geom["lines"].append({"start": [x - r, y], "end": [x + r, y], "layer": "ANNOTATION", "style": "solid"})
        
        # Texts
        geom["texts"].append({"pos": [x, y + (r/2)], "text": view_name, "size": 2.5 * scale, "layer": "ANNOTATION_TEXT", "align": "CENTER"})
        geom["texts"].append({"pos": [x, y - (r/2)], "text": sheet_num, "size": 2.5 * scale, "layer": "ANNOTATION_TEXT", "align": "CENTER"})
        
        # Arrow (pointing up as default)
        geom["blocks"].append({
            "type": "polygon",
            "points": [[x, y + r + (2*scale)], [x - (2*scale), y + r], [x + (2*scale), y + r]],
            "layer": "ANNOTATION",
            "style": "solid"
        })
        
        return geom
