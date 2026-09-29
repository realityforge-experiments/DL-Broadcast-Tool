"""
Shared CSS for all OBS Browser Source HTML exports (matchup storyline,
the 8 ranking pages, rookie leaderboard). Fully responsive using
vw/vh/vmin units so the layout scales correctly regardless of what
resolution the OBS Browser Source is actually set to — no fixed pixel
width/height anywhere. vmin is used for anything text-sized so it scales
safely with whichever dimension (width or height) is the constraint,
avoiding overflow on unusual aspect ratios.
"""

SHARED_CSS = """
    * { box-sizing: border-box; }
    html, body {
        margin: 0;
        padding: 0;
        width: 100vw;
        height: 100vh;
        background: rgba(8, 8, 12, 0.96);
        color: #ffffff;
        font-family: 'Segoe UI', Arial, sans-serif;
        overflow: hidden;
    }
    .page {
        width: 100%;
        height: 100%;
        padding: 3vh 3vw;
        display: flex;
        flex-direction: column;
    }
    h1.page-title {
        text-align: center;
        text-transform: uppercase;
        letter-spacing: 0.4vw;
        font-size: 3.6vmin;
        margin: 0 0 0.5vh 0;
        flex-shrink: 0;
    }
    .page-subtitle {
        text-align: center;
        color: #999999;
        font-size: 1.7vmin;
        margin-bottom: 2.5vh;
        flex-shrink: 0;
    }
    .tier-badge {
        font-size: 1.4vmin;
        color: #bbbbbb;
        border: 0.1vmin solid #555;
        border-radius: 2vh;
        padding: 0.4vh 1.2vw;
    }
    .comparison {
        display: flex;
        flex-direction: row;
        gap: 1.6vw;
        flex: 1;
        min-height: 0;
    }
    .team-card {
        flex: 1 1 0;
        min-width: 0;
        background: rgba(255, 255, 255, 0.03);
        border: 0.25vmin solid #444;
        border-radius: 1.4vmin;
        padding: 2vh 1.6vw;
        overflow: auto;
    }
    .team-card-header {
        display: flex;
        align-items: baseline;
        justify-content: space-between;
        margin-bottom: 0.4vh;
    }
    .team-name {
        font-size: 2.6vmin;
        font-weight: bold;
        text-transform: uppercase;
        letter-spacing: 0.15vw;
    }
    .section-label {
        font-size: 1.4vmin;
        text-transform: uppercase;
        letter-spacing: 0.05vw;
        color: #888888;
        margin-top: 1.6vh;
        margin-bottom: 0.6vh;
        border-bottom: 0.1vmin solid #333;
        padding-bottom: 0.4vh;
    }
    .stat-bar-track {
        flex: 1;
        height: 1.3vh;
        background: #2a2a2e;
        border-radius: 0.7vh;
        overflow: hidden;
    }
    .stat-bar-fill {
        height: 100%;
        border-radius: 0.7vh;
    }
    .footer-note {
        margin-top: 1.6vh;
        font-size: 1.3vmin;
        color: #777777;
        text-align: center;
        flex-shrink: 0;
    }
"""
