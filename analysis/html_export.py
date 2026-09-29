"""
Pretty HTML exports for OBS Browser Source. Fully responsive (vw/vh/vmin
based, see html_style.py) so these scale correctly at any Browser Source
resolution, not just a fixed 1920x1080 canvas.
"""

import html

from analysis.html_style import SHARED_CSS


def _esc(value):
    return html.escape(str(value)) if value is not None else ""


# Shared by every exported page (including the Spotlight image wrapper
# below). OBS Browser Sources don't watch the file on disk — they load
# the page once and just sit there, same as a regular browser tab. This
# polls the file's own content every 1.5s and reloads ONLY when it has
# actually changed, so the OBS source updates itself the moment
# Generate Player Slots (or the Spotlight "Next" button) regenerates
# this file — no manual toggle/refresh needed. If fetch() is blocked
# (browsers commonly restrict it on file:// URLs), this silently does
# nothing, same as before this script existed; serving these files over
# a local http:// URL instead of file:// avoids that restriction.
AUTO_REFRESH_SCRIPT = """
<script>
(function() {
    var baseline = null;
    function checkForUpdate() {
        var url = window.location.href.split('?')[0] + '?t=' + Date.now();
        fetch(url, {cache: 'no-store'}).then(function(res) { return res.text(); }).then(function(text) {
            if (baseline === null) { baseline = text; return; }
            if (text !== baseline) { window.location.reload(); }
        }).catch(function() { /* fetch blocked — no-op */ });
    }
    setInterval(checkForUpdate, 1500);
})();
</script>
"""


def _page_shell(title_html, body_html, extra_css=""):
    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
{SHARED_CSS}
{extra_css}
</style>
</head>
<body>
<div class="page">
{title_html}
{body_html}
</div>
{AUTO_REFRESH_SCRIPT}
</body>
</html>"""


def render_spotlight_html(image_filename):
    """
    Thin wrapper around the existing 4K Spotlight PNG (still rendered by
    generate_player_card via PIL, unchanged) so it can be dropped into
    OBS as a Browser Source just like the other three graphics, instead
    of needing a screen-capture workaround. Full-bleed, transparent
    background so it composites cleanly over any OBS scene background
    (including an animated one). A cache-busting query string on the
    <img> tag is regenerated every call, so the browser is forced to
    fetch the new image bytes rather than serving a cached copy of the
    old card when the page auto-reloads.
    """
    import time
    cache_bust = int(time.time() * 1000)
    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
    * {{ box-sizing: border-box; }}
    html, body {{
        margin: 0;
        padding: 0;
        width: 100vw;
        height: 100vh;
        background: transparent;
        overflow: hidden;
    }}
    img {{
        width: 100%;
        height: 100%;
        object-fit: contain;
        display: block;
    }}
</style>
</head>
<body>
<img src="{_esc(image_filename)}?v={cache_bust}">
{AUTO_REFRESH_SCRIPT}
</body>
</html>"""


# ---------------------------------------------------------
# Matchup Storyline + Team Identity comparison
# ---------------------------------------------------------

def _identity_card_html(identity, team_name, color, tier=None):
    strengths = identity.get("strengths", []) or ["No standout strengths yet"]
    weaknesses = identity.get("weaknesses", []) or ["No clear weaknesses yet"]
    tags = identity.get("tags", {}) or {}

    strengths_html = "".join(f"<li>{_esc(s)}</li>" for s in strengths)
    weaknesses_html = "".join(f"<li>{_esc(w)}</li>" for w in weaknesses)

    tag_rows = ""
    for tag, data in tags.items():
        pct = data.get("avg_pct", 0)
        tier_label = data.get("tier", "-")
        tag_rows += f"""
        <div class="tag-row">
            <span class="tag-label">{_esc(tag.replace('_', ' ').title())}</span>
            <div class="stat-bar-track">
                <div class="stat-bar-fill" style="width:{pct}%; background:{color};"></div>
            </div>
            <span class="tag-pct">{tier_label} &middot; {pct:.0f}%</span>
        </div>"""

    tier_badge = f'<span class="tier-badge">{_esc(tier)} Tier</span>' if tier else ""

    return f"""
    <div class="team-card" style="border-color:{color};">
        <div class="team-card-header" style="color:{color};">
            <span class="team-name">{_esc(team_name)}</span>
            {tier_badge}
        </div>
        <div class="team-style">{_esc(identity.get('team_style', 'Unknown'))}</div>

        <div class="sw-columns">
            <div class="sw-col">
                <div class="section-label">Strengths</div>
                <ul class="strengths">{strengths_html}</ul>
            </div>
            <div class="sw-col">
                <div class="section-label">Weaknesses</div>
                <ul class="weaknesses">{weaknesses_html}</ul>
            </div>
        </div>

        <div class="section-label">Tag Breakdown</div>
        <div class="tag-breakdown">{tag_rows}</div>
    </div>"""


