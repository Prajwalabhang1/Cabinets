from typing import Dict, List, Any

class ADAEngine:
    """Validates and enforces ADA compliance rules for kitchen and vanity layouts."""
    
    @staticmethod
    def validate_clearances(geometry: Dict[str, Any]) -> Dict[str, Any]:
        """Checks for minimum 60-inch turning radius and 30x48 clear floor spaces."""
        issues = []
        # Placeholder logic: scan bounding boxes for a 60" diameter circle
        
        # Example validation:
        # if not has_60_inch_radius:
        #     issues.append({"severity": "ERROR", "message": "Turning radius < 60 inches."})
            
        return {
            "status": "PASS" if not issues else "FAIL",
            "issues": issues
        }

    @staticmethod
    def validate_reach_ranges(cabinets: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Validates that operable parts are within 15 to 48 inches AFF."""
        issues = []
        for cab in cabinets:
            if cab.get('family') == 'UPPER':
                # ADA Uppers often need to be mounted lower or have specialized pull-down hardware
                issues.append({"severity": "WARNING", "message": f"Upper cabinet {cab.get('id', '')} exceeds preferred ADA reach zone."})
        return {
            "status": "PASS" if not any(i['severity'] == 'ERROR' for i in issues) else "FAIL",
            "issues": issues
        }

    @staticmethod
    def validate_sink_approach(sink_cabinet: Dict[str, Any]) -> Dict[str, Any]:
        """Validates that sink bases have removable fronts and pipe protection."""
        issues = []
        if sink_cabinet.get('render_style') != 'sink_base':
            issues.append({"severity": "ERROR", "message": "ADA Sink cabinet must be a compliant sink base with knee clearance."})
        # Ensure it has a removable front or knee clearance
        return {
            "status": "PASS" if not issues else "FAIL",
            "issues": issues
        }

    @staticmethod
    def run_full_validation(unit_data: Dict[str, Any]) -> Dict[str, Any]:
        """Runs all ADA validation checks on a unit."""
        if not unit_data.get('is_ada', False):
            return {"status": "NOT_APPLICABLE"}
            
        clearance_res = ADAEngine.validate_clearances(unit_data.get('geometry', {}))
        reach_res = ADAEngine.validate_reach_ranges(unit_data.get('cabinets', []))
        
        # To get the sink cabinet, you'd find it in cabinets list. Assume empty for placeholder
        
        all_issues = clearance_res['issues'] + reach_res['issues']
        
        return {
            "status": "PASS" if not any(i['severity'] == 'ERROR' for i in all_issues) else "FAIL",
            "issues": all_issues
        }
