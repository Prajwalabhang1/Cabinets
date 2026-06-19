"""
===========================================================================
  core/config.py — Central Configuration Manager
===========================================================================
  Loads all settings from environment variables (.env) with sensible
  production defaults. Every module imports from here — no hardcoded
  values anywhere else in the codebase.
===========================================================================
"""
from __future__ import annotations
import os
from pathlib import Path
from dotenv import load_dotenv

# ── Resolve project root (2 levels up from this file) ──────────────────────
_HERE      = Path(__file__).resolve().parent          # …/Albert_Project/core/
PROJECT_ROOT = _HERE.parent                           # …/Albert_Project/

# ── Load .env from project root ────────────────────────────────────────────
load_dotenv(PROJECT_ROOT / ".env", override=False)

# ── API Keys ────────────────────────────────────────────────────────────────
ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
OPENAI_API_KEY:    str = os.getenv("OPENAI_API_KEY", "")
GEMINI_API_KEY:    str = os.getenv("GEMINI_API_KEY", "")
GROQ_API_KEY:      str = os.getenv("GROQ_API_KEY", "")

# ── Claude model config ─────────────────────────────────────────────────────
CLAUDE_MODEL        = "claude-3-5-sonnet-20241022"
CLAUDE_MAX_TOKENS   = 4096
CLAUDE_TEMPERATURE  = 0.1    # Low temp for structured/deterministic output
GPT4O_MODEL         = "gpt-4o"

# ── Currency & Unit Conversion ──────────────────────────────────────────────
EUR_USD_RATE: float = float(os.getenv("EUR_USD_RATE", "1.09"))

# ── PDF Rendering ───────────────────────────────────────────────────────────
CROP_DPI    = 400   # DPI for elevation crop images sent to Vision AI
RENDER_DPI  = 300   # DPI for full-page renders (reports, analysis)

# ── Job Costing Defaults ────────────────────────────────────────────────────
DEFAULT_GP_TARGET_PCT:             float = float(os.getenv("GP_TARGET_PCT",             "0.35"))
DEFAULT_COMMISSION_PCT:            float = float(os.getenv("COMMISSION_PCT",            "0.05"))
DEFAULT_BOND_PCT:                  float = float(os.getenv("BOND_PCT",                  "0.015"))
DEFAULT_LOCAL_USE_TAX_PCT:         float = float(os.getenv("LOCAL_USE_TAX_PCT",         "0.075"))
DEFAULT_OCEAN_FREIGHT_PER_CONTAINER: float = float(os.getenv("OCEAN_FREIGHT_PER_CONTAINER", "4500.00"))
DEFAULT_INLAND_DELIVERY:           float = float(os.getenv("INLAND_DELIVERY",           "1200.00"))
DEFAULT_INSTALLATION_PER_CABINET:  float = float(os.getenv("INSTALLATION_PER_CABINET",  "85.00"))
DEFAULT_WAREHOUSING_PCT:           float = float(os.getenv("WAREHOUSING_PCT",           "0.02"))
DEFAULT_MATERIAL_PROTECTION_PCT:   float = float(os.getenv("MATERIAL_PROTECTION_PCT",   "0.005"))
DEFAULT_INSURANCE_PCT:             float = float(os.getenv("INSURANCE_PCT",             "0.008"))
DEFAULT_MISC_ALLOWANCE:            float = float(os.getenv("MISC_ALLOWANCE",            "500.00"))
DEFAULT_CABINETS_PER_CONTAINER:    int   = int(os.getenv("CABINETS_PER_CONTAINER",      "220"))

# ── Validation Thresholds ───────────────────────────────────────────────────
# Cabinet width must be within ±25mm of a standard catalog size to auto-approve
CABINET_WIDTH_TOLERANCE_MM  = 25.0
# Total cabinet run must be within ±50mm of room width to auto-approve
ROOM_WIDTH_TOLERANCE_MM     = 50.0
# AI confidence threshold for auto-approval (no human review needed)
AUTO_APPROVE_CONFIDENCE     = 0.90
# Standard base cabinet height (non-ADA)
BASE_CABINET_HEIGHT_STD_MM  = 720.0
# ADA base cabinet height (max 34" countertop)
BASE_CABINET_HEIGHT_ADA_MM  = 864.0

