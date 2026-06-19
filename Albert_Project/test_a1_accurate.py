"""
Test extract on Unit A1 ONLY — validate accuracy before running all 5 units.
"""
import sys
sys.path.insert(0, ".")

# Temporarily patch to only run A1
import extract_cabinets_accurate as ex

# Monkey-patch to only process A1
original = ex.UNIT_PDFS
ex.UNIT_PDFS = {"A1": original["A1"]}

results = ex.extract_all_units(output_dir="outputs/23-033/test_accurate", save_images=True)
