import sys
sys.stdout.reconfigure(encoding="utf-8")
import fitz

def inspect_pdf(path, label):
    print(f"\n{'='*65}")
    print(f"  FILE: {label}")
    print(f"  PATH: {path}")
    print(f"{'='*65}")
    pdf = fitz.open(path)
    print(f"  Total Pages: {pdf.page_count}")
    print(f"  Page size:   {pdf[0].rect.width:.0f} x {pdf[0].rect.height:.0f} pts  ({pdf[0].rect.width/72:.1f}\" x {pdf[0].rect.height/72:.1f}\")")
    print()

    for pg_num in range(min(pdf.page_count, 50)):
        page = pdf[pg_num]
        blocks = page.get_text("blocks")
        texts = []
        for b in blocks:
            t = b[4].strip().replace('\n', ' | ')
            if t and len(t) > 2:
                texts.append(t[:120])

        # Find key identifiers on each page
        full_text = " ".join(texts).upper()
        unit_hint = ""
        for kw in ["UNIT A", "UNIT B", "UNIT C", "UNIT D", "UNIT ST", "COVER", "MATRIX",
                   "A-1", "B-1", "C-1", "D-1", "ST-1", "A1", "B1", "B2", "A2", "A3",
                   "KITCHEN", "BATHROOM", "VANITY", "ELEVATION", "SCHEDULE"]:
            if kw in full_text:
                unit_hint += kw + " | "

        print(f"  Page {pg_num+1:2d}: {unit_hint[:100]}")
        # Print first few text items on each page
        for t in texts[:5]:
            print(f"           → {t[:100]}")
        print()

    pdf.close()


# ── Casa Familia real shop drawing ────────────────────────────────────────
inspect_pdf(
    r"Casa familia\03_Shop_Drawings\ITALIANKB SHOP DRAWINGS - 23-033 CASA FAMILIA - 03.04.2025 hatch corregido.pdf",
    "REAL SHOP DRAWING — CASA FAMILIA (23-033)"
)

# ── Heritage Village real shop drawing ───────────────────────────────────
inspect_pdf(
    r"Heritage\03_Shop_Drawings\05_Cabinet_Estimation_Shop_Drawings_Heritage_Village.pdf",
    "REAL SHOP DRAWING — HERITAGE VILLAGE (23-045)"
)
