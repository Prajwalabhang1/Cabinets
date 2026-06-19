"""
Deep inspection of the REAL Casa Familia shop drawing PDF.
Extract EVERY piece of data: layout, dimensions, cabinet items, fonts, structure.
"""
import fitz
import json
from pathlib import Path

PDF_PATH = r"Casa familia\03_Shop_Drawings\ITALIANKB SHOP DRAWINGS - 23-033 CASA FAMILIA - 03.04.2025 hatch corregido.pdf"
pdf = fitz.open(PDF_PATH)

print(f"{'='*70}")
print(f"  REAL SHOP DRAWING — COMPLETE DEEP INSPECTION")
print(f"  File: {Path(PDF_PATH).name}")
print(f"  Pages: {pdf.page_count}")
p = pdf[0]
print(f"  Page size: {p.rect.width:.1f} x {p.rect.height:.1f} pts  =  {p.rect.width/72:.2f}\" x {p.rect.height/72:.2f}\"")
print(f"{'='*70}")

full_data = {}

for pg_num in range(pdf.page_count):
    page = pdf[pg_num]
    blocks = page.get_text("dict")  # rich dict format with font info

    print(f"\n{'─'*70}")
    print(f"  PAGE {pg_num+1}")
    print(f"{'─'*70}")

    page_data = {"texts": [], "images": len(page.get_images())}

    for block in blocks["blocks"]:
        if block["type"] == 0:  # text block
            for line in block["lines"]:
                for span in line["spans"]:
                    txt = span["text"].strip()
                    if txt and len(txt) > 0:
                        entry = {
                            "text": txt,
                            "x": round(span["bbox"][0], 1),
                            "y": round(span["bbox"][1], 1),
                            "font": span["font"],
                            "size": round(span["size"], 1),
                            "color": span["color"],
                        }
                        page_data["texts"].append(entry)
                        print(f"  [{entry['size']:4.1f}pt {entry['font'][:20]:<20}] pos({entry['x']:6.1f},{entry['y']:6.1f}) → \"{txt[:80]}\"")

    full_data[f"page_{pg_num+1}"] = page_data

pdf.close()

# Save full extraction
out = Path("outputs/cf_real_inspection.json")
out.parent.mkdir(exist_ok=True)
with open(out, "w", encoding="utf-8") as f:
    json.dump(full_data, f, indent=2, ensure_ascii=False)

print(f"\n\nFull extraction saved to: {out}")
print(f"Total pages inspected: {len(full_data)}")
