import fitz
import sys

pdf_path = r"Casa familia\01_Architectural_Drawings\Unit_Plans_FHA_ADA\A-6.00-FHA-UNIT-A1-FLOOR-PLAN-&-DETAILS-Rev.10.pdf"
pdf = fitz.open(pdf_path)

print(f"FILE: {pdf_path.split(chr(92))[-1]}")
print(f"Pages: {pdf.page_count}")
print(f"Page size: {pdf[0].rect.width:.0f} x {pdf[0].rect.height:.0f} pts")
print(f"Page size (inches): {pdf[0].rect.width/72:.1f}\" wide x {pdf[0].rect.height/72:.1f}\" tall")
print()

page = pdf[0]
blocks = page.get_text("blocks")
print(f"Total text blocks on page 1: {len(blocks)}")
print()
print("--- ALL TEXT FOUND ON PAGE 1 ---")
for b in blocks:
    txt = b[4].strip().replace('\n', ' | ')
    if txt and len(txt) > 1:
        x0, y0 = round(b[0]), round(b[1])
        print(f"  pos({x0:4d},{y0:4d}): {txt[:100]}")

# Count rectangles
paths = page.get_drawings()
print(f"\nTotal drawn shapes (lines/rects): {len(paths)}")

pdf.close()
