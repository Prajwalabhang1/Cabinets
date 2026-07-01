from typing import Dict, List, Any
import datetime

class TitleBlockEngine:
    """Generates standardized architectural title blocks."""
    
    @staticmethod
    def draw_vertical_strip(sheet_w: float, sheet_h: float, strip_width: float = 3.0) -> Dict[str, List]:
        """Draws the right-side vertical title strip boundary."""
        geom = {"lines": [], "blocks": [], "texts": []}
        x_start = sheet_w - strip_width
        geom["lines"].append({"start": [x_start, 0], "end": [x_start, sheet_h], "layer": "TITLEBLOCK", "style": "solid"})
        # Outer border
        geom["blocks"].append({"type": "rect", "coords": [0, 0, sheet_w, sheet_h], "layer": "TITLEBLOCK", "style": "solid"})
        return geom

    @staticmethod
    def add_project_metadata(x: float, y: float, project_name: str, client_name: str) -> Dict[str, List]:
        """Adds project text to the title block."""
        geom = {"lines": [], "blocks": [], "texts": []}
        geom["texts"].append({"pos": [x, y], "text": project_name, "size": 6.0, "layer": "TITLEBLOCK"})
        geom["texts"].append({"pos": [x, y - 1.5], "text": client_name, "size": 4.0, "layer": "TITLEBLOCK"})
        return geom

    @staticmethod
    def add_sheet_info(x: float, y: float, sheet_number: str, sheet_title: str, scale: str) -> Dict[str, List]:
        """Adds specific sheet data."""
        geom = {"lines": [], "blocks": [], "texts": []}
        geom["texts"].append({"pos": [x, y], "text": f"SHEET: {sheet_number}", "size": 8.0, "layer": "TITLEBLOCK"})
        geom["texts"].append({"pos": [x, y - 2.0], "text": sheet_title, "size": 5.0, "layer": "TITLEBLOCK"})
        geom["texts"].append({"pos": [x, y - 4.0], "text": f"SCALE: {scale}", "size": 4.0, "layer": "TITLEBLOCK"})
        geom["texts"].append({"pos": [x, y - 6.0], "text": f"DATE: {datetime.date.today().isoformat()}", "size": 4.0, "layer": "TITLEBLOCK"})
        return geom

    @staticmethod
    def add_revision_log(x: float, y: float, revisions: List[Dict[str, str]]) -> Dict[str, List]:
        """Adds a revision table."""
        geom = {"lines": [], "blocks": [], "texts": []}
        geom["texts"].append({"pos": [x, y], "text": "REVISIONS", "size": 4.5, "layer": "TITLEBLOCK"})
        
        current_y = y - 1.5
        for rev in revisions:
            text = f"{rev.get('date', '')} - {rev.get('desc', '')}"
            geom["texts"].append({"pos": [x, current_y], "text": text, "size": 3.0, "layer": "TITLEBLOCK"})
            current_y -= 1.5
            
        return geom

    @staticmethod
    def draw_issue_history(x: float, y: float, issues: List[Dict[str, str]]) -> Dict[str, List]:
        """Draws the formal issue/submittal history block."""
        geom = {"lines": [], "blocks": [], "texts": []}
        geom["texts"].append({"pos": [x, y], "text": "ISSUE HISTORY", "size": 4.5, "layer": "TITLEBLOCK"})
        current_y = y - 1.5
        for issue in issues:
            text = f"ISSUED FOR {issue.get('purpose', 'REVIEW')} - {issue.get('date', '')}"
            geom["texts"].append({"pos": [x, current_y], "text": text, "size": 3.0, "layer": "TITLEBLOCK"})
            current_y -= 1.5
        return geom

    @staticmethod
    def draw_consultant_block(x: float, y: float, consultants: List[str]) -> Dict[str, List]:
        """Draws the consultant and engineering stamp block."""
        geom = {"lines": [], "blocks": [], "texts": []}
        geom["texts"].append({"pos": [x, y], "text": "CONSULTANTS", "size": 4.5, "layer": "TITLEBLOCK"})
        current_y = y - 1.5
        for cons in consultants:
            geom["texts"].append({"pos": [x, current_y], "text": cons, "size": 3.0, "layer": "TITLEBLOCK"})
            current_y -= 1.5
        return geom

    @staticmethod
    def draw_sheet_index(x: float, y: float, sheets: List[Dict[str, str]]) -> Dict[str, List]:
        """Draws the architectural sheet index."""
        geom = {"lines": [], "blocks": [], "texts": []}
        geom["texts"].append({"pos": [x, y], "text": "SHEET INDEX", "size": 5.0, "layer": "TITLEBLOCK"})
        current_y = y - 2.0
        for sheet in sheets:
            text = f"{sheet.get('num', '')} - {sheet.get('title', '')}"
            geom["texts"].append({"pos": [x, current_y], "text": text, "size": 3.5, "layer": "TITLEBLOCK"})
            current_y -= 2.0
        return geom

    @staticmethod
    def build_standard_title_block(sheet_size: str, project_name: str, sheet_num: str, sheet_title: str, scale: str) -> Dict[str, List]:
        """Composes a complete standard title block."""
        sheet_w, sheet_h = (17.0, 11.0) if sheet_size == '11x17' else (36.0, 24.0)
        strip_w = 3.0
        
        geom = {"lines": [], "blocks": [], "texts": []}
        
        # Merge strip
        strip = TitleBlockEngine.draw_vertical_strip(sheet_w, sheet_h, strip_w)
        geom["lines"].extend(strip["lines"])
        geom["blocks"].extend(strip["blocks"])
        
        # Center of strip
        cx = sheet_w - (strip_w / 2.0)
        
        # Top: Project Info
        proj = TitleBlockEngine.add_project_metadata(cx, sheet_h - 2.0, project_name, "Client XYZ")
        geom["texts"].extend(proj["texts"])
        
        # Middle: Revisions
        revs = TitleBlockEngine.add_revision_log(cx, sheet_h - 6.0, [{"date": "2024-01-01", "desc": "Initial Issue"}])
        geom["texts"].extend(revs["texts"])
        
        # Bottom: Sheet Info
        info = TitleBlockEngine.add_sheet_info(cx, 8.0, sheet_num, sheet_title, scale)
        geom["texts"].extend(info["texts"])
        
        return geom
