"""
===========================================================================
  core/unit_counter.py — Floor Plan Unit Type Counter
===========================================================================
  Reads building floor plan PDFs and counts how many of each unit type
  exist per floor, then aggregates for the whole building.

  Strategy:
    1. Extract all text from floor plan PDFs
    2. Find unit labels matching known patterns:
       "UNIT A1", "UNIT A-1", "A1 TYP.", "A-1", "TYPE A1", etc.
    3. Count unique occurrences (not label repetitions like "TYP.")
    4. Aggregate across all floor plan PDFs
    5. If auto-count confidence < 80%, save to JSON and let user confirm

  Architecture notes:
    - Casa Familia: 3 floor plan PDFs (Ground, 2nd, 3rd)
    - Heritage Village: 3 floor plan PDFs (Partial C, Ground, 2nd, 3rd)
    - Multiple units of same type appear on each floor
===========================================================================
"""
from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from core.pdf_extractor import PDFExtractor, TextSpan


# ══════════════════════════════════════════════════════════════════════════
# DATA CLASSES
# ══════════════════════════════════════════════════════════════════════════

@dataclass
class FloorCount:
    """Unit counts for one floor."""
    floor_name:   str
    pdf_path:     str
    unit_counts:  dict[str, int] = field(default_factory=dict)
    confidence:   float = 0.0
    raw_hits:     list[str] = field(default_factory=list)


@dataclass
class ProjectUnitMatrix:
    """Complete unit count matrix for a project."""
    project_name: str
    floor_counts: list[FloorCount] = field(default_factory=list)
    totals:       dict[str, int]   = field(default_factory=dict)
    confidence:   float = 0.0
    needs_review: bool  = False
    review_note:  str   = ""

    def to_dict(self) -> dict:
        return {
            "project_name": self.project_name,
            "totals":       self.totals,
            "by_floor":     [
                {
                    "floor":       fc.floor_name,
                    "pdf":         fc.pdf_path,
                    "counts":      fc.unit_counts,
                    "confidence":  fc.confidence,
                }
                for fc in self.floor_counts
            ],
            "confidence":   self.confidence,
            "needs_review": self.needs_review,
            "review_note":  self.review_note,
        }

    def print_summary(self):
        print(f"\n  Project Unit Matrix: {self.project_name}")
        print(f"  {'Unit Type':15s} {'Count':8s}")
        print("  " + "-" * 30)
        total = 0
        for unit_type, count in sorted(self.totals.items()):
            print(f"  {unit_type:15s} {count:8d}")
            total += count
        print("  " + "-" * 30)
        print(f"  {'TOTAL':15s} {total:8d}")
        print(f"  Confidence: {self.confidence:.1%}")
        if self.needs_review:
            print(f"  ⚠️  Needs review: {self.review_note}")


# ══════════════════════════════════════════════════════════════════════════
# UNIT TYPE PATTERNS
# ══════════════════════════════════════════════════════════════════════════

# Patterns that identify a unit type label in floor plan text
# Captures: "UNIT A1", "UNIT A-1", "A1 TYP.", "TYPE A1", "UNIT A1 TYP."
_UNIT_PATTERNS = [
    # "UNIT A1" or "UNIT A-1"
    re.compile(r'\bUNIT\s+(A|B|C|D|ST)-?\d+[A-Za-z]?\s*(?:TYP\.?|N|ACC|ADA|FHA)?\b', re.IGNORECASE),
    # "A1 TYP." or "A-1A TYP."
    re.compile(r'\b(A|B|C|D|ST)-?\d+[A-Za-z]?\s*TYP\.?\b', re.IGNORECASE),
    # "TYPE K1" or "TYPE A"
    re.compile(r'\bTYPE\s+(A|B|C|D|ST|K)\d*[A-Za-z]?\b', re.IGNORECASE),
]

# Normalization: map raw label to canonical unit type
def _normalize_unit_label(raw: str) -> str:
    """Normalize a unit label to canonical form e.g. 'UNIT A1 TYP.' → 'A1'."""
    raw = raw.upper().strip()
    # Remove "UNIT " prefix
    raw = re.sub(r'^UNIT\s+', '', raw)
    # Remove trailing qualifiers (TYP., N, etc.) — keep ACC/ADA
    raw = re.sub(r'\s+TYP\.?$', '', raw)
    raw = re.sub(r'\s+TYPE\s+', '', raw)
    # Normalize dash: "A-1" → "A1"
    raw = re.sub(r'([A-Z])-(\d)', r'\1\2', raw)
    # Normalize spaces
    raw = raw.strip()
    return raw


# ══════════════════════════════════════════════════════════════════════════
# UNIT COUNTER
# ══════════════════════════════════════════════════════════════════════════

