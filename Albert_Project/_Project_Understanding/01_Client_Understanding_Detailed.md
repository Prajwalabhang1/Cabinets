# Client Understanding — AI Cabinet Estimation & Shop Drawing Service

---

## 👤 Who Is the Client?

A **kitchen & bathroom cabinet supplier/manufacturer** serving large-scale **residential construction** projects:

| Project Type | Examples |
|---|---|
| High-rise buildings | Multi-floor apartment towers |
| Mid-rise buildings | 3–5 story residential |
| Housing communities | FHA/ADA affordable housing (like Casa Familia, Heritage Village) |

**Current pain point:** Estimation + shop drawing prep is slow & manual.  
**Goal:** AI-powered service with **< 24-hour turnaround** for **20–30 projects/week**.

---

## 📁 Real Projects in Hand (from provided files)

### Project 1 — Casa Familia (Atlantic Pacific Communities)
```
📁 Casa familia/
  ├── 01_Architectural_Drawings/
  │   ├── Floor_Plans/            (13 PDFs — Bldg A & B, Ground/2nd/3rd floors)
  │   ├── Unit_Plans_FHA_ADA/     (7 PDFs — Unit A1, A2-ADA, A3, B1, B2-ADA with ELEVATIONS)
  │   ├── Community_Center/       (5 PDFs — kitchenette, restrooms, multipurpose)
  │   └── Sections_Details/       (13 PDFs — wall sections, door/wall schedules)
  ├── 02_Price_List/              MS PRICE LIST LEVEL 1 - 90CM.xlsx
  └── 03_Shop_Drawings/           ITALIANKB reference shop drawing PDF ← TARGET OUTPUT
```
- Unit types: **A1 (1BR/FHA), A2 (1BR/ADA), A3 (1BR/FHA), B1 (2BR/FHA), B2 (2BR/ADA)**
- **Has elevation drawings** → First project for AI trial

### Project 2 — Heritage Village
```
📁 Heritage/
  ├── 01_Architectural_Drawings/
  │   ├── Floor_Plans/            (3 PDFs — Partial C, Ground/2nd/3rd)
  │   └── Unit_Plans_FHA_ADA/     (14 PDFs — Units A1, A1A-ACC, B1, B1A-ACC, C1, C2, C2a-ACC, C3, D1, D1N, D1A-ACC, ST1, ST1A-ACC)
  └── 02_Price_List/              MS PRICE LIST LEVEL 1 - 90CM.xlsx
```
- Unit types: **A1, B1, C1–C3, D1 (4BR), Studio — plus ADA variants**
- More complex — 14 unit types total

---

## 🔄 The 5-Step AI Workflow (Client's Exact Process)

### STEP 1 — Read Architectural Drawings → Generate Shop Drawings

**Input:**
- Architect PDF floor plans (unit plans with kitchen & bathroom elevations)
- Client's cabinet library (standard list with codes, specs, dimensions)
- Finish tiers: **Standard 1 / Standard 2 / Standard 3**

**AI Must Do:**
- Read elevation drawings to identify each cabinet position in kitchen & bathroom
- Match each position to the correct cabinet from the standard library
- Assign cabinet code, description, W×H×D dimensions, finish tier, elevation reference
- Produce a **Shop Drawing Schedule** per unit type (like the ItalianKB PDF reference)

**Output per unit type:**
- Itemized cabinet list: Item #, Cabinet Code, Description, Type (Upper/Lower/Tall/Vanity), Width, Height, Depth, Qty, Finish Tier, Elevation Ref, Location Note
- Section subtotals: Kitchen Upper count, Lower count, Tall count → Kitchen Total
- Section subtotals: Master Bath count, Bath 2 count → Bath Total
- **Unit Grand Total** cabinet count

> **Reference:** `03_Shop_Drawings/ITALIANKB SHOP DRAWINGS - 23-033 CASA FAMILIA.pdf`  
> The client will send this as the style/format example for AI to follow.

---

### STEP 2 — Build Project Matrix from Drawings

**Input:**
- All unit plan PDFs for a project
- Shop drawings (from Step 1) — cabinet counts per unit type

**AI Must Do:**
- Read building floor plans to count **how many of each unit type** exist per floor and total
- Build the **Project Cabinet Matrix**:

| Unit Type | Description | Qty in Project | Kitchen Upper | Kitchen Lower | Kitchen Tall | Kitchen Total | Bath Cabinets | Unit Total | Project Kitchen Total | Project Bath Total |
|---|---|---|---|---|---|---|---|---|---|---|
| A1 | 1BR/FHA | 14 | 3 | 5 | 0 | 8 | 2 | 10 | 112 | 28 |
| A2 | 1BR/ADA | 6 | 3 | 4 | 0 | 7 | 2 | 9 | 42 | 12 |
| ... | ... | ... | ... | ... | ... | ... | ... | ... | ... | ... |

- Produce **PROJECT TOTALS**: Grand total kitchen cabinets + bath cabinets for the entire building

---

### STEP 3 — Price the Material (Cabinet Cost)

**Input:**
- Project Cabinet Matrix (from Step 2)
- Vendor Price List catalog (client specifies which one, e.g., "MS Level 1 - 90CM")

