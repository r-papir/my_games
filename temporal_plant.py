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
  R           — Return to plant selection
  LEFT/RIGHT  — Navigate plant selection
  ENTER       — Confirm selection

Run locally:   python temporal_plant.py
Run in browser: python -m pygbag temporal_plant.py
"""

import asyncio
import time
import pygame

# ── Display ────────────────────────────────────────────────────────────────────

WIDTH, HEIGHT = 640, 480

# ── Colour palette ─────────────────────────────────────────────────────────────

BG     = ( 15,  20,  10)
FG     = (180, 220, 140)
DIM    = ( 70, 100,  50)
ACCENT = (220, 200,  80)
RED    = (210,  60,  60)
BLUE   = (100, 160, 210)
WHITE  = (240, 240, 240)

# ── ASCII art (5 growth stages per plant) ──────────────────────────────────────
# Keep each line ≤ 22 chars; aim for ≤ 10 lines per stage.

ART = {
    "Cactus": [
        # 0 — Seed
        [
            "     .  .      ",
            "    (    )     ",
            "     `--'      ",
            "   ___||___    ",
            "  |   ||   |   ",
        ],
        # 1 — Sprout
        [
            "      |        ",
            "     (|)       ",
            "      |        ",
            "   ___||___    ",
            "  |   ||   |   ",
        ],
        # 2 — Young
        [
            "      _|_      ",
            "     (|||)     ",
            "  --(|||)--    ",
            "      |||      ",
            "   ___|___     ",
            "  |   |   |    ",
        ],
        # 3 — Mature
        [
            "     _|||_     ",
            " _  (|||||)  _ ",
            "(|)--(||||)--(|)",
            " |   |||||   | ",
            " |   |||||   | ",
            "    _|||||_    ",
            "   |  |||  |   ",
        ],
        # 4 — Blooming
        [
            "  * _|||_ *    ",
            " * (|||||) *   ",
            "(|)--(||||)--(|)",
            " |   ||||    | ",
            " |   ||||    | ",
            "    _|||||_    ",
            "   |  |||  |   ",
            "      ~~~      ",
        ],
    ],

    "Fern": [
        # 0 — Seed
        [
            "     ( . )     ",
            "      `~'      ",
            "   ___|___     ",
            "  |       |    ",
        ],
        # 1 — Sprout
        [
            "      /\\       ",
            "     /  \\      ",
            "      ||       ",
            "   ___|___     ",
            "  |       |    ",
        ],
        # 2 — Young
        [
            "   /\\  /\\  /\\ ",
            "  /  \\/  \\/  \\",
            "      |||      ",
            "      |||      ",
            "   ___|___     ",
            "  |       |    ",
        ],
        # 3 — Mature
        [
            " _/\\/\\_/\\/\\_  ",
            "/  V    V   V\\  ",
            "   \\   |||  /   ",
            "    \\  ||| /    ",
            "       |||      ",
            "    ___|___     ",
            "   |       |    ",
        ],
        # 4 — Blooming
        [
            "~_/\\/\\_/\\/\\_~ ",
            "/  V    V   V\\  ",
            "  *\\   |||  /*  ",
            "    \\  ||| /    ",
            "    *  |||  *   ",
            "    ___|___     ",
            "   |       |    ",
            "    ~~~~~~~     ",
        ],
    ],

    "Peace Lily": [
        # 0 — Seed
        [
            "      o        ",
            "     (o)       ",
            "   ___|___     ",
            "  |       |    ",
        ],
        # 1 — Sprout
        [
            "      /        ",
            "     ( )       ",
            "      |        ",
            "   ___|___     ",
            "  |       |    ",
        ],
        # 2 — Young
        [
            "    /   \\      ",
            "   ( ) ( )     ",
            "    \\ | /      ",
            "     \\|/       ",
            "   ___|___     ",
            "  |       |    ",
        ],
        # 3 — Mature
        [
            "  /   |   \\    ",
            " /    |    \\   ",
            "(  )  |  (  )  ",
            " \\    |    /   ",
            "  \\   |   /    ",
            "   ___|___     ",
            "  |       |    ",
        ],
        # 4 — Blooming
        [
            "  /* |  \\      ",
            " /   |*  \\     ",
            "(*(*)|(*))     ",
            " \\   |*  /     ",
            "  \\* |  /      ",
            "   \\ | /       ",
            "   ___|___     ",
            "  |       |    ",
            "   ~~~~~~~     ",
        ],
    ],

    "Tulip": [
        # 0 — Seed
        [
            "      .        ",
            "     (.)       ",
            "   ___|___     ",
            "  |       |    ",
        ],
        # 1 — Sprout
        [
            "      |        ",
            "      |        ",
            "   ___|___     ",
            "  |       |    ",
        ],
        # 2 — Young
        [
            "     /|\\       ",
            "    / | \\      ",
            "      |        ",
            "      |        ",
            "   ___|___     ",
            "  |       |    ",
        ],
        # 3 — Mature
        [
            "    _/ \\_      ",
            "   (     )     ",
            "    \\___/      ",
            "      |        ",
            "      |        ",
            "   ___|___     ",
            "  |       |    ",
        ],
        # 4 — Blooming
        [
            "   _/***\\_     ",
            "  (* * * *)    ",
            "   \\*****/     ",
            "      |        ",
            "      |        ",
            "   ___|___     ",
            "  |       |    ",
            "   ~~~~~~~     ",
        ],
    ],
}

STAGE_NAMES = ["Seed", "Sprout", "Young", "Mature", "Blooming"]
PLANT_NAMES = ["Cactus", "Fern", "Peace Lily", "Tulip"]

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
    "Cactus": {
        "decay_rate":        0.3,
        "water_amount":      15,
        "optimal_range":     (20, 55),
        "overwater_thresh":  65,
        "sun_decay_rate":    1.5,
        "sun_amount":        30,
        "sun_optimal":       (55, 90),   # loves direct sun
        "overlight_thresh":  96,
        "growth_time":       45,
        "damage_rate":       1.0,
        "lethal_damage":     150,
    },
    "Fern": {
        "decay_rate":        2.0,
        "water_amount":      25,
        "optimal_range":     (45, 80),
        "overwater_thresh":  90,
        "sun_decay_rate":    0.7,
        "sun_amount":        18,
        "sun_optimal":       (15, 50),   # prefers dappled shade
        "overlight_thresh":  62,
        "growth_time":       30,
        "damage_rate":       2.5,
        "lethal_damage":     100,
    },
    "Peace Lily": {
        "decay_rate":        1.0,
        "water_amount":      20,
        "optimal_range":     (35, 70),
        "overwater_thresh":  80,
        "sun_decay_rate":    0.9,
        "sun_amount":        20,
        "sun_optimal":       (20, 58),   # indirect light
        "overlight_thresh":  70,
        "growth_time":       35,
        "damage_rate":       1.5,
        "lethal_damage":     120,
    },
    "Tulip": {
        "decay_rate":        1.5,
        "water_amount":      22,
        "optimal_range":     (30, 65),
        "overwater_thresh":  75,
        "sun_decay_rate":    1.2,
        "sun_amount":        25,
        "sun_optimal":       (40, 78),   # good direct sun, some shade ok
        "overlight_thresh":  88,
        "growth_time":       40,
        "damage_rate":       2.0,
        "lethal_damage":     110,
    },
}

# ── Game state ─────────────────────────────────────────────────────────────────

class PlantState:
    def __init__(self, name: str):
        p = PLANT_PARAMS[name]
        self.name            = name
        self.params          = p
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


# ── Drawing helpers ────────────────────────────────────────────────────────────

def blit_centred(surf, img, cy_or_y, *, centre_x=True, x=0):
    if centre_x:
        surf.blit(img, (WIDTH // 2 - img.get_width() // 2, cy_or_y))
    else:
        surf.blit(img, (x, cy_or_y))


def draw_ascii(surf, lines, font, cx, top_y, color=FG):
    """Render ASCII art list centred at cx, top-aligned at top_y. Returns bottom y."""
    _, ch = font.size("M")
    y = top_y
    for line in lines:
        img = font.render(line, True, color)
        surf.blit(img, (cx - img.get_width() // 2, y))
        y += ch
    return y


def draw_bar(surf, x, y, w, h, pct, fill_col, border_col=FG, bg_col=DIM):
    pygame.draw.rect(surf, bg_col, (x, y, w, h))
    if pct > 0:
        pygame.draw.rect(surf, fill_col, (x, y, int(w * pct), h))
    pygame.draw.rect(surf, border_col, (x, y, w, h), 1)


# ── Selection screen ───────────────────────────────────────────────────────────

BOX_W, BOX_H = 136, 170
BOX_GAP      = 10
SEL_BY       = 115   # top-y of plant boxes

def _box_x(i):
    total_w = len(PLANT_NAMES) * BOX_W + (len(PLANT_NAMES) - 1) * BOX_GAP
    return WIDTH // 2 - total_w // 2 + i * (BOX_W + BOX_GAP)


def draw_selection(surf, font_lg, font_sm, font_xs, selected_idx, hover_idx):
    surf.fill(BG)

    title = font_lg.render("TEMPORAL PLANT", True, ACCENT)
    blit_centred(surf, title, 14)

    sub = font_xs.render("choose your plant  —  LEFT/RIGHT then ENTER  or  click", True, DIM)
    blit_centred(surf, sub, 44)

    for i, name in enumerate(PLANT_NAMES):
        bx = _box_x(i)
        selected = (i == selected_idx)
        hovered  = (i == hover_idx)
        border   = ACCENT if selected else (FG if hovered else DIM)
        border_w = 3 if selected else 1

        pygame.draw.rect(surf, BG,     (bx, SEL_BY, BOX_W, BOX_H))
        pygame.draw.rect(surf, border, (bx, SEL_BY, BOX_W, BOX_H), border_w)

        # Preview: show stage-4 (blooming) art
        art = ART[name][4]
        _, ch = font_xs.size("M")
        art_px  = len(art) * ch
        art_top = SEL_BY + (BOX_H - art_px - 20) // 2
        art_col = ACCENT if selected else FG
        for j, line in enumerate(art):
            img = font_xs.render(line, True, art_col)
            surf.blit(img, (bx + BOX_W // 2 - img.get_width() // 2,
                            art_top + j * ch))

        label = font_sm.render(name, True, ACCENT if selected else FG)
        surf.blit(label, (bx + BOX_W // 2 - label.get_width() // 2,
                          SEL_BY + BOX_H - 20))

    # Brief temporal-logic flavour text
    flavour = [
        "Growth requires BOTH water and light in range simultaneously.",
        "Timing of each action matters — not just total quantity.",
    ]
    for k, line in enumerate(flavour):
        img = font_xs.render(line, True, DIM)
        blit_centred(surf, img, SEL_BY + BOX_H + 18 + k * 16)


# ── Game screen ────────────────────────────────────────────────────────────────

def draw_game(surf, font_lg, font_sm, font_xs, plant: PlantState, debug: bool):
    surf.fill(BG)

    # ── Header ────────────────────────────────────────────────────────────────
    title = font_lg.render(f"TEMPORAL PLANT  //  {plant.name}", True, ACCENT)
    blit_centred(surf, title, 8)

    if plant.dead:
        stage_str = "*** DEAD ***"
        stage_col = RED
    elif plant.won:
        stage_str = f"BLOOMING  — you grew a {plant.name}!"
        stage_col = ACCENT
    else:
        stage_str = STAGE_NAMES[plant.stage]
        stage_col = FG

    stage_img = font_sm.render(stage_str, True, stage_col)
    blit_centred(surf, stage_img, 34)

    # ── ASCII art ─────────────────────────────────────────────────────────────
    art_col   = RED if plant.dead else (ACCENT if plant.won else FG)
    art_lines = ART[plant.name][plant.stage]
    art_bot   = draw_ascii(surf, art_lines, font_sm, WIDTH // 2, 62, art_col)

    # ── Resource hints (moisture + sunlight) ──────────────────────────────────
    m_label, m_col = plant.moisture_hint()
    s_label, s_col = plant.sun_hint()
    m_img = font_sm.render(f"Water: {m_label}", True, m_col)
    s_img = font_sm.render(f"Light: {s_label}", True, s_col)
    hint_y = art_bot + 6
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
        lines = [
            "[ DEBUG — HIDDEN STATE ]",
            f"  Moisture       : {plant.moisture:6.1f}  (opt {mlo}–{mhi}, over>{p['overwater_thresh']})",
            f"  Sunlight       : {plant.sunlight:6.1f}  (opt {slo}–{shi}, over>{p['overlight_thresh']})",
            f"  Time in opt    : {plant.time_in_optimal:6.1f} s  (both in range)",
            f"  Stage threshold: {threshold:6.1f} s",
            f"  Damage         : {plant.damage:6.1f} / {p['lethal_damage']}",
            f"  Water decay    : {p['decay_rate']} / s",
            f"  Sun decay      : {p['sun_decay_rate']} / s",
        ]
        panel_h = len(lines) * 17 + 10
        panel   = pygame.Surface((320, panel_h), pygame.SRCALPHA)
        panel.fill((0, 0, 0, 185))
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

    screen       = "select"
    selected_idx = 0
    hover_idx    = -1
    plant        = None
    debug        = False

    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                return

            # ── Selection screen ───────────────────────────────────────────────
            if screen == "select":
                if event.type == pygame.KEYDOWN:
                    if event.key in (pygame.K_LEFT, pygame.K_a):
                        selected_idx = (selected_idx - 1) % len(PLANT_NAMES)
                    elif event.key in (pygame.K_RIGHT, pygame.K_d):
                        selected_idx = (selected_idx + 1) % len(PLANT_NAMES)
                    elif event.key == pygame.K_RETURN:
                        plant  = PlantState(PLANT_NAMES[selected_idx])
                        debug  = False
                        screen = "game"
                elif event.type == pygame.MOUSEMOTION:
                    mx, my = event.pos
                    hover_idx = -1
                    for i in range(len(PLANT_NAMES)):
                        bx = _box_x(i)
                        if bx <= mx <= bx + BOX_W and SEL_BY <= my <= SEL_BY + BOX_H:
                            hover_idx = i
                elif event.type == pygame.MOUSEBUTTONDOWN:
                    mx, my = event.pos
                    for i in range(len(PLANT_NAMES)):
                        bx = _box_x(i)
                        if bx <= mx <= bx + BOX_W and SEL_BY <= my <= SEL_BY + BOX_H:
                            selected_idx = i
                            plant  = PlantState(PLANT_NAMES[i])
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
                        screen = "select"
                        plant  = None
                elif event.type == pygame.MOUSEBUTTONDOWN:
                    plant.water()

        # ── Update & render ────────────────────────────────────────────────────
        if screen == "select":
            draw_selection(surf, font_lg, font_sm, font_xs, selected_idx, hover_idx)
        elif screen == "game" and plant is not None:
            plant.tick()
            draw_game(surf, font_lg, font_sm, font_xs, plant, debug)

        pygame.display.flip()
        clock.tick(30)
        await asyncio.sleep(0)   # yield to browser event loop (required by Pygbag)


asyncio.run(main())
