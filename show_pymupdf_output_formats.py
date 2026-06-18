#!/usr/bin/env python3
"""
===========================================================================
  PyMuPDF — RAW OUTPUT FORMAT DEMO
===========================================================================
  Shows the exact data type and format returned by each PyMuPDF method.
  Reads the real Casa Familia Unit A1 architectural PDF.
===========================================================================
"""
import sys, json, pprint
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

import fitz  # PyMuPDF

PDF = r"C:\Users\prajw\OneDrive\Desktop\Albert\Albert_Project\Casa familia\01_Architectural_Drawings\Unit_Plans_FHA_ADA\A-6.00-FHA-UNIT-A1-FLOOR-PLAN-&-DETAILS-Rev.10.pdf"

SEP  = "=" * 70
DASH = "-" * 70

doc  = fitz.open(PDF)
page = doc[0]

# ──────────────────────────────────────────────────────────────────────────
print(SEP)
print("  1.  fitz.open()  →  fitz.Document  object")
print(SEP)
print(f"  Python type : {type(doc)}")
print(f"  page count  : {len(doc)}")
print(f"  metadata    : {type(doc.metadata)}  ← dict")
print()
print("  doc.metadata  (Python dict) :")
pprint.pprint(doc.metadata, indent=4)

# ──────────────────────────────────────────────────────────────────────────
print()
print(SEP)
print("  2.  page.rect  →  fitz.Rect  object")
print(SEP)
print(f"  Python type : {type(page.rect)}")
print(f"  Value       : {page.rect}")
print(f"  .x0={page.rect.x0}  .y0={page.rect.y0}  .x1={page.rect.x1}  .y1={page.rect.y1}")
print(f"  .width={page.rect.width}  .height={page.rect.height}  (in PDF points, 72pts=1 inch)")

# ──────────────────────────────────────────────────────────────────────────
print()
print(SEP)
print("  3.  page.get_text('text')  →  plain str  (raw text dump)")
print(SEP)
raw_text = page.get_text("text")
print(f"  Python type : {type(raw_text)}")
print(f"  Total chars : {len(raw_text)}")
print()
print("  First 800 characters:")
print(DASH)
print(raw_text[:800])
print(DASH)

# ──────────────────────────────────────────────────────────────────────────
print()
print(SEP)
print("  4.  page.get_text('words')  →  list of tuples")
print(SEP)
words = page.get_text("words")
print(f"  Python type     : {type(words)}")
print(f"  Length (words)  : {len(words)}")
print(f"  Type of 1 item  : {type(words[0])}")
print()
print("  Each tuple = (x0, y0, x1, y1, 'word', block_no, line_no, word_no)")
print()
print("  First 10 words:")
print(DASH)
for w in words[:10]:
    print(f"    x0={w[0]:7.2f}  y0={w[1]:7.2f}  x1={w[2]:7.2f}  y1={w[3]:7.2f}  word={repr(w[4]):30s}  blk={w[5]}  ln={w[6]}  wn={w[7]}")
print(DASH)

# ──────────────────────────────────────────────────────────────────────────
print()
print(SEP)
print("  5.  page.get_text('blocks')  →  list of tuples (one per text block)")
print(SEP)
blocks = page.get_text("blocks")
print(f"  Python type     : {type(blocks)}")
print(f"  Total blocks    : {len(blocks)}")
print(f"  Type of 1 item  : {type(blocks[0])}")
print()
print("  Each tuple = (x0, y0, x1, y1, 'text\\nlines', block_no, block_type)")
print("  block_type: 0=text, 1=image")
print()
print("  First 5 text blocks:")
print(DASH)
for b in blocks[:5]:
    x0,y0,x1,y1,text,blk_no,blk_type = b
    print(f"    Block #{blk_no}  bbox=({x0:.1f},{y0:.1f},{x1:.1f},{y1:.1f})  type={blk_type}")
    print(f"    text={repr(text[:80])}")
    print()
print(DASH)

# ──────────────────────────────────────────────────────────────────────────
print()
print(SEP)
print("  6.  page.get_text('dict')  →  Python dict  (RICHEST output)")
print(SEP)
tdict = page.get_text("dict")
print(f"  Python type          : {type(tdict)}")
print(f"  Top-level keys       : {list(tdict.keys())}")
print(f"  Number of blocks     : {len(tdict['blocks'])}")
print()
print("  Structure:  dict → blocks[] → lines[] → spans[] → chars[]")
print()

