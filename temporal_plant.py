"""
temporal_plant.py — A virtual plant game modelling temporal logic.

The plant's growth outcome depends on three hidden dimensions:
  1. Moisture state    : decays continuously over real time; replenished by watering (W)
  2. Sunlight state    : decays continuously over real time; replenished by exposing (S)
  3. Latent temporal   : cumulative seconds where BOTH moisture AND sunlight are
                         simultaneously inside their optimal windows
                         (accumulates but never resets — past care is permanently remembered)

Growth advances only when the temporal accumulator crosses per-stage thresholds.
Stress from over-watering, scorching, drought, or deep shade accumulates and can kill the plant.
Each plant species has distinct optimal windows and decay rates for both resources.

Controls:
  W           — Water the plant
  S           — Expose to sunlight (open blinds / move to window)
  D           — Toggle debug overlay (reveals all hidden state)
  ENTER       — Confirm selection

Run locally:   python temporal_plant.py
Run in browser: python -m pygbag temporal_plant.py
"""

import asyncio
import json
import random
import time
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo
import pygame


WIDTH, HEIGHT = 640, 480

// SECTION #? DATA SAVING & TIMEZONE

SAVE_PATH    = Path.home() / ".temporal_plant_save.json"
TZ_EST       = ZoneInfo("America/New_York")
SAVE_INTERVAL = 30   # 30 seconds between auto-saves

BG     = ( 15,  20,  10)
FG     = (180, 220, 140)
DIM    = ( 70, 100,  50)
ACCENT = (220, 200,  80)
RED    = (210,  60,  60)
BLUE   = (100, 160, 210)
WHITE  = (240, 240, 240)


// SECTION #? BONSAI GENERATOR
# Draws onto a (BONSAI_W × BONSAI_H) grid of (char, color) cells, then
# renders that grid to a cached Pygame Surface via get_bonsai_surf().

BONSAI_W = 46
BONSAI_H = 18

_WOOD  = (145, 100,  48)
_LEAF  = ( 75, 165,  65)
_BLOOM = (230, 150, 200)
_POT   = (160, 105,  58)


def _put(chars, cols, x, y, ch, col, force=False):
    if 0 <= x < BONSAI_W and 0 <= y < BONSAI_H:
        if force or chars[y][x] == ' ':
            chars[y][x] = ch
            cols[y][x]  = col


def _br_char(dx, dy):
    if dx == 0:  return '|'
    if dy == 0:  return '-'
    return '/' if dx * dy < 0 else '\\'


def _leaves(chars, cols, rng, x, y, blooming):
    pool = '@*' if blooming else '~~.'
    col  = _BLOOM if blooming else _LEAF
    spots = [(0,0),(1,0),(-1,0),(0,-1),(1,-1),(-1,-1),
             (2,-1),(-2,-1),(0,-2),(1,-2),(-1,-2)]
    for ox, oy in spots:
        if rng.random() < 0.72:
            _put(chars, cols, x+ox, y+oy, rng.choice(pool), col)


def _branch(chars, cols, rng, x, y, dx, dy, steps, depth, blooming):
    for i in range(steps):
        nx, ny = x + dx, y + dy
        if not (0 <= nx < BONSAI_W and 0 <= ny < BONSAI_H):
            break
        _put(chars, cols, nx, ny, _br_char(dx, dy), _WOOD)
        x, y = nx, ny
        # Occasional horizontal extension — gives branches a wider feel
        if i < steps - 1 and rng.random() < 0.28:
            ex = x + dx
            if 0 <= ex < BONSAI_W:
                _put(chars, cols, ex, y, '-', _WOOD)
                x = ex

    if depth <= 0:
        _leaves(chars, cols, rng, x, y, blooming)
    else:
        sub = max(1, steps - 1)
        _branch(chars, cols, rng, x, y, -1, -1, sub, depth - 1, blooming)
        _branch(chars, cols, rng, x, y,  1, -1, sub, depth - 1, blooming)
        if depth >= 2 and rng.random() < 0.55:
            _branch(chars, cols, rng, x, y, 0, -1, max(1, sub - 1), depth - 2, blooming)


