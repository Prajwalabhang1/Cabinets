import json
import os
from typing import Dict, List, Any
from collections import defaultdict
from core.engines.layout_fingerprint_engine import LayoutFingerprintEngine

class UnitMatrixBuilder:
    @staticmethod
    def save_signatures(signatures_map: Dict[str, str], filepath: str = "data/layout_signatures.json"):
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        with open(filepath, 'w') as f:
            json.dump(signatures_map, f, indent=4)

    @staticmethod
    def load_signatures(filepath: str = "data/layout_signatures.json") -> Dict[str, str]:
        if os.path.exists(filepath):
            with open(filepath, 'r') as f:
                return json.load(f)
        return {}

    @staticmethod
    def build_unit_matrix(unit_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Groups units into K1, K2 and V1, V2 signatures."""
        kitchen_signatures = UnitMatrixBuilder.load_signatures("data/kitchen_signatures.json")
        vanity_signatures = UnitMatrixBuilder.load_signatures("data/vanity_signatures.json")
        
        k_counter = len(kitchen_signatures) + 1
        v_counter = len(vanity_signatures) + 1
        
        results = []
        
        for unit in unit_data:
            unit_name = unit.get('name', 'Unknown')
            unit_qty = unit.get('quantity', 1)
            is_ada = unit.get('is_ada', False)
            
            k_sig = "NONE"
            if 'kitchen' in unit:
                k_sig = LayoutFingerprintEngine.generate_fingerprint({'cabinets': unit['kitchen'], 'is_ada': is_ada})
                
            v_sig = "NONE"
            if 'vanity' in unit:
                v_sig = LayoutFingerprintEngine.generate_fingerprint({'cabinets': unit['vanity'], 'is_ada': is_ada})
            
            k_type = "NONE"
            if k_sig != "NONE":
                # Reverse lookup
                existing_type = None
                for t, s in kitchen_signatures.items():
                    if s == k_sig:
                        existing_type = t
                        break
                if not existing_type:
                    k_type = f"K{k_counter}"
                    kitchen_signatures[k_type] = k_sig
                    k_counter += 1
                else:
                    k_type = existing_type
                
            v_type = "NONE"
            if v_sig != "NONE":
                # Reverse lookup
                existing_type = None
                for t, s in vanity_signatures.items():
                    if s == v_sig:
                        existing_type = t
                        break
                if not existing_type:
                    v_type = f"V{v_counter}"
                    vanity_signatures[v_type] = v_sig
                    v_counter += 1
                else:
                    v_type = existing_type
                
            results.append({
                "unit_name": unit_name,
                "unit_qty": unit_qty,
                "kitchen_type": k_type,
                "vanity_type": v_type,
                "is_ada": is_ada
            })
            
        UnitMatrixBuilder.save_signatures(kitchen_signatures, "data/kitchen_signatures.json")
        UnitMatrixBuilder.save_signatures(vanity_signatures, "data/vanity_signatures.json")
        return results

    @staticmethod
    def group_by_building(unit_matrix: List[Dict[str, Any]], project_config: Dict[str, Any]) -> Dict[str, List[Dict[str, Any]]]:
        """Splits the matrix by building defined in project_config."""
        buildings_config = project_config.get('buildings', {})
        if not buildings_config:
            return {"PROJECT TOTALS": unit_matrix}
            
        grouped = defaultdict(list)
        unmapped = []
        
        for row in unit_matrix:
            unit_name = row['unit_name']
            assigned = False
            for bldg, units in buildings_config.items():
                if unit_name in units:
                    grouped[bldg].append(row)
                    assigned = True
                    break
            if not assigned:
                unmapped.append(row)
                
        if unmapped:
            grouped["UNMAPPED"] = unmapped
            
        return dict(grouped)

    @staticmethod
    def calculate_kitchen_totals(unit_matrix: List[Dict[str, Any]]) -> Dict[str, int]:
        totals = defaultdict(int)
        for row in unit_matrix:
            k_type = row.get('kitchen_type', 'NONE')
            if k_type != 'NONE':
                totals[k_type] += row.get('unit_qty', 0)
        return dict(totals)

    @staticmethod
    def calculate_vanity_totals(unit_matrix: List[Dict[str, Any]]) -> Dict[str, int]:
        totals = defaultdict(int)
        for row in unit_matrix:
            v_type = row.get('vanity_type', 'NONE')
            if v_type != 'NONE':
                totals[v_type] += row.get('unit_qty', 0)
        return dict(totals)
