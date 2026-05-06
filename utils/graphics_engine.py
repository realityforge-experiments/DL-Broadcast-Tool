import os
import math
from PIL import Image, ImageDraw, ImageFont

# --- PATHING ---
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSETS_DIR = os.path.join(BASE_DIR, "assets")
EXPORT_DIR = os.path.join(BASE_DIR, "..", "stats", "obs_exports")

# Hex to RGB conversion
COLOR_BLUE = (13, 134, 244) # #0d86f4
COLOR_RED = (244, 13, 53)   # #f40d35

SPOTLIGHT_PATH = os.path.join(EXPORT_DIR, "spotlight_card.png")
TAPE_PATH = os.path.join(EXPORT_DIR, "tale_of_the_tape.png")
DNA_PATH = os.path.join(EXPORT_DIR, "team_dna.png")
WIN_PATH = os.path.join(EXPORT_DIR, "win_probability.png")

def get_font(size):
    try: return ImageFont.truetype("arialbd.ttf", size)
    except: 
        try: return ImageFont.truetype("arial.ttf", size)
        except: return ImageFont.load_default()

def load_bg(screen_name):
    width, height = 3840, 2160
    paths = [os.path.join(ASSETS_DIR, f"{screen_name}_bg.png"), os.path.join(ASSETS_DIR, "background.png")]
    for p in paths:
        if os.path.exists(p): return Image.open(p).resize((width, height))
    return Image.new('RGB', (width, height), color=(10, 10, 15))

def draw_radar_chart(draw, center, radius, params, color):
    points = []
    for i, (label, value) in enumerate(params):
        angle = (i * 2 * math.pi / 5) - (math.pi / 2)
        dist = (max(5, value) / 100) * radius
        points.append((center[0] + dist * math.cos(angle), center[1] + dist * math.sin(angle)))
    
    for r_step in [0.25, 0.5, 0.75, 1.0]:
        grid_points = []
        for i in range(5):
            angle = (i * 2 * math.pi / 5) - (math.pi / 2)
            grid_points.append((center[0] + (radius * r_step) * math.cos(angle), center[1] + (radius * r_step) * math.sin(angle)))
        draw.polygon(grid_points, outline=(255, 255, 255, 30))
        if r_step == 1.0:
            for i, (label, _) in enumerate(params):
                angle = (i * 2 * math.pi / 5) - (math.pi / 2)
                draw.text((center[0] + (radius + 80) * math.cos(angle), center[1] + (radius + 40) * math.sin(angle)), label, font=get_font(50), fill=(255, 255, 255), anchor="mm")
    draw.polygon(points, fill=color + (80,), outline=color + (255,))

def generate_player_card(player_data, team_side="Blue"):
    img = load_bg("spotlight")
    draw = ImageDraw.Draw(img, 'RGBA')
    accent_color = COLOR_BLUE if team_side == "Blue" else COLOR_RED

    name = player_data.get("name", "Unknown").upper()
    draw.text((200, 150), name, font=get_font(220), fill=(255, 255, 255))
    
    matches = player_data.get("matches", [])
    career_kd = player_data.get("career", {}).get("KD", 1.0)
    last_5 = matches[-5:] if len(matches) >= 5 else matches
    recent_kd = (sum(m.get("Kills",0) for m in last_5)/sum(m.get("Deaths",1) for m in last_5)) if last_5 else career_kd
    diff = recent_kd - career_kd
    draw.rounded_rectangle([200, 400, 950, 500], radius=20, fill=(50, 255, 50) if diff >= 0 else (255, 50, 50))
    draw.text((230, 415), f"{'HOT FORM' if diff >=0 else 'COOLING'} ({'+' if diff >=0 else ''}{diff:.2f} KD)", font=get_font(45), fill=(0,0,0))

    career = player_data.get("career", {})
    stats = [("TOTAL KILLS", f"{int(career.get('kills', 0)):,}"), ("TOTAL SCORE", f"{int(career.get('score', 0)):,}"), ("MAPS PLAYED", f"{int(career.get('maps', 0))}"), ("CAREER KD", f"{career.get('KD', 0):.2f}")]
    y = 650
    for label, value in stats:
        draw.text((200, y), label, font=get_font(70), fill=(180, 180, 180))
        draw.text((200, y + 80), value, font=get_font(130), fill=(255, 255, 255))
        y += 280

    radar_params = [("SLY", player_data.get('slayer', {}).get('pct', 0)), ("AIM", player_data.get('sharpshooter', {}).get('pct', 0)), ("STA", player_data.get('consistency', {}).get('pct', 0)), ("CLU", player_data.get('clutch', {}).get('pct', 0)), ("ANC", player_data.get('anchor', {}).get('pct', 0))]
    draw_radar_chart(draw, (1850, 1150), 450, radar_params, accent_color)

    draw.text((2700, 550), "SKILL PROFILE", font=get_font(70), fill=accent_color)
    by = 680
    for label_long, key in [("SLAYING", "slayer"), ("MARKSMAN", "sharpshooter"), ("STABILITY", "consistency"), ("PRESSURE", "clutch"), ("DEFENSIVE", "anchor")]:
        pct = player_data.get(key, {}).get("pct", 0)
        draw.text((2700, by), label_long, font=get_font(45), fill=(200, 200, 200))
        draw.rectangle([2700, by+60, 3600, by+90], fill=(40, 40, 45))
        draw.rectangle([2700, by+60, 2700 + (900 * (pct/100)), by+90], fill=accent_color)
        draw.text((3610, by+45), f"{int(pct)}%", font=get_font(40), fill=(255,255,255), anchor="lm")
        by += 180

    best_tag = max(["slayer", "sharpshooter", "consistency", "clutch", "anchor"], key=lambda k: player_data.get(k, {}).get("pct", 0))
    intel = player_data.get(best_tag, {}).get("summary", "Reliable team player.")
    draw.rectangle([150, 1850, 3690, 2080], fill=(20, 20, 25))
    draw.text((200, 1880), "SCOUTING REPORT", font=get_font(70), fill=accent_color)
    draw.text((200, 1960), intel, font=get_font(60), fill=(230, 230, 230))
    img.save(SPOTLIGHT_PATH)

