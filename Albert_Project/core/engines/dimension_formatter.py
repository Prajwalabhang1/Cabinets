from typing import Tuple, Dict

class DimensionFormatter:
    """Converts and formats dimensions for dual representation."""
    
    @staticmethod
    def inches_to_mm(inches: float) -> float:
        """Convert inches to millimeters."""
        return round(inches * 25.4, 2)
    
    @staticmethod
    def format_imperial(inches: float) -> str:
        """Convert decimal inches to feet and inches.
        
        Example:
            98.62" → "8'-2 5/8\""
        """
        feet = int(inches // 12)
        remaining = inches - (feet * 12)
        
        # Convert to fraction
        frac_16ths = round(remaining * 16)
        frac_inches = frac_16ths // 16
        frac_num = frac_16ths % 16
        
        if feet == 0:
            if frac_num == 0:
                return f"{int(frac_inches)}\""
            else:
                gcd_val = DimensionFormatter._gcd(frac_num, 16)
                frac_num //= gcd_val
                frac_den = 16 // gcd_val
                return f"{int(frac_inches)} {frac_num}/{frac_den}\""
                
        if frac_num == 0:
            return f"{feet}'-{int(frac_inches)}\""
        else:
            # Simplify fraction
            gcd_val = DimensionFormatter._gcd(frac_num, 16)
            frac_num //= gcd_val
            frac_den = 16 // gcd_val
            return f"{feet}'-{int(frac_inches)} {frac_num}/{frac_den}\""
    
    @staticmethod
    def format_dual(inches: float) -> Dict[str, str]:
        """Return both metric and imperial formats.
        
        Returns:
            {
                'metric': '228.60',
                'metric_unit': 'mm',
                'imperial': "7'-6\"",
                'imperial_short': '228.6\"'
            }
        """
        mm = DimensionFormatter.inches_to_mm(inches)
        imperial = DimensionFormatter.format_imperial(inches)
        
        return {
            'metric': f"{mm:.2f}",
            'metric_unit': 'mm',
            'imperial': imperial,
            'imperial_short': f'{inches:.2f}"'
        }
    
    @staticmethod
    def _gcd(a: int, b: int) -> int:
        """Calculate greatest common divisor."""
        while b:
            a, b = b, a % b
        return a