def make_bonsai(stage: int, seed: int):
    """Return (chars, cols) 2-D lists for the given stage.
    chars[y][x] is a single character; cols[y][x] is an RGB tuple.
    """
    rng   = random.Random(seed)
    chars = [[' '] * BONSAI_W for _ in range(BONSAI_H)]
    cols  = [[BG]  * BONSAI_W for _ in range(BONSAI_H)]

    cx     = BONSAI_W // 2
    pot_y  = BONSAI_H - 4
    base_y = pot_y - 1

    # (trunk_height, branch_depth, branch_steps, blooming)
    configs = [
        (0, 0, 0, False),   # 0 — Seedling
        (2, 0, 2, False),   # 1 — Sprout
        (4, 1, 3, False),   # 2 — Sapling
        (6, 2, 4, False),   # 3 — Mature
        (8, 3, 5, True),    # 4 — Blooming
    ]
    trunk_h, br_depth, br_steps, blooming = configs[stage]

    # Trunk
    for j in range(trunk_h):
        y = base_y - j
        if j == 0:
            for ox in (-1, 0, 1):
                _put(chars, cols, cx + ox, y, '|', _WOOD, force=True)
        else:
            _put(chars, cols, cx - 1, y, '(', _WOOD, force=True)
            _put(chars, cols, cx,     y, '|', _WOOD, force=True)
            _put(chars, cols, cx + 1, y, ')', _WOOD, force=True)

    tip_y = base_y - trunk_h + 1

    if stage == 0:
        _put(chars, cols, cx, base_y,     ',', _LEAF, force=True)
        _put(chars, cols, cx, base_y - 1, '.', _LEAF, force=True)
    elif stage == 1:
        for ox, oy in [(-1, 0), (0, -1), (1, 0)]:
            _put(chars, cols, cx + ox, tip_y + oy, '~', _LEAF, force=True)
    else:
        _branch(chars, cols, rng, cx, tip_y, -1, -1, br_steps, br_depth, blooming)
        _branch(chars, cols, rng, cx, tip_y,  1, -1, br_steps, br_depth, blooming)
        if br_depth >= 2 and rng.random() < 0.6:
            _branch(chars, cols, rng, cx, tip_y, 0, -1, br_steps - 1, br_depth - 1, blooming)

    # Pot
    ph = 7   # half-width of pot interior
    for ox in range(-ph - 1, ph + 2):          # rim
        _put(chars, cols, cx + ox, pot_y, '_', _POT, force=True)
    _put(chars, cols, cx - ph - 1, pot_y + 1, '|', _POT, force=True)
    _put(chars, cols, cx + ph + 1, pot_y + 1, '|', _POT, force=True)
    for ox in range(-ph, ph + 1):              # floor
        _put(chars, cols, cx + ox, pot_y + 1, '_', _POT, force=True)
    _put(chars, cols, cx - ph,     pot_y + 2, '\\', _POT, force=True)
    _put(chars, cols, cx + ph,     pot_y + 2, '/',  _POT, force=True)
    for ox in range(-ph + 1, ph):              # base curve
        _put(chars, cols, cx + ox, pot_y + 2, '_', _POT, force=True)

    return chars, cols


_bonsai_cache: dict = {}


