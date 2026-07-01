from typing import Dict, List
from dataclasses import dataclass

@dataclass
class CabinetPart:
    """Single part in a cabinet assembly."""
    part_id: str           # "A", "B", "C", etc.
    description: str       # "SIDE PANEL 2 TIMES PER KITCHEN"
    width_mm: float
    height_mm: float
    width_in: float
    height_in: float
    quantity: int
    material: str
    finish: str
    notes: str = ""
    edge_banding: str = ""
    hinge_spec: str = ""

class PartsListGenerator:
    """Generate parts lists for shop drawings."""
    
    # Standard parts for 90CM base kitchen
    KITCHEN_BASE_90CM_PARTS = [
        CabinetPart(
            part_id='A',
            description='BASE 90 CM',
            width_mm=900, height_mm=720, width_in=35.4, height_in=28.4,
            quantity=1,
            material='PLYWOOD',
            finish='STRUCTURE WHITE PER KITCHEN',
            edge_banding='1mm PVC WHITE'
        ),
        CabinetPart(
            part_id='B',
            description='SIDE PANEL',
            width_mm=600, height_mm=720, width_in=23.6, height_in=28.4,
            quantity=2,
            material='PLYWOOD',
            finish='FIXED PANEL FINISH',
            edge_banding='1mm PVC COLOR MATCH'
        ),
        CabinetPart(
            part_id='C',
            description='BACK PANEL',
            width_mm=900, height_mm=600, width_in=35.4, height_in=23.6,
            quantity=1,
            material='PLYWOOD',
            finish='STRUCTURE WHITE PER KITCHEN'
        ),
        # ... more standard parts
    ]
    
    KITCHEN_ADA_SINK_PARTS = [
        CabinetPart(
            part_id='A',
            description='KITCHEN ADA SINK',
            width_mm=840, height_mm=720, width_in=33.1, height_in=28.4,
            quantity=1,
            material='PLYWOOD',
            finish='FIXED PANEL FINISH'
        ),
        CabinetPart(
            part_id='B',
            description='SIDE PANEL',
            width_mm=600, height_mm=720, width_in=23.6, height_in=28.4,
            quantity=2,
            material='PLYWOOD',
            finish='FIXED PANEL FINISH'
        ),
        # ... more parts
    ]
    
    @classmethod
    def generate_parts_list(cls, cabinet_type: str, kitchen_type: str) -> Dict:
        """Generate parts list for a specific cabinet type."""
        if cabinet_type == 'base_90cm':
            parts = cls.KITCHEN_BASE_90CM_PARTS
        elif cabinet_type == 'ada_sink':
            parts = cls.KITCHEN_ADA_SINK_PARTS
        else:
            parts = []
        
        parts_list = {
            'cabinet_type': cabinet_type,
            'kitchen_type': kitchen_type,
            'parts': parts,
            'total_parts': sum(p.quantity for p in parts),
            'scale': '1/2" = 1\'-0"'
        }
        
        return parts_list
    
    @classmethod
    def generate_all_parts_sheets(cls, project_config) -> List[Dict]:
        """Generate complete parts list sheets for project."""
        sheets = []
        kitchen_sheet = cls._generate_kitchen_sheet(project_config)
        sheets.append(kitchen_sheet)
        vanity_sheet = cls._generate_vanity_sheet(project_config)
        sheets.append(vanity_sheet)
        return sheets
    
    @staticmethod
    def _generate_kitchen_sheet(project_config) -> Dict:
        """Create kitchen parts sheet."""
        return {
            'title': 'PARTS BY KITCHEN',
            'scale': '1/2" = 1\'-0"',
            'page_layout': [
                {
                    'section': 'BASE 90 CM',
                    'parts': PartsListGenerator.KITCHEN_BASE_90CM_PARTS,
                    'position': [50, 500]
                },
                {
                    'section': 'ADA SINK',
                    'parts': PartsListGenerator.KITCHEN_ADA_SINK_PARTS,
                    'position': [50, 200]
                }
            ]
        }
    
    @staticmethod
    def _generate_vanity_sheet(project_config) -> Dict:
        """Create vanity parts sheet."""
        return {
            'title': 'PARTS BY VANITIES',
            'scale': '1/2" = 1\'-0"',
            'page_layout': [
                {
                    'section': 'VANITIES ADA SINK',
                    'parts': [],
                    'position': [50, 300]
                }
            ]
        }