**Price List Structure (actual file):**
- Prices are in **Euros**, dimensions in **mm** (metric — 90CM = 900mm depth standard)
- Cabinet types in price list:
  - Base Cabinet 1 Door (150mm–610mm wide)
  - Base Cabinet 2 Doors (762mm–1200mm wide)
  - Sink Base 1 Door / 2 Doors
  - Base 1 Door 1 Drawer / 2 Door 1 Drawer / 3 Drawers
  - Tall Wall Cabinet 1/2 Doors
  - Medium Wall Cabinet 1/2 Doors
  - Short Wall Cabinet 1/2 Doors
  - Tall Pantry 1/2 Doors
  - Fillers, Panels (base, pantry, wall)

**AI Must Do:**
- Match each cabinet from shop drawing to correct line in price list (by type + width)
- Calculate unit material cost per cabinet type
- Multiply by quantities from the matrix
- Produce **Total Material Cost** for the entire project

---

### STEP 4 — Job Costing → Selling Price

**Input:**
- Total Material Cost (from Step 3)
- Job Costing Form (client will provide — formula-based)
- Desired Gross Profit % (client sets this)

**Cost Build-Up (from actual job costing file):**

| # | Cost Item | Basis | Rate |
|---|---|---|---|
| 1 | Material Cost | From price list | Input |
| 2 | Local Use Tax | % of Material | 7.5% |
| 3 | Ocean Freight / Shipping | Per container | $4,500/container |
| 4 | Inland Delivery | Fixed per project | $1,200 |
| 5 | Installation | Per cabinet installed | $85/cabinet |
| 6 | Warehousing | % of Material | 2% |
| 7 | Material Protection | % of Material | 0.5% |
| 8 | Insurance | % of Material | 0.8% |
| 9 | Miscellaneous Allowance | Fixed | $500 |
| 10 | Commission | % of Selling Price | 5% |
| 11 | Bond | % of Selling Price | 1.5% |
| 12 | Gross Profit | % of Selling Price | 35% (target) |

> **Container sizing:** ~220 cabinets per container  
> **Selling Price** is auto-calculated: `Pre-Margin Cost ÷ (1 − GP% − Commission% − Bond%)`

**Output:** Final **Selling Price** for the entire project, with full cost breakdown verification

---

### STEP 5 — Repeat (Same Pattern, Different Projects)

- Same workflow applied to every new project
- Only variables that change: **architectural drawings**, **cabinet price list**, **GP% target**
- AI learns the client's style after the trial projects

---

## 📚 Reference Files Mapping

| What Client Sends | File Reference in Folder |
|---|---|
| Architectural drawings (with elevations) | `Unit_Plans_FHA_ADA/*.pdf` |
| Example shop drawing (style guide) | `Casa familia/03_Shop_Drawings/ITALIANKB...pdf` |
| Cabinet library (standard list) | To be provided by client |
| Vendor price list | `02_Price_List/MS PRICE LIST LEVEL 1 -90CM.xlsx` |
| Job costing form | To be provided by client |

---

## ⚠️ Key Technical Details Observed

| Detail | Finding |
|---|---|
| **Dimensions** | Price list uses **mm** (metric). Architectural drawings use **imperial** (inches/feet). Conversion needed. |
| **Prices** | Price list is in **Euros**. Final job costing appears to be in **USD**. Currency conversion needed. |
| **FHA/ADA** | ADA units have lower countertops (34" max instead of 36"), affects base cabinet specs |
| **Finish Tiers** | Standard 1 / 2 / 3 map to different price columns — client will specify per project |
| **Multiple unit types** | Heritage has 14 unit types; AI must handle per-type shop drawings then aggregate |
| **Trial approach** | Client starts with **elevation drawings first** (Casa Familia unit plans), before moving to plans without elevations |

---

## 🗂️ What Client Will Send (Trial Phase)

Per their message, client's 2 team members will provide:

1. ✅ **Architectural drawings** with elevations — first project (Casa Familia in hand)
2. ⬜ **Cabinet library** — their full standard catalog (to be received)
3. ⬜ **Vendor price list catalogs** — labeled (MS Level 1 already in hand, more coming)
4. ✅ **Example shop drawings** — ItalianKB PDF (already in hand as style reference)
5. ⬜ **Job costing form** — formula-based Excel (to be received)

---

## ❓ Open Questions to Clarify

1. **Output format** — Should shop drawings be delivered as Excel, PDF, or both? (ItalianKB reference is a PDF)
2. **Cabinet library** — When will this be sent? Is it the same as the MS 90CM price list or a separate spec sheet?
3. **Currency/Units** — Price list is in Euros & mm. Should final outputs be in USD & inches?
4. **Elevations vs. no elevations** — After the trial, how should AI handle floor plans WITHOUT elevations? Use standard/assumed layouts?
5. **Multiple price tiers** — Will they ever mix Standard 1 + Standard 2 in the same project?
6. **Container calc** — Is 220 cabinets/container a fixed rule or does it vary by cabinet size?
7. **Delivery timeline** — Is < 24 hours measured from when AI receives files to when output is delivered?
8. **Review step** — Does the client want to review/approve shop drawings before job costing runs?