def get_bonsai_surf(stage: int, seed: int, font) -> pygame.Surface:
    """Render make_bonsai() output to a cached Pygame Surface."""
    key = (stage, seed)
    if key not in _bonsai_cache:
        chars, cols = make_bonsai(stage, seed)
        cw, ch = font.size("M")
        bsurf = pygame.Surface((BONSAI_W * cw, BONSAI_H * ch))
        bsurf.fill(BG)   # solid background — avoids SRCALPHA issues in Pygbag
        for ry, (row_c, row_k) in enumerate(zip(chars, cols)):
            for rx, (c, k) in enumerate(zip(row_c, row_k)):
                if c != ' ':
                    img = font.render(c, True, k)
                    bsurf.blit(img, (rx * cw, ry * ch))
        _bonsai_cache[key] = bsurf
    return _bonsai_cache[key]


STAGE_NAMES = ["Seedling", "Sprout", "Sapling", "Mature", "Blooming"]
PLANT_NAMES = ["Bonsai"]

# ── Plant parameters ───────────────────────────────────────────────────────────
# decay_rate       moisture lost per second (continuous)
# water_amount     moisture added per W-press
# optimal_range    (low, high) — the target moisture window for growth
# overwater_thresh above this value → overwater stress begins
# sun_decay_rate   sunlight lost per second (clouds, angle of sun, etc.)
# sun_amount       sunlight added per S-press
# sun_optimal      (low, high) — the target sunlight window for growth
# overlight_thresh above this value → scorching stress begins
# growth_time      seconds of time_in_optimal needed to advance one stage
#                  (time_in_optimal only ticks when BOTH resources are in range)
# damage_rate      stress per second while any resource is out of bounds
# lethal_damage    total damage that kills the plant

PLANT_PARAMS = {
    "Bonsai": {
        "decay_rate":        0.8,    # moisture lost per second
        "water_amount":      20,
        "optimal_range":     (30, 65),
        "overwater_thresh":  76,
        "sun_decay_rate":    1.0,    # sunlight lost per second
        "sun_amount":        22,
        "sun_optimal":       (35, 70),  # filtered, indirect sun
        "overlight_thresh":  82,
        "growth_time":       50,     # seconds in dual-optimal per stage
        "damage_rate":       1.5,
        "lethal_damage":     120,
    },
}


