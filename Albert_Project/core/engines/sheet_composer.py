from typing import Dict, List, Any

class SheetComposer:
    """Orchestrates the layout of multiple viewports onto a single PDF/DXF sheet."""
    
    @staticmethod
    def compose_sheet(sheet_id: str, viewports: List[Dict[str, Any]], title_block: Dict[str, Any]) -> Dict[str, List]:
        """Combines multiple viewports and the title block into a final single geometry dict."""
        sheet_geom = {"lines": [], "blocks": [], "texts": []}
        
        # Add title block
        if title_block:
            sheet_geom["lines"].extend(title_block.get("lines", []))
            sheet_geom["blocks"].extend(title_block.get("blocks", []))
            sheet_geom["texts"].extend(title_block.get("texts", []))
            
        # Add each viewport
        for vp in viewports:
            geom = vp.get("geometry", {})
            sheet_geom["lines"].extend(geom.get("lines", []))
            sheet_geom["blocks"].extend(geom.get("blocks", []))
            sheet_geom["texts"].extend(geom.get("texts", []))
            
        return sheet_geom

    @staticmethod
    def place_floor_plan(floor_plan_geom: Dict[str, List], x_offset: float, y_offset: float, scale: float = 1.0) -> Dict[str, Any]:
        """Places the floor plan onto a specific coordinate on the sheet."""
        # Typically requires scaling engine here, but for now just pass through
        return {"id": "FLOOR_PLAN", "geometry": floor_plan_geom, "x": x_offset, "y": y_offset, "scale": scale}

    @staticmethod
    def place_elevation_A(elevation_geom: Dict[str, List], x_offset: float, y_offset: float, scale: float = 1.0) -> Dict[str, Any]:
        """Places Elevation A onto the sheet."""
        return {"id": "ELEV_A", "geometry": elevation_geom, "x": x_offset, "y": y_offset, "scale": scale}

    @staticmethod
    def place_section_A(section_geom: Dict[str, List], x_offset: float, y_offset: float, scale: float = 1.0) -> Dict[str, Any]:
        """Places Section A onto the sheet."""
        return {"id": "SECT_A", "geometry": section_geom, "x": x_offset, "y": y_offset, "scale": scale}

    @staticmethod
    def place_section_view(section_geom: Dict[str, List], x_offset: float, y_offset: float, scale: float = 1.0) -> Dict[str, Any]:
        """Places a generalized Section View."""
        return {"id": "SECT_VIEW", "geometry": section_geom, "x": x_offset, "y": y_offset, "scale": scale}

    @staticmethod
    def place_general_notes(notes_geom: Dict[str, List], x_offset: float, y_offset: float, scale: float = 1.0) -> Dict[str, Any]:
        """Places general architectural notes onto the sheet."""
        return {"id": "GENERAL_NOTES", "geometry": notes_geom, "x": x_offset, "y": y_offset, "scale": scale}

    @staticmethod
    def place_matrix_table(matrix_geom: Dict[str, List], x_offset: float, y_offset: float, scale: float = 1.0) -> Dict[str, Any]:
        """Places the project unit matrix table."""
        return {"id": "MATRIX_TABLE", "geometry": matrix_geom, "x": x_offset, "y": y_offset, "scale": scale}

    @staticmethod
    def place_revision_clouds(clouds_geom: Dict[str, List], x_offset: float, y_offset: float, scale: float = 1.0) -> Dict[str, Any]:
        """Places revision clouds marking recent changes."""
        return {"id": "REVISION_CLOUDS", "geometry": clouds_geom, "x": x_offset, "y": y_offset, "scale": scale}

    @staticmethod
    def place_title_block(title_block_geom: Dict[str, List]) -> Dict[str, Any]:
        """Positions the title block geometry (usually absolute coordinates)."""
        return {"id": "TITLE_BLOCK", "geometry": title_block_geom, "x": 0.0, "y": 0.0, "scale": 1.0}
