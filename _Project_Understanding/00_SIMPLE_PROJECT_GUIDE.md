# 🏠 Albert Project — Simple Guide
### AI Cabinet Estimation & Shop Drawing Automation

---

## 🤔 What Is This Project? (In Plain English)

> **The client is a kitchen cabinet company.**
> They sell and install cabinets for apartment buildings — sometimes 50 to 100+ apartments at once.
>
> **The problem?** Figuring out which cabinets go where, how many, what they cost, and drawing the final
> design documents — all of this takes their team days to do manually.
>
> **Our job:** Build an AI system that does it **automatically in under 24 hours.**

---

## 🏗️ Real Projects We Are Working On

| Project | Location | Units | Status |
|---------|----------|-------|--------|
| **Casa Familia** | Miami, FL | 50 apartments (A1, A2-ADA, A3, B1, B2-ADA) | ✅ Files in hand |
| **Heritage Village** | (TBD) | ~70 apartments, 14 unit types | 📋 Up next |

---

## 📋 The 5 Steps — What the AI Does

```
ARCHITECT DRAWINGS  ──►  STEP 1  ──►  STEP 2  ──►  STEP 3  ──►  STEP 4  ──►  FINAL PDF
    (PDFs)               Read        Count         Price         Cost          Shop
                         Cabinets    All Units    Cabinets      Calculate     Drawings
```

---

### STEP 1 — Read the Drawings & List All Cabinets

**Input:** Architect's PDF drawings (floor plans + elevation views of kitchens/bathrooms)

**What it does:**
- Opens each apartment unit's drawing (e.g., Unit A1 — 1-bedroom apartment)
- Looks at the kitchen and bathroom walls (elevation views)
- Identifies every cabinet: upper wall cabinets, lower base cabinets, pantry cabinets
- Assigns each cabinet a code, size (Width × Height × Depth), and a type

**Output:** A schedule (list) of all cabinets for that unit type

```
Example for Unit A1 - Kitchen:
┌────────────────────────────────────────────────────────────┐
│ Item  │ Code   │ Description          │ Type  │ W   H   D  │
│  1    │ W3630  │ Wall Cabinet 36"W    │ Upper │ 36" 30" 12"│
│  2    │ B36    │ Base Cabinet 36"W    │ Lower │ 36" 34" 24"│
│  3    │ BC36   │ Corner Base Cabinet  │ Lower │ 36" 34" 24"│
│  ...  │  ...   │  ...                 │  ...  │  ...       │
└────────────────────────────────────────────────────────────┘
```

---

### STEP 2 — Count All Units Across the Building

**Input:** Building floor plan PDFs + cabinet list from Step 1

**What it does:**
- Reads the full building plan to count how many of each unit type exist
- Multiplies cabinet counts by unit quantities

**Output:** The Project Matrix (the "big picture" table)

```
Example Matrix:
┌──────────────┬─────┬──────────────┬──────────────┬────────────┐
│ Unit Type    │ Qty │ Kitchen Cabs │ Bathroom Cabs│ TOTAL Cabs │
│ A1 (1BR/FHA) │ 14  │    8 each    │    2 each    │ 140 total  │
│ A2 (ADA)     │  6  │    7 each    │    2 each    │  54 total  │
│ B1 (2BR)     │  6  │   10 each    │    4 each    │  84 total  │
│ ...           │ ... │    ...       │    ...       │  ...       │
│ PROJECT TOTAL│ 50  │     ---      │     ---      │ 630 total  │
└──────────────┴─────┴──────────────┴──────────────┴────────────┘
```

---

### STEP 3 — Price the Cabinets

**Input:** Cabinet matrix + Price list (MS PRICE LIST LEVEL 1 - 90CM.xlsx)

**What it does:**
- Matches each cabinet code to its price in the vendor catalog
- Prices are in **Euros** (we convert to USD)
- Dimensions in the price list are in **mm** (we convert from inches)

**Output:** Total material cost for all cabinets in the project

```
Example Pricing:
  Base Cabinet 36"W   →   €142.50 per unit × 140 units = €19,950
  Wall Cabinet 30"W   →   €98.00 per unit  × 140 units = €13,720
  ...
  TOTAL MATERIAL COST = €85,000 → ~$91,000 USD
```

---

### STEP 4 — Calculate Final Selling Price

**Input:** Total material cost + Job Costing formula

**What it adds on top of material cost:**

| Cost Item | How Calculated |
|-----------|---------------|
| 🚢 Ocean Freight | $4,500 per shipping container (~220 cabinets each) |
| 🚚 Inland Delivery | $1,200 flat fee |
| 🔧 Installation | $85 per cabinet installed |
| 📦 Warehousing | 2% of material cost |
| 🛡️ Insurance | 0.8% of material cost |
| 💰 Commission | 5% of final selling price |
| 📄 Bond | 1.5% of final selling price |
| 📈 Gross Profit | 35% of final selling price (client target) |

**Formula:**
```
Selling Price = (All Costs Above) ÷ (1 - 35% - 5% - 1.5%)
             = Total Pre-Margin Costs ÷ 58.5%
```

**Output:** Final **Selling Price** with full cost breakdown

---

### STEP 5 — Generate the Shop Drawing PDF

**Input:** Cabinet data + Project info + ItalianKB template style

**What it generates:**
- A professional **17" × 11" landscape PDF** — the same format used by ItalianKB
- One page per kitchen/bathroom type
- Contains: floor plan views, elevation views (front view of each wall), dimensions

