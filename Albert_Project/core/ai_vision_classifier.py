"""
===========================================================================
  core/ai_vision_classifier.py — OpenRouter Vision Cabinet Classifier
===========================================================================
  Uses OpenRouter API (Google Gemini models only) to classify cabinets
  from architectural elevation drawings.

  PRIMARY MODEL:  google/gemini-2.5-flash
    - Best for technical/architectural drawings
    - Excellent spatial reasoning and OCR on dimension annotations
    - $1.5/1M input tokens — fast and affordable
    - 1M token context window

  FALLBACK MODEL: google/gemini-2.5-pro
    - More powerful Gemini for complex/ambiguous drawings
    - $2.5/1M input tokens
    - Kicks in when Flash returns low-confidence or invalid JSON

  Pipeline per elevation crop:
    1. Receive: PNG image bytes (400 DPI crop) + pre-extracted dims + rects
    2. Build: structured prompt with dimension context
    3. Call: OpenRouter API (gemini-2.5-flash) with base64 image
    4. Parse: JSON response → list[CabinetItem]
    5. Retry with gemini-2.5-pro if JSON parse fails or confidence < 0.7
    6. Exponential backoff on API errors

  Get key at: https://openrouter.ai
==========================================================================="""
from __future__ import annotations

import base64
import json
import re
import time
import urllib.request
from dataclasses import dataclass, field, asdict
from typing import Optional

import os
from core.config import AUTO_APPROVE_CONFIDENCE, OPENROUTER_API_KEY

# ── OpenRouter Configuration ─────────────────────────────────────────────────
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1/chat/completions"

# Primary: Gemini 2.5 Flash — best at technical/spatial drawings, fast & cheap
PRIMARY_MODEL   = "google/gemini-2.5-flash"
# Fallback: Gemini 2.5 Pro — stronger reasoning for ambiguous/complex drawings
FALLBACK_MODEL  = "google/gemini-2.5-pro"
MAX_TOKENS      = 4096

# ── Demo Mode — low token usage for client demonstrations ─────────────────────
# Set DEMO_MODE=true in .env or environment, or pass demo_mode=True to classify_elevation()
# Reduces cost from ~$0.0015/call → ~$0.0002/call (~85% savings)
DEMO_MODE: bool = os.getenv("DEMO_MODE", "false").lower() in ("1", "true", "yes")
DEMO_DPI        = 150    # vs 400 in full mode  — image tokens: ~88% smaller
DEMO_MAX_TOKENS = 800    # vs 4096              — output capped tightly
DEMO_MAX_DIMS   = 8      # vs 30 pre-extracted dims sent in context
DEMO_MAX_RECTS  = 10     # vs 40 rectangle vectors sent in context

# ══════════════════════════════════════════════════════════════════════════
# DATA CLASSES
# ══════════════════════════════════════════════════════════════════════════

# Valid cabinet types the AI can return
VALID_CABINET_TYPES = {
    "upper_wall",       # Standard wall cabinet (upper)
    "base",             # Standard base cabinet
    "sink_base",        # Base cabinet under sink
    "dw_adjacent",      # Base cabinet next to dishwasher space
    "microwave_shelf",  # Upper cabinet/shelf housing microwave
    "pantry",           # Tall pantry cabinet
    "corner_upper",     # Corner wall cabinet (blind or lazy susan)
    "corner_base",      # Corner base cabinet
    "vanity",           # Bathroom vanity (lower)
    "medicine_cabinet", # Bathroom medicine cabinet / mirror
    "linen",            # Linen/storage cabinet
    "appliance_space",  # Placeholder: dishwasher, fridge, range (no cabinet)
    "filler",           # Filler panel
    "unknown",          # Classifier couldn't determine
}


