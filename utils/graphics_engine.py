import os
import math
from PIL import Image, ImageDraw, ImageFont

# --- PATHING CONFIGURATION ---
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSETS_DIR = os.path.join(BASE_DIR, "assets")
# This points to your stats folder for OBS to read
OUTPUT_PATH = os.path.join(BASE_DIR, "..", "stats", "obs_exports", "spotlight_card.png")

# Ensure directories exist
os.makedirs(ASSETS_DIR, exist_ok=True)
os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)

def generate_player_card(player_data, team_side="Blue"):
    """
    Generates a 4K (3840x2160) Player Spotlight card.
    team_side: "Blue" or "Red" (determines accent colors)
    """
    # 1. Setup Canvas (4K)
    width, height = 3840, 2160
    # Professional Blue/Red Hex codes
    accent_color = (0, 162, 255) if team_side == "Blue" else (255, 38, 0)
    
    # 2. Background Logic
    bg_path = os.path.join(ASSETS_DIR, "background.png")
    if os.path.exists(bg_path):
        img = Image.open(bg_path).resize((width, height))
    else:
        # Create a deep dark slate gradient-style background
        img = Image.new('RGB', (width, height), color=(10, 10, 15))
    
    draw = ImageDraw.Draw(img, 'RGBA') # RGBA for semi-transparent lines
    
    # Font Helper
    def get_font(size):
        # On Windows, arial is standard. On Linux/Mac, you might need a path to a .ttf
        try:
            return ImageFont.truetype("arial.ttf", size)
        except:
            return ImageFont.load_default()

    # Define Font Styles
    title_font = get_font(220)
    label_font = get_font(70)
    stat_font = get_font(130)
    tag_font = get_font(90)
    hook_font = get_font(60)

    # 3. DRAW PLAYER HEADER
    name = player_data.get("name", "Unknown Player").upper()
    draw.text((200, 150), name, font=title_font, fill=(255, 255, 255))
    
    # 4. TREND ANALYSIS (Last 5 Matches vs Career)
    matches = player_data.get("matches", [])
    career_kd = player_data.get("career", {}).get("KD", 1.0)
    
    recent_kd = career_kd
    if len(matches) >= 3:
        last_5 = matches[-5:]
        recent_kills = sum(m.get("Kills", 0) or 0 for m in last_5)
        recent_deaths = sum(m.get("Deaths", 0) or 0 for m in last_5)
        recent_kd = recent_kills / recent_deaths if recent_deaths > 0 else recent_kills
    
    diff = recent_kd - career_kd
    trend_color = (50, 255, 50) if diff >= 0 else (255, 50, 50)
    trend_text = "HOT FORM" if diff >= 0 else "COOLING"
    
    # Draw Trend Box
    draw.rounded_rectangle([200, 400, 850, 500], radius=20, fill=trend_color)
    draw.text((230, 415), f"{trend_text} ({'+' if diff >=0 else ''}{diff:.2f} KD)", font=get_font(45), fill=(0,0,0))

    # 5. LEFT COLUMN: CORE CAREER STATS
    career = player_data.get("career", {})
    stats = [
        ("TOTAL KILLS", f"{int(career.get('kills', 0)):,}"),
        ("TOTAL SCORE", f"{int(career.get('score', 0)):,}"),
        ("MAPS PLAYED", f"{int(career.get('maps', 0))}"),
        ("CAREER KD", f"{career.get('KD', 0):.2f}")
    ]

    curr_y = 650
    for label, value in stats:
        draw.text((200, curr_y), label, font=label_font, fill=(180, 180, 180))
        draw.text((200, curr_y + 80), value, font=stat_font, fill=(255, 255, 255))
        curr_y += 280

    # 6. RIGHT COLUMN: SKILL BARS
    draw.text((2000, 450), "SKILL PROFILE vs LEAGUE AVG", font=label_font, fill=accent_color)
    
    tags_to_show = [
        ("SLAYING", "slayer"),
        ("MARKSMAN", "sharpshooter"),
        ("CONSISTENCY", "consistency"),
        ("PRESSURE", "clutch"),
        ("DEFENSIVE", "anchor")
    ]

    bar_y = 550
    for display_name, key in tags_to_show:
        tag_obj = player_data.get(key, {})
        pct = tag_obj.get("pct", 0)
        tier = tag_obj.get("tier", "D")
        
        # Label
        draw.text((2000, bar_y), f"{display_name} ({tier})", font=tag_font, fill=(255, 255, 255))
        
        # Bar BG
        draw.rectangle([2000, bar_y + 110, 3600, bar_y + 140], fill=(40, 40, 45))
        # Actual Data Bar
        fill_width = 2000 + (1600 * (pct / 100))
        draw.rectangle([2000, bar_y + 110, fill_width, bar_y + 140], fill=accent_color)
        
        # --- LEAGUE AVG LINE (50%) ---
        avg_x = 2000 + (1600 * 0.5)
        # Drawing a vertical white line at 50%
        draw.line([avg_x, bar_y + 100, avg_x, bar_y + 150], fill=(255, 255, 255, 180), width=6)
        
        bar_y += 230

    # 7. FOOTER: SCOUTING REPORT
    # Get the summary from their highest-performing tag
    best_tag_key = max(tags_to_show, key=lambda x: player_data.get(x[1], {}).get("pct", 0))[1]
    intel = player_data.get(best_tag_key, {}).get("summary", "Reliable league veteran.")

    # Semi-transparent dark box for footer
    draw.rectangle([150, 1800, 3690, 2050], fill=(20, 20, 25))
    draw.text((200, 1830), "SCOUTING REPORT", font=label_font, fill=accent_color)
    draw.text((200, 1920), intel, font=hook_font, fill=(230, 230, 230))

    # 8. SAVE
    img.save(OUTPUT_PATH)
    return OUTPUT_PATH