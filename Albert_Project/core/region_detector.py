"""
===========================================================================
  core/region_detector.py — Elevation & Kitchen/Bath Region Finder
===========================================================================
  Identifies which parts of an architectural PDF page correspond to:
    - Kitchen elevation A, B, C views
    - Bathroom elevation views
    - Floor plan areas
    - Title block / notes

  Key improvements over step1_crop_elevations.py:
    1. De-duplicates overlapping crop zones by x-cluster proximity
    2. Returns confidence score per region
    3. Auto-detects title block right boundary (no hardcoded x threshold)
    4. Builds tighter crop rectangles using actual content boundaries
       (not fixed 600×400 pt windows)
    5. Correctly handles multi-elevation pages (Elevation A + Elevation B
       on same page = two separate well-bounded crop zones)
===========================================================================
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

from core.config import (
    ELEVATION_LABELS, KITCHEN_LABELS, BATH_LABELS,
    PAGE_W_PTS, PAGE_H_PTS,
)
from core.pdf_extractor import TextSpan, VectorRect


# ══════════════════════════════════════════════════════════════════════════
# DATA CLASSES
# ══════════════════════════════════════════════════════════════════════════

@dataclass
class DetectedRegion:
    """One identified section on the PDF page."""
    region_type:  str    # "ELEVATION_A" | "ELEVATION_B" | "KITCHEN" | "BATH" | "FLOOR_PLAN"
    label:        str    # original text found e.g. "UNIT A1 KITCHEN EL."
    crop_rect:    tuple[float, float, float, float]   # (x0, y0, x1, y1) in PDF points
    origin:       tuple[float, float]                 # label text position
    confidence:   float = 1.0   # how clearly the label was found
    font_size:    float = 10.0  # label font size (larger = more prominent)

    @property
    def x0(self) -> float:  return self.crop_rect[0]
    @property
    def y0(self) -> float:  return self.crop_rect[1]
    @property
    def x1(self) -> float:  return self.crop_rect[2]
    @property
    def y1(self) -> float:  return self.crop_rect[3]
    @property
    def width(self) -> float:  return self.x1 - self.x0
    @property
    def height(self) -> float: return self.y1 - self.y0

    def is_elevation(self) -> bool:
        return self.region_type.startswith("ELEVATION")

    def is_kitchen(self) -> bool:
        return self.region_type in ("KITCHEN", "ELEVATION_A", "ELEVATION_B", "ELEVATION_C")

    def is_bath(self) -> bool:
        return "BATH" in self.region_type or "VANITY" in self.region_type


# ══════════════════════════════════════════════════════════════════════════
# REGION DETECTOR
# ══════════════════════════════════════════════════════════════════════════

class RegionDetector:
    """
    Detects kitchen, bathroom, and elevation regions on an architectural PDF page.

    Usage:
        detector = RegionDetector(spans, rects, page_w, page_h)
        regions  = detector.detect()
        title_x  = detector.title_block_x
    """

    def __init__(
        self,
        spans:  list[TextSpan],
        rects:  list[VectorRect],
        page_w: float,
        page_h: float,
    ):
        self.spans  = spans
        self.rects  = rects
        self.page_w = page_w
        self.page_h = page_h
        self._title_block_x: Optional[float] = None

    # ── Public API ────────────────────────────────────────────────────────

    def detect(self) -> list[DetectedRegion]:
        """Main entry point. Returns all detected regions, deduplicated."""
        title_x = self.title_block_x

        # 1. Find all keyword label hits
        raw_hits = self._find_label_hits(title_x)

        # 2. De-duplicate by clustering nearby hits
        deduped = self._deduplicate_hits(raw_hits)

        # 3. Build crop zones with smart boundaries
        regions = self._build_crop_zones(deduped, title_x)

        # 4. Remove overlapping regions (keep highest confidence)
        regions = self._remove_overlapping_regions(regions)

        # 5. Cap per-type to prevent explosion (max 2 KITCHEN, 2 BATH, 2 VANITY)
        regions = self._cap_regions_per_type(regions)

        # 6. Sort top-to-bottom, left-to-right
        regions.sort(key=lambda r: (r.origin[1], r.origin[0]))

        return regions

    @property
    def title_block_x(self) -> float:
        """
        Auto-detect the left boundary of the title block (right-side strip).
        Strategy: find the rightmost full-height vertical line.
        Falls back to page_w * 0.92 if none found.
        """
        if self._title_block_x is not None:
            return self._title_block_x

        # Look for vertical lines spanning > 70% of page height
        full_height_threshold = self.page_h * 0.70
        candidates = []

        for r in self.rects:
            if r.h > full_height_threshold and r.w < 5:  # tall thin rect = vertical line
                candidates.append(r.x0)

        for r in self.rects:
            # Also check very wide rects that span full height (title block frame)
            if r.h > full_height_threshold and r.w > 40:
                candidates.append(r.x0)

        if candidates:
            # The rightmost candidate that's not at the page edge
            valid = [x for x in candidates if x < self.page_w * 0.99 and x > self.page_w * 0.5]
            if valid:
                self._title_block_x = max(valid)
                return self._title_block_x

        # Fallback: use 92% of page width
        self._title_block_x = self.page_w * 0.92
        return self._title_block_x

    # ── Step 1: Find label hits ───────────────────────────────────────────

    def _find_label_hits(self, title_x: float) -> list[dict]:
        """Scan all spans for matching region labels."""
        hits = []
        for span in self.spans:
            # Skip spans in the title block area
            if span.x0 > title_x:
                continue
            # Skip very small text (footnotes, etc.)
            if span.size < 4.0:
                continue

            t_up = span.upper
            region_type, confidence = self._classify_label(t_up)
            if region_type:
                hits.append({
                    "region_type": region_type,
                    "label":       span.text,
                    "origin":      span.origin,
                    "bbox":        span.bbox,
                    "font_size":   span.size,
                    "confidence":  confidence,
                })
        return hits

    def _classify_label(self, text_upper: str) -> tuple[Optional[str], float]:
        """Return (region_type, confidence) for a text string."""
        # Elevation labels — specific
        for lbl in ELEVATION_LABELS:
            if lbl in text_upper:
                # Determine which elevation (A, B, C, D)
                for letter in ["A", "B", "C", "D"]:
                    if f"ELEVATION {letter}" in text_upper or f"ELEV {letter}" in text_upper \
                            or f"EL. {letter}" in text_upper or f"EL {letter}" in text_upper \
                            or f"ELEV. {letter}" in text_upper:
                        return f"ELEVATION_{letter}", 0.95
                return "ELEVATION", 0.80

        # Kitchen labels
        for lbl in KITCHEN_LABELS:
            if lbl in text_upper:
                # Check if it also says "ELEVATION" → already caught above
                if "ELEVATION" in text_upper or "EL." in text_upper:
                    for letter in ["A", "B", "C"]:
                        if letter in text_upper.split()[-1]:
                            return f"ELEVATION_{letter}", 0.90
                return "KITCHEN", 0.85

        # Bath labels
        for lbl in BATH_LABELS:
            if lbl in text_upper:
                if "VANITY" in text_upper:
                    return "VANITY", 0.90
                if "MASTER" in text_upper:
                    return "MASTER_BATH", 0.90
                return "BATH", 0.85

        # Floor plan
        if "FLOOR PLAN" in text_upper or "FLOOR PLN" in text_upper:
            return "FLOOR_PLAN", 0.85

        return None, 0.0

    # ── Step 2: De-duplicate by spatial clustering ────────────────────────

    def _deduplicate_hits(self, hits: list[dict]) -> list[dict]:
        """
        Remove duplicate hits that are within 200 pts of each other
        (same label detected multiple times in different sub-spans).
        Keep the hit with the largest font size (most prominent).
        """
        if not hits:
            return []

        # Group by (region_type, x-cluster, y-cluster)
        groups: list[list[dict]] = []
        CLUSTER_DIST = 200.0  # pts — increased from 80 to collapse nearby duplicates

        for hit in hits:
            placed = False
            for group in groups:
                rep = group[0]
                dx = abs(hit["origin"][0] - rep["origin"][0])
                dy = abs(hit["origin"][1] - rep["origin"][1])
                same_type = (
                    hit["region_type"] == rep["region_type"] or
                    # Also merge BATH/VANITY/MASTER_BATH into same cluster
                    (hit["region_type"] in ("BATH","VANITY","MASTER_BATH") and
                     rep["region_type"] in ("BATH","VANITY","MASTER_BATH"))
                )
                if same_type and dx < CLUSTER_DIST and dy < CLUSTER_DIST:
                    group.append(hit)
                    placed = True
                    break
            if not placed:
                groups.append([hit])

        # From each group, keep the one with largest font size
        return [max(g, key=lambda h: h["font_size"]) for g in groups]

    # ── Step 3: Build crop zones with smart boundaries ────────────────────

    def _build_crop_zones(
        self,
        hits: list[dict],
        title_x: float,
    ) -> list[DetectedRegion]:
        """
        For each label hit, determine the crop rectangle that tightly
        bounds the actual content of that section.

        Strategy:
        1. Sort hits by Y position (top-to-bottom)
        2. For each hit, the crop zone extends:
           - Left:   to left page margin (or nearest large rect boundary)
           - Right:  to title block X
           - Top:    from label Y - padding
           - Bottom: to next section's label Y (or page bottom)
        """
        if not hits:
            return []

        # Sort all hits by y position
        sorted_hits = sorted(hits, key=lambda h: h["origin"][1])

        # Also create horizontal clusters for multi-column layouts
        # (e.g., Casa Familia: floor plan left + elevations right)
        x_clusters = self._find_x_clusters(sorted_hits)

        regions = []
        for col_hits in x_clusters:
            col_hits_sorted = sorted(col_hits, key=lambda h: h["origin"][1])

            for idx, hit in enumerate(col_hits_sorted):
                ox, oy = hit["origin"]

                # Top boundary: label y - 60 pts padding (include labels above drawing)
                y_top = max(0.0, oy - 60.0)

                # Bottom boundary: next label y in same column, or page bottom
                if idx + 1 < len(col_hits_sorted):
                    next_oy = col_hits_sorted[idx + 1]["origin"][1]
                    y_bot = min(next_oy - 10.0, self.page_h)
                else:
                    y_bot = self.page_h - 10.0

                # Left boundary: leftmost content in this column
                col_x_min = min(h["origin"][0] for h in col_hits)
                x_left = max(0.0, col_x_min - 40.0)

                # Right boundary: title block or next column's left edge
                x_right = min(title_x - 4.0, self.page_w)

                # If this column has hits clustered on right side, constrain right
                if len(x_clusters) > 1:
                    col_idx = x_clusters.index(col_hits)
                    if col_idx < len(x_clusters) - 1:
                        next_col = x_clusters[col_idx + 1]
                        next_x = min(h["origin"][0] for h in next_col)
                        x_right = min(x_right, next_x - 20.0)

                # Ensure crop has minimum useful size
                if (x_right - x_left) < 100 or (y_bot - y_top) < 50:
                    # Fallback to generous padding
                    x_left  = max(0, ox - 50)
                    x_right = min(title_x - 4, ox + 650)
                    y_top   = max(0, oy - 80)
                    y_bot   = min(self.page_h, oy + 500)

                regions.append(DetectedRegion(
                    region_type = hit["region_type"],
                    label       = hit["label"],
                    crop_rect   = (x_left, y_top, x_right, y_bot),
                    origin      = hit["origin"],
                    confidence  = hit["confidence"],
                    font_size   = hit["font_size"],
                ))

        return regions

    def _find_x_clusters(self, hits: list[dict]) -> list[list[dict]]:
        """
        Group hits into horizontal columns.
        Hits within 200 pts on x-axis share a column.
        Returns list of columns, each being a list of hits.
        """
        if not hits:
            return []

        X_CLUSTER_DIST = 200.0
        columns: list[list[dict]] = []

        for hit in hits:
            hx = hit["origin"][0]
            placed = False
            for col in columns:
                col_center = sum(h["origin"][0] for h in col) / len(col)
                if abs(hx - col_center) < X_CLUSTER_DIST:
                    col.append(hit)
                    placed = True
                    break
            if not placed:
                columns.append([hit])

        return columns

    def _remove_overlapping_regions(
        self,
        regions: list[DetectedRegion],
    ) -> list[DetectedRegion]:
        """
        Remove crop regions that heavily overlap each other.
        If two regions of the SAME type share > 60% of the smaller one's area,
        keep only the one with higher confidence (larger font = more prominent label).
        """
        if len(regions) <= 1:
            return regions

        def overlap_ratio(a: DetectedRegion, b: DetectedRegion) -> float:
            ix0 = max(a.x0, b.x0)
            iy0 = max(a.y0, b.y0)
            ix1 = min(a.x1, b.x1)
            iy1 = min(a.y1, b.y1)
            if ix1 <= ix0 or iy1 <= iy0:
                return 0.0
            inter = (ix1 - ix0) * (iy1 - iy0)
            area_a = a.width * a.height
            area_b = b.width * b.height
            smaller = min(area_a, area_b)
            return inter / smaller if smaller > 0 else 0.0

        # Sort by confidence desc so we keep the best ones
        sorted_r = sorted(regions, key=lambda r: -r.confidence)
        kept: list[DetectedRegion] = []

        for candidate in sorted_r:
            dominated = False
            for keeper in kept:
                same_family = (
                    candidate.region_type == keeper.region_type or
                    (candidate.region_type in ("BATH","VANITY","MASTER_BATH") and
                     keeper.region_type    in ("BATH","VANITY","MASTER_BATH"))
                )
                if same_family and overlap_ratio(candidate, keeper) > 0.60:
                    dominated = True
                    break
            if not dominated:
                kept.append(candidate)

        return kept

    def _cap_regions_per_type(
        self,
        regions: list[DetectedRegion],
    ) -> list[DetectedRegion]:
        """
        Hard cap on how many regions of each type are sent to AI.
        A unit plan has at most 2 kitchen elevations, 2 bath elevations,
        1-2 vanity views. More than that = detector false positives.
        """
        CAPS = {
            "KITCHEN":     2,
            "BATH":        2,
            "VANITY":      2,
            "MASTER_BATH": 1,
            "ELEVATION_A": 1,
            "ELEVATION_B": 1,
            "ELEVATION_C": 1,
            "ELEVATION_D": 1,
            "FLOOR_PLAN":  1,
        }
        from collections import Counter
        type_count: Counter = Counter()
        capped: list[DetectedRegion] = []

        # Sort by confidence desc so we keep the best detections
        for r in sorted(regions, key=lambda r: -r.confidence):
            cap = CAPS.get(r.region_type, 2)
            if type_count[r.region_type] < cap:
                capped.append(r)
                type_count[r.region_type] += 1

        return capped


def detect_regions(
    spans:  list[TextSpan],
    rects:  list[VectorRect],
    page_w: float,
    page_h: float,
) -> list[DetectedRegion]:
    """One-call convenience wrapper."""
    return RegionDetector(spans, rects, page_w, page_h).detect()


def get_title_block_x(
    spans:  list[TextSpan],
    rects:  list[VectorRect],
    page_w: float,
    page_h: float,
) -> float:
    """Detect title block left edge x-coordinate."""
    return RegionDetector(spans, rects, page_w, page_h).title_block_x


# ══════════════════════════════════════════════════════════════════════════
# QUICK TEST
# ══════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    import sys
    from core.pdf_extractor import PDFExtractor

    if len(sys.argv) < 2:
        print("Usage: python -m core.region_detector <path_to_pdf>")
        sys.exit(1)

    pdf_path = sys.argv[1]
    with PDFExtractor(pdf_path) as ex:
        page = ex.extract_page(0)

    detector = RegionDetector(page.spans, page.rects, page.page_w, page.page_h)
    regions  = detector.detect()
    title_x  = detector.title_block_x

    print(f"PDF: {pdf_path}")
    print(f"Page: {page.page_w:.0f}×{page.page_h:.0f} pts")
    print(f"Title block X: {title_x:.1f}")
    print(f"\nDetected {len(regions)} regions:")
    for r in regions:
        print(f"  [{r.confidence:.2f}] {r.region_type:20s}  '{r.label[:35]}'")
        print(f"         crop: ({r.x0:.0f},{r.y0:.0f}) → ({r.x1:.0f},{r.y1:.0f})"
              f"  [{r.width:.0f}×{r.height:.0f} pts]")
