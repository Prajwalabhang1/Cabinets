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

        # Create drawing
        doc = ezdxf.new('R2010')
        msp = doc.modelspace()

        # Add typical layers
        doc.layers.add('WALLS', color=7)
        doc.layers.add('CABINETS_BASE', color=7) # Black/White
        doc.layers.add('CABINETS_UPPER', color=7) # Black/White
        doc.layers.add('GROUND', color=8)
        doc.layers.add('CEILING', color=8)
        doc.layers.add('DIMENSIONS', color=8) # Gray/Pencil like
        doc.layers.add('TEXT', color=7)        # Calculate wall length in inches dynamically to position views correctly
        wall_length_in = 90.0
        if geometry["elevation"]["lines"]:
            max_x_geom = max(line["end"][0] for line in geometry["elevation"]["lines"])
            wall_length_in = (max_x_geom - 250.0) / 4.0
            
        ELEV_Y_OFFSET = 60.0
        SIDE_X_OFFSET = max(90.0, wall_length_in) + 30.0

        # Helper coordinate mapping functions (converting raw visual coordinates back to actual inches)
        def to_plan_inch(pt):
            return ((pt[0] - 250.0) / 4.0, (pt[1] - 450.0) / 4.0)

        def to_elev_inch(pt):
            return ((pt[0] - 250.0) / 4.0, (pt[1] - 150.0) / 3.0 + ELEV_Y_OFFSET)

        def to_side_inch(pt):
            return ((pt[0] - 250.0) / 4.0 + SIDE_X_OFFSET, (pt[1] - 150.0) / 3.0 + ELEV_Y_OFFSET)

        # 1. Write Plan Geometry to model space
        for line in geometry["plan"]["lines"]:
            layer = line.get("layer", "WALLS")
            msp.add_line(to_plan_inch(line["start"]), to_plan_inch(line["end"]), dxfattribs={'layer': layer})

        for block in geometry["plan"]["blocks"]:
            layer = block.get("layer", "CABINETS_BASE")
            x, y, w, h = block["coords"]
            x_in = (x - 250.0) / 4.0
            y_in = (y - 450.0) / 4.0
            w_in = w / 4.0
            h_in = h / 4.0
            msp.add_line((x_in, y_in), (x_in + w_in, y_in), dxfattribs={'layer': layer})
            msp.add_line((x_in + w_in, y_in), (x_in + w_in, y_in + h_in), dxfattribs={'layer': layer})
            msp.add_line((x_in + w_in, y_in + h_in), (x_in, y_in + h_in), dxfattribs={'layer': layer})
            msp.add_line((x_in, y_in + h_in), (x_in, y_in), dxfattribs={'layer': layer})

        for txt in geometry["plan"]["texts"]:
            layer = txt.get("layer", "TEXT")
            pos_in = to_plan_inch(txt["pos"])
            text_str = txt["text"].replace('\n', ' ')
            msp.add_text(text_str, dxfattribs={'layer': layer, 'height': 2.5}).set_placement(pos_in)

        for dim in geometry["plan"]["dimensions"]:
            layer = "DIMENSIONS"
            s_in = to_plan_inch(dim["start"])
            e_in = to_plan_inch(dim["end"])
            msp.add_line(s_in, e_in, dxfattribs={'layer': layer})
            text_pos = [(s_in[0] + e_in[0])/2, (s_in[1] + e_in[1])/2 + 2.0]
            msp.add_text(dim["text"], dxfattribs={'layer': layer, 'height': 2.0}).set_placement(text_pos)

        # 2. Write Elevation Geometry
        for line in geometry["elevation"]["lines"]:
            layer = line.get("layer", "WALLS")
            msp.add_line(to_elev_inch(line["start"]), to_elev_inch(line["end"]), dxfattribs={'layer': layer})

        for block in geometry["elevation"]["blocks"]:
            layer = block.get("layer", "CABINETS_BASE")
            x, y, w, h = block["coords"]
            x_in = (x - 250.0) / 4.0
            y_in = (y - 150.0) / 3.0 + ELEV_Y_OFFSET
            w_in = w / 4.0
            h_in = h / 3.0
            msp.add_line((x_in, y_in), (x_in + w_in, y_in), dxfattribs={'layer': layer})
            msp.add_line((x_in + w_in, y_in), (x_in + w_in, y_in + h_in), dxfattribs={'layer': layer})
            msp.add_line((x_in + w_in, y_in + h_in), (x_in, y_in + h_in), dxfattribs={'layer': layer})
            msp.add_line((x_in, y_in + h_in), (x_in, y_in), dxfattribs={'layer': layer})

        for txt in geometry["elevation"]["texts"]:
            layer = txt.get("layer", "TEXT")
            pos_in = to_elev_inch(txt["pos"])
            text_str = txt["text"].replace('\n', ' ')
            msp.add_text(text_str, dxfattribs={'layer': layer, 'height': 2.5}).set_placement(pos_in)

        for dim in geometry["elevation"]["dimensions"]:
            layer = "DIMENSIONS"
            s_in = to_elev_inch(dim["start"])
            e_in = to_elev_inch(dim["end"])
            msp.add_line(s_in, e_in, dxfattribs={'layer': layer})
            text_pos = [(s_in[0] + e_in[0])/2, (s_in[1] + e_in[1])/2 + 2.0]
            msp.add_text(dim["text"], dxfattribs={'layer': layer, 'height': 2.0}).set_placement(text_pos)

        # 3. Write Side Section Geometry
        for line in geometry.get("side", {}).get("lines", []):
            layer = line.get("layer", "WALLS")
            msp.add_line(to_side_inch(line["start"]), to_side_inch(line["end"]), dxfattribs={'layer': layer})
            
        for block in geometry.get("side", {}).get("blocks", []):
            layer = block.get("layer", "CABINETS_BASE")
            x, y, w, h = block["coords"]
            x_in = (x - 250.0) / 4.0 + SIDE_X_OFFSET
            y_in = (y - 150.0) / 3.0 + ELEV_Y_OFFSET
            w_in = w / 4.0
            h_in = h / 3.0
            msp.add_line((x_in, y_in), (x_in + w_in, y_in), dxfattribs={'layer': layer})
            msp.add_line((x_in + w_in, y_in), (x_in + w_in, y_in + h_in), dxfattribs={'layer': layer})
            msp.add_line((x_in + w_in, y_in + h_in), (x_in, y_in + h_in), dxfattribs={'layer': layer})
            msp.add_line((x_in, y_in + h_in), (x_in, y_in), dxfattribs={'layer': layer})
            
        for txt in geometry.get("side", {}).get("texts", []):
            layer = txt.get("layer", "TEXT")
            pos_in = to_side_inch(txt["pos"])
            text_str = txt["text"].replace('\n', ' ')
            msp.add_text(text_str, dxfattribs={'layer': layer, 'height': 2.5}).set_placement(pos_in)

        for dim in geometry.get("side", {}).get("dimensions", []):
            layer = "DIMENSIONS"
            s_in = to_side_inch(dim["start"])
            e_in = to_side_inch(dim["end"])
            msp.add_line(s_in, e_in, dxfattribs={'layer': layer})
            text_pos = [(s_in[0] + e_in[0])/2, (s_in[1] + e_in[1])/2 + 2.0]
            msp.add_text(dim["text"], dxfattribs={'layer': layer, 'height': 2.0}).set_placement(text_pos)

        # 4. Add view labels to DXF model space
        msp.add_text("COUNTERTOP PLAN VIEW", dxfattribs={'layer': 'TEXT', 'height': 3.5}).set_placement((wall_length_in / 2, -40.0))
        msp.add_text("FRONT ELEVATION VIEW", dxfattribs={'layer': 'TEXT', 'height': 3.5}).set_placement((wall_length_in / 2, ELEV_Y_OFFSET - 15.0))
        msp.add_text("SIDE SECTION VIEW", dxfattribs={'layer': 'TEXT', 'height': 3.5}).set_placement((SIDE_X_OFFSET + 15.0, ELEV_Y_OFFSET - 15.0))

        # Save file
        doc.saveas(str(output_path))
        print(f"  [SUCCESS] DXF drawing saved: {output_path}")
        return output_path
