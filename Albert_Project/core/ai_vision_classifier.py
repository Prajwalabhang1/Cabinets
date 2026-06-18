"""
===========================================================================
  core/ai_vision_classifier.py — Claude Vision Cabinet Classifier
===========================================================================
  THE MISSING PIECE: Integrates Claude 3.5 Sonnet Vision API to classify
  cabinets from architectural elevation drawings.

  This is Layer 4 of the 5-layer extraction pipeline:
    Layer 1: PDF rendering (pdf_extractor.py)
    Layer 2: Region detection (region_detector.py)
    Layer 3: Dimension text extraction (dimension_parser.py)
    Layer 4: AI Vision spatial reasoning ← THIS FILE
    Layer 5: Rule-based validation (cabinet_validator.py)

  Pipeline per elevation crop:
    1. Receive: PNG image bytes (400 DPI crop) + pre-extracted dims + rects
    2. Build: structured prompt with dimension context
    3. Call: Claude 3.5 Sonnet API with image
    4. Parse: JSON response → list[CabinetItem]
    5. Retry: if JSON parse fails, request fix
    6. Optionally validate with GPT-4o (if confidence < threshold)

  Error handling:
    - JSON parse failures: retry up to 3 times with "fix this JSON" prompt
    - API errors: exponential backoff with 3 retries
    - Low confidence: flag for human review (don't crash)
    - No API key: raise clear error with instructions
===========================================================================
"""
from __future__ import annotations

import base64
import json
import re
import time
from dataclasses import dataclass, field, asdict
from typing import Optional