@dataclass
class CabinetItem:
    """One cabinet identified in an elevation drawing."""
    item_num:      int
    cabinet_type:  str            # from VALID_CABINET_TYPES
    width_mm:      float
    height_mm:     float
    depth_mm:      float
    location:      str            # human-readable position note
    elevation_ref: str            # "ELEVATION A", "ELEVATION B", etc.
    confidence:    float          # 0.0–1.0
    quantity:      int    = 1
    is_ada:        bool   = False
    notes:         str    = ""
    source:        str    = "gemini"  # "gemini" | "manual" | "fallback"

    @property
    def code(self) -> str:
        """Generate a standard cabinet code from type and dimensions."""
        w_in = round(self.width_mm / 25.4)
        h_in = round(self.height_mm / 25.4)
        type_prefix = {
            # Width-only codes
            "base":             f"B{w_in}",
            "sink_base":        f"SB{w_in}",
            "dw_adjacent":      f"DWA{w_in}",
            "corner_base":      f"BC{w_in}",
            "vanity":           f"VAN{w_in}",
            "medicine_cabinet": f"MED{w_in}",
            "linen":            f"LIN{w_in}",
            "filler":           f"FIL{w_in}",
            # Width+height codes
            "upper_wall":       f"W{w_in}-{h_in}",
            "microwave_shelf":  f"MW{w_in}-{h_in}",
            "pantry":           f"T{w_in}-{h_in}",
            "corner_upper":     f"WC{w_in}",
            "appliance_space":  "APPL",
            "unknown":          f"UNK",
        }.get(self.cabinet_type, f"CAB{w_in}")
        if self.is_ada:
            type_prefix += "-ADA"
        return type_prefix

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ElevationResult:
    """Result of classifying one elevation section."""
    elevation_label:  str                # "ELEVATION A"
    unit_type:        str                # "A1", "B1-ADA"
    project_name:     str
    cabinets:         list[CabinetItem] = field(default_factory=list)
    total_width_mm:   Optional[float]   = None
    is_ada:           bool              = False
    auto_approved:    bool              = False
    review_flags:     list[str]         = field(default_factory=list)
    api_calls:        int               = 0

    @property
    def kitchen_cabinets(self) -> list[CabinetItem]:
        return [c for c in self.cabinets
                if c.cabinet_type not in ("vanity", "medicine_cabinet", "linen", "appliance_space")]

    @property
    def bath_cabinets(self) -> list[CabinetItem]:
        return [c for c in self.cabinets
                if c.cabinet_type in ("vanity", "medicine_cabinet", "linen")]

    @property
    def min_confidence(self) -> float:
        if not self.cabinets:
            return 0.0
        return min(c.confidence for c in self.cabinets)

    @property
    def avg_confidence(self) -> float:
        if not self.cabinets:
            return 0.0
        return sum(c.confidence for c in self.cabinets) / len(self.cabinets)


# ══════════════════════════════════════════════════════════════════════════
# PROMPT BUILDER
# ══════════════════════════════════════════════════════════════════════════

