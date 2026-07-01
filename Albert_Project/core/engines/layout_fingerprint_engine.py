import json
import hashlib
from typing import Dict, Any, List

class LayoutFingerprintEngine:
    """
    Engine to generate a deterministic, hierarchical architectural fingerprint 
    for kitchens and vanities. This signature is based on layout topology, 
    cabinet geometry, appliance placements, and ADA requirements.
    """

    @staticmethod
    def _infer_layout_topology(cabinets: List[Dict[str, Any]]) -> str:
        """
        Infer if the layout is Straight, L-Shape, U-Shape, etc. 
        based on corner cabinets and bounding boxes.
        """
        corner_count = 0
        for cab in cabinets:
            cab_type = cab.get('cabinet_type', '').lower()
            notes = cab.get('notes', '').lower()
            if 'corner' in cab_type or 'blind' in cab_type or 'corner' in notes:
                corner_count += 1
        
        if corner_count == 0:
            return "Straight"
        elif corner_count == 1:
            return "L-Shape"
        elif corner_count >= 2:
            return "U-Shape"
        return "Complex"

    @staticmethod
    def _extract_cabinets(cabinets: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Extract purely cabinet geometry and types."""
        extracted = []
        for cab in cabinets:
            cab_type = cab.get('cabinet_type', '')
            if 'appliance' in cab_type or 'microwave' in cab_type:
                continue
            
            extracted.append({
                "type": cab_type,
                "width": cab.get('width_in', 0.0),
                "height": cab.get('height_in', 0.0),
                "depth": cab.get('depth_in', 0.0),
                "position_hint": cab.get('location', '')
            })
        return extracted

    @staticmethod
    def _extract_appliances(cabinets: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Extract appliance spaces from the sequence."""
        extracted = []
        for cab in cabinets:
            cab_type = cab.get('cabinet_type', '')
            if 'appliance' in cab_type or 'microwave' in cab_type or 'ref' in cab.get('notes', '').lower() or 'range' in cab.get('notes', '').lower():
                extracted.append({
                    "type": cab_type,
                    "width": cab.get('width_in', 0.0),
                    "notes": cab.get('notes', '')
                })
        return extracted

    @staticmethod
    def _extract_openings(cabinets: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Extract explicit openings (windows/doors/columns) if mentioned."""
        openings = []
        for cab in cabinets:
            notes = cab.get('notes', '').lower()
            if 'window' in notes:
                openings.append({"type": "Window", "near": cab.get('location', '')})
            if 'door' in notes:
                openings.append({"type": "Door", "near": cab.get('location', '')})
            if 'column' in notes:
                openings.append({"type": "Column", "near": cab.get('location', '')})
        return openings

    @staticmethod
    def generate_fingerprint(unit_elevation: Dict[str, Any]) -> str:
        """
        Generates the MD5 hash of the hierarchical fingerprint for an elevation.
        """
        cabinets = unit_elevation.get('cabinets', [])
        is_ada = unit_elevation.get('is_ada', False)
        
        # 1. Layout Topology
        layout = LayoutFingerprintEngine._infer_layout_topology(cabinets)
        
        # 2. Cabinets
        cabs_fingerprint = LayoutFingerprintEngine._extract_cabinets(cabinets)
        
        # 3. Appliances
        apps_fingerprint = LayoutFingerprintEngine._extract_appliances(cabinets)
        
        # 4. Openings
        openings = LayoutFingerprintEngine._extract_openings(cabinets)
        
        # 5. Overall dimensions
        total_width = sum(c.get('width_in', 0.0) for c in cabinets if c.get('cabinet_type') not in ['upper_wall'])
        
        # Build hierarchy
        fingerprint_dict = {
            "Layout": layout,
            "Cabinets": cabs_fingerprint,
            "Appliances": apps_fingerprint,
            "Openings": openings,
            "Countertop": {
                "Topology": layout,
                "CornerCount": sum(1 for c in cabinets if 'corner' in c.get('cabinet_type', '').lower())
            },
            "ADA": is_ada,
            "Overall": {
                "TotalBaseWidth": total_width
            }
        }
        
        # Hash
        sig_str = json.dumps(fingerprint_dict, sort_keys=True)
        return hashlib.md5(sig_str.encode()).hexdigest()
