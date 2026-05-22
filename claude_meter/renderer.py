import os
import time
from datetime import datetime
from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    import sys
    sys.exit("Run: pip install pillow")

import claude_meter.config as config

THINKING_VERBS = [
    "Accomplishing", "Actioning", "Actualizing", "Architecting", "Baking",
    "Beaming", "Beboppin'", "Befuddling", "Billowing", "Blanching",
    "Bloviating", "Boogieing", "Boondoggling", "Booping", "Bootstrapping",
    "Brewing", "Bunning", "Burrowing", "Calculating", "Canoodling",
    "Caramelizing", "Cascading", "Catapulting", "Cerebrating", "Channeling",
    "Channelling", "Choreographing", "Churning", "Clauding", "Coalescing",
    "Cogitating", "Combobulating", "Composing", "Computing", "Concocting",
    "Considering", "Contemplating", "Cooking", "Crafting", "Creating",
    "Crunching", "Crystallizing", "Cultivating", "Deciphering", "Deliberating",
    "Determining", "Dilly-dallying", "Discombobulating", "Doing", "Doodling",
    "Drizzling", "Ebbing", "Effecting", "Elucidating", "Embellishing",
    "Enchanting", "Envisioning", "Evaporating", "Fermenting", "Fiddle-faddling",
    "Finagling", "Flambeing", "Flibbertigibbeting", "Flowing", "Flummoxing",
    "Fluttering", "Forging", "Forming", "Frolicking", "Frosting",
    "Gallivanting", "Galloping", "Garnishing", "Generating", "Gesticulating",
    "Germinating", "Gitifying", "Grooving", "Gusting", "Harmonizing",
    "Hashing", "Hatching", "Herding", "Honking", "Hullaballooing",
    "Hyperspacing", "Ideating", "Imagining", "Improvising", "Incubating",
    "Inferring", "Infusing", "Ionizing", "Jitterbugging", "Julienning",
    "Kneading", "Leavening", "Levitating", "Lollygagging", "Manifesting",
    "Marinating", "Meandering", "Metamorphosing", "Misting", "Moonwalking",
    "Moseying", "Mulling", "Mustering", "Musing", "Nebulizing", "Nesting",
    "Newspapering", "Noodling", "Nucleating", "Orbiting", "Orchestrating",
    "Osmosing", "Perambulating", "Percolating", "Perusing", "Philosophising",
    "Photosynthesizing", "Pollinating", "Pondering", "Pontificating",
    "Pouncing", "Precipitating", "Prestidigitating", "Processing", "Proofing",
    "Propagating", "Puttering", "Puzzling", "Quantumizing", "Razzle-dazzling",
    "Razzmatazzing", "Recombobulating", "Reticulating", "Roosting",
    "Ruminating", "Sauteing", "Scampering", "Schlepping", "Scurrying",
    "Seasoning", "Shenaniganing", "Shimmying", "Simmering", "Skedaddling",
    "Sketching", "Slithering", "Smooshing", "Sock-hopping", "Spelunking",
    "Spinning", "Sprouting", "Stewing", "Sublimating", "Swirling",
    "Swooping", "Symbioting", "Synthesizing", "Tempering", "Thinking",
    "Thundering", "Tinkering", "Tomfoolering", "Topsy-turvying",
    "Transfiguring", "Transmuting", "Twisting", "Undulating", "Unfurling",
    "Unravelling", "Vibing", "Waddling", "Wandering", "Warping",
    "Whatchamacalliting", "Whirlpooling", "Whirring", "Whisking", "Wibbling",
    "Working", "Wrangling", "Zesting", "Zigzagging",
]

# Icon lives at the project root (one level above this package)
_ICON_PATH = Path(__file__).parent / "claude_icon.png"

SPINNER_FRAMES = ["·  ", "✻", "✽", "✶", "✳", "✢"]


def _load_font(size):
    candidates = [
        r"C:\Windows\Fonts\consola.ttf",
        r"C:\Windows\Fonts\cour.ttf",
        r"C:\Windows\Fonts\arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
    ]
    for p in candidates:
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                pass
    return ImageFont.load_default()