def _build_system_prompt(demo: bool = False) -> str:
    if demo:
        # Compact prompt — ~250 tokens vs ~800 tokens
        return (
            "You are a cabinet estimator. Analyze this architectural elevation drawing and return "
            "a JSON array of cabinets. Types: upper_wall, base, sink_base, dw_adjacent, "
            "microwave_shelf, pantry, corner_upper, corner_base, vanity, medicine_cabinet, "
            "linen, appliance_space, filler, unknown. "
            "Each item: {item_num, cabinet_type, width_mm, height_mm, depth_mm, location, "
            "elevation_ref, confidence, quantity, is_ada, notes}. "
            "Std widths: 300,350,400,450,500,550,600,762,900mm. "
            "Base h=720mm d=600mm. Wall h=300mm d=330mm. Pantry h=2130mm. "
            "Return ONLY valid JSON array, no markdown."
        )
    return """You are an expert cabinet estimator with 20+ years of experience reading architectural kitchen and bathroom elevation drawings for US residential construction projects (FHA/ADA housing).

Your job is to analyze architectural elevation drawings and extract a precise, complete cabinet schedule.

CABINET TYPES you must classify:
- upper_wall: Wall-mounted cabinet (above countertop)
- base: Standard floor base cabinet
- sink_base: Base cabinet under sink (open back or plumbing cutout)
- dw_adjacent: Base cabinet adjacent to dishwasher slot (not the DW itself)
- microwave_shelf: Upper cabinet housing a microwave above range
- pantry: Tall floor-to-ceiling pantry cabinet (usually 84" high)
- corner_upper: Corner wall cabinet (blind corner or lazy susan)
- corner_base: Corner base cabinet  
- vanity: Bathroom vanity (lower cabinet with sink)
- medicine_cabinet: Bathroom medicine cabinet / mirror cabinet
- linen: Linen closet or storage cabinet in bathroom
- appliance_space: Space reserved for appliance (DW, fridge, range) — NO CABINET, just a placeholder
- filler: Filler panel (narrow strips between cabinets or walls)
- unknown: Cannot determine type with confidence

STANDARD DIMENSIONS (metric, 90cm depth standard):
- Base cabinets: height 720mm (34.5"), depth 600mm (24")
- ADA base: height 864mm (34" countertop max), depth 600mm  
- Wall/upper cabinets: height 300mm (12"), 380mm (15"), 720mm (30"), depth 330mm (13")
- Pantry: height 2130mm (84"), depth 600mm
- Vanity: height 870mm (34.5"), depth 530mm (21")
- Standard widths: 150, 300, 350, 400, 450, 500, 550, 600mm (6",12",14",16",18",20",22",24")
  and 762mm (30"), 900mm (35.4"), 1050mm (41.3"), 1200mm (47.2")

RULES:
1. Count ONLY cabinets. Do NOT count appliances (dishwasher, refrigerator, range, microwave).
2. Mark appliance positions as type "appliance_space" with the appliance name in "notes".
3. If the drawing shows ADA text or 34" countertop, set is_ada: true.
4. Provide a confidence score (0.0-1.0) for EACH item. Be conservative — if unsure, score 0.7 or lower.
5. ALWAYS return valid JSON — no markdown, no explanation text around the JSON.
6. If you cannot determine a dimension precisely, use the nearest standard size and note your assumption.

OUTPUT FORMAT (JSON array, no other text):
[
  {
    "item_num": 1,
    "cabinet_type": "upper_wall",
    "width_mm": 762,
    "height_mm": 300,
    "depth_mm": 330,
    "location": "Left of range, Elevation A",
    "elevation_ref": "ELEVATION A",
    "confidence": 0.92,
    "quantity": 1,
    "is_ada": false,
    "notes": ""
  }
]"""


def _build_user_prompt(
    unit_type:       str,
    elevation_label: str,
    project_name:    str,
    pre_extracted_dims: list[dict],
    pre_extracted_rects: list[dict],
    is_ada:          bool = False,
    demo:            bool = False,
) -> str:
    """Build the user message with pre-extracted context."""
    ada_note = " (ADA — base h≤864mm, countertop≤34\")" if is_ada else ""

    # Demo mode: send fewer context items to save tokens
    max_dims  = DEMO_MAX_DIMS  if demo else 30
    max_rects = DEMO_MAX_RECTS if demo else 40

    dims_str = ""
    if pre_extracted_dims:
        dims_str = "\nDIMENSIONS (ground truth):\n"
        for d in pre_extracted_dims[:max_dims]:
            dims_str += f"  [{d.get('type','?')}] '{d.get('text','')}' x={d.get('x',0):.0f} y={d.get('y',0):.0f}\n"

    rects_str = ""
    if pre_extracted_rects and not demo:  # skip rect context in demo (saves ~300 tokens)
        rects_str = "\nRECTANGLES (potential cabinet boxes):\n"
        for i, r in enumerate(pre_extracted_rects[:max_rects]):
            rects_str += (f"  R{i+1}: W={r.get('w',0):.0f}pt H={r.get('h',0):.0f}pt "
                          f"@ ({r.get('x0',0):.0f},{r.get('y0',0):.0f})\n")

    if demo:
        return (f"Project:{project_name} Unit:{unit_type}{ada_note} Section:{elevation_label}\n"
                f"{dims_str}\nIdentify all cabinets. Return ONLY JSON array.")

    return f"""Project: {project_name}
Unit Type: {unit_type}{ada_note}
Section: {elevation_label}

I am showing you a cropped section of an architectural elevation drawing.
{dims_str}{rects_str}

Please identify EVERY cabinet in this elevation drawing.
For each rectangle/cabinet shape visible:
1. Determine its type (upper_wall, base, sink_base, dw_adjacent, microwave_shelf, pantry, corner_upper, corner_base, vanity, medicine_cabinet, linen, appliance_space, filler, unknown)
2. Measure/estimate its width in mm (use pre-extracted dimensions if available)
3. Determine height and depth from standard sizes
4. Note its position
5. Score your confidence

Include appliance spaces (dishwasher, range, refrigerator) as type "appliance_space".
Return ONLY the JSON array, nothing else."""


