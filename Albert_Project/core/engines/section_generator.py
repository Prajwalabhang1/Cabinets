from typing import Dict, List, Any

class SectionGenerator:
    """Generate detailed CAD sections with fabrication specs."""
    
    SECTION_TYPES = {
        'kitchen_ada': {
            'title': 'KITCHEN ADA',
            'height': 228.0,  # 7'-6" typical
            'callouts': [
                'PLYWOOD BACKING 6" H',
                'ACCESSIBLE CABINET',
                'ADA SINK - MAX 34" HEIGHT TO COUNTERTOP',
            ]
        },
        'kitchen_drawer': {
            'title': 'KITCHEN DRAWER',
            'notes': 'Show internal drawer construction'
        },
        'kitchen_refrigerator': {
            'title': 'REFRIGERATOR SECTION',
            'callouts': [
                'REFRIGERATOR GTE18GSNRSS',
                'PLYWOOD BACKING 6" H',
                'CLEARANCE FOR DOOR SWING'
            ]
        },
        'kitchen_microwave': {
            'title': 'MICROWAVE SECTION',
            'callouts': [
                '24" MICROWAVE JVM3160RFSS',
                'MOUNTING BRACKETS',
                'CLEARANCE BELOW: MIN 15"'
            ]
        },
        'kitchen_hood': {
            'title': 'KITCHEN HOOD',
            'callouts': [
                'RANGE HOOD (ADA: JVX3300SJSS)',
                'MIN 24" ABOVE RANGE',
                'DUCTWORK BY OTHERS'
            ]
        },
        'kitchen_pantry': {
            'title': 'PANTRY SECTION',
            'height': 228.0,  # Full 7'-6" height
            'callouts': [
                'FULL HEIGHT PANTRY',
                'SHELVING EVERY 12"',
                'PLYWOOD BACKING FULL HEIGHT'
            ]
        },
        'vanity_ada': {
            'title': 'VANITY ADA',
            'callouts': [
                'FULL ACCESSIBLE LAVATORY W/COVERED PANEL',
                'KNEE CLEARANCE: MIN 27" W x 19" D @ 32" H',
                'ACCESSIBILITY REQUIREMENTS MET',
                'MOUNTED PER ADA GUIDELINES'
            ]
        },
        'vanity_pantry': {
            'title': 'VANITY PANTRY',
            'height': 228.0,
            'callouts': [
                'FULL HEIGHT LINEN STORAGE',
                'ADJUSTABLE SHELVES',
                'PLYWOOD BACKING 6" H'
            ]
        }
    }
    
    @classmethod
    def generate_section(cls, section_type: str, **kwargs) -> Dict[str, Any]:
        """Generate detailed section drawing.
        
        Args:
            section_type: One of SECTION_TYPES keys
            **kwargs: Additional parameters (width, height, etc.)
        
        Returns:
            Dictionary with section geometry and callouts
        """
        if section_type not in cls.SECTION_TYPES:
            raise ValueError(f"Unknown section type: {section_type}")
        
        spec = cls.SECTION_TYPES[section_type]
        section = {
            'type': section_type,
            'title': spec['title'],
            'geometry': {
                'lines': [],
                'blocks': [],
                'circles': [],
                'texts': [],
                'dimensions': []
            },
            'callouts': spec.get('callouts', []),
            'notes': spec.get('notes', '')
        }
        
        # Generate base outline
        cls._draw_base_outline(section, kwargs.get('width', 84.0), 
                              kwargs.get('height', spec.get('height', 84.0)))
        
        # Add specific details based on type
        if section_type == 'kitchen_ada':
            cls._add_kitchen_ada_details(section, **kwargs)
        elif section_type == 'kitchen_drawer':
            cls._add_drawer_details(section, **kwargs)
        elif section_type == 'vanity_ada':
            cls._add_vanity_ada_details(section, **kwargs)
        # ... more section types
        
        # Add dimensions
        cls._add_dimensions(section, **kwargs)
        
        return section
    
    @staticmethod
    def _draw_base_outline(section: Dict, width: float, height: float, **kwargs):
        """Draw full cabinet profile."""
        geom = section['geometry']
        
        # Determine ADA flag for height
        is_ada = kwargs.get('ada', False)
        
        # FLOOR LINE
        geom['lines'].append({'start': [0, 0], 'end': [width, 0], 'layer': 'FLOOR'})
        
        # TOE KICK (3" inset, 4" high)
        toe_kick_y = 4.0
        toe_kick_inset = 3.0
        geom['blocks'].append({
            'type': 'rect',
            'coords': [toe_kick_inset, 0, width - toe_kick_inset, toe_kick_y],
            'hatch': 'DIAGONAL',
            'layer': 'STRUCTURE'
        })
        
        # BASE CABINET (24" depth, 28.4" height standard, 34" ADA max minus toe kick)
        # 34" total ADA counter height - 1.6" counter = 32.4" top of cabinet.
        # Height of base cab above floor: 28.4" standard, 32.4" ADA.
        base_top = 32.4 if is_ada else 28.4
        geom['blocks'].append({
            'type': 'rect',
            'coords': [0, toe_kick_y, width, base_top],
            'fill': False,
            'layer': 'CABINET'
        })
        
        # PLYWOOD BACKING (6" height)
        plywood_height = 6.0
        geom['blocks'].append({
            'type': 'rect',
            'coords': [0, toe_kick_y, width, toe_kick_y + plywood_height],
            'hatch': 'BRICKS',
            'layer': 'BACKING'
        })
        
        # COUNTERTOP (1.6" thick, 1" overhang on front)
        counter_y = base_top
        counter_thickness = 1.6
        counter_overhang = 1.0
        geom['blocks'].append({
            'type': 'rect',
            'coords': [-counter_overhang, counter_y, width + counter_overhang, counter_y + counter_thickness],
            'fill': False,
            'layer': 'COUNTERTOP'
        })
        
        # UPPER CABINET (12" depth typical, 30" height, 16" clearance from counter)
        upper_y = counter_y + counter_thickness + 16.0
        upper_height = 30.0
        upper_depth = 12.0
        # Determine depth of the wall bounds (which is 'width' passed to function, e.g. 24")
        # Upper cabinet is typically flush with back wall
        geom['blocks'].append({
            'type': 'rect',
            'coords': [width - upper_depth, upper_y, width, upper_y + upper_height],
            'fill': False,
            'layer': 'CABINET'
        })

    
    @staticmethod
    def _add_kitchen_ada_details(section: Dict, **kwargs):
        """Add ADA-specific kitchen section details."""
        geom = section['geometry']
        
        # Accessible cabinet marker
        geom['texts'].append({
            'pos': [kwargs.get('width', 24.0) / 2, 15.0],
            'text': 'ACCESSIBLE CABINET',
            'size': 4.0,
            'layer': 'CALLOUTS',
            'bold': True
        })
        
        # Sink clearance zone (typical 27" W x 19" D)
        # Note: In section view, we are looking at the side profile. 
        # Knee clearance is 19" depth from front of cabinet.
        # Height is typically 27" min.
        width = kwargs.get('width', 24.0)
        knee_height = 27.0
        knee_depth = 19.0
        geom['blocks'].append({
            'type': 'rect',
            'coords': [-1.0, 0, knee_depth - 1.0, knee_height],
            'id': 'SINK_CLEAR',
            'layer': 'ACCESSIBILITY',
            'fill': False,
            'linestyle': 'dashed'
        })

    @staticmethod
    def _add_drawer_details(section: Dict, **kwargs):
        pass
    
    @staticmethod
    def _add_vanity_ada_details(section: Dict, **kwargs):
        """Add ADA vanity section details."""
        geom = section['geometry']
        
        # Covered panel specification
        geom['blocks'].append({
            'type': 'rect',
            'coords': [0, 0, kwargs.get('width', 61.0), 32.0],
            'id': 'COVERED_PANEL',
            'layer': 'CONSTRUCTION',
            'fill': False
        })
        
        # Knee clearance callout
        geom['texts'].append({
            'pos': [kwargs.get('width', 61.0) / 2, 16.0],
            'text': 'FULL ACCESSIBLE LAVATORY\nW/COVERED PANEL',
            'size': 3.5,
            'layer': 'CALLOUTS',
            'align': 'center'
        })
    
    @staticmethod
    def _add_dimensions(section: Dict, **kwargs):
        """Add 15-20 dimension lines capturing all critical measurements."""
        geom = section['geometry']
        is_ada = kwargs.get('ada', False)
        
        width = kwargs.get('width', 24.0)
        base_top = 32.4 if is_ada else 28.4
        toe_kick_y = 4.0
        counter_y = base_top
        upper_y = counter_y + 1.6 + 16.0
        
        dims = []
        
        # LEFT SIDE VERTICAL DIMENSIONS
        dims.extend([
            # Floor to toe kick top
            {'start': [-30, 0], 'end': [-30, toe_kick_y], 'text': str(toe_kick_y), 'label': 'TOE KICK', 'position': 'left'},
            # Toe kick to counter top
            {'start': [-30, toe_kick_y], 'end': [-30, counter_y], 'text': str(round(base_top - toe_kick_y, 1)), 'label': 'BASE CAB HEIGHT', 'position': 'left'},
            # Counter thickness
            {'start': [-30, counter_y], 'end': [-30, counter_y + 1.6], 'text': "1.6", 'label': 'COUNTERTOP', 'position': 'left'},
            # Clearance from counter to upper
            {'start': [-30, counter_y + 1.6], 'end': [-30, upper_y], 'text': "16.0", 'label': 'CLEARANCE', 'position': 'left'},
            # Upper cabinet height
            {'start': [-30, upper_y], 'end': [-30, upper_y + 30.0], 'text': "30.0", 'label': 'UPPER CAB HEIGHT', 'position': 'left'},
            # Total height (example 84")
            {'start': [-45, 0], 'end': [-45, 84.0], 'text': "84.0", 'label': 'TOTAL HEIGHT', 'position': 'left'},
        ])
        
        # BOTTOM HORIZONTAL DIMENSIONS
        dims.extend([
            # Width
            {'start': [0, -15], 'end': [width, -15], 'text': str(width), 'label': 'BASE DEPTH', 'position': 'below'},
            # Toe kick inset (left front)
            {'start': [0, -5], 'end': [3, -5], 'text': "3.0", 'label': 'INSET', 'position': 'below'}
        ])
        
        # UPPER DEPTH
        dims.extend([
            # Upper cabinet depth
            {'start': [width - 12, upper_y + 35], 'end': [width, upper_y + 35], 'text': "12.0", 'label': 'UPPER DEPTH', 'position': 'above'},
        ])
        
        # APPLIANCE-SPECIFIC DIMENSIONS
        if 'refrigerator' in section.get('type', '').lower():
            dims.append({'start': [0, counter_y + 1.6], 'end': [28, counter_y + 1.6], 'text': "28.0", 'label': 'FRIDGE WIDTH', 'position': 'above'})
        
        if 'sink' in section.get('type', '').lower() or 'vanity' in section.get('type', '').lower() or is_ada:
            if is_ada:
                # Knee clearance dimensions (side profile)
                dims.extend([
                    {'start': [-1, toe_kick_y + 15], 'end': [18, toe_kick_y + 15], 'text': "19.0", 'label': 'KNEE DEPTH', 'position': 'above'},
                ])
        
        geom['dimensions'].extend(dims)
