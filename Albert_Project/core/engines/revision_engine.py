from typing import Dict, List, Any
import math

class RevisionEngine:
    """Handles revision tracking and dynamic revision cloud generation."""

    @staticmethod
    def draw_revision_cloud(x: float, y: float, w: float, h: float, arc_radius: float = 2.0, scale: float = 1.0) -> Dict[str, List]:
        """Draws a scalloped revision cloud around a bounding box."""
        geom = {"lines": [], "blocks": [], "texts": []}
        
        r = arc_radius * scale
        x_min, x_max = x, x + (w * scale)
        y_min, y_max = y, y + (h * scale)
        
        # In a true CAD system, we'd draw arcs. 
        # For our abstract geometry model, we represent it as a specialized block or segmented arcs.
        # Here we emit a custom block type 'rev_cloud' which the sheet composer can render appropriately.
        
        geom["blocks"].append({
            "type": "rev_cloud",
            "coords": [x_min, y_min, w * scale, h * scale],
            "arc_radius": r,
            "layer": "REVISIONS",
            "style": "cloud"
        })
        
        # Add a revision delta triangle
        geom["blocks"].append({
            "type": "polygon",
            "points": [
                [x_max, y_max], 
                [x_max + (3*scale), y_max + (5*scale)], 
                [x_max - (3*scale), y_max + (5*scale)]
            ],
            "layer": "REVISIONS",
            "style": "solid"
        })
        
        return geom

    @staticmethod
    def generate_revision_log(revisions: List[Dict[str, str]]) -> Dict[str, Any]:
        """Compiles a revision history for the title block."""
        issues = []
        for rev in revisions:
            issues.append({
                "rev_id": rev.get("id", ""),
                "date": rev.get("date", ""),
                "description": rev.get("description", ""),
                "author": rev.get("author", "AUTO")
            })
        return {"revisions": issues}
