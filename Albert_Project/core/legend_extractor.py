"""
===========================================================================
  core/legend_extractor.py — Keynote Legend Extractor
===========================================================================
  Dynamically extracts the U-code keynotes legend (e.g., U1-U50) and their
  descriptions from architectural drawing sheets. Works for both single-page
  and multi-page PDFs, and handles multi-column legend layouts.
===========================================================================
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Optional, Dict

import fitz  # PyMuPDF
from core.pdf_extractor import PDFExtractor, TextSpan


class LegendExtractor:
    """
    Extracts U-code legends from architectural drawing pages.
    """

    def __init__(self, spans: list[TextSpan], page_w: float, page_h: float):
        self.spans = spans
        self.page_w = page_w
        self.page_h = page_h

    def extract(self) -> dict[str, str]:
        """
        Scan page text, find the legend area, and reconstruct keynote dictionary.
        Returns a dictionary of { "U1": "Description...", "U2": "Description..." }
        """
        # 1. Locate the legend header (e.g., "KEYNOTE LEGEND" or "SYMBOL LEGEND")
        header_span = None
        for s in self.spans:
            t = s.upper
            if "KEYNOTE" in t and "LEGEND" in t:
                header_span = s
                break
        
        if not header_span:
            # Fallback: search for first span containing "LEGEND" or "KEYNOTE"
            for s in self.spans:
                t = s.upper
                if "LEGEND" in t:
                    header_span = s
                    break

        # Define boundary of legend area
        if header_span:
            # Legend starts below the header and occupies the right portion of the sheet
            lx0 = header_span.x0 - 200
            ly0 = header_span.y1
            # Extend to right edge of page
            lx1 = self.page_w
            ly1 = self.page_h
        else:
            # Fallback to rightmost 30% of the page
            lx0 = self.page_w * 0.70
            ly0 = 0
            lx1 = self.page_w
            ly1 = self.page_h

        # 2. Filter spans within the legend area
        legend_spans = [
            s for s in self.spans
            if lx0 <= s.x0 <= lx1 and ly0 <= s.y0 <= ly1 and len(s.text.strip()) > 0
        ]

        if not legend_spans:
            return {}

        # 3. Detect column X coordinates for U-codes dynamically
        # Look for spans matching U\d+ to identify U-code columns
        u_pattern = re.compile(r'^U(\d+)$', re.IGNORECASE)
        u_x_coords = []
        for s in legend_spans:
            if u_pattern.match(s.text.strip()):
                u_x_coords.append(s.x0)

        # Cluster U-code X coordinates to identify column starting points
        columns = []
        for x in sorted(u_x_coords):
            # Group into existing column if close (within 40 pts)
            matched = False
            for col in columns:
                if abs(col["start"] - x) < 40:
                    col["coords"].append(x)
                    col["start"] = sum(col["coords"]) / len(col["coords"])
                    matched = True
                    break
            if not matched:
                columns.append({"start": x, "coords": [x]})

        columns.sort(key=lambda c: c["start"])

        # Determine boundaries between columns
        boundaries = []
        for i in range(len(columns) - 1):
            mid = (columns[i]["start"] + columns[i+1]["start"]) / 2
            boundaries.append(mid)

        # 4. Group legend spans by Y coordinate
        lines_by_y: dict[float, list[TextSpan]] = {}
        for s in legend_spans:
            y = round(s.bbox[1], 1)
            matched_y = None
            for existing_y in lines_by_y:
                if abs(existing_y - y) <= 3.0:
                    matched_y = existing_y
                    break
            if matched_y is None:
                lines_by_y[y] = [s]
            else:
                lines_by_y[matched_y].append(s)

        # Sort lines top-to-bottom
        sorted_ys = sorted(lines_by_y.keys())

        # 5. Process each line and assign to columns
        # We will track the current active U-code description for each column
        col_active_key: dict[int, Optional[str]] = {i: None for i in range(len(columns) + 1)}
        legend_dict: dict[str, list[str]] = {}

        for y in sorted_ys:
            line_spans = sorted(lines_by_y[y], key=lambda s: s.x0)
            
            # Distribute spans on this line to columns based on boundaries
            col_spans: dict[int, list[TextSpan]] = {i: [] for i in range(len(columns) + 1)}
            for s in line_spans:
                col_idx = 0
                for b in boundaries:
                    if s.x0 > b:
                        col_idx += 1
                    else:
                        break
                col_spans[col_idx].append(s)

            # Process each column on this line
            for col_idx in range(len(columns) + 1):
                spans_in_col = col_spans[col_idx]
                if not spans_in_col:
                    continue

                # Check if first span is a U-code (starts a new description)
                first_text = spans_in_col[0].text.strip()
                m = u_pattern.match(first_text)
                if m:
                    u_code = first_text.upper()
                    col_active_key[col_idx] = u_code
                    legend_dict[u_code] = []
                    # The rest of the spans in this column are part of the description
                    desc_parts = [s.text.strip() for s in spans_in_col[1:] if s.text.strip()]
                    if desc_parts:
                        legend_dict[u_code].append(" ".join(desc_parts))
                else:
                    # Append to active keynote in this column if we have one
                    u_code = col_active_key[col_idx]
                    if u_code:
                        desc_parts = [s.text.strip() for s in spans_in_col if s.text.strip()]
                        if desc_parts:
                            legend_dict[u_code].append(" ".join(desc_parts))

        # Join the list of text lines for each U-code into a single string
        final_legend: dict[str, str] = {}
        for u_code, lines in legend_dict.items():
            full_desc = " ".join(lines).strip()
            # Clean up double spaces or trailing periods/commas
            full_desc = re.sub(r'\s+', ' ', full_desc)
            final_legend[u_code] = full_desc

        return final_legend


def extract_legend_from_pdf(pdf_path: str | Path) -> dict[str, str]:
    """Convenience wrapper to load PDF and extract keynote legend."""
    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        return {}

    with PDFExtractor(pdf_path) as ex:
        # Keynotes are always on sheet 0 (first page of details)
        page = ex.extract_page(0)

    extractor = LegendExtractor(page.spans, page.page_w, page.page_h)
    return extractor.extract()


# ══════════════════════════════════════════════════════════════════════════
# QUICK TEST
# ══════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python -m core.legend_extractor <path_to_pdf>")
        sys.exit(1)

    pdf = sys.argv[1]
    legend = extract_legend_from_pdf(pdf)
    print(f"\nExtracted {len(legend)} U-code legend keys:")
    for k in sorted(legend.keys(), key=lambda x: int(x[1:]) if x[1:].isdigit() else 999):
        print(f"  {k:5s} -> {legend[k][:80]}...")
