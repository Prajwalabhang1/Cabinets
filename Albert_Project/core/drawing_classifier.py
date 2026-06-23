"""
===========================================================================
  core/drawing_classifier.py — Stage 0 Drawing Sheet Page Classifier
===========================================================================
  Analyzes text spans on a drawing page to classify it into:
  - FLOOR PLAN
  - UNIT PLAN
  - ELEVATION
  - RCP
  - DETAIL
  - SECTION
===========================================================================
"""
from __future__ import annotations

import re
from typing import List, Any
from core.pdf_extractor import TextSpan

class DrawingClassifier:
    """
    Classifies drawings based on text tokens and layout annotations.
    """

    @staticmethod
    def classify_page(spans: list[TextSpan]) -> str:
        """
        Classifies page text content into drawing type labels.
        """
        text_content = " ".join(s.text.upper() for s in spans)
        
        # 1. RCP Check (Reflected Ceiling Plan)
        if "RCP" in text_content or "REFLECTED CEILING" in text_content:
            return "RCP"

        # 2. Elevation Check
        if "ELEVATION" in text_content or "INT. ELEV" in text_content:
            return "ELEVATION"

        # 3. Unit Plan Details Check
        if "UNIT PLAN" in text_content or "UNIT A" in text_content or "UNIT B" in text_content or "UNIT D" in text_content or "UNIT ST" in text_content or "ENLARGED PLAN" in text_content:
            return "UNIT PLAN"

        # 4. Overall Floor Plan Check
        if "FLOOR PLAN" in text_content or "GROUND LEVEL" in text_content or "LEVEL PLAN" in text_content or "OVERALL PLAN" in text_content:
            return "FLOOR PLAN"

        # 5. Section Check
        if "BUILDING SECTION" in text_content or "WALL SECTION" in text_content:
            return "SECTION"

        # 6. Detail Check
        if "DETAIL" in text_content or "SECTION" in text_content or "MOUNTING" in text_content:
            return "DETAIL"

        # Fallback
        return "UNIT PLAN" # Most details pages are unit plan/elevations
