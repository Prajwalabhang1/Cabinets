from typing import Dict, List

class DimensionEngine:
    """Generates standard CAD-compatible dimension objects."""

    @staticmethod
    def generate_horizontal_chain(components: List[Dict], start_x: float, y_pos: float, scale: float = 1.0) -> List[Dict]:
        """Generates continuous chain dimensions for a row of components with collision avoidance."""
        dims = []
        current_x = start_x
        toggle_offset = False
        
        for comp in components:
            width = float(comp.get('width', 0))
            if width > 0:
                scaled_width = width * scale
                # Collision Avoidance: Stagger narrow dimensions vertically
                if scaled_width < 18.0:
                    current_y_pos = y_pos + (12.0 * scale if toggle_offset else 0.0)
                    toggle_offset = not toggle_offset
                else:
                    current_y_pos = y_pos
                    toggle_offset = False
                    
                dims.append({
                    "start": [current_x, current_y_pos],
                    "end": [current_x + scaled_width, current_y_pos],
                    "text": f'{width}"'
                })
                current_x += scaled_width
                
        return dims

    @staticmethod
    def generate_overall_dimensions(start_pos: List[float], end_pos: List[float], total_width: float) -> Dict:
        """Generates the overall total dimension line."""
        return {
            "start": start_pos,
            "end": end_pos,
            "text": f"{total_width}\""
        }

    @staticmethod
    def generate_vertical_dimensions(start_pos: List[float], end_pos: List[float], total_height: float) -> Dict:
        """Generates overall vertical dimension."""
        return {
            "start": start_pos,
            "end": end_pos,
            "text": f"{total_height}\""
        }

    @staticmethod
    def generate_opening_dimensions(start_pos: List[float], end_pos: List[float], width: float, label: str = "OPENING") -> Dict:
        """Generates dimension for appliance/fixture openings."""
        return {
            "start": start_pos,
            "end": end_pos,
            "text": f"{width}\" {label}"
        }

    @staticmethod
    def generate_countertop_dimensions(start_pos: List[float], end_pos: List[float], width: float) -> Dict:
        """Generates countertop specific dimensions including overhangs."""
        return {
            "start": start_pos,
            "end": end_pos,
            "text": f"{width}\" C.TOP"
        }

    @staticmethod
    def generate_appliance_dimensions(start_pos: List[float], end_pos: List[float], width: float, label: str) -> Dict:
        """Generates specific appliance dimension callouts."""
        return {
            "start": start_pos,
            "end": end_pos,
            "text": f"{width}\" {label}"
        }

    @staticmethod
    def generate_clearance_dimensions(start_pos: List[float], end_pos: List[float], width: float, required_clearance: float) -> Dict:
        """Generates clearance dimensions for ADA validation."""
        return {
            "start": start_pos,
            "end": end_pos,
            "text": f"{width}\" CLR (MIN {required_clearance}\")"
        }
