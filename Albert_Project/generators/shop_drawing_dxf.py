"""
===========================================================================
  generators/shop_drawing_dxf.py — AutoCAD DXF Generator
===========================================================================
  Translates coordinate lines, annotations, and boxes into AutoCAD-compatible
  dxf files using ezdxf.
===========================================================================
"""
from __future__ import annotations

import os
from pathlib import Path
import ezdxf
try:
    from ezdxf.addons.drawing.matplotlib import qsave
except ImportError:
    qsave = None

class DXFDrawingGenerator:
    """
    Generates dxf CAD vector files for units and elevations.
    """

    def __init__(self):
        pass

    def generate(self, geometry: dict, output_path: str | Path):
        """
        Generates plan and elevation views and saves to a dxf file.
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Create drawing with standard styles
        doc = ezdxf.new('R2010', setup=True)
        msp = doc.modelspace()

        # Add typical layers
        doc.layers.add('WALLS', color=7) # White/Black
        doc.layers.add('WALLS_HIDDEN', color=8)
        doc.layers.add('WALLS_DEMO', color=1) # Red
        doc.layers.add('WALLS_SECTION', color=7)
        doc.layers.add('CENTERLINES', color=3) # Green
        doc.layers.add('CABINETS_BASE', color=4) # Cyan
        doc.layers.add('CABINETS_UPPER', color=2) # Yellow
        doc.layers.add('CABINETS_SECTION', color=4)
        doc.layers.add('COUNTERTOP_SECTION', color=6) # Magenta
        doc.layers.add('SOFFIT', color=8)
        doc.layers.add('SOFFIT_SECTION', color=8)
        doc.layers.add('BACKSPLASH_SECTION', color=5) # Blue
        doc.layers.add('MOLDING_SECTION', color=6)
        doc.layers.add('APPLIANCES', color=7)
        doc.layers.add('SINK', color=8)
        doc.layers.add('HANDLES', color=7)
        doc.layers.add('SWING', color=8)
        doc.layers.add('GROUND', color=8)
        doc.layers.add('CEILING', color=8)
        doc.layers.add('DIMENSIONS', color=8)
        doc.layers.add('TEXT', color=7)
        doc.layers.add('ANNOTATION', color=2)
        doc.layers.add('ANNOTATION_TEXT', color=7)
        doc.layers.add('REVISIONS', color=1) # Red for revisions
        doc.layers.add('TITLEBLOCK', color=7)
        wall_length_in = 90.0
        if geometry["elevation"]["lines"]:
            max_x_geom = max(line["end"][0] for line in geometry["elevation"]["lines"])
            wall_length_in = max_x_geom
            
        ELEV_Y_OFFSET = 60.0
        SIDE_X_OFFSET = max(90.0, wall_length_in) + 30.0

        # Helper coordinate mapping functions (converting raw visual coordinates back to actual inches)
        def to_plan_inch(pt):
            return (pt[0], pt[1])

        def to_elev_inch(pt):
            return (pt[0], pt[1] + ELEV_Y_OFFSET)

        def to_side_inch(pt):
            return (pt[0] + SIDE_X_OFFSET, pt[1] + ELEV_Y_OFFSET)

        # 1. Write Plan Geometry to model space
        for line in geometry["plan"]["lines"]:
            layer = line.get("layer", "WALLS")
            ltype = "DASHED" if line.get("style") == "dashed" else "CONTINUOUS"
            msp.add_line(to_plan_inch(line["start"]), to_plan_inch(line["end"]), dxfattribs={'layer': layer, 'linetype': ltype})

        for block in geometry["plan"]["blocks"]:
            layer = block.get("layer", "CABINETS_BASE")
            ltype = "DASHED" if block.get("style") == "dashed" else "CONTINUOUS"
            x, y, w, h = block["coords"]
            if block.get("type") == "circle":
                msp.add_circle(to_plan_inch((x, y)), w, dxfattribs={'layer': layer})
            else:
                x_in = x
                y_in = y
                w_in = w
                h_in = h
                msp.add_line((x_in, y_in), (x_in + w_in, y_in), dxfattribs={'layer': layer, 'linetype': ltype})
                msp.add_line((x_in + w_in, y_in), (x_in + w_in, y_in + h_in), dxfattribs={'layer': layer, 'linetype': ltype})
                msp.add_line((x_in + w_in, y_in + h_in), (x_in, y_in + h_in), dxfattribs={'layer': layer, 'linetype': ltype})
                msp.add_line((x_in, y_in + h_in), (x_in, y_in), dxfattribs={'layer': layer, 'linetype': ltype})

        for txt in geometry["plan"]["texts"]:
            layer = txt.get("layer", "TEXT")
            pos_in = to_plan_inch(txt["pos"])
            text_str = txt["text"]
            msp.add_mtext(text_str, dxfattribs={'layer': layer, 'char_height': 2.5}).set_location(pos_in)

        for dim in geometry["plan"]["dimensions"]:
            layer = "DIMENSIONS"
            s_in = to_plan_inch(dim["start"])
            e_in = to_plan_inch(dim["end"])
            
            dim_entity = msp.add_linear_dim(
                base=s_in, 
                p1=s_in, 
                p2=e_in, 
                dimstyle='EZDXF', 
                override={'dimtxsty': 'Standard', 'dimtxt': 2.0},
                text=dim["text"],
                dxfattribs={'layer': layer}
            )
            dim_entity.render()

        # 2. Write Elevation Geometry
        for line in geometry["elevation"]["lines"]:
            layer = line.get("layer", "WALLS")
            ltype = "DASHED" if line.get("style") == "dashed" else "CONTINUOUS"
            msp.add_line(to_elev_inch(line["start"]), to_elev_inch(line["end"]), dxfattribs={'layer': layer, 'linetype': ltype})

        for block in geometry["elevation"]["blocks"]:
            layer = block.get("layer", "CABINETS_BASE")
            ltype = "DASHED" if block.get("style") == "dashed" else "CONTINUOUS"
            x, y, w, h = block["coords"]
            if block.get("type") == "circle":
                msp.add_circle((x, y + ELEV_Y_OFFSET), w, dxfattribs={'layer': layer})
            else:
                x_in = x
                y_in = y + ELEV_Y_OFFSET
                w_in = w
                h_in = h
                msp.add_line((x_in, y_in), (x_in + w_in, y_in), dxfattribs={'layer': layer, 'linetype': ltype})
                msp.add_line((x_in + w_in, y_in), (x_in + w_in, y_in + h_in), dxfattribs={'layer': layer, 'linetype': ltype})
                msp.add_line((x_in + w_in, y_in + h_in), (x_in, y_in + h_in), dxfattribs={'layer': layer, 'linetype': ltype})
                msp.add_line((x_in, y_in + h_in), (x_in, y_in), dxfattribs={'layer': layer, 'linetype': ltype})

        for txt in geometry["elevation"]["texts"]:
            layer = txt.get("layer", "TEXT")
            pos_in = to_elev_inch(txt["pos"])
            text_str = txt["text"]
            msp.add_mtext(text_str, dxfattribs={'layer': layer, 'char_height': 2.5}).set_location(pos_in)

        for dim in geometry["elevation"]["dimensions"]:
            layer = "DIMENSIONS"
            s_in = to_elev_inch(dim["start"])
            e_in = to_elev_inch(dim["end"])
            
            # Use angled dimension if vertical
            angle = 90 if abs(s_in[0] - e_in[0]) < 0.1 else 0
            
            dim_entity = msp.add_linear_dim(
                base=s_in, 
                p1=s_in, 
                p2=e_in, 
                angle=angle,
                dimstyle='EZDXF', 
                override={'dimtxsty': 'Standard', 'dimtxt': 2.0},
                text=dim["text"],
                dxfattribs={'layer': layer}
            )
            dim_entity.render()

        # 3. Write Side Section Geometry
        for line in geometry.get("side", {}).get("lines", []):
            layer = line.get("layer", "WALLS")
            ltype = "DASHED" if line.get("style") == "dashed" else "CONTINUOUS"
            msp.add_line(to_side_inch(line["start"]), to_side_inch(line["end"]), dxfattribs={'layer': layer, 'linetype': ltype})
            
        for block in geometry.get("side", {}).get("blocks", []):
            layer = block.get("layer", "CABINETS_BASE")
            ltype = "DASHED" if block.get("style") == "dashed" else "CONTINUOUS"
            x, y, w, h = block["coords"]
            x_in = (x - 250.0) / 4.0 + SIDE_X_OFFSET
            y_in = (y - 150.0) / 3.0 + ELEV_Y_OFFSET
            w_in = w / 4.0
            h_in = h / 3.0
            msp.add_line((x_in, y_in), (x_in + w_in, y_in), dxfattribs={'layer': layer, 'linetype': ltype})
            msp.add_line((x_in + w_in, y_in), (x_in + w_in, y_in + h_in), dxfattribs={'layer': layer, 'linetype': ltype})
            msp.add_line((x_in + w_in, y_in + h_in), (x_in, y_in + h_in), dxfattribs={'layer': layer, 'linetype': ltype})
            msp.add_line((x_in, y_in + h_in), (x_in, y_in), dxfattribs={'layer': layer, 'linetype': ltype})
            
        for txt in geometry.get("side", {}).get("texts", []):
            layer = txt.get("layer", "TEXT")
            pos_in = to_side_inch(txt["pos"])
            text_str = txt["text"].replace('\n', ' ')
            msp.add_text(text_str, dxfattribs={'layer': layer, 'height': 2.5}).set_placement(pos_in)

        for dim in geometry.get("side", {}).get("dimensions", []):
            layer = "DIMENSIONS"
            s_in = to_side_inch(dim["start"])
            e_in = to_side_inch(dim["end"])
            
            # Use angled dimension if vertical
            angle = 90 if abs(s_in[0] - e_in[0]) < 0.1 else 0
            
            dim_entity = msp.add_linear_dim(
                base=s_in, 
                p1=s_in, 
                p2=e_in, 
                angle=angle,
                dimstyle='EZDXF', 
                override={'dimtxsty': 'Standard', 'dimtxt': 2.0},
                text=dim["text"],
                dxfattribs={'layer': layer}
            )
            dim_entity.render()

        # 4. Add view labels to DXF model space
        # (Labels are now generated dynamically by the geometry engines for each wall)

        # Save file
        doc.saveas(str(output_path))
        print(f"  [SUCCESS] DXF drawing saved: {output_path}")
        
        # Also save to PDF if matplotlib is available
        
        if qsave:
            from ezdxf.addons.drawing.config import Configuration, BackgroundPolicy, ColorPolicy
            # We want a white background and monochrome black lines for printing
            config = Configuration(
                background_policy=BackgroundPolicy.WHITE,
                color_policy=ColorPolicy.BLACK
            )
            pdf_path = str(output_path).replace('.dxf', '.pdf')
            try:
                # Specify high resolution and white background
                qsave(doc.modelspace(), pdf_path, bg='#FFFFFF', config=config, dpi=300)
                print(f"  [SUCCESS] DXF-based PDF drawing saved: {pdf_path}")
            except Exception as e:
                print(f"  [WARN] Failed to export DXF to PDF: {e}")
        return output_path
