# 🔍 How the System Analyzes Input Drawings

## Step-by-Step Technical Explanation — Using Real Unit A1 as Example

---

## 📄 What's Inside One Input PDF (Unit A1 — `A-6.00`)

This single PDF has **7 different drawings on 1 page**:

```
┌─────────────────────────────────────────────────────────────────┐
│  1. UNIT A1 TYP. FLOOR PLAN     │  2. UNIT A1 TYP. RCP         │
│     Scale: 1/4"=1'-0"           │     Scale: 1/4"=1'-0"        │
│     (whole apartment, top view) │     (ceiling plan)            │
├─────────────────────────────────┼───────────────────────────────┤
│  3. UNIT A1 CORNER CONDITION    │  4. UNIT A1 CORNER RCP        │
│     FLOOR PLAN                  │                               │
│     (alternate layout version)  │                               │
├─────────────────────────────────┼───────────────────────────────┤
│  5. UNIT A1 KITCHEN PLAN   ←KEY │  6. UNIT A1 KITCHEN EL. A ←KEY│
│     Scale: 1/2"=1'-0"          │     Scale: 1/2"=1'-0"        │
│     (top-down kitchen view)     │     (front view of wall A)   │
│                                 ├───────────────────────────────┤
│                                 │  7. UNIT A1 KITCHEN EL. 2 ←KEY│
│                                 │     (front view of wall B)   │
└─────────────────────────────────┴───────────────────────────────┘
```

> ✅ **Only drawings 5, 6, and 7 matter for cabinet extraction.**
> The others (floor plan, RCP, ceiling) are NOT used for cabinet data.

---

## 🤖 The 4-Stage AI Analysis Process

---

### STAGE 1 — Open the PDF & Locate the Kitchen Views

**What the system does:**

1. Opens the PDF using `PyMuPDF` (fitz library)
2. Scans all text on the page
3. Finds labels like `"UNIT A1 KITCHEN EL."` and `"UNIT A1 KITCHEN PLAN"`
4. Records the **position** (x, y coordinates) of those labels
5. Defines a bounding box around each view

```python
# The system finds text like this in the PDF:
"UNIT A1 KITCHEN PLAN"   → at position x=856, y=1523
"UNIT A1 KITCHEN EL."    → at position x=1338, y=1628
"SCALE: 1/2\" = 1'-0\""  → at position x=855,  y=1554
```

**Why this works:**
Every architect drawing has a label below each view. The system reads those labels to find where each view is on the page.

---

### STAGE 2 — Extract Cabinet Data from the Elevation View

This is the **most important stage** — reading the kitchen elevation drawing (the front wall view).

**What the system sees in the elevation view:**

```
        ←──────── 14'-0" TOTAL ────────→
      
  ┌────┬──────────┬────┬──────┬──────┐ ← UPPER CABINETS (wall cabinets)
  │ 24"│   36"    │    │  30" │  36" │
  │    │          │    │      │      │
  └────┴──────────┴────┴──────┴──────┘
  ┌────┬──────────┬────┬──────┬──────┐ ← BASE CABINETS (lower cabinets)
  │ DW │   36"    │    │RANGE │  36" │
  │    │          │    │      │      │
  └────┴──────────┴────┴──────┴──────┘
   24"    36"             30"    36"
  [2']   [3']            [2'6"] [3']
```

**The AI extracts 3 things from this view:**

#### A) Dimension Numbers (width of each cabinet)

```
The text in the elevation drawing includes:
  "2' - 0""    → 24 inches = 61 cm  → Dishwasher / small base
  "3' - 0""    → 36 inches = 91 cm  → Standard base cabinet
  "2' - 6""    → 30 inches = 76 cm  → Range slot
  "7' - 6""    → 90 inches = 228 cm → Total wall height
```

#### B) Labels / Annotations

```
  "DW"         → Dishwasher position
  "RANGE"      → Range/oven position  
  "REF."       → Refrigerator position
  "SINK"       → Sink location
  "MICROWAVE"  → Microwave position
  "D/W TYPE HANDLES (TYP. ALL CABINETS)" → Door style
  "UPPER CABINETS" → These are wall cabinets
  "BACKSPLASH W/ CERAMIC TILE FINISH"
  "CABINET OVER REF. TO BE 24" DEPTH"
```

#### C) Drawing Paths (the actual lines of the cabinet boxes)

```
Each rectangle drawn in the PDF = one cabinet box
The system reads these as vector paths:
  Rectangle at x:540→630, y:252→331  → Width=90pts = 76cm cabinet
  Rectangle at x:630→720, y:252→331  → Width=90pts = 76cm cabinet
  etc.
```

---

### STAGE 3 — Match Cabinets to Cabinet Library Codes

After extracting dimensions, the system matches each extracted cabinet to the standard catalog.

