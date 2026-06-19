"""Quick test: verify Groq API key and vision capability on real architectural drawing."""
import os, base64
from dotenv import load_dotenv
load_dotenv()

key = os.getenv("GROQ_API_KEY", "")
print(f"Key: {key[:10]}...{key[-4:]} ({len(key)} chars)")

try:
    from groq import Groq
    import fitz

    client = Groq(api_key=key)

    # Test 1: Text only
    print("\nTest 1: Text prompt...")
    r = client.chat.completions.create(
        model="meta-llama/llama-4-scout-17b-16e-instruct",
        messages=[{"role": "user", "content": "Reply with exactly: GROQ WORKING"}],
        max_tokens=20, temperature=0
    )
    print(f"  Response: {r.choices[0].message.content.strip()}")
    print("  [PASS] Text works!")

    # Test 2: Vision on Unit A1 kitchen elevation
    print("\nTest 2: Vision on Unit A1 kitchen elevation...")
    pdf = fitz.open(r"Casa familia\01_Architectural_Drawings\Unit_Plans_FHA_ADA\A-6.00-FHA-UNIT-A1-FLOOR-PLAN-&-DETAILS-Rev.10.pdf")
    page = pdf[0]
    # Kitchen elevation zone (bottom-right area of the sheet)
    rect = fitz.Rect(820, 720, 1280, 1180)
    mat = fitz.Matrix(3, 3)  # 3x zoom = ~216 DPI
    pix = page.get_pixmap(matrix=mat, clip=rect)
    img_bytes = pix.tobytes("png")
    pdf.close()
    img_b64 = base64.standard_b64encode(img_bytes).decode("utf-8")
    print(f"  Image: {len(img_bytes):,} bytes ({pix.width}x{pix.height}px)")

    r2 = client.chat.completions.create(
        model="meta-llama/llama-4-scout-17b-16e-instruct",
        messages=[{
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img_b64}"}},
                {"type": "text", "text": (
                    "This is a kitchen cabinet elevation drawing. "
                    "List what you see: cabinet types, widths/dimensions shown, and any appliance labels. "
                    "Be specific and brief."
                )}
            ]
        }],
        max_tokens=500, temperature=0.1
    )
    print(f"\n  Vision response:\n{r2.choices[0].message.content.strip()}")
    print("\n  [PASS] Groq Vision works! Ready to run the pipeline.")

except Exception as e:
    print(f"\n  [FAIL] {e}")
    import traceback; traceback.print_exc()