# ══════════════════════════════════════════════════════════════════════════
# MAIN CLASSIFIER
# ══════════════════════════════════════════════════════════════════════════

class CabinetVisionClassifier:
    """
    Classifies cabinets from architectural elevation drawing images
    using Google Gemini vision models through OpenRouter.

    Usage:
        classifier = CabinetVisionClassifier()
        result = classifier.classify_elevation(
            image_bytes=png_bytes,
            unit_type="A1",
            elevation_label="ELEVATION A",
            project_name="Casa Familia",
        )
    """

    def __init__(self):
        self._validate_keys()

    def _validate_keys(self):
        if not OPENROUTER_API_KEY:
            raise EnvironmentError(
                "OPENROUTER_API_KEY is not set.\n"
                "Get your key at: https://openrouter.ai\n"
                "Add to .env: OPENROUTER_API_KEY=sk-or-v1-...\n"
                "Or use --skip-ai flag to skip AI extraction"
            )

    # ── Main Classification ───────────────────────────────────────────────

    def classify_elevation(
        self,
        image_bytes:          bytes,
        unit_type:            str,
        elevation_label:      str,
        project_name:         str,
        pre_extracted_dims:   Optional[list[dict]] = None,
        pre_extracted_rects:  Optional[list[dict]] = None,
        is_ada:               bool = False,
        max_retries:          int = 3,
        demo_mode:            bool = None,   # None = use global DEMO_MODE
    ) -> ElevationResult:
        """
        Classify all cabinets in one elevation section.

        Args:
            image_bytes:  PNG bytes of the cropped elevation (400 DPI)
            unit_type:    e.g. "A1", "B1-ADA"
            elevation_label: e.g. "ELEVATION A", "KITCHEN EL."
            project_name: e.g. "Casa Familia"
            pre_extracted_dims: list of {text, type, x, y} from dimension_parser
            pre_extracted_rects: list of {x0, y0, x1, y1, w, h} from pdf_extractor
            is_ada:       True if this unit is ADA/accessible
            max_retries:  number of API retry attempts on failure

        Returns:
            ElevationResult with list of CabinetItem
        """
        # Resolve demo mode — argument overrides global flag
        use_demo = DEMO_MODE if demo_mode is None else demo_mode

        result = ElevationResult(
            elevation_label = elevation_label,
            unit_type       = unit_type,
            project_name    = project_name,
            is_ada          = is_ada,
        )

        if use_demo:
            print(f"    [AI-DEMO] Low-token mode: DPI={DEMO_DPI}, max_tokens={DEMO_MAX_TOKENS}")
            # Downscale image from 400 DPI to 150 DPI equivalent using PIL if available
            image_bytes = _downscale_image_if_possible(image_bytes, target_dpi=DEMO_DPI)

        # Build the prompt
        user_prompt = _build_user_prompt(
            unit_type            = unit_type,
            elevation_label      = elevation_label,
            project_name         = project_name,
            pre_extracted_dims   = pre_extracted_dims or [],
            pre_extracted_rects  = pre_extracted_rects or [],
            is_ada               = is_ada,
            demo                 = use_demo,
        )

        # Demo: fewer retries, tighter token budget
        retries    = 1 if use_demo else max_retries
        max_tokens = DEMO_MAX_TOKENS if use_demo else MAX_TOKENS

        # Call primary model (Gemini 2.5 Flash) with retries
        mode_tag = "DEMO" if use_demo else "FULL"
        print(f"    [AI-{mode_tag}] Calling {PRIMARY_MODEL} for {elevation_label}...")
        raw_json = self._call_openrouter(
            image_bytes = image_bytes,
            user_prompt = user_prompt,
            model       = PRIMARY_MODEL,
            max_retries = retries,
            max_tokens  = max_tokens,
        )
        result.api_calls += 1

        if raw_json is None:
            result.review_flags.append(f"{PRIMARY_MODEL} API call failed after all retries")
            return result

        # Parse JSON response
        cabinets = self._parse_cabinet_json(raw_json, elevation_label)
        if cabinets is None and not use_demo:
            # Full mode only: retry with fallback model (Gemini 2.5 Pro)
            fix_prompt = (
                f"{user_prompt}\n\nIMPORTANT: Return ONLY a valid JSON array. "
                "No explanation text, no markdown fences, just the raw JSON array."
            )
            print(f"    [AI] Retrying with fallback {FALLBACK_MODEL}...")
            raw_json2 = self._call_openrouter(
                image_bytes, fix_prompt, model=FALLBACK_MODEL, max_retries=1
            )
            if raw_json2:
                cabinets = self._parse_cabinet_json(raw_json2, elevation_label)

        if cabinets is None:
            model_info = f"{PRIMARY_MODEL}" + ("" if use_demo else f" + {FALLBACK_MODEL}")
            result.review_flags.append(f"Failed to parse AI JSON from {model_info}")
            return result

        result.cabinets = cabinets

        # Set auto-approve flag
        result.auto_approved = (
            result.avg_confidence >= AUTO_APPROVE_CONFIDENCE and
            len(result.cabinets) > 0
        )
        if not result.auto_approved:
            result.review_flags.append(
                f"Requires review: avg confidence {result.avg_confidence:.2f} < {AUTO_APPROVE_CONFIDENCE}"
            )
        return result

    # ── OpenRouter API Call ──────────────────────────────────────────────────

    def _call_openrouter(
        self,
        image_bytes: bytes,
        user_prompt: str,
        model:       str = PRIMARY_MODEL,
        max_retries: int = 3,
        max_tokens:  int = MAX_TOKENS,
    ) -> Optional[str]:
        """
        Call OpenRouter vision API with any supported model.
        Returns raw text response or None on failure.
        """
        image_b64     = base64.standard_b64encode(image_bytes).decode("utf-8")
        # Use compact system prompt if max_tokens budget is tight (demo mode)
        use_demo_prompt = max_tokens <= DEMO_MAX_TOKENS
        system_prompt = _build_system_prompt(demo=use_demo_prompt)
        img_kb = len(image_bytes) / 1024
        print(f"    [API] Image size: {img_kb:.1f} KB | max_tokens: {max_tokens}")

        payload = json.dumps({
            "model": model,
            "max_tokens": max_tokens,
            "temperature": 0.1,
            "messages": [
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{image_b64}",
                            },
                        },
                        {"type": "text", "text": user_prompt},
                    ],
                },
            ],
        }).encode("utf-8")

        headers = {
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type":  "application/json",
            "HTTP-Referer":  "https://github.com/Prajwalabhang1/Cabinets",
            "X-Title":       "Cabinet Shop Drawing Generator",
        }

        for attempt in range(max_retries):
            try:
                req = urllib.request.Request(
                    OPENROUTER_BASE_URL,
                    data    = payload,
                    headers = headers,
                    method  = "POST",
                )
                with urllib.request.urlopen(req, timeout=60) as resp:
                    result = json.loads(resp.read())

                content = result["choices"][0]["message"]["content"]
                usage   = result.get("usage", {})
                cost    = usage.get("cost", 0)
                print(f"    [OK] {model.split('/')[-1]} responded | "
                      f"tokens={usage.get('total_tokens',0)} | "
                      f"cost=${cost:.5f}")
                return content

            except Exception as e:
                wait = 2 ** attempt
                print(f"  [WARN] OpenRouter attempt {attempt+1}/{max_retries} "
                      f"({model}) failed: {e}")
                if attempt < max_retries - 1:
                    print(f"         Retrying in {wait}s...")
                    time.sleep(wait)
                else:
                    print(f"  [FAIL] All retries exhausted for {model}.")
        return None

    # ── JSON Parsing ──────────────────────────────────────────────────────

    def _parse_cabinet_json(
        self,
        raw_text:       str,
        elevation_label: str,
    ) -> Optional[list[CabinetItem]]:
        """
        Parse JSON array from AI response.
        Handles: extra markdown fences, trailing commas, partial JSON.
        """
        # Strip markdown code fences
        text = raw_text.strip()
        text = re.sub(r'^```(?:json)?\s*', '', text, flags=re.MULTILINE)
        text = re.sub(r'\s*```\s*$', '', text, flags=re.MULTILINE)
        text = text.strip()

        # Find JSON array
        start = text.find('[')
        end   = text.rfind(']')
        if start == -1 or end == -1:
            # Try to find a JSON object
            print(f"  ⚠️  No JSON array found in response. Raw: {text[:200]}")
            return None

        json_str = text[start:end+1]

        # Fix common AI JSON mistakes
        json_str = re.sub(r',\s*([}\]])', r'\1', json_str)  # trailing commas

        try:
            data = json.loads(json_str)
        except json.JSONDecodeError as e:
            print(f"  ⚠️  JSON parse error: {e}")
            print(f"      Raw snippet: {json_str[:300]}")
            return None

        if not isinstance(data, list):
            print(f"  ⚠️  Expected JSON array, got {type(data)}")
            return None

        cabinets = []
        for i, item in enumerate(data, 1):
            if not isinstance(item, dict):
                continue

            # Validate and normalize cabinet_type
            cab_type = item.get("cabinet_type", "unknown").lower().strip()
            if cab_type not in VALID_CABINET_TYPES:
                # Try to map common variations
                cab_type = _normalize_cabinet_type(cab_type)

            width_mm  = float(item.get("width_mm",  0) or 0)
            height_mm = float(item.get("height_mm", 0) or 0)
            depth_mm  = float(item.get("depth_mm",  0) or 0)

            # Apply standard defaults if missing
            if height_mm == 0:
                height_mm = _default_height(cab_type)
            if depth_mm == 0:
                depth_mm = _default_depth(cab_type)

            confidence = float(item.get("confidence", 0.7))
            confidence = max(0.0, min(1.0, confidence))

            cabinets.append(CabinetItem(
                item_num      = item.get("item_num", i),
                cabinet_type  = cab_type,
                width_mm      = width_mm,
                height_mm     = height_mm,
                depth_mm      = depth_mm,
                location      = str(item.get("location", "")),
                elevation_ref = item.get("elevation_ref", elevation_label),
                confidence    = confidence,
                quantity      = int(item.get("quantity", 1)),
                is_ada        = bool(item.get("is_ada", False)),
                notes         = str(item.get("notes", "")),
                source        = "gemini",
            ))

        return cabinets

    # (merge_results removed — single-model pipeline with Gemini)


