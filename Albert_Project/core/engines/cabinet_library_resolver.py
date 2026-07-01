import re
from functools import lru_cache
from typing import Dict, Any

class CabinetLibraryResolver:
    @staticmethod
    @lru_cache(maxsize=512)
    def resolve_cabinet(nomenclature: str) -> Dict[str, Any]:
        """Resolves a cabinet string like SB36 or W3036 into a detailed dictionary."""
        nom = nomenclature.upper().strip()
        
        # Extract all numbers
        nums = re.findall(r'\d+', nom)
        width = float(nums[0]) if nums else 0.0
        height = 0.0
        depth = 0.0
        
        family = 'BASE'
        render_style = 'standard'
        doors = 1 if width < 24 else 2
        drawers = 1 if width < 24 else 2
        
        if nom.startswith('W'):
            family = 'UPPER'
            depth = 12.0
            if len(nums) >= 2:
                height = float(nums[1])
            else:
                height = 30.0
            drawers = 0
            if nom.startswith('WF'):
                render_style = 'filler'
                doors = 0
            elif nom.startswith('WEP') or nom == 'WP':
                render_style = 'panel'
                width = width if width > 0 else 1.5
                doors = 0
            
        elif nom.startswith('P') or nom.startswith('WP') or nom.startswith('REP'):
            family = 'TALL'
            depth = 24.0
            height = 84.0
            if len(nums) >= 2:
                height = float(nums[1])
            drawers = 0
            if nom.startswith('TF'):
                render_style = 'filler'
                doors = 0
            elif nom.startswith('REP') or nom.startswith('TP') or nom.startswith('TEP'):
                render_style = 'panel'
                width = width if width > 0 else 1.5
                doors = 0
            
        elif nom.startswith('SB') or 'SINK' in nom:
            family = 'BASE'
            depth = 24.0
            height = 34.5
            render_style = 'sink_base'
            drawers = 0 # Sink bases usually have false fronts, not functional drawers
            
        elif nom.startswith('DB') or nom.startswith('3DB') or nom.startswith('4DB'):
            family = 'BASE'
            depth = 24.0
            height = 34.5
            render_style = 'drawer_base'
            doors = 0
            if '3' in nom: drawers = 3
            elif '4' in nom: drawers = 4
            else: drawers = 3
            
        elif nom.startswith('F') or nom.startswith('BF'):
            family = 'BASE'
            depth = 24.0
            height = 34.5
            render_style = 'filler'
            doors = 0
            drawers = 0
            
        elif nom.startswith('BEP') or nom == 'BP':
            family = 'BASE'
            depth = 24.0
            height = 34.5
            render_style = 'panel'
            width = width if width > 0 else 1.5
            doors = 0
            drawers = 0
            
        else:
            family = 'BASE'
            depth = 24.0
            height = 34.5
            
        return {
            'family': family,
            'width': width,
            'depth': depth,
            'height': height,
            'doors': doors,
            'drawers': drawers,
            'render_style': render_style
        }
