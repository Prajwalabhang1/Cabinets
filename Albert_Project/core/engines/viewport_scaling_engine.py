from typing import Dict, List, Tuple

class ViewportScalingEngine:
    SHEET_SIZES = {
        '11x17': {'w': 17.0, 'h': 11.0},
        '24x36': {'w': 36.0, 'h': 24.0}
    }
    
    SCALES = {
        "1/2\"=1'-0\"": 24.0,
        "3/8\"=1'-0\"": 32.0,
        "1/4\"=1'-0\"": 48.0,
        "1/8\"=1'-0\"": 96.0
    }
    
    @staticmethod
    def get_bounds(geometry: Dict[str, List]) -> Tuple[float, float, float, float]:
        min_x, min_y = float('inf'), float('inf')
        max_x, max_y = float('-inf'), float('-inf')
        has_geometry = False
        
        for rect in geometry.get('blocks', []):
            if rect['type'] == 'rect':
                x, y, w, h = rect['coords']
                min_x, max_x = min(min_x, x), max(max_x, x + w)
                min_y, max_y = min(min_y, y), max(max_y, y + h)
                has_geometry = True
            elif rect['type'] == 'circle':
                x, y, r = rect['coords']
                min_x, max_x = min(min_x, x - r), max(max_x, x + r)
                min_y, max_y = min(min_y, y - r), max(max_y, y + r)
                has_geometry = True
                
        for line in geometry.get('lines', []):
            x1, y1 = line['start']
            x2, y2 = line['end']
            min_x, max_x = min(min_x, x1, x2), max(max_x, x1, x2)
            min_y, max_y = min(min_y, y1, y2), max(max_y, y1, y2)
            has_geometry = True
            
        if not has_geometry:
            return 0.0, 0.0, 0.0, 0.0
        return min_x, min_y, max_x, max_y

    @staticmethod
    def compute_scale(bbox: Tuple[float, float, float, float], sheet_bounds: Tuple[float, float], margins: float = 1.0) -> float:
        min_x, min_y, max_x, max_y = bbox
        geom_w = max_x - min_x
        geom_h = max_y - min_y
        
        if geom_w <= 0 or geom_h <= 0:
            return 1.0
            
        sheet_w, sheet_h = sheet_bounds
        avail_w = sheet_w - (margins * 2)
        avail_h = sheet_h - (margins * 2)
        
        scale_x = avail_w / geom_w
        scale_y = avail_h / geom_h
        
        return min(scale_x, scale_y) * 0.9  # 90% to leave breathing room

    @staticmethod
    def center_geometry(geometry: Dict[str, List], dx: float, dy: float, scale: float = 1.0) -> Dict[str, List]:
        centered = {'lines': [], 'blocks': [], 'texts': []}
        
        for b in geometry.get('blocks', []):
            nb = b.copy()
            if b['type'] == 'rect':
                x, y, w, h = b['coords']
                nb['coords'] = [(x * scale) + dx, (y * scale) + dy, w * scale, h * scale]
            elif b['type'] == 'circle':
                x, y, r = b['coords']
                nb['coords'] = [(x * scale) + dx, (y * scale) + dy, r * scale]
            centered['blocks'].append(nb)
            
        for l in geometry.get('lines', []):
            nl = l.copy()
            x1, y1 = l['start']
            x2, y2 = l['end']
            nl['start'] = [(x1 * scale) + dx, (y1 * scale) + dy]
            nl['end'] = [(x2 * scale) + dx, (y2 * scale) + dy]
            centered['lines'].append(nl)
            
        for t in geometry.get('texts', []):
            nt = t.copy()
            x, y = t['pos']
            nt['pos'] = [(x * scale) + dx, (y * scale) + dy]
            nt['size'] = t.get('size', 4.5) * scale
            centered['texts'].append(nt)
            
        return centered
        
    @staticmethod
    def fit_to_sheet(geometry: Dict[str, List], sheet_size: str = '11x17') -> Dict[str, List]:
        size = ViewportScalingEngine.SHEET_SIZES.get(sheet_size, ViewportScalingEngine.SHEET_SIZES['11x17'])
        sheet_w, sheet_h = size['w'], size['h']
        
        bbox = ViewportScalingEngine.get_bounds(geometry)
        scale = ViewportScalingEngine.compute_scale(bbox, (sheet_w, sheet_h))
        
        min_x, min_y, max_x, max_y = bbox
        geom_center_x = (min_x + max_x) / 2.0 * scale
        geom_center_y = (min_y + max_y) / 2.0 * scale
        
        sheet_center_x = sheet_w / 2.0
        sheet_center_y = sheet_h / 2.0
        
        dx = sheet_center_x - geom_center_x
        dy = sheet_center_y - geom_center_y
        
        return ViewportScalingEngine.center_geometry(geometry, dx, dy, scale)
