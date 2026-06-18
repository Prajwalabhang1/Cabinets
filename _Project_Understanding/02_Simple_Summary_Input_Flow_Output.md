# AI Cabinet Estimation System — Simple Summary

![AI Cabinet Workflow](file:///C:/Users/prajw/.gemini/antigravity-ide/brain/ac98622d-6bdc-4220-841e-f47c9833e9be/ai_cabinet_workflow_1781689295034.png)

---

## 📥 INPUTS — What Goes In

| # | Input | Format | Example (from files) |
|---|---|---|---|
| 1 | **Architectural Floor Plans** | PDF | `A-6.00-FHA-UNIT-A1-FLOOR-PLAN.pdf` — shows kitchen layout + elevations |
| 2 | **Cabinet Library** | Excel/PDF | Standard list: cabinet codes, sizes (W×H×D), door style, finish tier |
| 3 | **Vendor Price List** | Excel | `MS PRICE LIST LEVEL 1 - 90CM.xlsx` — 107 cabinet types, price in Euros, dims in mm |
| 4 | **Job Costing Form** | Excel | Formula-based form with tax, freight, install, GP% |

> **First trial input:** Casa Familia — Unit plans A1, A2(ADA), A3, B1, B2(ADA) — all have elevation drawings ✅

---

## 🔄 FLOW — What AI Does (5 Steps)

```
  STEP 1           STEP 2            STEP 3           STEP 4          STEP 5
─────────────   ──────────────   ─────────────   ──────────────   ────────────
Read the PDF  → Make Shop       → Count How     → Match Cabinets → Calculate
floor plan +    Drawing for       Many Units      to Price List     Full Job
elevations      each unit type    in building     → Material Cost   Cost + Quote
─────────────   ──────────────   ─────────────   ──────────────   ────────────
```

### Step 1 — Read Elevations → Identify Every Cabinet
- AI reads each unit's kitchen & bathroom elevation drawings
- Identifies position, size, and type of every cabinet
- Matches to standard cabinet library (Upper / Lower / Tall / Vanity)
- Real example from ItalianKB PDF:
  - Kitchen Elevation A: REF panel + 3 upper wall cabs + base cabs
  - Kitchen Elevation B: Sink base + DW adjacent + upper run
  - Vanity: 45cm + 45cm double vanity + 110cm mirror

### Step 2 — Generate Shop Drawings (per unit type)
- AI creates a shop drawing for each unit (A1, A2-ADA, B1, etc.)
- Each shop drawing contains:
  - **Floor plan view** — cabinet layout at scale
  - **Elevation views** — A, B (wall-by-wall cabinet positions with dimensions in cm & inches)
  - **Cabinet schedule table** — Item #, Code, Description, W×H×D, Qty, Finish
- Output format: matches the **ItalianKB PDF style** (23 pages for Casa Familia)
- Real dimensions from ItalianKB: shown in both **mm/cm AND inches** side by side

### Step 3 — Build Project Matrix
- AI reads building floor plans to count units per type
- Builds summary table:

| Unit | Count | Kitchen Cabs | Bath Cabs | Unit Total | Project Total |
|------|-------|-------------|-----------|------------|---------------|
| A1 (1BR) | 14 | 8 | 2 | 10 | 140 |
| A2-ADA (1BR) | 6 | 7 | 2 | 9 | 54 |
| B1 (2BR) | 12 | 10 | 3 | 13 | 156 |
| ... | ... | ... | ... | ... | ... |
| **TOTAL** | **50** | | | | **~500 cabs** |

### Step 4 — Price Match → Material Cost
- Each cabinet from matrix → matched to vendor price list by type + width
- Price list has 107 lines: Base cabs, Sink bases, Drawers, Wall cabs, Pantries, Panels, Fillers
- All priced in **Euros**, dimensions in **mm** (90cm depth standard)
- AI calculates: `Qty × Unit Price = Line Total` → **Grand Material Cost**

### Step 5 — Job Costing → Final Selling Price
Starting from Material Cost, AI applies:

| Cost Item | How Calculated |
|-----------|---------------|
| Local Use Tax | 7.5% × Material |
| Ocean Freight | $4,500 × containers (÷220 cabs per container) |
| Inland Delivery | Fixed $1,200 |
| Installation | $85 × total cabinet count |
| Warehousing | 2% × Material |
| Protection | 0.5% × Material |
| Insurance | 0.8% × Material |
| Misc Allowance | Fixed $500 |
| Commission | 5% of Selling Price |
| Bond | 1.5% of Selling Price |
| **Gross Profit** | **35% of Selling Price (client sets this)** |

**Formula:** `Selling Price = Pre-Margin Cost ÷ (1 − 35% − 5% − 1.5%)`

---

## 📤 OUTPUTS — What Comes Out

| # | Output | Format | Contents |
|---|---|---|---|
| 1 | **Shop Drawings** | PDF (like ItalianKB) | Per unit: floor plan view + elevation views + dimensions in cm & inches |
| 2 | **Project Matrix** | Excel / table | All unit types × counts × cabinet totals for whole building |
| 3 | **Material Cost Report** | Excel | Cabinet-by-cabinet pricing with vendor price list applied |
| 4 | **Final Project Quote** | Excel | Full job cost breakdown + **Selling Price with GP%** |

---

## ⏱️ Timeline Goal
**All 4 outputs delivered in < 24 hours** per project, for up to **20–30 projects/week**

---

## 🔑 Key Facts from Files

| Fact | Detail |
|------|--------|
| Shop drawing style | ItalianKB PDF — 23 pages for Casa Familia (5 unit types) |
| Dimensions shown | Both **metric (cm/mm) AND imperial (feet/inches)** on same drawing |
| Finish shown | `K019 Silver Liberty Elm` — cabinet finish label |
| ADA difference | Lower countertop, ADA dishwasher/range, accessible base cabinet |
| Price list unit | Euros + mm (AI must convert to USD + inches for US projects) |
| Trial project | Casa Familia first → 5 unit types with elevations ready |

---

## ✅ What's Still Needed from Client
- [ ] Cabinet library / standard spec list
- [ ] Job costing form (Excel template)
- [ ] More vendor price catalogs (labeled)
