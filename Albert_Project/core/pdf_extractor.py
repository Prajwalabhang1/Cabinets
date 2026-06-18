"""
===========================================================================
  core/pdf_extractor.py — Reusable PyMuPDF Extraction Wrapper
===========================================================================
  Provides clean, typed extraction of all data from architectural PDFs:
    - Text spans with exact (x,y) coordinates
    - Vector geometry (lines, rectangles, curves)
    - High-DPI PNG renders (full page or clipped region)
    - Page dimensions and metadata

  Key improvements over step1_crop_elevations.py:
    - Generic (any PDF path, any page number)
    - Returns typed dataclasses instead of raw dicts
    - Handles multi-page PDFs
    - Proper resource cleanup (context manager)
    - 3 extraction modes: full, region-clipped, batch
===========================================================================
"""
from __future__ import annotations

import io
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import fitz  # PyMuPDF

from core.config import CROP_DPI, RENDER_DPI


# ══════════════════════════════════════════════════════════════════════════
# DATA CLASSES
# ══════════════════════════════════════════════════════════════════════════

@dataclass
class TextSpan:
    """A single text string with exact position on the page."""
    text:     str
    bbox:     tuple[float, float, float, float]   # (x0, y0, x1, y1)
    origin:   tuple[float, float]                 # (x, y) baseline
    font:     str
    size:     float
    color:    int                                  # packed RGB int
    dir:      tuple[float, float] = (1.0, 0.0)    # text direction vector

    @property
    def x0(self) -> float:   return self.bbox[0]
    @property
    def y0(self) -> float:   return self.bbox[1]
    @property
    def x1(self) -> float:   return self.bbox[2]
    @property
    def y1(self) -> float:   return self.bbox[3]
    @property
    def cx(self) -> float:   return (self.bbox[0] + self.bbox[2]) / 2
    @property
    def cy(self) -> float:   return (self.bbox[1] + self.bbox[3]) / 2
    @property
    def upper(self) -> str:  return self.text.upper()
    @property
    def is_horizontal(self) -> bool:
        return abs(self.dir[0]) > abs(self.dir[1])


@dataclass
class VectorRect:
    """A rectangle extracted from vector drawings."""
    x0:     float
    y0:     float
    x1:     float
    y1:     float
    fill:   Optional[tuple] = None    # RGB tuple or None
    stroke: Optional[tuple] = None   # RGB tuple or None
    width_stroke: float = 0.5

    @property
    def w(self) -> float:  return self.x1 - self.x0
    @property
    def h(self) -> float:  return self.y1 - self.y0
    @property
    def cx(self) -> float: return (self.x0 + self.x1) / 2
    @property
    def cy(self) -> float: return (self.y0 + self.y1) / 2
    @property
    def area(self) -> float: return self.w * self.h


@dataclass
class VectorPath:
    """A raw vector drawing path from PyMuPDF get_drawings()."""
    items:       list          # raw PyMuPDF path items
    fill:        Optional[tuple]
    stroke:      Optional[tuple]
    width_stroke: float
    dashes:      str
    close_path:  bool
    rect:        fitz.Rect


@dataclass
class PageData:
    """All extracted data from one PDF page."""
    pdf_path:  str
    page_num:  int
    page_w:    float           # width in PDF points
    page_h:    float           # height in PDF points
    spans:     list[TextSpan]  = field(default_factory=list)
    rects:     list[VectorRect] = field(default_factory=list)
    paths:     list[VectorPath] = field(default_factory=list)

    @property
    def cabinet_spans(self) -> list[TextSpan]:
        """Spans containing cabinet-related keywords."""
        from core.config import CABINET_KEYWORDS
        return [s for s in self.spans
                if any(kw in s.upper for kw in CABINET_KEYWORDS)]

    @property
    def label_spans(self) -> list[TextSpan]:
        """Spans containing section label keywords."""
        LABELS = ["ELEVATION", "KITCHEN", "BATH", "VANITY", "SCALE",
                  "FLOOR PLAN", "SECTION", "UNIT", "NOTE", "ADA", "FHA"]
        return [s for s in self.spans
                if any(kw in s.upper for kw in LABELS)]

    def cabinet_rects(self, min_w: float = 20.0, min_h: float = 10.0) -> list[VectorRect]:
        """Rectangles likely to be cabinet boxes (filter by minimum size)."""
        return [r for r in self.rects if r.w >= min_w and r.h >= min_h]