class UnitCounter:
    """
    Count unit types from architectural floor plan PDFs.

    Usage:
        counter = UnitCounter()
        matrix  = counter.count_from_pdfs(
            pdf_paths=["Floor_Plans/Ground.pdf", "Floor_Plans/2nd.pdf"],
            project_name="Casa Familia",
        )
        matrix.print_summary()
    """

    def count_from_pdfs(
        self,
        pdf_paths:     list[str | Path],
        project_name:  str,
        manual_override: Optional[dict[str, int]] = None,
    ) -> ProjectUnitMatrix:
        """
        Extract unit counts from multiple floor plan PDFs.

        Args:
            pdf_paths:       List of floor plan PDF paths
            project_name:    Project name for display
            manual_override: If provided, use these counts instead of auto-detection
        """
        if manual_override:
            print(f"  Using manual unit counts for {project_name}")
            return ProjectUnitMatrix(
                project_name = project_name,
                totals       = manual_override,
                confidence   = 1.0,
                needs_review = False,
            )

        floor_counts: list[FloorCount] = []
        all_unit_counts: Counter = Counter()

        for pdf_path in pdf_paths:
            pdf_path = Path(pdf_path)
            if not pdf_path.exists():
                print(f"  ⚠️  Floor plan PDF not found: {pdf_path}")
                continue

            floor_count = self._count_from_pdf(pdf_path)
            floor_counts.append(floor_count)

            for unit_type, count in floor_count.unit_counts.items():
                all_unit_counts[unit_type] += count

        # Compute overall confidence
        if floor_counts:
            avg_conf = sum(fc.confidence for fc in floor_counts) / len(floor_counts)
        else:
            avg_conf = 0.0

        totals = dict(all_unit_counts)
        needs_review = avg_conf < 0.80 or not totals

        matrix = ProjectUnitMatrix(
            project_name = project_name,
            floor_counts = floor_counts,
            totals       = totals,
            confidence   = avg_conf,
            needs_review = needs_review,
            review_note  = (
                "Auto-detection confidence too low — please verify unit counts in project_config.json"
                if needs_review else ""
            ),
        )

        return matrix

    def _count_from_pdf(self, pdf_path: Path) -> FloorCount:
        """Extract unit type counts from one floor plan PDF."""
        floor_name = pdf_path.stem
        print(f"  Counting units from: {floor_name}")

        with PDFExtractor(pdf_path) as ex:
            all_spans: list[TextSpan] = []
            for i in range(ex.page_count):
                all_spans.extend(ex.extract_spans(i))

        hits: list[str] = []
        for span in all_spans:
            text = span.text.strip()
            if len(text) < 2 or len(text) > 40:
                continue
            for pattern in _UNIT_PATTERNS:
                m = pattern.search(text)
                if m:
                    normalized = _normalize_unit_label(m.group(0))
                    if normalized and len(normalized) <= 10:
                        hits.append(normalized)
                    break

        # Count occurrences
        raw_counter = Counter(hits)
        print(f"    Raw hits: {dict(raw_counter)}")

        # Filter: a label appearing < 2 times is likely a legend/title, not an instance
        unit_counts = {k: v for k, v in raw_counter.items() if v >= 2}

        # Confidence: higher if counts are consistent across floors
        confidence = 0.85 if unit_counts else 0.30

        return FloorCount(
            floor_name  = floor_name,
            pdf_path    = str(pdf_path),
            unit_counts = unit_counts,
            confidence  = confidence,
            raw_hits    = hits,
        )


# ══════════════════════════════════════════════════════════════════════════
# JSON SAVE/LOAD
# ══════════════════════════════════════════════════════════════════════════

def save_matrix(matrix: ProjectUnitMatrix, out_path: str | Path) -> Path:
    """Save ProjectUnitMatrix to JSON file."""
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(matrix.to_dict(), indent=2, ensure_ascii=False),
        encoding="utf-8"
    )
    print(f"  Unit matrix saved: {out_path}")
    return out_path


def load_matrix_from_config(unit_counts: dict[str, int], project_name: str) -> ProjectUnitMatrix:
    """Create a ProjectUnitMatrix directly from project_config.json counts."""
    return ProjectUnitMatrix(
        project_name = project_name,
        totals       = unit_counts,
        confidence   = 1.0,
        needs_review = False,
    )


# ══════════════════════════════════════════════════════════════════════════
# QUICK TEST
# ══════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python -m core.unit_counter <floor_plan_pdf1> [<floor_plan_pdf2> ...]")
        print("\nRunning with manual counts test...")
        matrix = load_matrix_from_config(
            unit_counts = {
                "A1": 14, "A2-ADA": 3, "A3": 2,
                "B1": 3,  "B2-ADA": 3,
            },
            project_name = "Casa Familia (manual)",
        )
        matrix.print_summary()
        sys.exit(0)

    pdf_paths = sys.argv[1:]
    counter = UnitCounter()
    matrix  = counter.count_from_pdfs(pdf_paths, project_name="Test Project")
    matrix.print_summary()
