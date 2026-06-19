"""Final zone validation - now correctly targeting the kitchen elevation drawings."""
import fitz
from pathlib import Path

pdf_path = Path(r"Casa familia\01_Architectural_Drawings\Unit_Plans_FHA_ADA\A-6.00-FHA-UNIT-A1-FLOOR-PLAN-&-DETAILS-Rev.10.pdf")
out_dir = Path("outputs/23-033/zone_validation")
out_dir.mkdir(parents=True, exist_ok=True)

doc = fitz.open(str(pdf_path))
page = doc[0]
W, H = page.rect.width, page.rect.height
print(f"Page: {W:.0f} x {H:.0f} pts")

# From text inspection: 'UNIT A1 KITCHEN EL.' label is at x=1338, y=1196
# 'UNIT A1 KITCHEN PLAN' is at x=856, y=1523
# 'UNIT A1 (CORNER CONDITION) FLOOR PLAN' is at x=159, y=1494
# The RCP label '5 UNIT A1 (CORNER CONDITION) RCP' visible in right column
# 
# The page layout (landscape 36"x24"):
#   x=0-630:    Floor Plan (left side, top)
#   x=630-1320: Unit A1 Typ. RCP (top center)  
#   x=1320-1840: Unit A1 Corner Condition RCP (top right)
#   x=1840-2200: Notes/Legend column
#
#   x=0-630:    Corner Condition Floor Plan (bottom left)
#   x=630-1090: Kitchen Plan (bottom center-left)
#   x=1090-1840: Kitchen Elevation A & B (bottom center-right) ← WE WANT THIS
#   x=1840-2200: Notes column

zones = {
    "A_overview_bottom_right": (1050, 870, 1840, 1540),   # Full elevation area
    "B_kitchen_el_narrow":     (1320, 880, 1840, 1540),   # Narrowed to right side
    "C_kitchen_el_wide":       (1050, 880, 1840, 1540),   # Wide shot
    "D_center_x1100_1500":     (1100, 880, 1500, 1280),   # Kitchen EL top portion
    "E_bottom_elev_zone":      (1100, 1100, 1840, 1540),  # Where label 'UNIT A1 KITCHEN EL' is (y=1196)
    "F_full_right_half":       (1050, 50,  1840, 1720),   # Right half full height
}

for name, (x0, y0, x1, y1) in zones.items():
    clip = fitz.Rect(x0, y0, x1, y1)
    mat = fitz.Matrix(150/72, 150/72)
    pix = page.get_pixmap(matrix=mat, clip=clip)
    out_path = out_dir / f"v2_{name}.png"
    pix.save(str(out_path))
    print(f"  {name}: ({x0},{y0})→({x1},{y1})  {pix.width}x{pix.height}px")

doc.close()
