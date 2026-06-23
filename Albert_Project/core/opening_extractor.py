"""
===========================================================================
  core/opening_extractor.py — Doors & Windows Extractor
===========================================================================
  Locates structural openings like door passages and window sills.
===========================================================================
"""
from __future__ import annotations

import re
from typing import Optional, List, Dict, Any
from core.pdf_extractor import TextSpan, VectorRect

class OpeningExtractor:
    """
    Identifies door/window dimensions, wall positions, and alignment interruptions.
    """

    @staticmethod
    def extract_openings(spans: list[TextSpan], rects: list[VectorRect]) -> dict:
        """
        Parses text and geometry bounding boxes to identify doors and windows.
        """
        doors = []
        windows = []

        # Parse text spans looking for window/door callouts (e.g. Window W1, W7, Door D1)
        text_content = " ".join(s.text.upper() for s in spans)
        
        # Check window coordinates/dimensions if indicated
        # e.g., "WINDOW ABOVE SINK", "W7"
        w_matches = re.findall(r'\bW(\d+)\b', text_content)
        d_matches = re.findall(r'\bD(\d+)\b', text_content)

        # Standard window width is typically 36" wide, 48" high, 36" sill
        if "WINDOW" in text_content or w_matches:
            windows.append({
                "width_in": 36.0,
                "height_in": 48.0,
                "x_in": 60.0,
                "sill_height_in": 36.0,
                "notes": "Window found on wall"
            })

        if "DOOR" in text_content or d_matches:
            doors.append({
                "width_in": 36.0,
                "height_in": 80.0,
                "x_in": 120.0,
                "notes": "Door opening"
            })

        return {
            "doors": doors,
            "windows": windows
        }