def generate_tale_of_the_tape(rosterA, rosterB, nameA, nameB):
    img = load_bg("tape")
    draw = ImageDraw.Draw(img, 'RGBA')
    rosterA.sort(key=lambda p: p['career'].get('KD', 0), reverse=True)
    rosterB.sort(key=lambda p: p['career'].get('KD', 0), reverse=True)

    draw.text((960, 150), nameA, font=get_font(150), fill=COLOR_BLUE, anchor="mm")
    draw.text((2880, 150), nameB, font=get_font(150), fill=COLOR_RED, anchor="mm")
    draw.text((1920, 150), "PVP MATCHUPS", font=get_font(80), fill=(255, 255, 255), anchor="mm")

    y = 350
    # Added ANCHOR (Stability is Consistency)
    tags = [("SLAYER", "slayer"), ("AIM", "sharpshooter"), ("STABLE", "consistency"), ("CLUTCH", "clutch"), ("ANCHOR", "anchor")]
    
    for i in range(5):
        pA = rosterA[i] if i < len(rosterA) else {"name": "---"}
        pB = rosterB[i] if i < len(rosterB) else {"name": "---"}
        draw.text((250, y+100), pA['name'].upper(), font=get_font(90), fill=(255,255,255))
        draw.text((3590, y+100), pB['name'].upper(), font=get_font(90), fill=(255,255,255), anchor="ra")
        
        sub_y = y + 10
        for label, key in tags:
            pctA, pctB = pA.get(key, {}).get("pct", 0), pB.get(key, {}).get("pct", 0)
            draw.text((1920, sub_y), label, font=get_font(25), fill=(150,150,150), anchor="mm")
            draw.rectangle([1450, sub_y-10, 1850, sub_y+10], fill=(30,30,35))
            draw.rectangle([1850 - (400 * (pctA/100)), sub_y-10, 1850, sub_y+10], fill=COLOR_BLUE)
            draw.rectangle([1990, sub_y-10, 2390, sub_y+10], fill=(30,30,35))
            draw.rectangle([1990, sub_y-10, 1990 + (400 * (pctB/100)), sub_y+10], fill=COLOR_RED)
            sub_y += 48

        draw.line([200, y+280, 3640, y+280], fill=(255,255,255, 15), width=2)
        y += 310

    avgA = sum(p.get('slayer', {}).get('pct', 0) for p in rosterA) / 5
    avgB = sum(p.get('slayer', {}).get('pct', 0) for p in rosterB) / 5
    draw.rectangle([0, 1950, 3840, 2160], fill=(15, 15, 20))
    draw.text((400, 2055), f"SQUAD SLAYER POWER: {avgA:.1f}%", font=get_font(60), fill=COLOR_BLUE, anchor="lm")
    draw.text((3440, 2055), f"SQUAD SLAYER POWER: {avgB:.1f}%", font=get_font(60), fill=COLOR_RED, anchor="rm")
    img.save(TAPE_PATH)