# ══════════════════════════════════════════════════════════════════════════
# MAIN EXTRACTOR
# ══════════════════════════════════════════════════════════════════════════

class PDFExtractor:
    """
    Thread-safe, resource-managed PDF extraction engine.

    Usage:
        with PDFExtractor(pdf_path) as ex:
            page_data = ex.extract_page(0)
            crop_png  = ex.render_region(rect=(x0, y0, x1, y1), dpi=400)
    """

    def __init__(self, pdf_path: str | Path):
        self.pdf_path = Path(pdf_path)
        if not self.pdf_path.exists():
            raise FileNotFoundError(f"PDF not found: {self.pdf_path}")
        self._doc: Optional[fitz.Document] = None

    def __enter__(self) -> "PDFExtractor":
        self._doc = fitz.open(str(self.pdf_path))
        return self

    def __exit__(self, *_):
        if self._doc:
            self._doc.close()
            self._doc = None

    @property
    def page_count(self) -> int:
        self._ensure_open()
        return len(self._doc)

    def _ensure_open(self):
        if self._doc is None:
            raise RuntimeError(
                "PDFExtractor must be used as a context manager: "
                "  with PDFExtractor(path) as ex: ..."
            )

    # ── Text Extraction ───────────────────────────────────────────────────

    def extract_spans(self, page_num: int = 0) -> list[TextSpan]:
        """Extract all text spans with exact coordinates from a page."""
        self._ensure_open()
        page = self._doc[page_num]
        tdict = page.get_text("dict", flags=fitz.TEXT_PRESERVE_WHITESPACE)

        spans: list[TextSpan] = []
        for block in tdict.get("blocks", []):
            if block.get("type") != 0:  # skip image blocks
                continue
            for line in block.get("lines", []):
                dir_vec = line.get("dir", (1.0, 0.0))
                for s in line.get("spans", []):
                    text = s["text"].strip()
                    if not text:
                        continue
                    spans.append(TextSpan(
                        text   = text,
                        bbox   = tuple(s["bbox"]),
                        origin = tuple(s["origin"]),
                        font   = s.get("font", ""),
                        size   = s.get("size", 10.0),
                        color  = s.get("color", 0),
                        dir    = tuple(dir_vec),
                    ))
        return spans

    # ── Vector Geometry Extraction ────────────────────────────────────────

    def extract_rects(
        self,
        page_num: int = 0,
        min_w: float = 5.0,
        min_h: float = 3.0,
    ) -> list[VectorRect]:
        """Extract all rectangles from vector drawings."""
        self._ensure_open()
        page = self._doc[page_num]
        rects: list[VectorRect] = []

        for draw in page.get_drawings():
            fill   = tuple(draw["fill"])   if draw.get("fill")   else None
            stroke = tuple(draw["color"])  if draw.get("color")  else None
            for item in draw.get("items", []):
                if item[0] != "re":
                    continue
                r = item[1]
                if r.width < min_w or r.height < min_h:
                    continue
                rects.append(VectorRect(
                    x0           = round(r.x0, 2),
                    y0           = round(r.y0, 2),
                    x1           = round(r.x1, 2),
                    y1           = round(r.y1, 2),
                    fill         = fill,
                    stroke       = stroke,
                    width_stroke = draw.get("width", 0.5),
                ))
        return rects

    def extract_paths(self, page_num: int = 0) -> list[VectorPath]:
        """Extract all raw vector paths (lines, rects, curves)."""
        self._ensure_open()
        page = self._doc[page_num]
        paths = []
        for draw in page.get_drawings():
            paths.append(VectorPath(
                items        = draw.get("items", []),
                fill         = tuple(draw["fill"])  if draw.get("fill")  else None,
                stroke       = tuple(draw["color"]) if draw.get("color") else None,
                width_stroke = draw.get("width", 0.5),
                dashes       = draw.get("dashes", "[] 0"),
                close_path   = draw.get("closePath", False),
                rect         = draw.get("rect", fitz.Rect()),
            ))
        return paths

    # ── Full Page Extraction ──────────────────────────────────────────────

    def extract_page(self, page_num: int = 0) -> PageData:
        """Extract all text, geometry from a single page."""
        self._ensure_open()
        page = self._doc[page_num]
        return PageData(
            pdf_path = str(self.pdf_path),
            page_num = page_num,
            page_w   = page.rect.width,
            page_h   = page.rect.height,
            spans    = self.extract_spans(page_num),
            rects    = self.extract_rects(page_num),
            paths    = self.extract_paths(page_num),
        )

    # ── Image Rendering ───────────────────────────────────────────────────

    def render_full_page(
        self,
        page_num: int = 0,
        dpi: int = RENDER_DPI,
    ) -> bytes:
        """Render entire page as PNG bytes."""
        self._ensure_open()
        page = self._doc[page_num]
        mat  = fitz.Matrix(dpi / 72.0, dpi / 72.0)
        pix  = page.get_pixmap(matrix=mat, colorspace=fitz.csRGB)
        return pix.tobytes("png")

    def render_region(
        self,
        rect: tuple[float, float, float, float] | fitz.Rect,
        page_num: int = 0,
        dpi: int = CROP_DPI,
    ) -> bytes:
        """
        Render a clipped region of the page at the specified DPI.
        rect: (x0, y0, x1, y1) in PDF points.
        Returns PNG bytes.
        """
        self._ensure_open()
        page = self._doc[page_num]
        if not isinstance(rect, fitz.Rect):
            rect = fitz.Rect(*rect)
        mat = fitz.Matrix(dpi / 72.0, dpi / 72.0)
        pix = page.get_pixmap(matrix=mat, clip=rect, colorspace=fitz.csRGB)
        return pix.tobytes("png")

    def render_region_to_file(
        self,
        rect: tuple[float, float, float, float],
        out_path: str | Path,
        page_num: int = 0,
        dpi: int = CROP_DPI,
    ) -> Path:
        """Render a region and save it to a PNG file."""
        out_path = Path(out_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        png_bytes = self.render_region(rect, page_num, dpi)
        out_path.write_bytes(png_bytes)
        return out_path

    def save_full_page_png(
        self,
        out_path: str | Path,
        page_num: int = 0,
        dpi: int = RENDER_DPI,
    ) -> Path:
        """Render full page and save to PNG file."""
        out_path = Path(out_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_bytes(self.render_full_page(page_num, dpi))
        return out_path

    # ── Batch Operations ──────────────────────────────────────────────────

    def extract_all_pages(self) -> list[PageData]:
        """Extract data from all pages."""
        return [self.extract_page(i) for i in range(self.page_count)]


# ══════════════════════════════════════════════════════════════════════════
# CONVENIENCE FUNCTIONS (no context manager needed for quick one-off calls)
# ══════════════════════════════════════════════════════════════════════════

def quick_extract(pdf_path: str | Path, page_num: int = 0) -> PageData:
    """One-shot extraction — opens and closes PDF automatically."""
    with PDFExtractor(pdf_path) as ex:
        return ex.extract_page(page_num)


def quick_crop(
    pdf_path: str | Path,
    rect: tuple[float, float, float, float],
    out_path: str | Path,
    dpi: int = CROP_DPI,
) -> Path:
    """One-shot region crop — opens, renders, saves, closes."""
    with PDFExtractor(pdf_path) as ex:
        return ex.render_region_to_file(rect, out_path, dpi=dpi)


# ══════════════════════════════════════════════════════════════════════════
# QUICK TEST
# ══════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python -m core.pdf_extractor <path_to_pdf>")
        sys.exit(1)

    pdf_path = sys.argv[1]
    print(f"Extracting: {pdf_path}")
    with PDFExtractor(pdf_path) as ex:
        print(f"  Pages: {ex.page_count}")
        for i in range(ex.page_count):
            pd = ex.extract_page(i)
            print(f"  Page {i}: {pd.page_w:.0f}×{pd.page_h:.0f} pts | "
                  f"{len(pd.spans)} spans | {len(pd.rects)} rects | "
                  f"{len(pd.paths)} paths")
            print(f"    Label spans: {len(pd.label_spans)}")
            print(f"    Cabinet spans: {len(pd.cabinet_spans)}")
            print(f"    Cabinet-sized rects: {len(pd.cabinet_rects())}")
