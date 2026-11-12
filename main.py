"""NEON KEYS - a falling-tile rhythm tap game (pygame).

Controls: D F J K (or mouse click on a lane). Tap the lowest glowing tile.
Wrong lane or a tile slipping past the bottom ends the run.
"""
import array
import colorsys
import json
import math
import os
import random
import sys

import pygame

W, H = 480, 800
LANES = 4
LW = W // LANES
TH = 190                      # tile height
PAD = 5
KEYS = [pygame.K_d, pygame.K_f, pygame.K_j, pygame.K_k]
KEY_NAMES = "DFJK"
SR = 22050
BEST_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "best.json")
TEST = bool(os.environ.get("NK_TEST"))


# ---------------------------------------------------------------- audio
def synth(freqs, dur=0.8, decay=4.5, vol=0.28):
    n = int(SR * dur)
    buf = array.array("h", [0]) * n
    for i in range(n):
        t = i / SR
        env = math.exp(-decay * t) * min(1.0, t * 250)
        v = 0.0
        for f in freqs:
            w = 2 * math.pi * f * t
            v += math.sin(w) + 0.45 * math.sin(2 * w) + 0.2 * math.sin(3 * w) + 0.08 * math.sin(4 * w)
        buf[i] = int(max(-1, min(1, v * env * vol / len(freqs))) * 32000)
    return pygame.mixer.Sound(buffer=buf.tobytes())


PENTA = [60, 62, 64, 67, 69, 72, 74, 76, 79, 81, 84]          # free-play scale (MIDI)
# Public-domain melodies as MIDI note numbers; one tile = one note, looped.
SONGS = [
    ("FREE PLAY", None),
    ("TWINKLE STAR", [60, 60, 67, 67, 69, 69, 67, 65, 65, 64, 64, 62, 62, 60,
                      67, 67, 65, 65, 64, 64, 62, 67, 67, 65, 65, 64, 64, 62,
                      60, 60, 67, 67, 69, 69, 67, 65, 65, 64, 64, 62, 62, 60]),
    ("ODE TO JOY", [64, 64, 65, 67, 67, 65, 64, 62, 60, 60, 62, 64, 64, 62, 62,
                    64, 64, 65, 67, 67, 65, 64, 62, 60, 60, 62, 64, 62, 60, 60,
                    62, 62, 64, 60, 62, 64, 65, 64, 60, 62, 64, 65, 64, 62, 60, 62, 55,
                    64, 64, 65, 67, 67, 65, 64, 62, 60, 60, 62, 64, 62, 60, 60]),
    ("FUR ELISE", [76, 75, 76, 75, 76, 71, 74, 72, 69, 60, 64, 69, 71, 64, 68, 71, 72,
                   64, 76, 75, 76, 75, 76, 71, 74, 72, 69, 60, 64, 69, 71, 64, 72, 71, 69]),
    ("CANON IN D", [78, 76, 74, 73, 71, 69, 71, 73, 74, 73, 71, 69, 67, 66, 67, 64,
                    62, 66, 69, 67, 66, 62, 66, 64, 62, 59, 62, 69, 67, 71, 69, 67]),
]


SONGS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "songs")