def generate_team_dna(rosterA, rosterB, nameA, nameB):
    img = load_bg("dna")
    draw = ImageDraw.Draw(img, 'RGBA')
    draw.text((200, 100), nameA, font=get_font(140), fill=COLOR_BLUE)
    draw.text((3640, 100), nameB, font=get_font(140), fill=COLOR_RED, anchor="ra")
    draw.text((1920, 150), "STRATEGY DNA", font=get_font(100), fill=(255,255,255), anchor="mm")

    tags = ["slayer", "sharpshooter", "consistency", "clutch", "objective_payload", "objective_domination", "anchor"]
    y = 450
    for tag in tags:
        avgA = sum(p.get(tag, {}).get("pct", 0) for p in rosterA) / max(1, len(rosterA))
        avgB = sum(p.get(tag, {}).get("pct", 0) for p in rosterB) / max(1, len(rosterB))
        draw.text((1920, y - 40), tag.replace("_", " ").upper(), font=get_font(55), fill=(160,160,160), anchor="mm")
        draw.rectangle([600, y, 1850, y+70], fill=(30, 30, 35))
        draw.rectangle([1850 - (1250 * (avgA/100)), y, 1850, y+70], fill=COLOR_BLUE)
        draw.rectangle([1990, y, 3240, y+70], fill=(30, 30, 35))
        draw.rectangle([1990, y, 1990 + (1250 * (avgB/100)), y+70], fill=COLOR_RED)
        y += 200

    draw.rectangle([0, 1850, 3840, 2160], fill=(15, 15, 20)) 
    vitals = [("TOTAL KILLS", lambda r: sum(p['career'].get('kills', 0) for p in r)), ("AVG KD", lambda r: sum(p['career'].get('KD', 0) for p in r) / len(r)), ("TOTAL MAPS", lambda r: sum(p['career'].get('maps', 0) for p in r))]
    vx_pos = [450, 1100, 1750] # Increased spacing to fix overlap
    for i, (label, func) in enumerate(vitals):
        valA, valB = func(rosterA), func(rosterB)
        draw.text((vx_pos[i], 1920), label, font=get_font(45), fill=(150, 150, 150), anchor="mm")
        draw.text((vx_pos[i], 2020), f"{valA:,.1f}" if isinstance(valA, float) else f"{valA:,}", font=get_font(90), fill=COLOR_BLUE, anchor="mm")
        draw.text((3840 - vx_pos[i], 1920), label, font=get_font(45), fill=(150, 150, 150), anchor="mm")
        draw.text((3840 - vx_pos[i], 2020), f"{valB:,.1f}" if isinstance(valB, float) else f"{valB:,}", font=get_font(90), fill=COLOR_RED, anchor="mm")
    img.save(DNA_PATH)

def draw_vs_donut(draw, center, radius, valA, valB, colorA, colorB, label):
    """Draws a split donut showing relative strength, matching screen sides perfectly."""
    cx, cy = center
    width = 35
    total = valA + valB
    if total <= 0: # Prevent div by zero
        valA, valB = 50, 50
        total = 100
        
    pctA = valA / total
    
    # Draw background circle
    draw.ellipse([cx-radius, cy-radius, cx+radius, cy+radius], outline=(40, 40, 45), width=width)
    
    # --- SWAP CORRECTION ---
    # We start at 90 degrees (6 o'clock) and draw clockwise. 
    # This aligns Team A (Blue, Left) with the Left Side of the donut, 
    # and Team B (Red, Right) with the Right Side.
    startA = 90
    endA = startA + (360 * pctA)
    
    # Blue Arc (Team A - Left side)
    draw.arc([cx-radius, cy-radius, cx+radius, cy+radius], start=startA, end=endA, fill=colorA, width=width)
    # Red Arc (Team B - Right side)
    draw.arc([cx-radius, cy-radius, cx+radius, cy+radius], start=endA, end=startA + 360, fill=colorB, width=width)
    
    # Center Text
    pctA_display = int((valA/total)*100)
    pctB_display = 100 - pctA_display
    draw.text((cx, cy), f"{pctA_display}% | {pctB_display}%", font=get_font(45), fill=(255, 255, 255), anchor="mm")
    draw.text((cx, cy + radius + 60), label, font=get_font(40), fill=(180, 180, 180), anchor="mm")