MATCHUP_CSS = """
    .storyline-banner {
        background: rgba(255, 255, 255, 0.04);
        border: 0.2vmin solid #333;
        border-radius: 1.4vmin;
        padding: 1.8vh 1.8vw;
        font-size: 1.7vmin;
        line-height: 1.5;
        margin-top: 2vh;
        flex-shrink: 0;
        overflow: hidden;
        word-wrap: break-word;
        overflow-wrap: break-word;
    }
    .storyline-banner br {
        content: "";
        display: block;
        margin-bottom: 0.3vh;
    }
    .team-style {
        font-size: 1.6vmin;
        color: #cccccc;
        font-style: italic;
        margin-bottom: 1.2vh;
    }
    .sw-columns {
        display: flex;
        flex-direction: row;
        gap: 1.2vw;
    }
    .sw-col {
        flex: 1 1 0;
        min-width: 0;
    }
    ul.strengths, ul.weaknesses {
        margin: 0;
        padding-left: 1.1vw;
        font-size: 1.6vmin;
        line-height: 1.5;
    }
    ul.strengths li { color: #7CFC7C; }
    ul.weaknesses li { color: #FF8A8A; }
    .tag-row {
        display: flex;
        align-items: center;
        gap: 0.8vw;
        margin-bottom: 0.9vh;
    }
    .tag-label {
        width: 9vw;
        font-size: 1.4vmin;
        color: #dddddd;
        flex-shrink: 0;
    }
    .tag-pct {
        width: 7vw;
        font-size: 1.3vmin;
        color: #aaaaaa;
        text-align: right;
        flex-shrink: 0;
    }
"""


def render_matchup_html(narrative_text, identity_a, identity_b, team_a, team_b,
                         season=None, tier_a=None, tier_b=None):
    """
    Full matchup page. Order (top to bottom): page title (once), the
    team identity comparison side by side (team_a in blue on the left,
    team_b in red on the right, each with strengths/weaknesses as two
    sub-columns to keep card height down), then the narrative
    (Elite Players + Matchup Breakdown) in a 2-column banner below.
    narrative_text should be storylines.matchup_narrative(...) output,
    NOT matchup_storyline()/generate_storyline() — the latter embeds its
    own title and a full identity dump, which would duplicate what's
    already on this page.
    """
    COLOR_A = "#0d86f4"
    COLOR_B = "#f40d35"

    narrative_html = _esc(narrative_text).replace("\n", "<br>")
    card_a = _identity_card_html(identity_a, team_a, COLOR_A, tier_a)
    card_b = _identity_card_html(identity_b, team_b, COLOR_B, tier_b)
    subtitle = f"Season {season}" if season else ""

    title_html = (
        f'<h1 class="page-title">Match Storyline</h1>'
        f'<div class="page-subtitle">{_esc(team_a)} vs {_esc(team_b)}'
        f'{" &middot; " + _esc(subtitle) if subtitle else ""}</div>'
    )
    body_html = (
        f'<div class="comparison">{card_a}{card_b}</div>'
        f'<div class="storyline-banner">{narrative_html}</div>'
    )
    return _page_shell(title_html, body_html, MATCHUP_CSS)


# ---------------------------------------------------------
# Ranking pages (one per tag: Slayer, Sharpshooter, etc.)
# ---------------------------------------------------------