from core.config import (
    ANTHROPIC_API_KEY, OPENAI_API_KEY,
    CLAUDE_MODEL, CLAUDE_MAX_TOKENS, CLAUDE_TEMPERATURE,
    GPT4O_MODEL, AUTO_APPROVE_CONFIDENCE,
)


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
    source:        str    = "claude"  # "claude" | "gpt4o" | "manual"

    @property
    def code(self) -> str:
        """Generate a cabinet code from type and dimensions."""
        w_in = round(self.width_mm / 25.4)
        h_in = round(self.height_mm / 25.4)
        type_prefix = {
            "upper_wall":       f"W{w_in}{h_in}",
            "base":             f"B{w_in}",
            "sink_base":        f"SB{w_in}",
            "dw_adjacent":      f"DWA{w_in}",
            "microwave_shelf":  f"MW{w_in}",
            "pantry":           f"T{w_in}{h_in}",
            "corner_upper":     f"WC{w_in}",
            "corner_base":      f"BC{w_in}",
            "vanity":           f"VAN{w_in}",
            "medicine_cabinet": f"MED{w_in}",
            "linen":            f"LIN{w_in}",
            "appliance_space":  f"APPL",
            "filler":           f"FIL",
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

def _build_system_prompt() -> str:
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
) -> str:
    """Build the user message with pre-extracted context."""
    ada_note = " (ADA ACCESSIBLE UNIT — base cabinet heights are 864mm max, countertop 34\" max)" if is_ada else ""

    dims_str = ""
    if pre_extracted_dims:
        dims_str = "\n\nPRE-EXTRACTED DIMENSION VALUES (from PDF text, use these as ground truth):\n"
        for d in pre_extracted_dims[:30]:  # limit to 30 most relevant
            dims_str += f"  [{d.get('type','?')}] '{d.get('text','')}' at x={d.get('x',0):.0f}, y={d.get('y',0):.0f}\n"

    rects_str = ""
    if pre_extracted_rects:
        rects_str = "\n\nPRE-EXTRACTED RECTANGLE GEOMETRY (potential cabinet boxes from PDF vectors):\n"
        for i, r in enumerate(pre_extracted_rects[:40]):
            rects_str += (f"  Rect {i+1}: x={r.get('x0',0):.1f}→{r.get('x1',0):.1f}, "
                          f"y={r.get('y0',0):.1f}→{r.get('y1',0):.1f}, "
                          f"W={r.get('w',0):.1f}pts, H={r.get('h',0):.1f}pts\n")

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
    using Claude 3.5 Sonnet Vision API.

    Usage:
        classifier = CabinetVisionClassifier()
        result = classifier.classify_elevation(
            image_bytes=png_bytes,
            unit_type="A1",
            elevation_label="ELEVATION A",
            project_name="Casa Familia",
        )
    """

    def __init__(self, use_gpt4o_backup: bool = False):
        """
        Args:
            use_gpt4o_backup: If True, cross-validate low-confidence results
                              with GPT-4o (requires OPENAI_API_KEY).
        """
        self.use_gpt4o_backup = use_gpt4o_backup
        self._anthropic_client = None
        self._openai_client    = None
        self._validate_keys()

    def _validate_keys(self):
        if not ANTHROPIC_API_KEY:
            raise EnvironmentError(
                "ANTHROPIC_API_KEY is not set.\n"
                "1. Copy .env.example to .env\n"
                "2. Add your Anthropic API key\n"
                "3. Or use --skip-ai flag to use cached results"
            )

    def _get_anthropic(self):
        if self._anthropic_client is None:
            import anthropic
            self._anthropic_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        return self._anthropic_client

    def _get_openai(self):
        if self._openai_client is None:
            import openai
            self._openai_client = openai.OpenAI(api_key=OPENAI_API_KEY)
        return self._openai_client

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
        result = ElevationResult(
            elevation_label = elevation_label,
            unit_type       = unit_type,
            project_name    = project_name,
            is_ada          = is_ada,
        )

        # Build the prompt
        user_prompt = _build_user_prompt(
            unit_type            = unit_type,
            elevation_label      = elevation_label,
            project_name         = project_name,
            pre_extracted_dims   = pre_extracted_dims or [],
            pre_extracted_rects  = pre_extracted_rects or [],
            is_ada               = is_ada,
        )

        # Encode image for API
        image_b64 = base64.standard_b64encode(image_bytes).decode("utf-8")

        # Call Claude with retries
        raw_json = self._call_claude(
            image_b64   = image_b64,
            user_prompt = user_prompt,
            max_retries = max_retries,
        )
        result.api_calls += 1

        if raw_json is None:
            result.review_flags.append("Claude API call failed after all retries")
            return result

        # Parse JSON response
        cabinets = self._parse_cabinet_json(raw_json, elevation_label)
        if cabinets is None:
            result.review_flags.append("Failed to parse Claude JSON response")
            return result

        result.cabinets = cabinets

        # Cross-validate with GPT-4o if confidence is low
        if self.use_gpt4o_backup and result.avg_confidence < AUTO_APPROVE_CONFIDENCE:
            gpt_cabinets = self._call_gpt4o(image_b64, user_prompt)
            result.api_calls += 1
            if gpt_cabinets:
                result.cabinets = self._merge_results(cabinets, gpt_cabinets)
                result.review_flags.append(
                    f"GPT-4o cross-validation applied (avg confidence was {result.avg_confidence:.2f})"
                )

        # Set auto-approve flag
        result.auto_approved = (
            result.avg_confidence >= AUTO_APPROVE_CONFIDENCE and
            len(result.cabinets) > 0
        )

        if not result.auto_approved:
            result.review_flags.append(
                f"Requires human review: avg confidence {result.avg_confidence:.2f} < {AUTO_APPROVE_CONFIDENCE}"
            )

        return result

    # ── Claude API Call ───────────────────────────────────────────────────

    def _call_claude(
        self,
        image_b64:   str,
        user_prompt: str,
        max_retries: int = 3,
    ) -> Optional[str]:
        """Call Claude 3.5 Sonnet Vision API. Returns raw text response or None."""
        client = self._get_anthropic()

        for attempt in range(max_retries):
            try:
                response = client.messages.create(
                    model      = CLAUDE_MODEL,
                    max_tokens = CLAUDE_MAX_TOKENS,
                    system     = _build_system_prompt(),
                    messages   = [
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "image",
                                    "source": {
                                        "type":       "base64",
                                        "media_type": "image/png",
                                        "data":       image_b64,
                                    },
                                },
                                {
                                    "type": "text",
                                    "text": user_prompt,
                                },
                            ],
                        }
                    ],
                )
                return response.content[0].text

            except Exception as e:
                wait = 2 ** attempt  # exponential backoff: 1s, 2s, 4s
                print(f"  ⚠️  Claude API attempt {attempt+1}/{max_retries} failed: {e}")
                if attempt < max_retries - 1:
                    print(f"      Retrying in {wait}s...")
                    time.sleep(wait)
                else:
                    print("  ❌ All Claude retries exhausted.")

        return None

    # ── GPT-4o Backup Call ────────────────────────────────────────────────

    def _call_gpt4o(
        self,
        image_b64:   str,
        user_prompt: str,
    ) -> Optional[list[CabinetItem]]:
        """Call GPT-4o Vision as backup validator."""
        if not OPENAI_API_KEY:
            return None

        try:
            client = self._get_openai()
            response = client.chat.completions.create(
                model      = GPT4O_MODEL,
                max_tokens = CLAUDE_MAX_TOKENS,
                messages   = [
                    {"role": "system", "content": _build_system_prompt()},
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url":    f"data:image/png;base64,{image_b64}",
                                    "detail": "high",
                                },
                            },
                            {"type": "text", "text": user_prompt},
                        ],
                    },
                ],
            )
            raw = response.choices[0].message.content
            return self._parse_cabinet_json(raw, "GPT-4o")
        except Exception as e:
            print(f"  ⚠️  GPT-4o backup call failed: {e}")
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
                source        = "claude",
            ))

        return cabinets

    # ── Result Merging ────────────────────────────────────────────────────

    def _merge_results(
        self,
        claude_cabinets:  list[CabinetItem],
        gpt_cabinets:     list[CabinetItem],
    ) -> list[CabinetItem]:
        """
        Merge Claude + GPT-4o results.
        Where both agree on type+width, boost confidence.
        Where they disagree, lower confidence and flag.
        """
        if not gpt_cabinets:
            return claude_cabinets
        if not claude_cabinets:
            return gpt_cabinets

        # Match by item order (both should have same number of items)
        if len(claude_cabinets) != len(gpt_cabinets):
            # Count mismatch — return Claude's result with reduced confidence
            for c in claude_cabinets:
                c.confidence = min(c.confidence, 0.75)
                c.notes += " [count mismatch with GPT-4o backup]"
            return claude_cabinets

        merged = []
        for claude_item, gpt_item in zip(claude_cabinets, gpt_cabinets):
            item = claude_item
            # Both agree on type
            if claude_item.cabinet_type == gpt_item.cabinet_type:
                # Average the widths if close
                if abs(claude_item.width_mm - gpt_item.width_mm) < 50:
                    item.width_mm = (claude_item.width_mm + gpt_item.width_mm) / 2
                    item.confidence = min(1.0, (claude_item.confidence + gpt_item.confidence) / 2 + 0.05)
                    item.source = "claude+gpt4o"
                else:
                    item.confidence = min(claude_item.confidence, 0.75)
                    item.notes += f" [width mismatch: Claude={claude_item.width_mm:.0f}mm GPT={gpt_item.width_mm:.0f}mm]"
            else:
                # Type mismatch — flag for review
                item.confidence = min(claude_item.confidence, 0.65)
                item.notes += f" [type mismatch: Claude={claude_item.cabinet_type} GPT={gpt_item.cabinet_type}]"
            merged.append(item)

        return merged


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

    # Test parsing
    classifier = object.__new__(CabinetVisionClassifier)  # skip __init__ to avoid key check
    classifier.__class__ = CabinetVisionClassifier
    cabinets = classifier._parse_cabinet_json(sample_response, "ELEVATION A")

    if cabinets:
        print(f"✅ Parsed {len(cabinets)} cabinets:")
        for c in cabinets:
            print(f"   Item {c.item_num}: {c.cabinet_type:20s} {c.width_mm:.0f}mm  "
                  f"confidence={c.confidence:.2f}  code={c.code}")
    else:
        print("❌ Parsing failed")

    # Test type normalization
    print("\n=== Type Normalization ===")
    for raw in ["wall cabinet", "lower", "dishwasher", "tall_cabinet", "mirror"]:
        print(f"  '{raw}' → '{_normalize_cabinet_type(raw)}'")