# Show one full block → line → span chain
first_block = next((b for b in tdict['blocks'] if b.get('type')==0), None)
if first_block:
    print("  --- One full BLOCK ---")
    print(f"  block keys : {list(first_block.keys())}")
    print(f"  block bbox : {first_block['bbox']}")
    print(f"  block type : {first_block['type']}  (0=text)")
    print(f"  lines count: {len(first_block['lines'])}")
    print()
    first_line = first_block['lines'][0]
    print("  --- One LINE inside block ---")
    print(f"  line keys  : {list(first_line.keys())}")
    print(f"  line bbox  : {first_line['bbox']}")
    print(f"  line dir   : {first_line['dir']}  (text direction vector, 1.0,0.0 = left-to-right)")
    print(f"  line wmode : {first_line['wmode']}  (0=horizontal)")
    print(f"  spans count: {len(first_line['spans'])}")
    print()
    first_span = first_line['spans'][0]
    print("  --- One SPAN inside line ---")
    print(f"  span keys  : {list(first_span.keys())}")
    print(f"  span text  : {repr(first_span['text'])}")
    print(f"  span bbox  : {first_span['bbox']}         ← (x0, y0, x1, y1) exact bounding box")
    print(f"  span origin: {first_span['origin']}       ← (x, y) baseline start point")
    print(f"  span size  : {first_span['size']}         ← font size in pts")
    print(f"  span font  : {first_span['font']}         ← font name")
    print(f"  span color : {first_span['color']}        ← integer (0=black, decode via bitshift)")
    print(f"  span flags : {first_span['flags']}        ← bitfield (bold/italic/etc)")
    print()
    print("  COLOR decode example:")
    col = first_span['color']
    r = (col >> 16) & 0xFF
    g = (col >>  8) & 0xFF
    b =  col        & 0xFF
    print(f"    color int={col}  →  R={r}  G={g}  B={b}  →  #{r:02X}{g:02X}{b:02X}")

# ──────────────────────────────────────────────────────────────────────────
print()
print(SEP)
print("  7.  page.get_text('json')  →  JSON string")
print(SEP)
json_str = page.get_text("json")
print(f"  Python type     : {type(json_str)}")
print(f"  Total length    : {len(json_str)} characters")
print()
# Parse it back to confirm
parsed = json.loads(json_str)
print(f"  json.loads() →  {type(parsed)}  (same structure as 'dict' mode)")
print()
print("  First 600 chars of JSON string:")
print(DASH)
print(json_str[:600])
print(DASH)

# ──────────────────────────────────────────────────────────────────────────
print()
print(SEP)
print("  8.  page.get_drawings()  →  list of dicts  (VECTOR GEOMETRY)")
print(SEP)
drawings = page.get_drawings()
print(f"  Python type     : {type(drawings)}")
print(f"  Total paths     : {len(drawings)}")
print(f"  Type of 1 item  : {type(drawings[0])}")
print()
print("  Keys in each drawing dict:")
print(f"  {list(drawings[0].keys())}")
print()

# Count types
item_types = {}
for d in drawings:
    for item in d.get("items", []):
        item_types[item[0]] = item_types.get(item[0], 0) + 1
print(f"  item[0] type codes found:")
print(f"    'l'  = line        →  {item_types.get('l',0):,} total")
print(f"    're' = rectangle   →  {item_types.get('re',0):,} total")
print(f"    'c'  = bezier curve→  {item_types.get('c',0):,} total")
print(f"    'qu' = quad        →  {item_types.get('qu',0):,} total")
print()
print("  First 3 drawing path dicts:")
print(DASH)
for i, d in enumerate(drawings[:3]):
    print(f"  Drawing #{i+1}")
    print(f"    type    : {d.get('type')}  (f=fill, s=stroke, fs=fill+stroke)")
    print(f"    rect    : {d.get('rect')}   ← bounding box")
    print(f"    color   : {d.get('color')}  ← stroke color (r,g,b) floats 0.0-1.0")
    print(f"    fill    : {d.get('fill')}   ← fill color (r,g,b) or None")
    print(f"    width   : {d.get('width')}  ← line width")
    print(f"    dashes  : {d.get('dashes')} ← dash pattern string")
    print(f"    items   : {d.get('items')[:2]} ...")
    print(f"    closePath: {d.get('closePath')}")
    print()
print(DASH)

# Show a real LINE item in detail
line_draw = next((d for d in drawings for item in d.get("items",[]) if item[0]=="l"), None)
if line_draw:
    line_item = next(item for item in line_draw["items"] if item[0]=="l")
    print()
    print("  A LINE item unpacked:")
    print(f"    item[0] = {repr(line_item[0])}       ← type code 'l'")
    print(f"    item[1] = {line_item[1]}  ← fitz.Point  start (x,y)")
    print(f"    item[2] = {line_item[2]}  ← fitz.Point  end   (x,y)")
    print(f"    item[1].x = {line_item[1].x:.4f}   item[1].y = {line_item[1].y:.4f}")