def _load_spinner_font(size):
    candidates = [
        r"C:\Windows\Fonts\seguisym.ttf",
        r"C:\Windows\Fonts\segoeui.ttf",
        r"C:\Windows\Fonts\arial.ttf",
    ]
    for p in candidates:
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                pass
    return _load_font(size)


FONT_HUGE  = _load_font(44)
FONT_TITLE = _load_font(20)
FONT_BADGE = _load_font(14)
FONT_MED   = _load_font(13)
FONT_SMALL = _load_font(11)
FONT_TINY  = _load_font(9)
FONT_SPIN  = _load_spinner_font(11)


def text_w(d, text, font):
    try:
        return int(d.textlength(text, font=font))
    except AttributeError:
        return d.textsize(text, font=font)[0]


def _calc_spinner_slot():
    tmp = Image.new("RGB", (1, 1))
    td  = ImageDraw.Draw(tmp)
    return max(text_w(td, ch, FONT_SPIN) for ch in SPINNER_FRAMES) + 4


SPINNER_SLOT = _calc_spinner_slot()


def fmt_tokens(n):
    if n >= 1_000_000:
        return f"{n/1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n/1_000:.0f}k"
    return str(n)


def bar_color(pct):
    if pct < 60:
        return config.GREEN
    if pct < 85:
        return config.YELLOW
    return config.RED


def get_spinner_char():
    return SPINNER_FRAMES[int(time.time() * 2) % len(SPINNER_FRAMES)]


def get_activity_text(is_active, last_ts_raw):
    if not is_active:
        return ""
    slot = int(time.time() / 4) % len(THINKING_VERBS)
    return THINKING_VERBS[slot] + "..."


def _draw_bar(d, x, y, w, h, pct, color):
    d.rounded_rectangle([x, y, x + w, y + h], radius=3, fill=config.BORDER)
    fw = max(int(w * pct / 100), 6 if pct > 0 else 0)
    if fw:
        d.rounded_rectangle([x, y, x + fw, y + h], radius=3, fill=color)


def _draw_badge(d, text, right_edge, cy, font, bg):
    tw   = text_w(d, text, font)
    padx, pady = 10, 5
    bw   = tw + padx * 2
    bh   = 22
    bx   = right_edge - bw
    by   = cy - bh // 2
    d.rounded_rectangle([bx, by, bx + bw, by + bh], radius=5, fill=bg)
    d.text((bx + padx, by + pady - 1), text, font=font, fill=config.WHITE)


def _draw_robot(d, x, y):
    c    = (220, 70, 70)
    dark = (10, 15, 25)
    d.rectangle([x + 4,  y,      x + 6,  y + 3],  fill=c)
    d.rectangle([x + 15, y,      x + 17, y + 3],  fill=c)
    d.rectangle([x + 3,  y,      x + 7,  y + 1],  fill=c)
    d.rectangle([x + 14, y,      x + 18, y + 1],  fill=c)
    d.rounded_rectangle([x + 1, y + 3, x + 21, y + 18], radius=2, fill=c)
    d.rectangle([x + 4,  y + 6,  x + 9,  y + 11], fill=dark)
    d.rectangle([x + 12, y + 6,  x + 17, y + 11], fill=dark)
    d.rectangle([x + 5,  y + 7,  x + 6,  y + 8],  fill=(255, 200, 200))
    d.rectangle([x + 13, y + 7,  x + 14, y + 8],  fill=(255, 200, 200))


