import json

with open('outputs/23-033/json/cabinet_schedule_A1.json', encoding='utf-8') as f:
    data = json.load(f)

print(f"UNIT: {data['unit_type']}  |  ADA: {data['is_ada']}  |  Auto-Approved: {data['auto_approved']}")
print()
total_cabs = 0
for ev in data['elevations']:
    cabs = [c for c in ev['cabinets'] if c['cabinet_type'] != 'appliance_space']
    print(f"  ELEVATION: {ev['elevation_label']}  (avg confidence: {ev['avg_confidence']:.0%})")
    for c in ev['cabinets']:
        w_mm = c['width_mm']
        w_in = round(w_mm / 25.4)
        marker = "[APPL]" if c['cabinet_type'] == 'appliance_space' else "      "
        note = c['notes'][:35] if c['notes'] else ""
        print(f"    {marker} {c['item_num']:2d}. {c['cabinet_type']:20s}  {w_mm:.0f}mm ({w_in}\")  conf={c['confidence']:.0%}  {note}")
    total_cabs += len(cabs)
    print()

print(f"  TOTAL CABINETS (excl. appliances): {total_cabs}")
print(f"  REVIEW FLAGS: {data.get('review_flags', [])}")