RANKING_CSS = """
    .ranking-table {
        width: 100%;
        border-collapse: collapse;
        font-size: 1.8vmin;
    }
    .ranking-table th {
        text-align: left;
        color: #888888;
        text-transform: uppercase;
        font-size: 1.2vmin;
        letter-spacing: 0.05vw;
        padding-bottom: 0.8vh;
        border-bottom: 0.15vmin solid #333;
    }
    .ranking-table td {
        padding: 0.9vh 0.4vw;
        border-bottom: 0.08vmin solid rgba(255,255,255,0.08);
    }
    .ranking-table td.rank { color: #888888; width: 10%; }
    .ranking-table td.name { font-weight: bold; width: 45%; }
    .ranking-table td.score { text-align: right; font-family: monospace; width: 25%; }
    .ranking-table td.pct { text-align: right; color: #aaaaaa; font-family: monospace; width: 20%; }
    .team-totals {
        margin-top: 1.6vh;
        font-size: 1.5vmin;
        color: #cccccc;
        border-top: 0.15vmin solid #333;
        padding-top: 1.2vh;
    }
    .team-totals div { margin-bottom: 0.4vh; }
    .verdict-banner {
        flex-shrink: 0;
        background: rgba(255,255,255,0.04);
        border: 0.2vmin solid #333;
        border-radius: 1.4vmin;
        padding: 1.6vh 1.8vw;
        margin-bottom: 2vh;
        font-size: 1.9vmin;
        text-align: center;
    }
    .verdict-banner .win-chance { font-weight: bold; }
    .formula-box {
        flex-shrink: 0;
        margin-top: 2vh;
        font-size: 1.3vmin;
        color: #999999;
        border-top: 0.1vmin solid #333;
        padding-top: 1.2vh;
        line-height: 1.5;
    }
"""


def _ranking_column_html(rows, color):
    trs = ""
    for r in rows:
        has_data = r.get("has_data", True)
        pct = r.get("pct")

        if has_data:
            pct_str = f"{pct:.0f}%" if pct is not None else "&mdash;"
            score_str = _esc(r['score_display'])
        elif pct is not None or (r.get('score_raw') or 0) != 0:
            # No CAREER data, but a live-match estimate was computed —
            # show it, clearly labelled, rather than blanking it out.
            pct_str = (f"{pct:.0f}%" if pct is not None else "&mdash;") + " (est)"
            score_str = _esc(r['score_display']) + " (est)"
        else:
            # Truly nothing to show — not even a live-match estimate.
            pct_str = "&mdash;"
            score_str = '<span style="color:#888;">NO DATA</span>'

        row_style = ' style="opacity:0.6;"' if not has_data else ''
        trs += f"""
        <tr{row_style}>
            <td class="rank">#{r['rank']}</td>
            <td class="name">{_esc(r['name'])}</td>
            <td class="score" style="color:{color};">{score_str}</td>
            <td class="pct">{pct_str}</td>
        </tr>"""
    return f"""
    <table class="ranking-table">
        <tr><th>Rank</th><th>Name</th><th>Score</th><th>Pctl</th></tr>
        {trs}
    </table>"""


