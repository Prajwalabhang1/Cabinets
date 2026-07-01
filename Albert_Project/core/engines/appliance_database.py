from dataclasses import dataclass
from typing import Dict, Optional, List

@dataclass
class ApplianceModel:
    """Specification for a single appliance model."""
    model_code: str          # e.g., "GTE18GSNRSS"
    model_name: str          # e.g., "GTE18GSNRSS"
    appliance_type: str      # "refrigerator", "range", "dishwasher", "microwave", "hood"
    width_in: float
    height_in: float
    depth_in: float
    width_mm: float
    height_mm: float
    depth_mm: float
    is_ada: bool
    manufacturer: str
    notes: str = ""

class ApplianceDatabase:
    """Central database for appliance specifications."""
    
    CATALOG = {
        # Refrigerators
        "GTE18GSNRSS": ApplianceModel(
            model_code="GTE18GSNRSS",
            model_name="GTE18GSNRSS",
            appliance_type="refrigerator",
            width_in=28.0,
            height_in=67.6,
            depth_in=29.75,
            width_mm=711.2,
            height_mm=1717.04,
            depth_mm=755.65,
            is_ada=False,
            manufacturer="GE",
            notes="Standard French door refrigerator"
        ),
        
        # Ranges - Regular
        "GRF400PV": ApplianceModel(
            model_code="GRF400PV",
            model_name="GRF400PV",
            appliance_type="range",
            width_in=30.0,
            height_in=36.0,
            depth_in=28.75,
            width_mm=762.0,
            height_mm=914.4,
            depth_mm=730.3,
            is_ada=False,
            manufacturer="GE",
            notes="Gas range with oven"
        ),
        
        # Ranges - ADA
        "GRS500PVSS": ApplianceModel(
            model_code="GRS500PVSS",
            model_name="GRS500PVSS",
            appliance_type="range",
            width_in=30.0,
            height_in=34.0,
            depth_in=28.5,
            width_mm=762.0,
            height_mm=863.6,
            depth_mm=723.9,
            is_ada=True,
            manufacturer="GE",
            notes="ADA-compliant gas range, max 34\" height"
        ),
        
        # Dishwashers - Regular
        "GDT535PSRSS": ApplianceModel(
            model_code="GDT535PSRSS",
            model_name="GDT535PSRSS",
            appliance_type="dishwasher",
            width_in=24.0,
            height_in=33.875,
            depth_in=24.75,
            width_mm=609.6,
            height_mm=860.55,
            depth_mm=628.65,
            is_ada=False,
            manufacturer="GE",
            notes="Standard undercounter dishwasher"
        ),
        
        # Dishwashers - ADA
        "GDT225SSLSS": ApplianceModel(
            model_code="GDT225SSLSS",
            model_name="GDT225SSLSS ADA",
            appliance_type="dishwasher",
            width_in=24.0,
            height_in=33.875,
            depth_in=24.75,
            width_mm=609.6,
            height_mm=860.55,
            depth_mm=628.65,
            is_ada=True,
            manufacturer="GE",
            notes="ADA-compliant dishwasher"
        ),
        
        # Microwaves - Regular
        "JVM3160RFSS": ApplianceModel(
            model_code="JVM3160RFSS",
            model_name="JVM3160RFSS",
            appliance_type="microwave",
            width_in=30.0,
            height_in=15.875,
            depth_in=15.375,
            width_mm=762.0,
            height_mm=403.225,
            depth_mm=390.525,
            is_ada=False,
            manufacturer="GE",
            notes="Over-the-range microwave"
        ),
        
        # Microwaves - ADA
        "JES1145SHSS": ApplianceModel(
            model_code="JES1145SHSS",
            model_name="JES1145SHSS",
            appliance_type="microwave",
            width_in=30.0,
            height_in=15.625,
            depth_in=15.375,
            width_mm=762.0,
            height_mm=396.875,
            depth_mm=390.525,
            is_ada=True,
            manufacturer="GE",
            notes="ADA-compliant microwave oven"
        ),
        
        # Range Hoods - ADA Only
        "JVX3300SJSS": ApplianceModel(
            model_code="JVX3300SJSS",
            model_name="JVX3300SJSS",
            appliance_type="hood",
            width_in=30.0,
            height_in=17.0,
            depth_in=20.0,
            width_mm=762.0,
            height_mm=431.8,
            depth_mm=508.0,
            is_ada=True,
            manufacturer="GE",
            notes="ADA range hood for accessible kitchens"
        ),
        
        # Another refrigerator model just in case
        "GTE18GTNRBB": ApplianceModel(
            model_code="GTE18GTNRBB",
            model_name="GTE18GTNRBB",
            appliance_type="refrigerator",
            width_in=28.0,
            height_in=67.6,
            depth_in=29.75,
            width_mm=711.2,
            height_mm=1717.04,
            depth_mm=755.65,
            is_ada=False,
            manufacturer="GE",
            notes="Standard refrigerator"
        )
    }
    
    @classmethod
    def get_appliance(cls, model_code: str) -> Optional[ApplianceModel]:
        """Retrieve appliance specification by model code."""
        return cls.CATALOG.get(model_code)
    
    @classmethod
    def get_appliances_by_type(cls, appliance_type: str, ada: bool = False) -> List[ApplianceModel]:
        """Get all appliances of a type (optionally filtered for ADA)."""
        return [
            app for app in cls.CATALOG.values()
            if app.appliance_type == appliance_type
            and (not ada or app.is_ada)
        ]
    
    @classmethod
    def get_appliance_schedule(cls, project_config: dict) -> dict:
        """Generate appliance schedule from project config.
        
        Validates that specified models exist in database.
        """
        schedule = {
            'regular': [],
            'ada': []
        }
        
        for model_str in project_config.get('appliances_regular', []):
            model_code = cls._extract_model_code(model_str)
            app = cls.get_appliance(model_code)
            if app:
                schedule['regular'].append({
                    'model': model_code,
                    'spec': app,
                    'name': model_str
                })
        
        for model_str in project_config.get('appliances_ada', []):
            model_code = cls._extract_model_code(model_str)
            app = cls.get_appliance(model_code)
            if app:
                schedule['ada'].append({
                    'model': model_code,
                    'spec': app,
                    'name': model_str
                })
        
        return schedule
    
    @staticmethod
    def _extract_model_code(model_string: str) -> str:
        """Extract model code from description string."""
        parts = model_string.split()
        if "MODEL" in model_string:
            try:
                idx = parts.index("MODEL")
                if idx + 1 < len(parts):
                    # In cases like "GTE18GSNRSS ADA", take the first part
                    return parts[idx + 1]
            except ValueError:
                pass
        
        # If MODEL is not found or fails, try to find a known code
        for known_code in ApplianceDatabase.CATALOG.keys():
            if known_code in model_string:
                return known_code
        return ""