def load_midi(path):
    """Minimal Standard MIDI File reader -> melody as a list of MIDI note numbers.

    Takes the highest note at each onset from the most melody-like track/channel
    (drum channel ignored). Timing is dropped: one tile plays one note.
    """
    with open(path, "rb") as f:
        d = f.read()
    if d[:4] != b"MThd":
        raise ValueError("not a MIDI file")
    ntr = int.from_bytes(d[10:12], "big")
    pos = 8 + int.from_bytes(d[4:8], "big")
    groups = {}

    def varlen(p):
        v = 0
        while True:
            b = d[p]
            p += 1
            v = (v << 7) | (b & 0x7F)
            if b < 0x80:
                return v, p

    for tr in range(ntr):
        if d[pos:pos + 4] != b"MTrk":
            break
        p = pos + 8
        end = pos = p + int.from_bytes(d[pos + 4:pos + 8], "big")
        t = status = 0
        while p < end:
            dv, p = varlen(p)
            t += dv
            if d[p] >= 0x80:
                status = d[p]
                p += 1
            if status == 0xFF:
                ln, p = varlen(p + 1)
                p += ln
            elif status in (0xF0, 0xF7):
                ln, p = varlen(p)
                p += ln
            elif status & 0xF0 in (0xC0, 0xD0):
                p += 1
            else:
                note, vel = d[p], d[p + 1]
                p += 2
                ch = status & 0x0F
                if status & 0xF0 == 0x90 and vel > 0 and ch != 9:
                    g = groups.setdefault((tr, ch), {})
                    g[t] = max(g.get(t, 0), note)
    if not groups:
        raise ValueError("no notes")
    most = max(len(g) for g in groups.values())
    cands = [g for g in groups.values() if len(g) >= most * 0.3]
    g = max(cands, key=lambda g: sum(g.values()) / len(g))
    seq = []
    for t in sorted(g):
        n = g[t]
        while n < 48:
            n += 12
        while n > 96:
            n -= 12
        seq.append(n)
    if len(seq) < 4:
        raise ValueError("too few notes")
    return seq


def load_user_songs():
    try:
        os.makedirs(SONGS_DIR, exist_ok=True)
        files = sorted(f for f in os.listdir(SONGS_DIR) if f.lower().endswith((".mid", ".midi")))
    except OSError:
        return
    for f in files:
        try:
            SONGS.append((os.path.splitext(f)[0][:22].upper(), load_midi(os.path.join(SONGS_DIR, f))))
        except Exception as e:
            print(f"[songs] skipped {f}: {e}")


def build_sounds():
    pitches = set(PENTA)
    for _, seq in SONGS:
        pitches.update(seq or [])
    notes = {m: synth([440.0 * 2 ** ((m - 69) / 12)]) for m in pitches}
    fail = synth([98.0, 103.8, 146.8], dur=1.0, decay=3.0, vol=0.5)
    return notes, fail


# ---------------------------------------------------------------- gfx helpers
def hue_rgb(h, s=0.75, v=1.0):
    r, g, b = colorsys.hsv_to_rgb(h % 1.0, s, v)
    return int(r * 255), int(g * 255), int(b * 255)