class PlantState:
    def __init__(self, name: str):
        p = PLANT_PARAMS[name]
        self.name            = name
        self.params          = p
        self.seed            = random.randint(0, 999_999)  # shapes the procedural tree
        self.moisture        = 50.0   # 0–100, hidden (debug only)
        self.sunlight        = 50.0   # 0–100, hidden (debug only)
        self.stage           = 0      # 0–4
        self.time_in_optimal = 0.0    # latent temporal accumulator (hidden)
                                      # ticks only when BOTH resources are in range
        self.damage          = 0.0    # cumulative stress (hidden)
        self.dead            = False
        self.won             = False
        self.last_tick       = time.monotonic()

    def tick(self):
        """Advance simulation by real elapsed time."""
        if self.dead or self.won:
            return
        now = time.monotonic()
        dt  = now - self.last_tick
        self.last_tick = now

        p = self.params

        # 1. Both resources decay continuously over time
        self.moisture = max(0.0, self.moisture - p["decay_rate"]     * dt)
        self.sunlight = max(0.0, self.sunlight - p["sun_decay_rate"] * dt)

        mlo, mhi = p["optimal_range"]
        slo, shi = p["sun_optimal"]

        moisture_ok = mlo <= self.moisture <= mhi
        sunlight_ok = slo <= self.sunlight <= shi

        # 2. Latent temporal accumulator — only ticks when BOTH are in range
        #    Past care is permanent: accumulator never resets
        if moisture_ok and sunlight_ok:
            self.time_in_optimal += dt

        # 3. Stress from any out-of-bounds resource
        critically_dry  = self.moisture < mlo * 0.35
        critically_dark = self.sunlight < slo * 0.35
        if self.moisture > p["overwater_thresh"] or critically_dry:
            self.damage += p["damage_rate"] * dt
        if self.sunlight > p["overlight_thresh"] or critically_dark:
            self.damage += p["damage_rate"] * dt

        # 4. Stage advance when accumulator crosses next threshold
        threshold = p["growth_time"] * (self.stage + 1)
        if self.stage < 4 and self.time_in_optimal >= threshold:
            self.stage += 1
            if self.stage == 4:
                self.won = True

        # 5. Death
        if self.damage >= p["lethal_damage"]:
            self.dead = True

    def water(self):
        if self.dead or self.won:
            return
        self.moisture = min(100.0, self.moisture + self.params["water_amount"])

    def expose_to_sun(self):
        if self.dead or self.won:
            return
        self.sunlight = min(100.0, self.sunlight + self.params["sun_amount"])

    def moisture_hint(self):
        """Return (label, color) — deliberately vague moisture indicator."""
        if self.dead:
            return "Dead", RED
        p = self.params
        lo, hi = p["optimal_range"]
        if self.moisture > p["overwater_thresh"]:
            return "Overwatered", RED
        elif self.moisture < lo * 0.35:
            return "Parched", RED
        elif lo <= self.moisture <= hi:
            return "Hydrated", FG
        elif self.moisture < lo:
            return "Thirsty", ACCENT
        else:
            return "Moist", BLUE

    def sun_hint(self):
        """Return (label, color) — deliberately vague sunlight indicator."""
        if self.dead:
            return "Dead", RED
        p = self.params
        slo, shi = p["sun_optimal"]
        if self.sunlight > p["overlight_thresh"]:
            return "Scorched", RED
        elif self.sunlight < slo * 0.35:
            return "In the dark", RED
        elif slo <= self.sunlight <= shi:
            return "Well-lit", ACCENT
        elif self.sunlight < slo:
            return "Needs light", DIM
        else:
            return "Bright", BLUE

    def stage_progress(self):
        """Fraction [0,1] through the current growth stage."""
        if self.won:
            return 1.0
        p   = self.params
        lo  = p["growth_time"] * self.stage
        pct = (self.time_in_optimal - lo) / p["growth_time"]
        return max(0.0, min(1.0, pct))

    # ── Persistence ───────────────────────────────────────────────────────────

    def to_dict(self) -> dict:
        return {
            "name":            self.name,
            "seed":            self.seed,
            "moisture":        self.moisture,
            "sunlight":        self.sunlight,
            "stage":           self.stage,
            "time_in_optimal": self.time_in_optimal,
            "damage":          self.damage,
            "dead":            self.dead,
            "won":             self.won,
            "saved_utc":       datetime.now(timezone.utc).isoformat(),
        }

    @classmethod
    def from_dict(cls, d: dict) -> "PlantState":
        plant = cls(d["name"])
        plant.seed            = d.get("seed", random.randint(0, 999_999))
        plant.moisture        = d["moisture"]
        plant.sunlight        = d["sunlight"]
        plant.stage           = d["stage"]
        plant.time_in_optimal = d["time_in_optimal"]
        plant.damage          = d["damage"]
        plant.dead            = d["dead"]
        plant.won             = d["won"]
        saved_at = datetime.fromisoformat(d["saved_utc"])
        elapsed  = (datetime.now(timezone.utc) - saved_at).total_seconds()
        if elapsed > 0 and not plant.dead and not plant.won:
            plant._apply_offline(elapsed)
        return plant

    def _apply_offline(self, elapsed: float):
        """Analytically apply decay and stress for time spent offline.

        For each resource we compute how long (t_crit) until it crossed
        the critical threshold, then accumulate damage only for the time
        beyond that point — mirroring what tick() would have done.
        """
        p = self.params
        mlo, _ = p["optimal_range"]
        slo, _ = p["sun_optimal"]
        crit_m = mlo * 0.35
        crit_s = slo * 0.35

        # Time until moisture goes critically dry from its current level
        if self.moisture > crit_m and p["decay_rate"] > 0:
            t_dry = (self.moisture - crit_m) / p["decay_rate"]
            dry_time = max(0.0, elapsed - t_dry)
        else:
            dry_time = elapsed if self.moisture <= crit_m else 0.0

        # Time until sunlight goes critically dark
        if self.sunlight > crit_s and p["sun_decay_rate"] > 0:
            t_dark = (self.sunlight - crit_s) / p["sun_decay_rate"]
            dark_time = max(0.0, elapsed - t_dark)
        else:
            dark_time = elapsed if self.sunlight <= crit_s else 0.0

        # Apply decay
        self.moisture = max(0.0, self.moisture - p["decay_rate"]     * elapsed)
        self.sunlight = max(0.0, self.sunlight - p["sun_decay_rate"] * elapsed)

        # Apply accumulated stress
        self.damage += p["damage_rate"] * dry_time
        self.damage += p["damage_rate"] * dark_time

        if self.damage >= p["lethal_damage"]:
            self.dead = True