def generate_win_probability(rosterA, rosterB, nameA, nameB):
    img = load_bg("win")
    draw = ImageDraw.Draw(img, 'RGBA')
    
    # 1. DATA CALCULATION
    from analysis.team_identity_v2 import summarize_team_tags
    sumA, sumB = summarize_team_tags(rosterA), summarize_team_tags(rosterB)

    # Calculate Strengths (Tags >= 60th percentile)
    def get_strengths(summary):
        s_list = []
        for tag, data in summary.items():
            if data["avg_pct"] >= 60:
                s_list.append(f"{tag.replace('_',' ').title()} Specialists")
        return s_list if s_list else ["Versatile Roster"]

    strengthsA = get_strengths(sumA)
    strengthsB = get_strengths(sumB)

    # 2. WIN PROBABILITY MATH
    weights = {"slayer": 0.35, "consistency": 0.25, "clutch": 0.15, "objective_payload": 0.15, "sharpshooter": 0.10}
    powerA = sum(sumA[tag]["avg_pct"] * weights[tag] for tag in weights)
    powerB = sum(sumB[tag]["avg_pct"] * weights[tag] for tag in weights)
    
    probA = (powerA / (powerA + powerB)) * 100 if (powerA + powerB) > 0 else 50
    probB = 100 - probA

    # 3. HEADER
    draw.text((1920, 150), "MATCH PREVIEW & PROBABILITY", font=get_font(120), fill=(255,255,255), anchor="mm")
    
    # Big Win Numbers
    draw.text((960, 450), nameA.upper(), font=get_font(100), fill=COLOR_BLUE, anchor="mm")
    draw.text((960, 650), f"{probA:.1f}%", font=get_font(300), fill=(255,255,255), anchor="mm")
    
    draw.text((2880, 450), nameB.upper(), font=get_font(100), fill=COLOR_RED, anchor="mm")
    draw.text((2880, 650), f"{probB:.1f}%", font=get_font(300), fill=(255,255,255), anchor="mm")

    # 4. VS DONUT GAUGES (6 Total)
    gauge_tags = [
        ("SLAYING", "slayer"), ("AIM", "sharpshooter"), 
        ("STABILITY", "consistency"), ("PRESSURE", "clutch"), ("TACTICS", "anchor")
    ]
    gx = 450
    for label, key in gauge_tags:
        draw_vs_donut(draw, (gx, 1150), 120, sumA[key]["avg_pct"], sumB[key]["avg_pct"], COLOR_BLUE, COLOR_RED, label)
        gx += 600

    # 6th Gauge: EXPERIENCE (Maps Played)
    mapsA = sum(p['career'].get('maps', 0) for p in rosterA)
    mapsB = sum(p['career'].get('maps', 0) for p in rosterB)
    draw_vs_donut(draw, (gx, 1150), 120, mapsA, mapsB, COLOR_BLUE, COLOR_RED, "EXPERIENCE")

    # 5. MATCH KEY FACTOR
    diffs = {tag: sumA[tag]["avg_pct"] - sumB[tag]["avg_pct"] for tag in weights}
    best_tag = max(diffs, key=lambda k: abs(diffs[k]))
    favored = nameA if diffs[best_tag] > 0 else nameB
    
    hooks = {
        "slayer": f"The '{favored}' Firepower: Superior elimination pressure likely to dictate map pace.",
        "consistency": f"The '{favored}' Floor: Higher stability makes them significantly harder to upset.",
        "clutch": f"The '{favored}' Resolve: Statistical advantage in high-pressure closing moments.",
        "objective_payload": f"The '{favored}' Efficiency: Superior objective focus provides a clear win-condition.",
        "sharpshooter": f"The '{favored}' Precision: Lethal accuracy in duels could negate enemy numbers."
    }
    key_hook = hooks.get(best_tag, f"The {best_tag.title()} Edge: {favored} hold the strategic advantage.")

    draw.rectangle([400, 1450, 3440, 1700], fill=(20, 20, 25))
    draw.text((1920, 1510), "PRODUCER'S KEY FACTOR", font=get_font(50), fill=COLOR_BLUE if favored == nameA else COLOR_RED, anchor="mm")
    draw.text((1920, 1610), key_hook, font=get_font(70), fill=(255, 255, 255), anchor="mm")

    # 6. TEAM INTEL (Strengths Only)
    def draw_intel(draw, x, name, strengths, color):
        draw.text((x, 1800), f"{name} STRENGTHS", font=get_font(55), fill=color, anchor="mm")
        y_off = 1880
        for s in strengths[:3]: 
            draw.text((x, y_off), f"• {s}", font=get_font(45), fill=(220, 220, 220), anchor="mm")
            y_off += 65

    draw_intel(draw, 960, nameA, strengthsA, COLOR_BLUE)
    draw_intel(draw, 2880, nameB, strengthsB, COLOR_RED)

    img.save(WIN_PATH)