# ── Standard Cabinet Widths (industry standard, in mm) ─────────────────────
STANDARD_WIDTHS_MM = [
    150, 200, 250, 300, 350, 400, 450, 500, 550, 600,
    610, 762, 900, 1050, 1200, 1500,  # 24", 30", 35.4", 41.3", 47.2", 59"
]

# ── Region Detection Labels ─────────────────────────────────────────────────
ELEVATION_LABELS = [
    "ELEVATION A", "ELEVATION B", "ELEVATION C", "ELEVATION D",
    "ELEV. A", "ELEV. B", "ELEV. C",
    "ELEV A",  "ELEV B",  "ELEV C",
    "EL. A",   "EL. B",   "EL. C",
    "EL A",    "EL B",    "EL C",
]
KITCHEN_LABELS = ["KITCHEN", "KITCHEN ELEVATION", "KITCHEN EL.", "KIT.", "KIT EL"]
BATH_LABELS    = [
    "BATHROOM", "BATH", "MASTER BATH", "MASTER BEDROOM BATH",
    "VANITY", "BATH 2", "BATH 1", "MASTER BATH EL.", "BATH EL.",
    "ADA BATHROOM", "FHA BATHROOM",
]
APPLIANCE_LABELS = [
    "DISHWASHER", "D/W", "DW", "REFRIGERATOR", "REF.", "REF",
    "MICROWAVE", "M/W", "MW", "RANGE", "OVEN", "SINK",
]
CABINET_KEYWORDS = APPLIANCE_LABELS + [
    "UPPER", "LOWER", "BASE", "WALL CAB", "PANTRY",
    "TALL", "COUNTERTOP", "COUNTER", "CABINET", "CAB",
    "W.I.C", "CLOSET", "LINEN", "VANITY",
]

# ── Page Layout (ItalianKB / Italian Kitchen and Bath standard) ─────────────
PAGE_W_PTS = 1224.0   # 17" × 72 pt/in
PAGE_H_PTS = 792.0    # 11" × 72 pt/in

# Title block (right-side vertical strip)
TB_X     = 1161.6     # left edge of title block
TB_W     = 62.4       # width of title block
TB_COLS  = [TB_X + i * 14.4 for i in range(5)] + [TB_X + TB_W]

# Drawing area bounds
DA_LEFT  = 18.0
DA_RIGHT = TB_X - 4.0
DA_TOP   = 8.0
DA_BOTTOM = PAGE_H_PTS - 14.0

# ── Output directories ──────────────────────────────────────────────────────
OUTPUTS_ROOT = PROJECT_ROOT / "outputs"

def get_output_dir(project_id: str) -> Path:
    """Return (and create) the output directory for a project."""
    d = OUTPUTS_ROOT / project_id
    d.mkdir(parents=True, exist_ok=True)
    (d / "crops").mkdir(exist_ok=True)
    (d / "json").mkdir(exist_ok=True)
    return d

# ── Data files ──────────────────────────────────────────────────────────────
CABINET_LIBRARY_PATH = PROJECT_ROOT / "data" / "cabinet_library.json"

def validate_config() -> list[str]:
    """Return a list of warnings about missing/invalid configuration."""
    warnings = []
    if not ANTHROPIC_API_KEY:
        warnings.append(
            "ANTHROPIC_API_KEY not set — Claude Vision integration will not work. "
            "Set it in .env or use --skip-ai flag."
        )
    if not OPENAI_API_KEY:
        warnings.append(
            "OPENAI_API_KEY not set — GPT-4o backup validation disabled."
        )
    if EUR_USD_RATE <= 0:
        warnings.append(f"EUR_USD_RATE={EUR_USD_RATE} is invalid.")
    return warnings


if __name__ == "__main__":
    print(f"Project root: {PROJECT_ROOT}")
    warnings = validate_config()
    if warnings:
        print("\n⚠️  Configuration warnings:")
        for w in warnings:
            print(f"   • {w}")
    else:
        print("✅ Configuration OK")
    print(f"\n   EUR/USD rate: {EUR_USD_RATE}")
    print(f"   Claude model: {CLAUDE_MODEL}")
    print(f"   Auto-approve threshold: {AUTO_APPROVE_CONFIDENCE}")