def save_plant(plant: PlantState):
    """Write plant state to disk. Silently fails in browser context."""
    try:
        SAVE_PATH.write_text(json.dumps(plant.to_dict(), indent=2))
    except Exception:
        pass


def load_plant() -> "PlantState | None":
    """Load and return a saved plant, applying offline time. Returns None if no save."""
    try:
        if SAVE_PATH.exists():
            return PlantState.from_dict(json.loads(SAVE_PATH.read_text()))
    except Exception:
        pass
    return None


def delete_save():
    try:
        SAVE_PATH.unlink(missing_ok=True)
    except Exception:
        pass


# ── Drawing helpers ────────────────────────────────────────────────────────────

def blit_centred(surf, img, cy_or_y, *, centre_x=True, x=0):
    if centre_x:
        surf.blit(img, (WIDTH // 2 - img.get_width() // 2, cy_or_y))
    else:
        surf.blit(img, (x, cy_or_y))


def draw_bar(surf, x, y, w, h, pct, fill_col, border_col=FG, bg_col=DIM):
    pygame.draw.rect(surf, bg_col, (x, y, w, h))
    if pct > 0:
        pygame.draw.rect(surf, fill_col, (x, y, int(w * pct), h))
    pygame.draw.rect(surf, border_col, (x, y, w, h), 1)


# ── Title screen ───────────────────────────────────────────────────────────────

def draw_title(surf, font_lg, font_sm, font_xs, saved_plant, preview_surf):
    surf.fill(BG)

    title = font_lg.render("TEMPORAL BONSAI", True, ACCENT)
    blit_centred(surf, title, 14)

    # Bonsai preview (stage-4 blooming, fixed seed)
    if preview_surf is not None:
        px = WIDTH // 2 - preview_surf.get_width() // 2
        surf.blit(preview_surf, (px, 44))
        bot = 44 + preview_surf.get_height()
    else:
        bot = 60

    if saved_plant and not saved_plant.dead and not saved_plant.won:
        c_img = font_sm.render(
            f"[C] Continue your bonsai  ({STAGE_NAMES[saved_plant.stage]})", True, FG)
        n_img = font_sm.render("[N] Start a new bonsai", True, DIM)
        blit_centred(surf, c_img, bot + 8)
        blit_centred(surf, n_img, bot + 28)
    elif saved_plant and (saved_plant.dead or saved_plant.won):
        state = "bloomed" if saved_plant.won else "died"
        msg = font_sm.render(
            f"Your last bonsai {state}.  [ENTER] Grow a new one", True, DIM)
        blit_centred(surf, msg, bot + 8)
    else:
        msg = font_sm.render("[ENTER]  Begin growing your bonsai", True, FG)
        blit_centred(surf, msg, bot + 8)

    flavour = font_xs.render(
        "Growth needs BOTH water + light in range — timing matters, not just quantity.",
        True, DIM)
    blit_centred(surf, flavour, HEIGHT - 22)


# ── Game screen ────────────────────────────────────────────────────────────────

def draw_game(surf, font_lg, font_sm, font_xs, plant: PlantState, debug: bool):
    surf.fill(BG)

    # ── EST/EDT clock (top-right) ─────────────────────────────────────────────
    now_est   = datetime.now(TZ_EST)
    tz_label  = "EDT" if now_est.dst().seconds else "EST"
    clock_str = now_est.strftime(f"%I:%M %p {tz_label}")
    clk_img   = font_xs.render(clock_str, True, DIM)
    surf.blit(clk_img, (WIDTH - clk_img.get_width() - 8, 10))

    # ── Header ────────────────────────────────────────────────────────────────
    title = font_lg.render("TEMPORAL BONSAI", True, ACCENT)
    blit_centred(surf, title, 8)

    if plant.dead:
        stage_str = "*** DEAD ***"
        stage_col = RED
    elif plant.won:
        stage_str = "BLOOMING  — your bonsai is complete!"
        stage_col = ACCENT
    else:
        stage_str = STAGE_NAMES[plant.stage]
        stage_col = FG

    stage_img = font_sm.render(stage_str, True, stage_col)
    blit_centred(surf, stage_img, 32)

    # ── Procedural bonsai ─────────────────────────────────────────────────────
    bonsai_surf = get_bonsai_surf(plant.stage, plant.seed, font_sm)
    bx = WIDTH // 2 - bonsai_surf.get_width() // 2
    art_top = 52
    surf.blit(bonsai_surf, (bx, art_top))
    # Dim the tree when dead by drawing a semi-opaque rect over it
    if plant.dead:
        tint = pygame.Surface(bonsai_surf.get_size())
        tint.fill((40, 10, 10))
        tint.set_alpha(120)
        surf.blit(tint, (bx, art_top))
    art_bot = art_top + bonsai_surf.get_height()

    # ── Resource hints (moisture + sunlight) ──────────────────────────────────
    m_label, m_col = plant.moisture_hint()
    s_label, s_col = plant.sun_hint()
    m_img = font_sm.render(f"Water: {m_label}", True, m_col)
    s_img = font_sm.render(f"Light: {s_label}", True, s_col)
    hint_y = art_bot + 4
    blit_centred(surf, m_img, hint_y)
    blit_centred(surf, s_img, hint_y + 18)

    # ── Growth progress bar ───────────────────────────────────────────────────
    bar_w = 220
    bar_x = WIDTH // 2 - bar_w // 2
    bar_y = HEIGHT - 58

    if not plant.dead:
        pct     = plant.stage_progress()
        bar_col = ACCENT if plant.won else FG
        draw_bar(surf, bar_x, bar_y, bar_w, 10, pct, bar_col)
        prog_lbl = font_xs.render("Growth progress", True, DIM)
        surf.blit(prog_lbl, (bar_x, bar_y - 16))

    # ── Controls ──────────────────────────────────────────────────────────────
    ctrl = font_xs.render("[W] Water    [S] Sunlight    [D] Debug    [R] Restart", True, DIM)
    blit_centred(surf, ctrl, HEIGHT - 34)

    # ── Debug overlay (hidden state) ──────────────────────────────────────────
    if debug:
        p         = plant.params
        mlo, mhi  = p["optimal_range"]
        slo, shi  = p["sun_optimal"]
        threshold = p["growth_time"] * (plant.stage + 1)
        save_ts = "unsaved"
        try:
            if SAVE_PATH.exists():
                d = json.loads(SAVE_PATH.read_text())
                saved_est = datetime.fromisoformat(d["saved_utc"]).astimezone(TZ_EST)
                tz_lbl    = "EDT" if saved_est.dst().seconds else "EST"
                save_ts   = saved_est.strftime(f"%m/%d %I:%M %p {tz_lbl}")
        except Exception:
            pass
        lines = [
            "[ DEBUG — HIDDEN STATE ]",
            f"  Moisture       : {plant.moisture:6.1f}  (opt {mlo}–{mhi}, over>{p['overwater_thresh']})",
            f"  Sunlight       : {plant.sunlight:6.1f}  (opt {slo}–{shi}, over>{p['overlight_thresh']})",
            f"  Time in opt    : {plant.time_in_optimal:6.1f} s  (both in range)",
            f"  Stage threshold: {threshold:6.1f} s",
            f"  Damage         : {plant.damage:6.1f} / {p['lethal_damage']}",
            f"  Water decay    : {p['decay_rate']} / s",
            f"  Sun decay      : {p['sun_decay_rate']} / s",
            f"  Last saved     : {save_ts}",
        ]
        panel_h = len(lines) * 17 + 10
        panel   = pygame.Surface((320, panel_h))
        panel.fill((0, 0, 0))
        panel.set_alpha(200)
        surf.blit(panel, (6, 54))
        for k, line in enumerate(lines):
            col = ACCENT if k == 0 else WHITE
            img = font_xs.render(line, True, col)
            surf.blit(img, (12, 58 + k * 17))


# ── Main loop ──────────────────────────────────────────────────────────────────

async def main():
    pygame.init()
    surf  = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("Temporal Plant")
    clock = pygame.time.Clock()

    font_lg = pygame.font.SysFont("monospace", 20, bold=True)
    font_sm = pygame.font.SysFont("monospace", 14)
    font_xs = pygame.font.SysFont("monospace", 12)

    screen      = "title"
    plant       = None
    debug       = False
    saved_plant = load_plant()
    last_save   = time.monotonic()
    # Preview surface for the title screen (fixed seed, stage 4)
    preview_surf = get_bonsai_surf(4, 77777, font_sm)

    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                if plant is not None:
                    save_plant(plant)
                pygame.quit()
                return

            # ── Title screen ───────────────────────────────────────────────────
            if screen == "title":
                start_new = False
                do_continue = False
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_c:
                        do_continue = True
                    elif event.key in (pygame.K_RETURN, pygame.K_n):
                        start_new = True
                elif event.type == pygame.MOUSEBUTTONDOWN:
                    # Click: continue if a live save exists, otherwise start new
                    if saved_plant and not saved_plant.dead and not saved_plant.won:
                        do_continue = True
                    else:
                        start_new = True

                if do_continue and saved_plant and \
                        not saved_plant.dead and not saved_plant.won:
                    plant           = saved_plant
                    plant.last_tick = time.monotonic()
                    saved_plant     = None
                    debug           = False
                    screen          = "game"
                elif start_new:
                    plant  = PlantState("Bonsai")
                    delete_save()
                    debug  = False
                    screen = "game"

            # ── Game screen ────────────────────────────────────────────────────
            elif screen == "game":
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_w:
                        plant.water()
                    elif event.key == pygame.K_s:
                        plant.expose_to_sun()
                    elif event.key == pygame.K_d:
                        debug = not debug
                    elif event.key == pygame.K_r:
                        save_plant(plant)
                        saved_plant = plant
                        screen      = "title"
                        plant       = None
                elif event.type == pygame.MOUSEBUTTONDOWN:
                    plant.water()

        # ── Auto-save ─────────────────────────────────────────────────────────
        now_mono = time.monotonic()
        if plant is not None and now_mono - last_save >= SAVE_INTERVAL:
            save_plant(plant)
            last_save = now_mono

        # ── Update & render ────────────────────────────────────────────────────
        if screen == "title":
            draw_title(surf, font_lg, font_sm, font_xs, saved_plant, preview_surf)
        elif screen == "game" and plant is not None:
            plant.tick()
            draw_game(surf, font_lg, font_sm, font_xs, plant, debug)

        pygame.display.flip()
        clock.tick(30)
        await asyncio.sleep(0)   # yield to browser event loop (required by Pygbag)


asyncio.run(main())
