def _draw_unit_pages(c, config: dict, unit_type: str, schedule,
                    start_page_num: int, total_pages: int) -> int:
    """Draw three pages for a unit type: Plan, Elevation, Schedule."""
    is_ada = "ACC" in unit_type or "ADA" in unit_type
    page_num = start_page_num

    # If no schedule, just print empty message
    if not schedule:
        _draw_page_border(c)
        _draw_title_block(c, config, page_num, total_pages, f"UNIT {unit_type}")
        c.setFillColor(colors.black)
        c.setFont(_FONT_REG, 8)
        c.drawString(DA_L + 20, DA_T - 28, "No AI schedule available — PDF not processed")
        return page_num

    from core.geometry_engine import GeometryEngine
    
    # Build walls for GeometryEngine
    walls_info = []
    for ev in schedule.elevations:
        cabs_list = []
        base_x = 0
        for cab in ev.cabinets:
            w_in = round(cab.width_in) if hasattr(cab, 'width_in') else 24
            h_in = round(cab.height_in) if hasattr(cab, 'height_in') else 34.5
            d_in = round(cab.depth_in) if getattr(cab, 'depth_in', None) else 0
            cabs_list.append({
                "id": cab.cabinet_id or cab.code,
                "x": base_x,
                "width": w_in,
                "height": h_in,
                "depth": d_in,
                "cabinet_type": cab.cabinet_type,
                "is_ada": cab.is_ada if hasattr(cab, 'is_ada') else False,
                "location": cab.location if hasattr(cab, 'location') else "",
                "notes": cab.notes if hasattr(cab, 'notes') else ""
            })
            base_x += w_in
        if cabs_list:
            walls_info.append({"length": sum(c["width"] for c in cabs_list), "cabinets": cabs_list})
            
    if not walls_info:
        walls_info = [{"length": 90.0, "cabinets": []}]

    geom_engine = GeometryEngine()
    geom_data = geom_engine.generate_layout_geometry(
        walls=walls_info,
        appliances=[],
        ceiling_height=108.0,
        soffit_height=96.0
    )
    
    visual_width_allowed = 1000.0
    total_length_inches = sum(w.get("length", 90.0) for w in walls_info) + (len(walls_info) - 1) * 25.0
    wall_length_inches = total_length_inches
    
    # Base scale: 1.0 (GeometryEngine already scales by 4.0)
    draw_scale = 1.0
    if wall_length_inches * 4.0 > visual_width_allowed:
        draw_scale = visual_width_allowed / (wall_length_inches * 4.0)
        
    GE_PLAN_OX, GE_PLAN_OY = 0.0, 0.0
    GE_ELEV_OX, GE_ELEV_OY = 0.0, 0.0
    GE_SIDE_OX, GE_SIDE_OY = 0.0, 0.0

    PDF_PLAN_OX = 50.0
    PDF_PLAN_OY = PAGE_H / 2 - 200.0 # Bottom of the page
    
    PDF_ELEV_OX = 50.0
    PDF_ELEV_OY = PAGE_H / 2 + 100.0 # Top of the page

    PDF_SIDE_OX = 600.0
    PDF_SIDE_OY = PAGE_H / 2 + 100.0 # Top right

    # ---------------------------------------------------------
    # PAGE 1: PLAN, ELEVATION, & SECTION
    # ---------------------------------------------------------
    _draw_page_border(c)
    _draw_title_block(c, config, page_num, total_pages, f"UNIT {unit_type} - LAYOUTS")
    c.setFillColor(NAVY)
    c.setFont(_FONT_BOLD, 12)
    c.drawString(DA_L + 4, DA_T - 18, f"UNIT {unit_type} — SHOP DRAWING")

    # Draw Plan View
    for line in geom_data.get("plan", {}).get("lines", []):
        x0 = (line["start"][0] - GE_PLAN_OX) * draw_scale + PDF_PLAN_OX
        y0 = (line["start"][1] - GE_PLAN_OY) * draw_scale + PDF_PLAN_OY
        x1 = (line["end"][0] - GE_PLAN_OX) * draw_scale + PDF_PLAN_OX
        y1 = (line["end"][1] - GE_PLAN_OY) * draw_scale + PDF_PLAN_OY
        c.saveState()
        c.setStrokeColor(NAVY if line.get("layer") == "WALLS" else colors.black)
        c.setLineWidth(1.5 if line.get("layer") == "WALLS" else 0.5)
        if line.get("style") == "dashed":
            c.setDash([2, 2])
        c.line(x0, y0, x1, y1)
        c.restoreState()
        
    for block in geom_data.get("plan", {}).get("blocks", []):
        if block.get("type") == "circle":
            x, y, r = block["coords"]
            c.saveState()
            c.setStrokeColor(colors.black)
            c.setFillColor(colors.white)
            c.circle((x - GE_PLAN_OX) * draw_scale + PDF_PLAN_OX, (y - GE_PLAN_OY) * draw_scale + PDF_PLAN_OY, r * draw_scale, fill=1, stroke=1)
            c.restoreState()
            continue
            
        x, y, w, h = block["coords"]
        x_new = (x - GE_PLAN_OX) * draw_scale + PDF_PLAN_OX
        y_new = (y - GE_PLAN_OY) * draw_scale + PDF_PLAN_OY
        w_new = w * draw_scale
        h_new = h * draw_scale
        c.saveState()
        c.setStrokeColor(colors.black)
        c.setFillColor(colors.white)
        if block.get("style") == "dashed":
            c.setDash([2, 2])
        c.rect(x_new, y_new, w_new, h_new, fill=1, stroke=1)
        c.restoreState()
        
    for txt in geom_data.get("plan", {}).get("texts", []):
        pos_x = (txt["pos"][0] - GE_PLAN_OX) * draw_scale + PDF_PLAN_OX
        pos_y = (txt["pos"][1] - GE_PLAN_OY) * draw_scale + PDF_PLAN_OY
        text_str = txt["text"]
        c.saveState()
        c.setFont(_FONT_REG, max(4.0, txt.get("size", 5.0) * draw_scale))
        c.setFillColor(colors.black)
        lines = text_str.split('\n')
        for i, line_text in enumerate(lines):
            c.drawCentredString(pos_x, pos_y - i * (max(4.0, txt.get("size", 5.0) * draw_scale) + 1), line_text)
        c.restoreState()
        
    for dim in geom_data.get("plan", {}).get("dimensions", []):
        x0 = (dim["start"][0] - GE_PLAN_OX) * draw_scale + PDF_PLAN_OX
        y0 = (dim["start"][1] - GE_PLAN_OY) * draw_scale + PDF_PLAN_OY
        x1 = (dim["end"][0] - GE_PLAN_OX) * draw_scale + PDF_PLAN_OX
        y1 = (dim["end"][1] - GE_PLAN_OY) * draw_scale + PDF_PLAN_OY
        draw_dimension_line(c, x0, y0, x1, y1, dim["text"])
        
    c.setFont(_FONT_BOLD, 14)
    c.setFillColor(colors.black)
    c.drawString(PDF_PLAN_OX, PDF_PLAN_OY - 100, f"FLOOR PLAN")
    c.setFont(_FONT_REG, 10)
    c.drawString(PDF_PLAN_OX + 100, PDF_PLAN_OY - 100, "SCALE 1/2 INCH = 1 FOOT")
    c.line(PDF_PLAN_OX, PDF_PLAN_OY - 103, PDF_PLAN_OX + 200, PDF_PLAN_OY - 103)
    c.setFont(_FONT_REG, 8)
    c.drawString(PDF_PLAN_OX, PDF_PLAN_OY - 115, f"{config.get('project_name', '')} UNIT {unit_type}")

    # --- ELEVATIONS ---

    # Draw Elevation View
    for line in geom_data.get("elevation", {}).get("lines", []):
        x0 = (line["start"][0] - GE_ELEV_OX) * draw_scale + PDF_ELEV_OX
        y0 = (line["start"][1] - GE_ELEV_OY) * draw_scale + PDF_ELEV_OY
        x1 = (line["end"][0] - GE_ELEV_OX) * draw_scale + PDF_ELEV_OX
        y1 = (line["end"][1] - GE_ELEV_OY) * draw_scale + PDF_ELEV_OY
        c.saveState()
        c.setStrokeColor(NAVY if line.get("layer") in ("GROUND", "CEILING") else colors.black)
        c.setLineWidth(1.0 if line.get("layer") in ("GROUND", "CEILING") else 0.5)
        if line.get("style") == "dashed":
            c.setDash([2, 2])
        c.line(x0, y0, x1, y1)
        c.restoreState()
        
    for block in geom_data.get("elevation", {}).get("blocks", []):
        if block.get("type") == "circle":
            x, y, r = block["coords"]
            c.saveState()
            c.setStrokeColor(colors.black)
            c.setFillColor(colors.white)
            c.circle((x - GE_ELEV_OX) * draw_scale + PDF_ELEV_OX, (y - GE_ELEV_OY) * draw_scale + PDF_ELEV_OY, r * draw_scale, fill=1, stroke=1)
            c.restoreState()
            continue
            
        x, y, w, h = block["coords"]
        x_new = (x - GE_ELEV_OX) * draw_scale + PDF_ELEV_OX
        y_new = (y - GE_ELEV_OY) * draw_scale + PDF_ELEV_OY
        w_new = w * draw_scale
        h_new = h * draw_scale
        c.saveState()
        c.setStrokeColor(colors.black)
        c.setFillColor(colors.white)
        if block.get("style") == "dashed":
            c.setDash([2, 2])
        c.rect(x_new, y_new, w_new, h_new, fill=1, stroke=1)
        c.restoreState()
        
    for txt in geom_data.get("elevation", {}).get("texts", []):
        pos_x = (txt["pos"][0] - GE_ELEV_OX) * draw_scale + PDF_ELEV_OX
        pos_y = (txt["pos"][1] - GE_ELEV_OY) * draw_scale + PDF_ELEV_OY
        text_str = txt["text"]
        c.saveState()
        c.setFont(_FONT_REG, max(4.0, txt.get("size", 5.0) * draw_scale))
        c.setFillColor(colors.black)
        lines = text_str.split('\n')
        for i, line_text in enumerate(lines):
            c.drawCentredString(pos_x, pos_y - i * (max(4.0, txt.get("size", 5.0) * draw_scale) + 1), line_text)
        c.restoreState()
        
    for dim in geom_data.get("elevation", {}).get("dimensions", []):
        x0 = (dim["start"][0] - GE_ELEV_OX) * draw_scale + PDF_ELEV_OX
        y0 = (dim["start"][1] - GE_ELEV_OY) * draw_scale + PDF_ELEV_OY
        x1 = (dim["end"][0] - GE_ELEV_OX) * draw_scale + PDF_ELEV_OX
        y1 = (dim["end"][1] - GE_ELEV_OY) * draw_scale + PDF_ELEV_OY
        draw_dimension_line(c, x0, y0, x1, y1, dim["text"])
        
    c.setFont(_FONT_BOLD, 14)
    c.setFillColor(colors.black)
    c.drawString(PDF_ELEV_OX, PDF_ELEV_OY - 100, f"ELEVATION")
    # (Side section geometry is empty in GeometryEngine, so we don't draw the hardcoded text anymore)
    
    c.showPage()
    page_num += 1

    # ---------------------------------------------------------
    # PAGE 3: SCHEDULE
    # ---------------------------------------------------------
    _draw_page_border(c)
    _draw_title_block(c, config, page_num, total_pages, f"UNIT {unit_type} SCHEDULE")

    # Page header for the schedule
    c.setFillColor(NAVY)
    c.setFont(_FONT_BOLD, 12)
    c.drawString(DA_L + 4, DA_T - 18, f"UNIT {unit_type} — CABINET SCHEDULE")
    
    c.setFont(_FONT_REG, 8)
    c.setFillColor(colors.black)
    labels = [
        ("PROJECT:", config.get("project_name", "")),
        ("ADDRESS:", config.get("address", "")),
        ("FINISH:", f"Standard {config.get('finish_tier', 1)}"),
        ("ADA:", "YES (Fully Accessible)" if is_ada else "NO (FHA Type B)"),
    ]
    y = DA_T - 40
    for label, val in labels:
        c.setFont(_FONT_BOLD, 7)
        c.drawString(50.0, y, label)
        c.setFont(_FONT_REG, 7)
        c.drawString(110.0, y, val)
        y -= 10

    col_widths = [25, 60, 180, 70, 40, 40, 40, 30, 60, 110]
    headers    = ["#", "Code", "Description", "Type",
                  "W(in)", "H(in)", "D(in)", "Qty", "Elev.", "Location"]
    table_x = 50.0
    table_y = y - 8

    # Header row
    c.setFillColor(LTGRAY)
    c.rect(table_x, table_y, sum(col_widths), 12, fill=1, stroke=1)
    
    c.setFillColor(colors.black)
    c.setFont(_FONT_BOLD, 6)
    cx = table_x
    for i, hw in enumerate(col_widths):
        c.drawString(cx + 4, table_y + 4, headers[i])
        cx += hw

    # Rows
    y = table_y - 12
    c.setFont(_FONT_REG, 6)
    
    idx = 1
    for ev in schedule.elevations:
        for cab in ev.cabinets:
            cx = table_x
            
            # #
            c.drawString(cx + 4, y + 4, str(idx))
            cx += col_widths[0]
            
            # Code
            c.drawString(cx + 4, y + 4, str(cab.cabinet_id))
            cx += col_widths[1]
            
            # Description
            notes_str = getattr(cab, 'notes', '') or ''
            desc = notes_str[:40] + "..." if len(notes_str) > 40 else notes_str
            c.drawString(cx + 4, y + 4, desc)
            cx += col_widths[2]
            
            # Type
            c.drawString(cx + 4, y + 4, str(cab.cabinet_type))
            cx += col_widths[3]
            
            # W, H, D
            w_in = round(cab.width_in, 1) if hasattr(cab, 'width_in') else "-"
            h_in = round(cab.height_in, 1) if hasattr(cab, 'height_in') else "-"
            d_in = round(cab.depth_in, 1) if hasattr(cab, 'depth_in') else "-"
            c.drawString(cx + 4, y + 4, str(w_in))
            cx += col_widths[4]
            c.drawString(cx + 4, y + 4, str(h_in))
            cx += col_widths[5]
            c.drawString(cx + 4, y + 4, str(d_in))
            cx += col_widths[6]
            
            # Qty
            c.drawString(cx + 4, y + 4, str(cab.quantity))
            cx += col_widths[7]
            
            # Elev
            c.drawString(cx + 4, y + 4, str(getattr(ev, 'elevation_label', '')))
            cx += col_widths[8]
            
            # Location
            c.drawString(cx + 4, y + 4, str(cab.location))
            
            y -= 12
            idx += 1
            
            # Pagination
            if y < DA_B + 20:
                c.showPage()
                _draw_page_border(c)
                _draw_title_block(c, config, page_num, total_pages, f"UNIT {unit_type} SCHEDULE (CONT)")
                page_num += 1
                y = DA_T - 30

    return page_num