def render_ranking_html(tag_display_name, data, formula_lines, season=None,
                         tier_a=None, tier_b=None):
    """
    data is the dict returned by DashLeagueGUI.compute_ranking_data():
    left/right rows, team totals/averages, delta, win chance, etc.
    """
    COLOR_A = "#0d86f4"
    COLOR_B = "#f40d35"

    team_a = data["team_a"]
    team_b = data["team_b"]

    tier_badge_a = f'<span class="tier-badge">{_esc(tier_a)} Tier</span>' if tier_a else ""
    tier_badge_b = f'<span class="tier-badge">{_esc(tier_b)} Tier</span>' if tier_b else ""

    col_a = f"""
    <div class="team-card" style="border-color:{COLOR_A};">
        <div class="team-card-header" style="color:{COLOR_A};">
            <span class="team-name">{_esc(team_a)}</span>
            {tier_badge_a}
        </div>
        {_ranking_column_html(data["left"], COLOR_A)}
        <div class="team-totals">
            <div>Total: {data['teamA_total']:.2f}</div>
            <div>Average: {data['teamA_avg']:.2f}</div>
        </div>
    </div>"""

    col_b = f"""
    <div class="team-card" style="border-color:{COLOR_B};">
        <div class="team-card-header" style="color:{COLOR_B};">
            <span class="team-name">{_esc(team_b)}</span>
            {tier_badge_b}
        </div>
        {_ranking_column_html(data["right"], COLOR_B)}
        <div class="team-totals">
            <div>Total: {data['teamB_total']:.2f}</div>
            <div>Average: {data['teamB_avg']:.2f}</div>
        </div>
    </div>"""

    verdict = (
        f'<span class="win-chance" style="color:{COLOR_A};">{_esc(team_a)} {data["teamA_win"]}%</span>'
        f' &mdash; '
        f'<span class="win-chance" style="color:{COLOR_B};">{_esc(team_b)} {data["teamB_win"]}%</span>'
        f'<br>Relative Advantage: {data["rel_adv"]:.1f}% in favour of {_esc(data["fav_delta"])}'
    )

    missing_total = data.get("missing_left", 0) + data.get("missing_right", 0)
    if missing_total:
        verdict += (
            f'<br><span style="color:#e0a030; font-size:0.8em;">'
            f'⚠ {missing_total} player(s) have no data for this tag and were '
            f'excluded from the averages above — treat this prediction with caution.'
            f'</span>'
        )

    formula_html = "<br>".join(_esc(line) for line in formula_lines)

    subtitle = f"Season {season}" if season else ""
    title_html = (
        f'<h1 class="page-title">{_esc(tag_display_name)} Rankings</h1>'
        f'<div class="page-subtitle">{_esc(team_a)} vs {_esc(team_b)}'
        f'{" &middot; " + _esc(subtitle) if subtitle else ""}</div>'
    )
    body_html = (
        f'<div class="verdict-banner">{verdict}</div>'
        f'<div class="comparison">{col_a}{col_b}</div>'
        f'<div class="formula-box">{formula_html}</div>'
    )
    return _page_shell(title_html, body_html, RANKING_CSS + MATCHUP_CSS)


# ---------------------------------------------------------
# Rookie Leaderboard
# ---------------------------------------------------------

ROOKIE_CSS = """
    .rookie-table {
        width: 100%;
        border-collapse: collapse;
        font-size: 2vmin;
        flex: 1;
    }
    .rookie-table th {
        border-bottom: 0.3vmin solid #f40d35;
        padding: 1.4vh 1vw;
        text-align: left;
        color: #aaaaaa;
        font-weight: bold;
        text-transform: uppercase;
        font-size: 1.3vmin;
    }
    .rookie-table td {
        padding: 1.2vh 1vw;
        border-bottom: 0.08vmin solid rgba(255,255,255,0.1);
    }
    .rookie-table .rank { font-weight: bold; color: #0d86f4; width: 8%; }
    .rookie-table .name { font-weight: bold; width: 27%; }
    .rookie-table .team { color: #aaaaaa; width: 17%; }
    .rookie-table .score { text-align: right; width: 15%; font-family: monospace; font-weight: bold; }
    .rookie-table .kd { text-align: right; width: 11%; font-family: monospace; }
    .rookie-table .kills { text-align: right; width: 11%; font-family: monospace; color: #f40d35; }
    .rookie-table .maps { text-align: right; width: 11%; font-family: monospace; }
"""


def render_rookie_leaderboard_html(rows, season, kill_threshold=1000):
    trs = ""
    for r in rows:
        trs += f"""
        <tr>
            <td class="rank">#{r['rank']}</td>
            <td class="name">{_esc(r['name'])}</td>
            <td class="team">{_esc(r['team'])}</td>
            <td class="score">{int(r['score']):,}</td>
            <td class="kd">{r['kd']:.2f}</td>
            <td class="kills">{int(r['kills'])}</td>
            <td class="maps">{int(r['maps'])}</td>
        </tr>"""

    title_html = f'<h1 class="page-title">Rookie Leaderboard</h1>'
    subtitle = f"Season {season} &middot; Rookie = under {kill_threshold:,} career kills"
    body_html = f"""
    <div class="page-subtitle">{subtitle}</div>
    <table class="rookie-table">
        <tr>
            <th class="rank">Rank</th>
            <th class="name">Name</th>
            <th class="team">Team</th>
            <th class="score">Score</th>
            <th class="kd">KD</th>
            <th class="kills">Kills</th>
            <th class="maps">Maps</th>
        </tr>
        {trs}
    </table>"""
    return _page_shell(title_html, body_html, ROOKIE_CSS)
