"""Quick test: verify Gemini API key works and can read an image."""
import os
from dotenv import load_dotenv
load_dotenv()

key = os.getenv("GEMINI_API_KEY", "")
print(f"Key loaded: {key[:10]}...{key[-4:]} ({len(key)} chars)")

try:
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=key)

    # Test 1: Simple text prompt
    print("\nTest 1: Simple text prompt...")
    response = client.models.generate_content(
        model="gemini-2.0-flash",
        contents=["Say: GEMINI API WORKING - 1 sentence only"]
    )
    print(f"  Response: {response.text.strip()}")
    print("  [PASS] Text generation works!")

    # Test 2: Image vision — use one of our cropped elevation images
    import fitz
    from pathlib import Path

    pdf_path = r"Casa familia\01_Architectural_Drawings\Unit_Plans_FHA_ADA\A-6.00-FHA-UNIT-A1-FLOOR-PLAN-&-DETAILS-Rev.10.pdf"
    print(f"\nTest 2: Vision on Unit A1 PDF...")
    pdf = fitz.open(pdf_path)
    page = pdf[0]
    # Crop the kitchen elevation area (right half, lower half of page)
    rect = fitz.Rect(800, 700, 1300, 1200)
    mat = fitz.Matrix(2, 2)
    pix = page.get_pixmap(matrix=mat, clip=rect)
    img_bytes = pix.tobytes("png")
    pdf.close()
    print(f"  Cropped image: {len(img_bytes):,} bytes")

    response2 = client.models.generate_content(
        model="gemini-2.0-flash",
        contents=[
            types.Part.from_bytes(data=img_bytes, mime_type="image/png"),
            "What do you see in this architectural drawing? List any cabinet labels, dimensions, or kitchen elements visible. Be brief."
        ],
        config=types.GenerateContentConfig(max_output_tokens=500, temperature=0.1)
    )
    print(f"\n  Vision response:\n{response2.text.strip()}")
    print("\n  [PASS] Vision API works! Gemini can read the architectural drawings.")

except Exception as e:
    print(f"\n  [FAIL] Error: {e}")
    import traceback
    traceback.print_exc()