def make_tile(hue, w, h):
    surf = pygame.Surface((w, h), pygame.SRCALPHA)
    top, bot = hue_rgb(hue, 0.55, 1.0), hue_rgb(hue + 0.08, 0.85, 0.75)
    for y in range(h):
        k = y / h
        c = [int(top[i] + (bot[i] - top[i]) * k) for i in range(3)]
        pygame.draw.line(surf, c, (0, y), (w, y))
    # glossy highlight
    gloss = pygame.Surface((w, h // 3), pygame.SRCALPHA)
    gloss.fill((255, 255, 255, 38))
    surf.blit(gloss, (0, 0))
    mask = pygame.Surface((w, h), pygame.SRCALPHA)
    pygame.draw.rect(mask, (255, 255, 255, 255), mask.get_rect(), border_radius=16)
    surf.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
    pygame.draw.rect(surf, (255, 255, 255, 150), surf.get_rect(), 2, border_radius=16)
    return surf


def make_background():
    bg = pygame.Surface((W, H))
    for y in range(H):
        k = y / H
        pygame.draw.line(bg, (int(10 + 14 * k), int(8 + 6 * k), int(28 + 30 * k)), (0, y), (W, y))
    return bg


class Game:
    def __init__(self):
        pygame.mixer.pre_init(SR, -16, 1, 256)
        pygame.init()
        pygame.display.set_caption("NEON KEYS")
        self.screen = pygame.display.set_mode((W, H))
        self.canvas = pygame.Surface((W, H))
        self.clock = pygame.time.Clock()
        load_user_songs()
        self.f_song = pygame.font.SysFont("applesdgothicneo,malgungothic,arial", 28, bold=True)
        try:
            self.notes, self.fail_snd = build_sounds()
        except pygame.error:
            self.notes, self.fail_snd = {}, None
        self.f_big = pygame.font.SysFont("avenirnext,helveticaneue,arial", 84, bold=True)
        self.f_mid = pygame.font.SysFont("avenirnext,helveticaneue,arial", 34, bold=True)
        self.f_sm = pygame.font.SysFont("avenirnext,helveticaneue,arial", 20, bold=True)
        self.bg = make_background()
        self.tile_cache = {}
        self.stars = [[random.uniform(0, W), random.uniform(0, H), random.uniform(10, 45)] for _ in range(60)]
        self.bests = self.load_best()
        self.song_i = 0
        self.sel_rect = pygame.Rect(30, 296, W - 60, 60)
        self.time = 0.0
        self.reset()

    # ---------- persistence (best score per song)
    def load_best(self):
        try:
            with open(BEST_FILE) as f:
                b = json.load(f)["best"]
            return b if isinstance(b, dict) else {SONGS[0][0]: int(b)}
        except Exception:
            return {}

    def save_best(self):
        try:
            with open(BEST_FILE, "w") as f:
                json.dump({"best": self.bests}, f)
        except OSError:
            pass

    @property
    def best(self):
        return self.bests.get(SONGS[self.song_i][0], 0)

    def change_song(self, d):
        if self.state != "ready":
            return
        self.song_i = (self.song_i + d) % len(SONGS)
        seq = SONGS[self.song_i][1]
        if self.notes:
            self.notes[seq[0] if seq else 72].play()

    # ---------- state
    def reset(self):
        self.state = "ready"
        self.score = 0
        self.tiles = []
        self.particles = []
        self.flashes = []            # [lane, life, color]
        self.count = 0
        self.note_i = 5
        self.note_pos = 0
        self.pop = 0.0
        self.shake = 0.0
        self.over_t = 0.0
        self.wrong = None            # (lane, y) red marker
        self.new_best = False
        self.key_glow = [0.0] * LANES
        self.spawn(first_y=H - TH - 90)

    def spawn(self, first_y=None):
        if first_y is not None:
            self.add_tile(first_y)
        while self.tiles[-1]["y"] > -TH * 2:
            self.add_tile(self.tiles[-1]["y"] - TH)

    def add_tile(self, y):
        prev = self.tiles[-1]["lane"] if self.tiles else -1
        lane = random.choice([l for l in range(LANES) if l != prev])
        self.tiles.append({"lane": lane, "y": y, "hit": False, "fade": 1.0, "n": self.count})
        self.count += 1

    def tile_surf(self, n):
        key = n % 36
        if key not in self.tile_cache:
            self.tile_cache[key] = make_tile(0.52 + key / 36, LW - PAD * 2, TH - PAD * 2)
        return self.tile_cache[key]

    @property
    def speed(self):
        return min(1500, 430 + self.score * 9)

    def target(self):
        for t in self.tiles:
            if not t["hit"]:
                return t
        return None

    # ---------- input
    def tap(self, lane):
        if self.state == "over":
            return
        self.key_glow[lane] = 1.0
        t = self.target()
        if t is None:
            return
        if t["lane"] == lane and t["y"] + TH > 0:
            if self.state == "ready":
                self.state = "play"
            self.hit(t)
        elif self.state == "play":
            self.game_over((lane, t["y"]))

    def hit(self, t):
        t["hit"] = True
        self.score += 1
        self.pop = 1.0
        col = hue_rgb(0.52 + (t["n"] % 36) / 36, 0.5)
        self.flashes.append([t["lane"], 1.0, col])
        cx, cy = t["lane"] * LW + LW / 2, max(40, min(H - 40, t["y"] + TH / 2))
        for _ in range(16):
            a, s = random.uniform(0, math.tau), random.uniform(90, 420)
            self.particles.append([cx, cy, math.cos(a) * s, math.sin(a) * s, 1.0, col, random.uniform(3, 7)])
        if self.notes:
            seq = SONGS[self.song_i][1]
            if seq:
                midi = seq[self.note_pos % len(seq)]
                self.note_pos += 1
            else:
                self.note_i = max(0, min(len(PENTA) - 1, self.note_i + random.choice([-2, -1, -1, 1, 1, 2])))
                midi = PENTA[self.note_i]
            self.notes[midi].play()

    def game_over(self, wrong):
        self.state = "over"
        self.wrong = wrong
        self.shake = 1.0
        self.over_t = 0.0
        if self.fail_snd:
            self.fail_snd.play()
        if self.score > self.best:
            self.bests[SONGS[self.song_i][0]] = self.score
            self.new_best = True
            self.save_best()

    # ---------- update
    def update(self, dt):
        self.time += dt
        for s in self.stars:
            s[1] += s[2] * dt
            if s[1] > H:
                s[0], s[1] = random.uniform(0, W), 0
        if self.state == "play":
            dy = self.speed * dt
            for t in self.tiles:
                t["y"] += dy
            t = self.target()
            if t and t["y"] > H - TH * 0.3:
                self.game_over((t["lane"], t["y"]))
            self.spawn()
        for t in self.tiles:
            if t["hit"]:
                t["fade"] -= dt * 5
        self.tiles = [t for t in self.tiles if not (t["hit"] and t["fade"] <= 0 and t["y"] > -TH) or not t["hit"]]
        self.tiles = [t for t in self.tiles if t["y"] < H + 10 or not t["hit"]]
        for p in self.particles:
            p[0] += p[2] * dt
            p[1] += p[3] * dt
            p[3] += 700 * dt
            p[4] -= dt * 1.8
        self.particles = [p for p in self.particles if p[4] > 0]
        for f in self.flashes:
            f[1] -= dt * 4
        self.flashes = [f for f in self.flashes if f[1] > 0]
        self.pop = max(0, self.pop - dt * 6)
        self.shake = max(0, self.shake - dt * 2.5)
        self.key_glow = [max(0, g - dt * 5) for g in self.key_glow]
        if self.state == "over":
            self.over_t += dt

    # ---------- draw
    def text(self, font, s, color, center, alpha=255, scale=1.0, shadow=True):
        img = font.render(s, True, color)
        if scale != 1.0:
            img = pygame.transform.smoothscale(img, (int(img.get_width() * scale), int(img.get_height() * scale)))
        if shadow:
            sh = font.render(s, True, (0, 0, 0))
            if scale != 1.0:
                sh = pygame.transform.smoothscale(sh, img.get_size())
            sh.set_alpha(alpha // 2)
            self.canvas.blit(sh, sh.get_rect(center=(center[0] + 2, center[1] + 3)))
        img.set_alpha(alpha)
        self.canvas.blit(img, img.get_rect(center=center))

    def draw(self):
        c = self.canvas
        c.blit(self.bg, (0, 0))
        for x, y, sp in self.stars:
            v = int(60 + sp * 3)
            c.fill((v, v, min(255, v + 40)), (x, y, 2, 2))
        ov = pygame.Surface((W, H), pygame.SRCALPHA)
        for lane, life, col in self.flashes:
            pygame.draw.rect(ov, (*col, int(70 * life)), (lane * LW, 0, LW, H))
        for i in range(1, LANES):
            pygame.draw.line(ov, (255, 255, 255, 28), (i * LW, 0), (i * LW, H))
        c.blit(ov, (0, 0))

        tgt = self.target()
        for t in self.tiles:
            if t["y"] > H or t["y"] + TH < 0:
                continue
            surf = self.tile_surf(t["n"])
            x, y = t["lane"] * LW + PAD, t["y"] + PAD
            if t["hit"]:
                if t["fade"] <= 0:
                    continue
                s = surf.copy()
                s.set_alpha(int(110 * t["fade"]))
                c.blit(s, (x, y))
            else:
                c.blit(surf, (x, y))
                if t is tgt and self.state != "over":
                    pulse = 0.5 + 0.5 * math.sin(self.time * 8)
                    pygame.draw.rect(c, (255, 255, 255), (x - 2, y - 2, LW - PAD * 2 + 4, TH - PAD * 2 + 4),
                                     2 + int(2 * pulse), border_radius=18)
                    if self.state == "ready":
                        self.text(self.f_mid, "TAP", (20, 20, 40), (x + LW / 2 - PAD, y + TH / 2 - PAD), shadow=False)

        if self.wrong:
            lane, y = self.wrong
            a = int(150 + 100 * math.sin(self.time * 18))
            red = pygame.Surface((LW - PAD * 2, TH - PAD * 2), pygame.SRCALPHA)
            pygame.draw.rect(red, (255, 50, 80, a), red.get_rect(), border_radius=16)
            c.blit(red, (lane * LW + PAD, max(-TH + 40, min(H - TH, y)) + PAD))

        for x, y, _, _, life, col, r in self.particles:
            pygame.draw.circle(c, col, (int(x), int(y)), max(1, int(r * life)))

        # key hints
        for i in range(LANES):
            g = self.key_glow[i]
            pad = pygame.Surface((LW - 16, 44), pygame.SRCALPHA)
            pygame.draw.rect(pad, (255, 255, 255, int(26 + 150 * g)), pad.get_rect(), border_radius=12)
            pygame.draw.rect(pad, (255, 255, 255, 90), pad.get_rect(), 1, border_radius=12)
            c.blit(pad, (i * LW + 8, H - 54))
            self.text(self.f_sm, KEY_NAMES[i], (235, 235, 255), (i * LW + LW // 2, H - 32), shadow=False)

        # HUD
        self.text(self.f_big, str(self.score), (255, 255, 255), (W // 2, 78), scale=1 + 0.35 * self.pop)
        self.text(self.f_sm, f"BEST {self.best}", (170, 200, 255), (W // 2, 138))
        if self.state == "play":
            self.text(self.f_sm, f"{self.speed / TH:.1f} tiles/s", (140, 150, 190), (W - 70, 24), shadow=False)
        if self.state == "ready":
            box = pygame.Surface((W - 40, 190), pygame.SRCALPHA)
            pygame.draw.rect(box, (12, 10, 34, 215), box.get_rect(), border_radius=24)
            c.blit(box, (20, 196))
            self.text(self.f_mid, "NEON KEYS", hue_rgb(self.time * 0.15, 0.45), (W // 2, 230))
            self.text(self.f_sm, "D  F  J  K  or click  -  tap the glowing tile", (200, 205, 235), (W // 2, 268))
            r = self.sel_rect
            pill = pygame.Surface(r.size, pygame.SRCALPHA)
            pygame.draw.rect(pill, (255, 255, 255, 22), pill.get_rect(), border_radius=18)
            pygame.draw.rect(pill, (*hue_rgb(self.time * 0.15, 0.5), 200), pill.get_rect(), 2, border_radius=18)
            c.blit(pill, r.topleft)
            cy = r.centery
            pygame.draw.polygon(c, (255, 255, 255), [(r.left + 18, cy), (r.left + 34, cy - 11), (r.left + 34, cy + 11)])
            pygame.draw.polygon(c, (255, 255, 255), [(r.right - 18, cy), (r.right - 34, cy - 11), (r.right - 34, cy + 11)])
            self.text(self.f_song, SONGS[self.song_i][0], (255, 255, 255), (W // 2, cy))
            self.text(self.f_sm, f"LEFT / RIGHT : song {self.song_i + 1}/{len(SONGS)}   (add .mid to songs/)", (150, 160, 200), (W // 2, 372), shadow=False)

        if self.state == "over":
            k = min(1.0, self.over_t * 3)
            dim = pygame.Surface((W, H), pygame.SRCALPHA)
            dim.fill((5, 5, 15, int(170 * k)))
            c.blit(dim, (0, 0))
            panel = pygame.Surface((360, 300), pygame.SRCALPHA)
            pygame.draw.rect(panel, (24, 22, 52, int(235 * k)), panel.get_rect(), border_radius=28)
            pygame.draw.rect(panel, (*hue_rgb(self.time * 0.2, 0.6), int(255 * k)), panel.get_rect(), 3, border_radius=28)
            oy = int((1 - k) * 40)
            c.blit(panel, (W // 2 - 180, H // 2 - 150 + oy))
            a = int(255 * k)
            self.text(self.f_mid, "GAME OVER", (255, 90, 120), (W // 2, H // 2 - 105 + oy), a)
            self.text(self.f_song, SONGS[self.song_i][0], (200, 205, 235), (W // 2, H // 2 - 68 + oy), a, scale=0.7)
            self.text(self.f_big, str(self.score), (255, 255, 255), (W // 2, H // 2 - 20 + oy), a)
            if self.new_best:
                self.text(self.f_sm, "NEW BEST!", hue_rgb(self.time, 0.6), (W // 2, H // 2 + 45 + oy), a)
            else:
                self.text(self.f_sm, f"BEST {self.best}", (170, 200, 255), (W // 2, H // 2 + 45 + oy), a)
            if self.over_t > 0.5 and int(self.time * 2) % 2 == 0:
                self.text(self.f_sm, "SPACE / CLICK to retry", (230, 230, 250), (W // 2, H // 2 + 105 + oy))

        off = (0, 0)
        if self.shake > 0:
            m = self.shake * 14
            off = (random.uniform(-m, m), random.uniform(-m, m))
        self.screen.fill((0, 0, 0))
        self.screen.blit(c, off)
        pygame.display.flip()

    # ---------- loop
    def run(self):
        frame = 0
        while True:
            dt = min(self.clock.tick(120) / 1000, 0.033)
            for e in pygame.event.get():
                if e.type == pygame.QUIT or (e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE):
                    pygame.quit()
                    return
                if e.type == pygame.KEYDOWN:
                    if e.key in KEYS:
                        self.tap(KEYS.index(e.key))
                    elif e.key in (pygame.K_LEFT, pygame.K_UP):
                        self.change_song(-1)
                    elif e.key in (pygame.K_RIGHT, pygame.K_DOWN):
                        self.change_song(1)
                    elif e.key in (pygame.K_SPACE, pygame.K_RETURN) and self.state == "over" and self.over_t > 0.5:
                        self.reset()
                if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
                    if self.state == "over":
                        if self.over_t > 0.5:
                            self.reset()
                    elif self.state == "ready" and self.sel_rect.collidepoint(e.pos):
                        self.change_song(-1 if e.pos[0] < W // 2 else 1)
                    else:
                        self.tap(min(LANES - 1, e.pos[0] // LW))
            if TEST:                                   # headless autoplay check
                frame += 1
                dt = 1 / 60
                t = self.target()
                if frame <= len(SONGS) + 2:
                    self.change_song(1)
                elif frame < 400 and t and t["y"] > H * 0.3:
                    self.tap(t["lane"])
                elif frame == 400:
                    self.tap((t["lane"] + 1) % LANES)
                elif frame > 460:
                    print(f"TEST OK score={self.score} state={self.state} best={self.best}")
                    pygame.quit()
                    return
            self.update(dt)
            self.draw()


if __name__ == "__main__":
    Game().run()
    sys.exit()