# ══════════════════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════════════════

def _normalize_cabinet_type(raw: str) -> str:
    """Map common AI output variations to canonical types."""
    mapping = {
        "wall":          "upper_wall",
        "wall_cabinet":  "upper_wall",
        "upper":         "upper_wall",
        "wall cabinet":  "upper_wall",
        "base_cabinet":  "base",
        "lower":         "base",
        "lower_cabinet": "base",
        "sink":          "sink_base",
        "sink_cabinet":  "sink_base",
        "dishwasher":    "appliance_space",
        "refrigerator":  "appliance_space",
        "fridge":        "appliance_space",
        "range":         "appliance_space",
        "oven":          "appliance_space",
        "microwave":     "microwave_shelf",
        "tall":          "pantry",
        "tall_cabinet":  "pantry",
        "corner":        "corner_base",
        "bath_vanity":   "vanity",
        "bathroom_vanity": "vanity",
        "mirror":        "medicine_cabinet",
        "medicine":      "medicine_cabinet",
    }
    return mapping.get(raw.lower().replace(" ", "_"), "unknown")


def _default_height(cabinet_type: str) -> float:
    """Return standard height in mm for a cabinet type."""
    defaults = {
        "upper_wall":       300.0,
        "base":             720.0,
        "sink_base":        720.0,
        "dw_adjacent":      720.0,
        "microwave_shelf":  460.0,
        "pantry":           2130.0,
        "corner_upper":     300.0,
        "corner_base":      720.0,
        "vanity":           870.0,
        "medicine_cabinet": 760.0,
        "linen":            2130.0,
        "appliance_space":  720.0,
        "filler":           720.0,
    }
    return defaults.get(cabinet_type, 720.0)


