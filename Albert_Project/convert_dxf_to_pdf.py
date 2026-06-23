#!/usr/bin/env python3
"""
===========================================================================
  convert_dxf_to_pdf.py — DXF to PDF sheet conversion utility
===========================================================================
  Converts AutoCAD DXF CAD drawing files into vector PDF sheets using
  ezdxf and matplotlib.

  Usage:
    python convert_dxf_to_pdf.py --input outputs/23-045/dxf/A-1.dxf --output outputs/23-045/A-1_dxf.pdf
    python convert_dxf_to_pdf.py --dir outputs/23-045/dxf/ --output-dir outputs/23-045/pdf_sheets/
===========================================================================
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

try:
    import ezdxf
    from ezdxf.addons.drawing import RenderContext, Frontend
    from ezdxf.addons.drawing.matplotlib import MatplotlibBackend
    import matplotlib.pyplot as plt
except ImportError as e:
    print(f"  [ERROR] Missing required dependencies for DXF rendering: {e}")
    print("  Please install them using: pip install ezdxf matplotlib")
    sys.exit(1)


def convert_file(dxf_path: str | Path, pdf_path: str | Path) -> bool:
    """Converts a single DXF file to PDF."""
    dxf_path = Path(dxf_path)
    pdf_path = Path(pdf_path)

    if not dxf_path.exists():
        print(f"  [ERROR] DXF file not found: {dxf_path}")
        return False

    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    print(f"  Rendering: {dxf_path.name} -> {pdf_path.name}...")

    try:
        doc = ezdxf.readfile(str(dxf_path))
        msp = doc.modelspace()
        
        from ezdxf.addons.drawing.properties import LayoutProperties
        
        # Set up a tabloid landscape sheet figure
        fig = plt.figure(figsize=(17, 11))
        ax = fig.add_axes([0, 0, 1, 1])
        ax.set_axis_off()
        
        ctx = RenderContext(doc)
        out = MatplotlibBackend(ax)
        
        # Force white background so colors adapt correctly (e.g. ACI 7 draws as black)
        layout_props = LayoutProperties.from_layout(msp)
        layout_props.set_colors(bg="#FFFFFF")
        
        Frontend(ctx, out).draw_layout(msp, finalize=True, layout_properties=layout_props)
        
        fig.savefig(str(pdf_path), dpi=300, bbox_inches='tight', pad_inches=0)
        plt.close(fig)
        print(f"  [SUCCESS] Rendered to PDF: {pdf_path}")
        return True
    except Exception as e:
        print(f"  [ERROR] Rendering failed for {dxf_path.name}: {e}")
        return False


def convert_directory(dxf_dir: str | Path, output_dir: str | Path):
    """Converts all DXF files inside a directory to PDF."""
    dxf_dir = Path(dxf_dir)
    output_dir = Path(output_dir)

    if not dxf_dir.exists() or not dxf_dir.is_dir():
        print(f"  [ERROR] DXF directory not found: {dxf_dir}")
        return

    dxf_files = list(dxf_dir.glob("*.dxf"))
    if not dxf_files:
        print(f"  [WARN] No .dxf files found in: {dxf_dir}")
        return

    output_dir.mkdir(parents=True, exist_ok=True)
    print(f"  Processing {len(dxf_files)} DXF files from: {dxf_dir.name}")

    success_count = 0
    for dxf_path in dxf_files:
        pdf_path = output_dir / f"{dxf_path.stem}_dxf.pdf"
        if convert_file(dxf_path, pdf_path):
            success_count += 1

    print(f"\n  [COMPLETE] Successfully converted {success_count}/{len(dxf_files)} DXF files to: {output_dir}")


def main():
    parser = argparse.ArgumentParser(description="AutoCAD DXF to PDF conversion utility")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--input", help="Path to single DXF file to convert")
    group.add_argument("--dir", help="Path to directory containing DXF files to convert")
    
    parser.add_argument("--output", help="Path to output PDF file (required for --input)")
    parser.add_argument("--output-dir", help="Path to output PDF directory (required for --dir)")

    args = parser.parse_args()

    if args.input:
        if not args.output:
            print("  [ERROR] --output is required when using --input")
            sys.exit(1)
        convert_file(args.input, args.output)
    elif args.dir:
        if not args.output_dir:
            # parser hyphens are converted to underscores in arg name
            pass
        out_dir = args.output_dir or str(Path(args.dir) / "pdf_sheets")
        convert_directory(args.dir, out_dir)


if __name__ == "__main__":
    main()