def render(stats):
    img = Image.new("RGB", (config.DISPLAY_W, config.DISPLAY_H), config.BG)
    d   = ImageDraw.Draw(img)

    # Header
    HDR_H = 34
    if _ICON_PATH.exists():
        icon = Image.open(_ICON_PATH).convert("RGBA")
        icon.thumbnail((26, 26), Image.Resampling.LANCZOS)
        bg = Image.new("RGBA", icon.size, config.BG + (255,))
        bg.paste(icon, mask=icon.split()[3])
        img.paste(bg.convert("RGB"), (8, 7))
    else:
        _draw_robot(d, 8, 7)
    title = "Usage"
    tw = text_w(d, title, FONT_TITLE)
    d.text(((config.DISPLAY_W - tw) // 2, 7), title, font=FONT_TITLE, fill=config.WHITE)
    d.rectangle([0, HDR_H, config.DISPLAY_W, HDR_H + 1], fill=config.BORDER)

    # Current (5-hour)
    S1_Y     = HDR_H + 5
    BAR1_Y   = S1_Y + 48
    RESET1_Y = BAR1_Y + 12
    SEP2_Y   = RESET1_Y + 18

    w_pct = stats["window_pct"]
    d.text((10, S1_Y), f"{w_pct:.0f}%", font=FONT_HUGE, fill=config.WHITE)
    _draw_badge(d, "Current", config.DISPLAY_W - 10, S1_Y + 22, FONT_BADGE, config.BADGE_CURRENT)
    _draw_bar(d, 10, BAR1_Y, config.DISPLAY_W - 20, 9, w_pct, bar_color(w_pct))
    d.text((10, RESET1_Y), f"Resets in {stats['window_reset']}", font=FONT_MED, fill=config.DIM)

    d.rectangle([0, SEP2_Y, config.DISPLAY_W, SEP2_Y + 1], fill=config.BORDER)

    # Weekly
    S2_Y     = SEP2_Y + 6
    BAR2_Y   = S2_Y + 48
    RESET2_Y = BAR2_Y + 12
    SEP3_Y   = RESET2_Y + 18

    wk_pct = stats["weekly_pct"]
    d.text((10, S2_Y), f"{wk_pct:.0f}%", font=FONT_HUGE, fill=config.WHITE)
    _draw_badge(d, "Weekly", config.DISPLAY_W - 10, S2_Y + 22, FONT_BADGE, config.BADGE_WEEKLY)
    _draw_bar(d, 10, BAR2_Y, config.DISPLAY_W - 20, 9, wk_pct, bar_color(wk_pct))
    d.text((10, RESET2_Y), f"Resets in {stats['weekly_reset']}", font=FONT_MED, fill=config.DIM)

    d.rectangle([0, SEP3_Y, config.DISPLAY_W, SEP3_Y + 1], fill=config.BORDER)

    # Footer
    FTR_Y    = SEP3_Y + 5
    cost_str = f"${stats['cost']:.2f}"
    cw       = text_w(d, cost_str, FONT_MED)
    cost_bb  = d.textbbox((0, 0), cost_str, font=FONT_MED)
    cost_mid = FTR_Y + 2 + (cost_bb[1] + cost_bb[3]) // 2
    d.text((config.DISPLAY_W - cw - 10, FTR_Y + 2), cost_str, font=FONT_MED, fill=config.DIM)

    activity = get_activity_text(stats["is_active"], stats["last_ts_raw"])
    if activity:
        spin   = get_spinner_char()
        label  = f"{spin} {activity}"
        lbl_bb = d.textbbox((0, 0), label, font=FONT_SPIN)
        lbl_y  = cost_mid - (lbl_bb[1] + lbl_bb[3]) // 2
        d.text((10, lbl_y), label, font=FONT_SPIN, fill=config.ORANGE)
    else:
        rate    = stats.get("burn_rate", 0)
        idle    = f"~{fmt_tokens(int(rate))} tok/min" if rate >= 1 else "idle"
        idle_bb = d.textbbox((0, 0), idle, font=FONT_MED)
        idle_y  = cost_mid - (idle_bb[1] + idle_bb[3]) // 2
        d.text((10, idle_y), idle, font=FONT_MED, fill=config.DIM)

    FTR2_Y      = FTR_Y + 18
    model_label = stats["model"] + (" *" if not stats.get("api_ok") else "")
    d.text((10, FTR2_Y), model_label, font=FONT_TINY, fill=config.DIM)
    clock = datetime.now().strftime("%H:%M:%S")
    clw   = text_w(d, clock, FONT_TINY)
    d.text((config.DISPLAY_W - clw - 10, FTR2_Y), clock, font=FONT_TINY, fill=config.DIM)

    return img