**The PDF includes:**
```
📄 Page 1: COVER SHEET
   - Project name, finish selection, appliance models, general notes

📄 Page 2: MATRIX
   - Table of all unit types, quantities, kitchen types, vanity types

📄 Page 3+: Per Unit Type (e.g., Kitchen Type K1 / Unit A1)
   - FLOOR PLAN (top-down view with cabinet layout)
   - ELEVATION A — Front view of wall A with every cabinet drawn
   - ELEVATION B — Front view of wall B
   - Dimensions in BOTH cm and inches

📄 Last pages: PARTS & SECTIONS
   - Exploded cabinet assembly views
   - Cross-sections showing inside dimensions
```

---

## 📐 The Shop Drawing — What It Looks Like

```
╔═══════════════════════════════════════════════════╦══════════════════╗
║                                                   ║ KITCHEN TYPE K1  ║
║   ←──────────── 426.72 cm [14'] ──────────────→   ║     UNIT A1      ║
║   ←── 394.22 cm ──────────────────────────────→   ╠══════════════════╣
║                                                   ║ ITALIAN KITCHEN  ║
║  ┌──────┬──────────┬────┬───────┬─────┬──────┐   ║ AND BATH         ║
║  │  X   │    X     │ X  │   X   │ X   │   X  │   ║                  ║
║  │ UPPR │   UPPR   │UPPR│  UPPR │UPPR │  UPPR│   ║─────────────────║
║  │      │          │    │       │     │      │   ║ PROJECT #: 23-033║
║  ├──────┼──────────┼────┼───────┼─────┼──────┤   ║ CASA FAMILIA     ║
║  │ D/W  │   BASE   │BASE│ RANGE │BASE │  BASE│   ║─────────────────║
║  │ 61cm │  90cm    │30cm│ 76cm  │35cm │ 90cm │   ║ DATE: 11/05/2024 ║
║  └──────┴──────────┴────┴───────┴─────┴──────┘   ║ REV: 5.0         ║
║  ↑       228.60 cm [7'-6"]       ↑               ║ DRAWN BY: A.C    ║
║                                                   ╠══════════════════╣
║  ELEVATION A    SCALE 1/2"=1'-0"                  ║ SHEET NUMBER     ║
║  CASA FAMILIA UNIT A1 / KITCHEN TYPE K1           ║      A.2         ║
╚═══════════════════════════════════════════════════╩══════════════════╝
```

---

## 📂 How the Files Are Organized

```
Albert_Project/
│
├── Casa familia/
│   ├── 01_Architectural_Drawings/        ← INPUT: PDFs from architect
│   │   ├── Floor_Plans/                  ← Building layout (count units)
│   │   ├── Unit_Plans_FHA_ADA/           ← Individual unit elevations (read cabinets)
│   │   └── Sections_Details/             ← Wall sections, details
│   │
│   ├── 02_Price_List/                    ← INPUT: Vendor catalog
│   │   └── MS PRICE LIST LEVEL 1 -90CM.xlsx
│   │
│   └── 03_Shop_Drawings/                 ← OUTPUT (generated here)
│       ├── ITALIANKB SHOP DRAWINGS...pdf ← REFERENCE (client's example)
│       └── GENERATED_SHOP_DRAWINGS_CF.pdf← ← OUR OUTPUT
│
├── generate_italiankb_shop_drawings.py   ← Main generator script
└── run_cabinet_estimation.py             ← Full pipeline runner
```

---

## 🔄 How to Run It

```bash
# Run the complete pipeline (estimation + shop drawings):
python run_cabinet_estimation.py

# Run ONLY the shop drawing generator:
python generate_italiankb_shop_drawings.py
```

The output PDF appears in:
`Casa familia → 03_Shop_Drawings → GENERATED_SHOP_DRAWINGS_CF.pdf`

---

## 🎯 What Makes This Production-Grade

| Feature | Detail |
|---------|--------|
| **Exact same page size** | 17" × 11" landscape — same as ItalianKB reference |
| **Same fonts** | Helvetica (matching Arial/CenturyGothic used in original) |
| **Same scale** | 1/2" = 1'-0" → exactly 3 PDF points per real inch |
| **Dual dimensions** | Every measurement shown in **cm AND inches** (e.g., `76.20 / [2'-6"]`) |
| **Real title block** | Right-side vertical strip with company info, project info, sheet numbers |
| **Real elevation views** | Cabinets drawn to scale with door patterns and dimension lines |
| **Data-driven** | Change the input data → get a different correctly-formatted PDF |

---

## ⚠️ Important Things to Know

| Topic | What to Know |
|-------|-------------|
| **ADA Units** | ADA (wheelchair accessible) units have LOWER countertops (34" instead of 36"). The AI handles this separately |
| **Dimensions** | Price list = millimeters in Euros. Drawings = feet/inches in USD. AI converts everything automatically |
| **Finish Tiers** | Standard 1 / 2 / 3 — different price columns. Client tells us which tier per project |
| **Containers** | Cabinets ship in containers (~220 per container). Freight cost depends on container count |
| **Not included** | Appliances, countertops, plumbing, and fixtures are **NOT** in the cabinet count |

---

## ❓ Still Needed From Client

- [ ] **Cabinet library** — Their full standard catalog (codes + specs)
- [ ] **Job costing form** — Their exact Excel formula template
- [ ] **More price lists** — Other vendor catalogs (MS Level 1 is in hand)
- [ ] **Confirm output format** — PDF only? Or also Excel?
- [ ] **Review step** — Does client want to approve before final PDF is sent?

---

*Last updated: June 2026 | Project: Casa Familia (23-033) | Status: AI Pipeline Built ✅*