rect_draw = next((d for d in drawings for item in d.get("items",[]) if item[0]=="re"), None)
if rect_draw:
    rect_item = next(item for item in rect_draw["items"] if item[0]=="re")
    print()
    print("  A RECTANGLE item unpacked:")
    print(f"    item[0] = {repr(rect_item[0])}      ← type code 're'")
    print(f"    item[1] = {rect_item[1]}  ← fitz.Rect  (x0,y0,x1,y1)")
    print(f"    item[1].x0={rect_item[1].x0:.2f}  .y0={rect_item[1].y0:.2f}  .width={rect_item[1].width:.2f}  .height={rect_item[1].height:.2f}")

# ──────────────────────────────────────────────────────────────────────────
print()
print(SEP)
print("  9.  page.get_images()  →  list of tuples")
print(SEP)
images = page.get_images()
print(f"  Python type    : {type(images)}")
print(f"  Count          : {len(images)}")
if images:
    print(f"  tuple format   : (xref, smask, width, height, bpc, colorspace, alt_colorspace, name, filter, referencer)")
    for img in images[:3]:
        print(f"  {img}")
else:
    print("  (no embedded images on this page — it's pure vector CAD)")

# ──────────────────────────────────────────────────────────────────────────
print()
print(SEP)
print("  10. page.get_pixmap(matrix)  →  fitz.Pixmap  object")
print(SEP)
mat = fitz.Matrix(72/72, 72/72)   # 72 DPI (low-res, fast)
pix = page.get_pixmap(matrix=mat, colorspace=fitz.csRGB)
print(f"  Python type    : {type(pix)}")
print(f"  pix.width      : {pix.width} px")
print(f"  pix.height     : {pix.height} px")
print(f"  pix.n          : {pix.n}     (channels: 3=RGB, 4=RGBA)")
print(f"  pix.colorspace : {pix.colorspace}")
print(f"  pix.stride     : {pix.stride} bytes per row")
print(f"  pix.samples    : bytes object, len={len(pix.samples)}")
print(f"  Save formats   : .png  .jpg  .ppm  .bmp  — pix.save('file.png')")
print(f"  To bytes       : pix.tobytes('png')  → {type(pix.tobytes('png'))}")

# ──────────────────────────────────────────────────────────────────────────
print()
print(SEP)
print("  SUMMARY — PyMuPDF Return Types")
print(SEP)
summary = [
    ("fitz.open(path)",               "fitz.Document",    "Custom object — iterable, len = page count"),
    ("doc[0]  / doc.load_page(0)",    "fitz.Page",        "Custom object — has all extraction methods"),
    ("page.rect",                     "fitz.Rect",        "x0,y0,x1,y1 in PDF points (72pt=1 inch)"),
    ("page.get_text('text')",         "str",              "Plain text, newlines between lines"),
    ("page.get_text('words')",        "list[tuple]",      "(x0,y0,x1,y1,word,blk,ln,wn)"),
    ("page.get_text('blocks')",       "list[tuple]",      "(x0,y0,x1,y1,text,blk_no,type)"),
    ("page.get_text('dict')",         "dict",             "{width,height,blocks:[{lines:[{spans:[...]}]}]}"),
    ("page.get_text('json')",         "str (JSON)",       "Same structure as 'dict' but serialised"),
    ("page.get_drawings()",           "list[dict]",       "[{type,rect,color,fill,width,items:[...]}]"),
    ("page.get_images()",             "list[tuple]",      "(xref,smask,w,h,bpc,colorspace,name,...)"),
    ("page.get_pixmap(matrix)",       "fitz.Pixmap",      ".width .height .samples(bytes) .save()"),
    ("fitz.Point",                    "fitz.Point",       ".x  .y  — coordinate"),
    ("drawing item 'l'",              "tuple",            "('l', fitz.Point start, fitz.Point end)"),
    ("drawing item 're'",             "tuple",            "('re', fitz.Rect)"),
    ("drawing item 'c'",              "tuple",            "('c', pt1, pt2, pt3, pt4)  bezier"),
]
print(f"  {'Method':<40} {'Returns':<20} {'Description'}")
print(f"  {'-'*38} {'-'*18} {'-'*30}")
for method, ret_type, desc in summary:
    print(f"  {method:<40} {ret_type:<20} {desc}")

print()
print(SEP)
print("  DONE")
print(SEP)
doc.close()