```
EXTRACTED from drawing:          MATCHED to cabinet code:
  Width=36", Type=Base       →   B36    (Base Cabinet 36"W × 34.5"H × 24"D)
  Width=36", Type=Upper      →   W3630  (Wall Cabinet 36"W × 30"H × 12"D)
  Width=24", Type=Upper      →   W2430  (Wall Cabinet 24"W × 30"H × 12"D)
  Width=24", Dishwasher slot →   [DW space — no cabinet code, appliance]
  Width=30", Type=Base       →   B30    (Base Cabinet 30"W × 34.5"H × 24"D)
  Corner cabinet             →   BC36   (Corner Base with lazy susan)
```

**Matching rules:**

- Width within ±0.5" tolerance (for slight variations)
- ADA units → different height specs (34" max countertop)
- Appliance spaces → no cabinet code, just marked as "appliance space"

---

### STAGE 4 — Build the Output Data Structure

After matching all cabinets, the system creates a structured record:

```
UNIT A1 — KITCHEN TYPE K1
─────────────────────────
ELEVATION A (Wall A — 14' wide)
  Item 1:  W3630  | Upper Cabinet 36"W  | Upper | 36"×30"×12" | Elev.A | Left of range
  Item 2:  W3630  | Upper Cabinet 36"W  | Upper | 36"×30"×12" | Elev.A | Right of range
  Item 3:  W2430  | Corner Wall Cab 24" | Upper | 24"×30"×12" | Elev.A | Blind corner
  Item 4:  B36    | Base Cabinet 36"W   | Lower | 36"×34"×24" | Elev.A | Standard base
  Item 5:  B36    | Base Cabinet 36"W   | Lower | 36"×34"×24" | Elev.A | Standard base
  Item 6:  BC36   | Corner Base Cab     | Lower | 36"×34"×24" | Elev.A | Corner
  [DW]     ---    | Dishwasher space     | Appl  | 24"wide     | Elev.A | At left end

ELEVATION B (Wall B — 7'10" wide)
  Item 7:  W3630  | Upper Cabinet 36"W  | Upper | 36"×30"×12" | Elev.B | Right of fridge
  Item 8:  W3618  | Over-Fridge Cabinet | Upper | 36"×18"×12" | Elev.B | Over refrigerator
  Item 9:  B30    | Base Cabinet 30"W   | Lower | 30"×34"×24" | Elev.B | Standard base
  [REF]    ---    | Refrigerator space  | Appl  | 28" wide    | Elev.B | Right end

KITCHEN TOTALS FOR UNIT A1:
  Upper Cabinets:  3 pieces
  Base Cabinets:   5 pieces
  Tall/Pantry:     0 pieces
  Kitchen Total:   8 cabinets per unit
```

---

## 🔁 This Repeats for Every Unit Type

The system runs this same 4-stage process for each of the 7 input PDFs:

| PDF File | Unit          | Process                         | Output                                |
| -------- | ------------- | ------------------------------- | ------------------------------------- |
| A-6.00   | Unit A1       | Read elevations → extract cabs | 8 kitchen + 2 bath = 10 cabinets/unit |
| A-6.01   | Unit A2 (ADA) | Same process, ADA heights       | 7 kitchen + 2 bath = 9 cabinets/unit  |
| A-6.02   | Unit A3       | Same process                    | ~8 cabinets/unit                      |
| A-6.03   | Unit B1 (2BR) | Same process + 2nd bathroom     | ~14 cabinets/unit                     |
| A-6.04   | Unit B2 (ADA) | Same process, ADA specs         | ~12 cabinets/unit                     |

---

## 📊 Then the Data Flows Into the Output

```
77 Unit PDFs analyzed
        │
        ▼
Cabinet data per unit type
        │
        ▼  Multiply by unit count (from floor plans)
        │  A1: 8 cabs × 14 units = 112 kitchen cabs
        │  A2: 7 cabs ×  6 units =  42 kitchen cabs
        │  ...
        │
        ▼  Match to price list
        │  B36 = €142.50/unit → total cost calculated
        │
        ▼  Job costing formula → Selling Price
        │
        ▼  PDF GENERATOR
           ┌──────────────────────────────────────────┐
           │  Shop Drawing PDF — matching ItalianKB   │
           │  Page 1: Cover (finish, appliances)      │
           │  Page 2: Matrix (all unit types table)   │
           │  Page 3: Unit A1 Floor Plan              │
           │  Page 4: Unit A1 Elevation A + B         │
           │  Page 5: Unit A1 Bathroom Floor Plan     │
           │  Page 6: Unit A2 (ADA) Elevations        │
           │  ...                                     │
           └──────────────────────────────────────────┘
```

---

## ⚡ The Key Insight

> The architect's elevation drawings already have all the information.
> The AI just **reads the text labels** (dimensions + cabinet names)
> and **reads the rectangle paths** (actual cabinet box locations).
>
> It's like a human reading the same drawing —
> except the AI reads the raw data underneath (text coordinates + vector paths)
> instead of just looking at the picture.

---

*Document: How the System Analyzes Input Drawings | Casa Familia Project*
