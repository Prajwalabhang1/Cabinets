from typing import Dict, List, Any
from collections import defaultdict

class MaterialTakeoffEngine:
    """Generates a Bill of Materials (BOM) for fabrication."""

    @staticmethod
    def generate_takeoff(cabinets: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Calculates material requirements based on the cabinet schedule."""
        takeoff = {
            "total_cabinets": len(cabinets),
            "sheet_goods_34": 0.0,  # 3/4" material (e.g. plywood) in sq ft
            "sheet_goods_14": 0.0,  # 1/4" material (e.g. backings) in sq ft
            "linear_edgebanding": 0.0, # edgebanding in linear feet
            "hardware": defaultdict(int)
        }

        for cab in cabinets:
            w_in = cab.get('width', 0)
            h_in = cab.get('height', 0)
            d_in = cab.get('depth', 0)
            
            # Simple heuristic calculations for a standard box
            # 2 sides, 1 top, 1 bottom, 1 back
            side_area = (h_in * d_in) / 144.0
            top_bottom_area = (w_in * d_in) / 144.0
            back_area = (w_in * h_in) / 144.0
            
            takeoff["sheet_goods_34"] += (side_area * 2) + (top_bottom_area * 2)
            takeoff["sheet_goods_14"] += back_area
            
            # Hardware
            doors = cab.get('doors', 0)
            drawers = cab.get('drawers', 0)
            
            if doors > 0:
                takeoff["hardware"]["hinges"] += (doors * 2)
                takeoff["hardware"]["pulls"] += doors
                
            if drawers > 0:
                takeoff["hardware"]["drawer_slides"] += drawers
                takeoff["hardware"]["pulls"] += drawers
                
        # Convert defaultdict back to dict for clean JSON serialization
        takeoff["hardware"] = dict(takeoff["hardware"])
        
        return takeoff

    @staticmethod
    def print_takeoff(takeoff: Dict[str, Any]) -> str:
        """Formats the BOM for printing."""
        lines = []
        lines.append("=== MATERIAL TAKEOFF (BOM) ===")
        lines.append(f"Total Cabinets: {takeoff['total_cabinets']}")
        lines.append(f"3/4\" Sheet Goods (sq ft): {takeoff['sheet_goods_34']:.2f}")
        lines.append(f"1/4\" Sheet Goods (sq ft): {takeoff['sheet_goods_14']:.2f}")
        
        lines.append("\nHardware Requirements:")
        for hw, qty in takeoff['hardware'].items():
            lines.append(f"  - {hw.replace('_', ' ').title()}: {qty}")
            
        return "\n".join(lines)