def _default_depth(cabinet_type: str) -> float:
    """Return standard depth in mm for a cabinet type."""
    defaults = {
        "upper_wall":       330.0,
        "base":             600.0,
        "sink_base":        600.0,
        "dw_adjacent":      600.0,
        "microwave_shelf":  330.0,
        "pantry":           600.0,
        "corner_upper":     330.0,
        "corner_base":      600.0,
        "vanity":           530.0,
        "medicine_cabinet": 100.0,
        "linen":            460.0,
        "appliance_space":  600.0,
        "filler":           60.0,
    }
    return defaults.get(cabinet_type, 600.0)


def _downscale_image_if_possible(image_bytes: bytes, target_dpi: int = 150) -> bytes:
    """
    Reduce image size by downscaling.
    In demo mode we crop at 400 DPI but then shrink to ~150 DPI equivalent
    to dramatically cut vision token cost (~88% smaller image).

    Falls back to returning original bytes if PIL/Pillow is not installed.
    """
    try:
        from PIL import Image
        import io as _io

        img = Image.open(_io.BytesIO(image_bytes))
        orig_w, orig_h = img.size
        scale = target_dpi / 400.0          # 400 DPI was used during crop
        new_w = max(1, int(orig_w * scale))
        new_h = max(1, int(orig_h * scale))

        img_resized = img.resize((new_w, new_h), Image.LANCZOS)
        buf = _io.BytesIO()
        img_resized.save(buf, format="PNG", optimize=True)
        result = buf.getvalue()

        orig_kb   = len(image_bytes) / 1024
        result_kb = len(result) / 1024
        print(f"    [DEMO] Image scaled {orig_w}×{orig_h} → {new_w}×{new_h}  "
              f"({orig_kb:.0f} KB → {result_kb:.0f} KB, "
              f"{100*(1-result_kb/orig_kb):.0f}% smaller)")
        return result

    except ImportError:
        print("    [DEMO] Pillow not installed — sending original image size.")
        return image_bytes
    except Exception as e:
        print(f"    [DEMO] Downscale failed ({e}) — sending original image.")
        return image_bytes


