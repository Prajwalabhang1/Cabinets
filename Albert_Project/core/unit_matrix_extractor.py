"""
===========================================================================
  core/unit_matrix_extractor.py — Unit Matrix Extractor
===========================================================================
  Counts and compiles floor-by-floor and building-wide unit takeoff matrices.
===========================================================================
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from collections import Counter, defaultdict
from typing import Optional, List, Dict
from dataclasses import dataclass
from core.pdf_extractor import PDFExtractor, TextSpan

@dataclass
class FloorCount:
    floor_name:   str
    pdf_path:     str
    unit_counts:  dict[str, int]
    confidence:   float

@dataclass
class UnitMatrixResult:
    project_name: str
    totals: dict[str, int]
    floor_counts: list[FloorCount]
    confidence: float = 1.0
    needs_review: bool = False

    def print_summary(self):
        print(f"\n--- Takeoff Matrix Summary: {self.project_name} ---")
        for ut, count in self.totals.items():
            print(f"  Unit {ut}: {count}")
        print(f"Confidence: {self.confidence:.2f} | Needs Review: {self.needs_review}")

def load_matrix_from_config(config_dict: dict, project_name: str) -> UnitMatrixResult:
    """Loads a unit takeoff matrix directly from configuration dictionary."""
    return UnitMatrixResult(
        project_name = project_name,
        totals = config_dict,
        floor_counts = [],
        confidence = 1.0,
        needs_review = False
    )

class UnitMatrixExtractor:
    """
    Handles unit occurrence count taking and output mapping.
    """

    def __init__(self):
        # Patterns for unit occurrences
        self._patterns = [
            re.compile(r'\bUNIT\s+(A|B|C|D|ST)-?\d+[A-Za-z]?\s*(?:TYP\.?|N|ACC|ADA|FHA)?\b', re.IGNORECASE),
            re.compile(r'\b(A|B|C|D|ST)-?\d+[A-Za-z]?\s*TYP\.?\b', re.IGNORECASE),
            re.compile(r'\bTYPE\s+(A|B|C|D|ST|K)\d*[A-Za-z]?\b', re.IGNORECASE),
        ]

    def count_from_pdfs(
        self,
        pdf_paths: list[str | Path],
        project_name: str
    ) -> UnitMatrixResult:
        """
        Count occurrences across PDFs and return structured results as a UnitMatrixResult.
        """
        totals = {}
        floor_counts = []

        for p in pdf_paths:
            path = Path(p)
            if not path.exists():
                continue
            
            # Count from individual floor plan sheet
            counts = self._count_units_on_sheet(path)
            floor_counts.append(counts)

            for ut, cnt in counts.unit_counts.items():
                totals[ut] = totals.get(ut, 0) + cnt

        conf = 1.0
        if floor_counts:
            conf = sum(fc.confidence for fc in floor_counts) / len(floor_counts)
        needs_review = conf < 0.8 or not totals

        return UnitMatrixResult(
            project_name = project_name,
            totals = totals,
            floor_counts = floor_counts,
            confidence = conf,
            needs_review = needs_review
        )

    def extract_matrix(
        self,
        pdf_paths: list[str | Path],
        project_name: str,
        manual_override: Optional[dict[str, int]] = None
    ) -> dict:
        """
        Backward compatible dict output.
        """
        res = self.count_from_pdfs(pdf_paths, project_name)
        if manual_override:
            res.totals = manual_override
        return {
            "project_name": res.project_name,
            "totals": res.totals,
            "floor_counts": res.floor_counts
        }



    def _count_units_on_sheet(self, pdf_path: Path) -> FloorCount:
        floor_name = pdf_path.stem
        hits = []
        
        with PDFExtractor(pdf_path) as ex:
            for i in range(ex.page_count):
                spans = ex.extract_spans(i)
                for s in spans:
                    text = s.text.strip()
                    if len(text) < 2 or len(text) > 45:
                        continue
                    for pat in self._patterns:
                        m = pat.search(text)
                        if m:
                            raw = m.group(0).upper().strip()
                            raw = re.sub(r'^UNIT\s+', '', raw)
                            raw = re.sub(r'\s+TYP\.?$', '', raw)
                            raw = re.sub(r'\s+TYPE\s+', '', raw)
                            raw = re.sub(r'([A-Z])-(\d)', r'\1\2', raw)
                            normalized = raw.strip()
                            if normalized and len(normalized) <= 12:
                                hits.append(normalized)
                            break

        raw_counter = Counter(hits)
        unit_counts = {k: v for k, v in raw_counter.items() if v >= 2}
        confidence = 0.85 if unit_counts else 0.30

        return FloorCount(
            floor_name = floor_name,
            pdf_path = str(pdf_path),
            unit_counts = unit_counts,
            confidence = confidence
        )
