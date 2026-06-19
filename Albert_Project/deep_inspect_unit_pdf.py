"""
Deep inspection of Unit A1 PDF to understand exact page structure,
what's on each page, and where the kitchen/bath elevations are.
This tells us EXACTLY which regions to crop for accurate extraction.
"""
import fitz
from pathlib import Path

pdf_path = Path(r"Casa familia\01_Architectural_Drawings\Unit_Plans_FHA_ADA\A-6.00-FHA-UNIT-A1-FLOOR-PLAN-&-DETAILS-Rev.10.pdf")
pdf = fitz.open(str(pdf_path))

print(f"PDF: {pdf_path.name}")
print(f"Pages: {len(pdf)}")
print(f"Page size (pt): {pdf[0].rect}")
print()

for page_num in range(len(pdf)):
    page = pdf[page_num]
    w, h = page.rect.width, page.rect.height
    print(f"{'='*60}")
    print(f"PAGE {page_num+1}  ({w:.0f} x {h:.0f} pts = {w/72:.1f}\" x {h/72:.1f}\")")
    print(f"{'='*60}")

    # Extract all text blocks with positions
    blocks = page.get_text("dict", flags=fitz.TEXT_PRESERVE_WHITESPACE)["blocks"]
    text_items = []
    for b in blocks:
        if b["type"] == 0:  # text block
            for line in b["lines"]:
                for span in line["spans"]:
                    text = span["text"].strip()
                    if text and len(text) > 1:
                        x0, y0 = span["bbox"][0], span["bbox"][1]
                        text_items.append((y0, x0, text, span["size"]))

    # Sort by vertical position
    text_items.sort()

    # Show key labels (elevation markers, titles, dimensions)
    print("  KEY TEXT LABELS (titles and elevation markers):")
    shown = set()
    for y, x, text, size in text_items:
        upper = text.upper()
        is_key = (
            any(k in upper for k in [
                'ELEVATION', 'ELEV', 'KITCHEN', 'BATH', 'VANITY',
                'PLAN', 'FLOOR', 'DETAIL', 'SCALE', 'SECTION',
                'UNIT', 'NOTE', 'SCHEDULE', 'CABINET',
                'EL.', 'ELV', 'VIEW', 'REF.', 'FHA', 'ADA'
            ]) or size > 9
        )
        if is_key and text not in shown:
            shown.add(text)
            print(f"    [{x:5.0f}, {y:5.0f}]  size={size:.1f}  '{text}'")

    # Show all dimensions found
    import re
    dims = [(y, x, t) for y, x, t, s in text_items
            if re.search(r"\d+['\-]\d+|\d+\"\s*|\d+\s*mm|\d+'\s*\d*\"?", t)]
    if dims:
        print(f"\n  DIMENSIONS FOUND ({len(dims)} total, first 15):")
        for y, x, t in dims[:15]:
            print(f"    [{x:5.0f}, {y:5.0f}]  '{t}'")

    # Show drawing regions (large rectangles)
    paths = page.get_drawings()
    rects = []
    for path in paths:
        r = path.get("rect")
        if r and r.width > 100 and r.height > 100:
            rects.append(r)

    # Cluster rectangles to find distinct zones
    if rects:
        print(f"\n  LARGE RECTANGLES / ZONES ({len(rects)} total, largest 8):")
        rects_sorted = sorted(rects, key=lambda r: -(r.width * r.height))
        for r in rects_sorted[:8]:
            print(f"    x={r.x0:.0f}-{r.x1:.0f}, y={r.y0:.0f}-{r.y1:.0f}  "
                  f"({r.width:.0f}w x {r.height:.0f}h pts)")

    print()

pdf.close()
print("\nDone. Use this info to hardcode exact crop zones per unit type.")
