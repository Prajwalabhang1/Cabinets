"""
===========================================================================
  core/ceiling_height_extractor.py — Ceiling & Soffit Height Extractor
===========================================================================
  Parses drawing annotations for ceiling heights and dropped bulkheads.
===========================================================================
"""
from __future__ import annotations

import re
from typing import Optional, List, Dict
from core.pdf_extractor import TextSpan

class CeilingHeightExtractor:
    """
    Parses ceiling elevations and soffit bounds from details annotations.
    """

    @staticmethod
    def extract_heights(spans: list[TextSpan]) -> dict:
        """
        Scan page text spans and extract ceiling_height and soffit_height.
        Returns values in inches (default: ceiling=108, soffit=None).
        """
        ceiling_height = 108.0 # default 9'
        soffit_height = None

        # Sort spans top-to-bottom, left-to-right
        sorted_spans = sorted(spans, key=lambda s: (s.y0, s.x0))

        for idx, s in enumerate(sorted_spans):
            t = s.text.upper()
            
            # Look for ceiling keywords: CEILING, CLG, AFF
            if "CEILING" in t or "CLG" in t or "AFF" in t or "SOFFIT" in t:
                # Search nearby spans (prev/next 5 spans) for height matches
                search_range = sorted_spans[max(0, idx-5):min(len(sorted_spans), idx+6)]
                for neighbor in search_range:
                    nt = neighbor.text.upper()
                    height_in = CeilingHeightExtractor._parse_height(nt)
                    if height_in is not None:
                        if "SOFFIT" in t or "SOFFIT" in nt:
                            soffit_height = height_in
                        else:
                            ceiling_height = height_in
                        break

        return {
            "ceiling_height": ceiling_height,
            "soffit_height": soffit_height or (ceiling_height - 12.0 if soffit_height is None else soffit_height)
        }

    @staticmethod
    def _parse_height(text: str) -> Optional[float]:
        """
        Helper to parse height specs e.g. 9'-0" clg or 8'-6" AFF to inches.
        """
        # Match 9'-0" or 9'0" or 9'-6"
        m_ft_in = re.search(r"(\d+)'\s*-?\s*(\d+)?\"?", text)
        if m_ft_in:
            ft = float(m_ft_in.group(1))
            inch_val = float(m_ft_in.group(2)) if m_ft_in.group(2) else 0.0
            return ft * 12 + inch_val
        
        # Match 108" or 96 in
        m_in = re.search(r"(\d+)\s*(?:\"|IN|INCHES)", text, re.IGNORECASE)
        if m_in:
            return float(m_in.group(1))

        # Match 9 FT or 9FT
        m_ft = re.search(r"(\d+)\s*(?:FT|FEET)", text, re.IGNORECASE)
        if m_ft:
            return float(m_ft.group(1)) * 12.0

        return None