# ══════════════════════════════════════════════════════════════════════════
# QUICK TEST (no API needed — tests JSON parsing logic)
# ══════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    print("Testing JSON parser (no API key needed)...")

    sample_response = """
```json
[
  {
    "item_num": 1,
    "cabinet_type": "upper_wall",
    "width_mm": 762,
    "height_mm": 300,
    "depth_mm": 330,
    "location": "Left of range, Elevation A",
    "elevation_ref": "ELEVATION A",
    "confidence": 0.92,
    "quantity": 1,
    "is_ada": false,
    "notes": ""
  },
  {
    "item_num": 2,
    "cabinet_type": "base",
    "width_mm": 900,
    "height_mm": 720,
    "depth_mm": 600,
    "location": "Sink base, Elevation A",
    "elevation_ref": "ELEVATION A",
    "confidence": 0.88,
    "quantity": 1,
    "is_ada": false,
    "notes": "sink base cabinet"
  },
  {
    "item_num": 3,
    "cabinet_type": "appliance_space",
    "width_mm": 610,
    "height_mm": 720,
    "depth_mm": 600,
    "location": "Dishwasher slot",
    "elevation_ref": "ELEVATION A",
    "confidence": 0.95,
    "quantity": 1,
    "is_ada": false,
    "notes": "24\" dishwasher space — no cabinet"
  }
]
```
"""

    # Test parsing (no API key needed for this test)
    classifier = object.__new__(CabinetVisionClassifier)  # skip __init__
    classifier.__class__ = CabinetVisionClassifier
    cabinets = classifier._parse_cabinet_json(sample_response, "ELEVATION A")

    if cabinets:
        print(f"[PASS] Parsed {len(cabinets)} cabinets:")
        for c in cabinets:
            print(f"   Item {c.item_num}: {c.cabinet_type:20s} {c.width_mm:.0f}mm  "
                  f"confidence={c.confidence:.2f}  code={c.code}")
    else:
        print("[FAIL] Parsing failed")

    # Test type normalization
    print("\n=== Type Normalization ===")
    for raw in ["wall cabinet", "lower", "dishwasher", "tall_cabinet", "mirror"]:
        print(f"  '{raw}' → '{_normalize_cabinet_type(raw)}'")
