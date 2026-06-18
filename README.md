# AI Cabinet Estimation & Shop Drawing Automation

An AI-powered pipeline that reads architectural PDF drawings and automatically generates:
- Cabinet shop drawings (ItalianKB-style PDF)
- Project cabinet matrix (Excel)
- Material cost report (Excel)
- Final job costing & selling price quote (Excel)

## Project: Casa Familia & Heritage Village
Client: Kitchen & bathroom cabinet supplier for large-scale US residential construction (FHA/ADA housing).

---

## Pipeline Overview

```
Architect PDF → PyMuPDF → Text + Geometry Extraction
                              ↓
                    Region Detection (Kitchen / Bath / Elevation)
                              ↓
                    400 DPI Crop → Claude Vision API
                              ↓
                    Cabinet Schedule JSON
                              ↓
                    ReportLab → Shop Drawing PDF
                    openpyxl  → Matrix + Pricing Excel
```

---

## Scripts

| File | Description |
|------|-------------|
| `step1_crop_elevations.py` | Reads architect PDF → detects regions → crops at 400 DPI → outputs JSON |
| `read_arch_drawing_pymupdf.py` | Full PyMuPDF extraction demo — 4-page visual output PDF |
| `show_pymupdf_output_formats.py` | Shows exact data types returned by each PyMuPDF method |
| `generate_italiankb_shop_drawings.py` | Generates Casa Familia shop drawing PDF (ItalianKB style) |
| `generate_heritage_shop_drawings.py` | Generates Heritage Village shop drawing PDF |
| `generate_heritage_excel.py` | Generates Heritage Village cabinet matrix + pricing Excel |
| `run_cabinet_estimation.py` | Master runner script |

---

## Tech Stack

| Layer | Tool | Purpose |
|-------|------|---------|
| PDF Reading | PyMuPDF (fitz) | Extract text, geometry, render images |
| PDF Writing | ReportLab | Generate shop drawing PDFs |
| Excel Output | openpyxl | Generate matrix + pricing spreadsheets |
| AI Vision | Claude 3.5 Sonnet / GPT-4o | Classify cabinets from elevation images |
| Orchestration | Python | Pipeline runner |

---

## Project Understanding

See `_Project_Understanding/` folder:
- `01_Client_Understanding_Detailed.md` — Full client requirements
- `02_Simple_Summary_Input_Flow_Output.md` — 5-step workflow summary
- `03_Extraction_Deep_Dive_Research.md` — Technical research on extraction pipeline

---

## 5-Step Client Workflow

1. **Read elevations** → Identify every cabinet (type, W×H×D)
2. **Generate shop drawings** → Per unit type PDF (ItalianKB style)
3. **Build project matrix** → Count units per floor × cabinet totals
4. **Price materials** → Match to vendor price list (Euros → USD, mm → inches)
5. **Job costing** → Apply tax/freight/install/GP% → Final selling price

---

## Status

- [x] PyMuPDF extraction pipeline working
- [x] Region detection (Kitchen/Bath/Elevation)
- [x] 400 DPI crop images generated
- [x] Shop drawing PDF generator (Casa Familia + Heritage)
- [x] Excel generator (Heritage Village)
- [ ] Claude Vision API integration (Step 1B)
- [ ] Automated cabinet schedule JSON → PDF pipeline
- [ ] Project matrix builder from floor plans

---

## Setup

```bash
pip install pymupdf reportlab openpyxl
```
