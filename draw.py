import math
import random
import sys

import pygame

from maze import DIRS, manhattan
from markov import MOVES
from settings import *
from warden import RETHINK, W_PROB, W_DIST, W_LATE

QUIT_HINT = "" if sys.platform == "emscripten" else "      Esc  quit"
MENU_LABELS = {"candy": "Candy", "potion": "Potion", "spider": "Spider", "web": "Cobweb", "ghosts": "Ghosts"}
MENU_NOTES = {
    "candy": "grab them all to unlock the gate",
    "potion": "gives back a heart",
    "spider": "bites for one heart",
    "web": "holds you in place for a moment",
    "ghosts": "they patrol, chase and call each other",
}


def center(cell):
    return cell[0] * TILE + TILE // 2, cell[1] * TILE + TILE // 2 + BAR


def cell_rect(cell, pad=0):
    return pygame.Rect(cell[0] * TILE + pad, cell[1] * TILE + BAR + pad, TILE - pad * 2, TILE - pad * 2)


def wrap(font, text, width):
    lines, line = [], ""
    for word in text.split():
        trial = f"{line} {word}".strip()
        if font.size(trial)[0] > width and line:
            lines.append(line)
            line = word
        else:
            line = trial
    return lines + [line] if line else lines


def glow(radius, strength=240):
    surf = pygame.Surface((radius * 2, radius * 2), pygame.SRCALPHA)
    for r in range(radius, 0, -2):
        alpha = int(strength * (1 - r / radius) ** 0.6)
        pygame.draw.circle(surf, (0, 0, 0, alpha), (radius, radius), r)
    return surf


class Painter:
    def __init__(self, surface):
        self.s = surface
        self.tiny = pygame.font.Font(None, 16)
        self.small = pygame.font.Font(None, 19)
        self.font = pygame.font.Font(None, 22)
        self.mid = pygame.font.Font(None, 32)
        self.big = pygame.font.Font(None, 84)
        self.dark = pygame.Surface((MAP_W, MAP_H), pygame.SRCALPHA)
        self.layer = pygame.Surface((MAP_W, MAP_H), pygame.SRCALPHA)
        self.shade = pygame.Surface((MAP_W, MAP_H), pygame.SRCALPHA)
        self.shade.fill((0, 0, 0, 175))
        self.lamps = [glow(r) for r in (110, 116, 121)]
        self.twinkle = glow(16, 200)
        self.haze = glow(30, 170)
        self.portal = glow(52)
        self.board = None

    def text(self, msg, pos, color=TEXT, font=None, anchor="topleft"):
        img = (font or self.font).render(str(msg), True, color)
        rect = img.get_rect(**{anchor: pos})
        self.s.blit(img, rect)
        return rect

    def tag(self, msg, pos, color):
        img = self.tiny.render(msg, True, color)
        box = img.get_rect(midbottom=pos).inflate(8, 4)
        pygame.draw.rect(self.s, (10, 8, 16), box, border_radius=3)
        self.s.blit(img, img.get_rect(center=box.center))

    def bake(self, world):
        rng = random.Random(world.seed)
        maze = world.maze
        board = pygame.Surface((MAP_W, MAP_H))
        board.fill(FLOOR)
        for y in range(maze.h):
            for x in range(maze.w):
                rect = pygame.Rect(x * TILE, y * TILE, TILE, TILE)
                if maze.walls[y][x]:
                    shade = rng.randint(-6, 6)
                    pygame.draw.rect(board, [c + shade for c in WALL], rect)
                    if y == 0 or not maze.walls[y - 1][x]:
                        pygame.draw.rect(board, WALL_TOP, (rect.x, rect.y, TILE, 3))
                    if y + 1 < maze.h and not maze.walls[y + 1][x]:
                        pygame.draw.rect(board, WALL_EDGE, (rect.x, rect.bottom - 5, TILE, 5))
                elif rng.random() < 0.3:
                    spot = (rect.x + rng.randint(4, TILE - 5), rect.y + rng.randint(4, TILE - 5))
                    pygame.draw.circle(board, FLOOR_SPECK, spot, rng.randint(1, 2))
        self.board = board

    def scene(self, game, t):
        self.s.fill(BG)
        self.s.blit(self.board, (0, BAR))
        self.gate(game.world.gate, game.gate_open, t)
        self.items(game.world.items, t)
        for g in game.ghosts:
            self.ghost(g, t)
        self.warden(game.warden, t)
        self.player(game.player, t)
        self.darkness(game, t)
        self.warden_eyes(game.warden, t)
        if game.debug:
            self.debug_map(game)
        for msg, cell, age, color in game.popups:
            x, y = center(cell)
            self.text(msg, (x, y - 16 - age * 26), color, self.small, "center")
        self.hud(game)
        pygame.draw.rect(self.s, PANEL_BG, (MAP_W, 0, PANEL, HEIGHT))
        if game.debug:
            self.ai_panel(game, MAP_W + 14, 10)
        else:
            self.help_panel(MAP_W + 16, 14)
        if game.mode == "over":
            self.game_over(game)
        elif game.paused:
            self.s.blit(self.shade, (0, BAR))
            self.text("PAUSED", (MAP_W // 2, BAR + MAP_H // 2), TEXT, self.big, "center")

    def items(self, items, t):
        for cell, kind in items.items():
            x, y = center(cell)
            self.item(kind, x, y, cell, t)

    def item(self, kind, x, y, cell=(1, 0), t=0.0):
        if kind == "candy":
            color = CANDY_COLORS[(cell[0] * 7 + cell[1]) % len(CANDY_COLORS)]
            self.candy(x, y + math.sin(t * 3 + cell[0]) * 1.5, color)
        elif kind == "potion":
            self.potion(x, y)
        elif kind == "spider":
            self.spider(x, y + math.sin(t * 2 + cell[1]) * 2)
        else:
            self.web(x, y)

    def candy(self, x, y, color):
        pygame.draw.polygon(self.s, color, [(x - 10, y - 5), (x - 10, y + 5), (x - 3, y)])
        pygame.draw.polygon(self.s, color, [(x + 10, y - 5), (x + 10, y + 5), (x + 3, y)])
        pygame.draw.circle(self.s, color, (x, y), 5)
        pygame.draw.circle(self.s, WHITE, (x - 2, y - 2), 1)

    def potion(self, x, y):
        pygame.draw.rect(self.s, (200, 230, 220), (x - 2, y - 8, 4, 5))
        pygame.draw.rect(self.s, (140, 90, 50), (x - 3, y - 10, 6, 3))
        pygame.draw.circle(self.s, GREEN, (x, y + 2), 6)
        pygame.draw.circle(self.s, (210, 255, 220), (x - 2, y), 2)

    def spider(self, x, y):
        pygame.draw.line(self.s, (95, 95, 110), (x, y - TILE // 2 - 2), (x, y))
        for side in (-1, 1):
            for i in range(4):
                knee = (x + side * 6, y - 5 + i * 3)
                foot = (x + side * 10, y - 3 + i * 3 + (i % 2) * 2)
                pygame.draw.lines(self.s, (16, 12, 20), False, [(x, y), knee, foot], 2)
        pygame.draw.circle(self.s, (16, 12, 20), (x, y), 5)
        pygame.draw.circle(self.s, RED, (x - 2, y - 1), 1)
        pygame.draw.circle(self.s, RED, (x + 2, y - 1), 1)

    def web(self, x, y):
        color = (150, 150, 170)
        for i in range(8):
            a = i * math.pi / 4
            pygame.draw.line(self.s, color, (x, y), (x + math.cos(a) * 11, y + math.sin(a) * 11))
        for r in (4, 8):
            ring = [(x + math.cos(i * math.pi / 4) * r, y + math.sin(i * math.pi / 4) * r) for i in range(8)]
            pygame.draw.polygon(self.s, color, ring, 1)

    def gate(self, cell, is_open, t):
        x, y = center(cell)
        if is_open:
            r = 9 + math.sin(t * 5) * 2
            pygame.draw.circle(self.s, PURPLE, (x, y), r + 3)
            pygame.draw.circle(self.s, (40, 10, 70), (x, y), r - 2)
            return
        rect = cell_rect(cell, 1)
        pygame.draw.rect(self.s, (20, 16, 26), rect)
        for i in range(4):
            bx = rect.x + 3 + i * 6
            pygame.draw.line(self.s, (110, 110, 125), (bx, rect.top), (bx, rect.bottom), 2)
        pygame.draw.rect(self.s, (110, 110, 125), rect, 2)

    def player(self, p, t):
        if p.safe > 0 and int(t * 14) % 2:
            return
        x, y = p.pixel()
        dx, dy = DIRS[p.facing]
        pygame.draw.circle(self.s, (250, 214, 170), (x, y + 2), 7)
        pygame.draw.polygon(self.s, (120, 60, 200), [(x - 6, y - 3), (x + 6, y - 3), (x + 3, y - 15)])
        pygame.draw.line(self.s, (120, 60, 200), (x - 10, y - 3), (x + 10, y - 3), 3)
        for side in (-3, 3):
            pygame.draw.circle(self.s, (40, 20, 30), (x + side + dx * 2, y + 2 + dy * 2), 1.5)
        lx = x + (dx * 10 if dx else 9)
        ly = y + 4 + dy * 5
        pygame.draw.circle(self.s, GOLD, (lx, ly), 3)
        pygame.draw.circle(self.s, (120, 90, 40), (lx, ly), 3, 1)
        if p.stuck > 0:
            self.web(x, y + 2)

    def ghost(self, g, t):
        x, y = g.pixel()
        y += math.sin(t * 3 + g.home[0]) * 2
        sprite = pygame.Surface((26, 28), pygame.SRCALPHA)
        color = (*g.color, 110 if g.state == "STUNNED" else 215)
        pygame.draw.circle(sprite, color, (13, 11), 9)
        pygame.draw.rect(sprite, color, (4, 11, 18, 9))
        for i in range(3):
            pygame.draw.circle(sprite, color, (7 + i * 6, 20), 3)
        if g.state == "STUNNED":
            for ex in (10, 16):
                pygame.draw.line(sprite, (30, 20, 40), (ex - 2, 9), (ex + 2, 13), 2)
                pygame.draw.line(sprite, (30, 20, 40), (ex + 2, 9), (ex - 2, 13), 2)
        else:
            eye = RED if g.state == "CHASE" else (25, 18, 35)
            pygame.draw.circle(sprite, eye, (10, 11), 2)
            pygame.draw.circle(sprite, eye, (16, 11), 2)
        self.s.blit(sprite, (x - 13, y - 14))

    def warden_head(self, w, t):
        x, y = w.pixel()
        sway = math.sin(t * 2.5) * 1.5
        return x, y, x + sway, y - 8

    def warden(self, w, t):
        x, y, hx, hy = self.warden_head(w, t)
        if w.state == "DORMANT":
            pygame.draw.ellipse(self.s, (64, 46, 34), (x - 12, y + 2, 24, 9))
            stone = pygame.Rect(x - 7, y - 11, 14, 16)
            pygame.draw.rect(self.s, (112, 108, 122), stone, border_top_left_radius=7, border_top_right_radius=7)
            pygame.draw.line(self.s, (70, 66, 80), (x, y - 8), (x, y - 1), 2)
            pygame.draw.line(self.s, (70, 66, 80), (x - 3, y - 6), (x + 3, y - 6), 2)
            return
        cloak = [(x - 11, y + 12), (x + 11, y + 12), (hx + 6, y - 3), (hx - 6, y - 3)]
        pygame.draw.polygon(self.s, (34, 18, 40), cloak)
        pygame.draw.polygon(self.s, (110, 30, 50), cloak, 2)
        pygame.draw.circle(self.s, (210, 100, 20), (hx, hy), 8)
        pygame.draw.line(self.s, (70, 120, 40), (hx, hy - 7), (hx + 2, hy - 12), 3)

    def warden_eyes(self, w, t):
        x, y, hx, hy = self.warden_head(w, t)
        if w.state == "DORMANT":
            dim = 90 + int(50 * math.sin(t * 4))
            pygame.draw.circle(self.s, (dim, 20, 20), (x - 3, y + 6), 1)
            pygame.draw.circle(self.s, (dim, 20, 20), (x + 3, y + 6), 1)
            return
        hot = (255, 60, 30) if w.state == "HUNT" else (255, 110, 40)
        for side in (-1, 1):
            ex = hx + side * 4
            pygame.draw.polygon(self.s, hot, [(ex - 2, hy), (ex + 2, hy), (ex, hy - 3)])
        mouth = [(hx - 4, hy + 3), (hx - 2, hy + 4), (hx, hy + 3), (hx + 2, hy + 4), (hx + 4, hy + 3)]
        pygame.draw.lines(self.s, hot, False, mouth, 1)

    def darkness(self, game, t):
        self.dark.fill((6, 4, 12, 110 if game.debug else 238))

        def light(img, pos):
            r = img.get_width() // 2
            self.dark.blit(img, (pos[0] - r, pos[1] - BAR - r), special_flags=pygame.BLEND_RGBA_SUB)

        light(self.lamps[(int(t * 9) * 7) % 3], game.player.pixel())
        for cell, kind in game.world.items.items():
            if kind == "candy":
                light(self.twinkle, center(cell))
        for g in game.ghosts:
            light(self.haze, g.pixel())
        if game.gate_open:
            light(self.portal, center(game.world.gate))
        self.s.blit(self.dark, (0, BAR))

    def route_line(self, start, path, color, width=2):
        points = [center(start)] + [center(c) for c in path]
        if len(points) > 1:
            pygame.draw.lines(self.s, color, False, points, width)

    def cross(self, cell, color):
        x, y = center(cell)
        pygame.draw.line(self.s, color, (x - 5, y - 5), (x + 5, y + 5), 2)
        pygame.draw.line(self.s, color, (x + 5, y - 5), (x - 5, y + 5), 2)

    def debug_map(self, game):
        w = game.warden
        self.layer.fill((0, 0, 0, 0))
        heat = {}
        for layer in w.forecast:
            for cell, p in layer.items():
                heat[cell] = max(heat.get(cell, 0.0), p)
        for (cx, cy), p in heat.items():
            alpha = int(30 + 170 * min(1.0, p))
            pygame.draw.rect(self.layer, (190, 70, 255, alpha), (cx * TILE + 3, cy * TILE + 3, TILE - 6, TILE - 6), border_radius=4)
        if w.choice and w.choice.route:
            for cx, cy in w.choice.route.explored:
                pygame.draw.rect(self.layer, (255, 80, 80, 60), (cx * TILE + 9, cy * TILE + 9, 6, 6))
        for o in w.options:
            cx, cy = o.cell
            pygame.draw.rect(self.layer, (255, 220, 60, 60), (cx * TILE + 1, cy * TILE + 1, TILE - 2, TILE - 2))
        self.s.blit(self.layer, (0, BAR))

        for g in game.ghosts:
            self.route_line(g.pos, g.path, g.color)
            if g.target:
                self.cross(g.target, g.color)
        if w.state != "DORMANT":
            self.route_line(w.pos, w.path, RED, 3)
        for o in w.options:
            win = o is w.choice
            pygame.draw.rect(self.s, WHITE if win else GOLD, cell_rect(o.cell), 2 if win else 1)
            label = "-inf" if o.score == float("-inf") else f"{o.score:.0f}"
            self.text(label, center(o.cell), WHITE if win else GOLD, self.tiny, "center")

        for g in game.ghosts:
            x, y = g.pixel()
            self.tag(g.state, (x, y - 13), g.color)
        x, y = w.pixel()
        self.tag(w.state, (x, y - 19), RED)

        p = game.player
        dist, _ = game.predictor.next_move(game.world.maze.exits(p.pos))
        if dist:
            guess = max(dist, key=dist.get)
            x, y = p.pixel()
            dx, dy = DIRS[guess]
            tip = (x + dx * 22, y + dy * 22)
            pygame.draw.line(self.s, PURPLE, (x, y), tip, 3)
            pygame.draw.circle(self.s, PURPLE, tip, 4)
            self.tag(f"{guess} {dist[guess]:.0%}", (tip[0], tip[1] - 5), PURPLE)

    def heart(self, x, y, full):
        color = RED if full else (60, 40, 62)
        pygame.draw.circle(self.s, color, (x - 4, y - 2), 5)
        pygame.draw.circle(self.s, color, (x + 4, y - 2), 5)
        pygame.draw.polygon(self.s, color, [(x - 9, y), (x + 9, y), (x, y + 9)])

    def hud(self, game):
        pygame.draw.rect(self.s, (16, 13, 24), (0, 0, MAP_W, BAR))
        p = game.player
        mid = BAR // 2
        for i in range(MAX_HEARTS):
            self.heart(18 + i * 24, mid - 2, i < p.hearts)
        self.candy(108, mid, CANDY_COLORS[0])
        self.text(f"{p.candy} / {game.world.total_candy}", (124, mid), TEXT, self.font, "midleft")
        mins, secs = divmod(int(game.elapsed), 60)
        self.text(f"{mins}:{secs:02d}", (210, mid), DIM, self.font, "midleft")
        if game.gate_open:
            self.text("gate is open, get out!", (270, mid), PURPLE, self.font, "midleft")
        else:
            self.text("gate locked", (270, mid), DIM, self.font, "midleft")
        flag = "F1 debug: ON" if game.debug else "F1 debug"
        self.text(flag, (MAP_W - 12, mid), GOLD if game.debug else DIM, self.small, "midright")

    def section(self, title, x, y):
        self.text(title, (x, y), GOLD, self.small)
        pygame.draw.line(self.s, (60, 50, 80), (x, y + 15), (x + PANEL - 28, y + 15))
        return y + 20

    def ai_panel(self, game, x, y):
        pr = game.predictor
        p = game.player
        dist, model = pr.next_move(game.world.maze.exits(p.pos))

        y = self.section("PLAYER MODEL (Markov)", x, y)
        self.text("last moves: " + (" ".join(pr.history[-9:]) or "-"), (x, y), TEXT, self.small)
        y += 16
        self.text(f"using {model}   transitions {pr.transitions}", (x, y), DIM, self.small)
        y += 20
        for i, d in enumerate(MOVES):
            by = y + i * 15
            prob = dist.get(d, 0.0)
            self.text(d, (x, by), TEXT, self.small)
            pygame.draw.rect(self.s, (50, 44, 64), (x + 14, by + 3, 70, 9))
            pygame.draw.rect(self.s, PURPLE, (x + 14, by + 3, int(70 * prob), 9))
            self.text(f"{prob:.0%}" if d in dist else "wall", (x + 90, by), DIM, self.small)
        mx = x + 140
        last = pr.history[-1] if pr.history else None
        self.text("from\\to", (mx - 6, y - 2), DIM, self.tiny)
        for j, b in enumerate(MOVES):
            self.text(b, (mx + 46 + j * 22, y - 2), DIM, self.tiny, "midtop")
        for i, a in enumerate(MOVES):
            ry = y + 12 + i * 13
            color = GOLD if a == last else TEXT
            self.text(a, (mx + 10, ry), color, self.tiny)
            for j, b in enumerate(MOVES):
                self.text(pr.first[a][b], (mx + 46 + j * 22, ry), color, self.tiny, "midtop")
        y += 66
        self.text(f"hit rate {pr.accuracy():.0%}   1st-order only {pr.accuracy('first'):.0%}", (x, y), TEXT, self.small)
        y += 24

        w = game.warden
        y = self.section("WARDEN (boss)", x, y)
        if w.state == "DORMANT":
            self.text(f"asleep, rises in {max(0.0, WAKE_TIME - w.clock):.1f}s", (x, y), TEXT, self.small)
            y += 16
            self.text("watching how you move...", (x, y), DIM, self.small)
            y += 22
        else:
            c = w.choice
            self.text(f"state {w.state}    rethink {max(0.0, w.rethink):.2f}/{RETHINK:.2f}s", (x, y), TEXT, self.small)
            y += 16
            if c.kind == "chase":
                where = "player now"
            else:
                where = f"player in {c.ahead} step{'s' if c.ahead > 1 else ''}"
            self.text(f"target {c.cell}  ({where})", (x, y), TEXT, self.small)
            y += 16
            h = manhattan(w.pos, c.cell)
            self.text(f"route g={c.cost}  h={h}  explored {len(c.route.explored)}", (x, y), DIM, self.small)
            y += 16
            self.text(f"U = {W_PROB}P - {W_DIST:g}cost - {W_LATE:g}late", (x, y), PURPLE, self.small)
            y += 18
            cols = [0, 64, 88, 136, 176, 222]
            for cx, head in zip(cols, ["tile", "t", "P", "cost", "late", "U"]):
                self.text(head, (x + cx, y), DIM, self.tiny)
            y += 13
            for o in w.options[:8]:
                color = GOLD if o is c else TEXT
                score = "-inf" if o.score == float("-inf") else f"{o.score:.1f}"
                row = [f"{o.cell[0]},{o.cell[1]}", "now" if o.kind == "chase" else o.ahead,
                       f"{o.prob:.2f}", o.cost, f"{o.late:.2f}", score]
                for cx, val in zip(cols, row):
                    self.text(val, (x + cx, y), color, self.tiny)
                y += 13
            y += 8

        y = self.section("GHOSTS (FSM)", x, y)
        if not game.ghosts:
            self.text("none this run", (x, y), DIM, self.small)
        for g in game.ghosts:
            pygame.draw.circle(self.s, g.color, (x + 5, y + 6), 5)
            self.text(g.state, (x + 16, y), TEXT, self.small)
            self.text(f"-> {g.target}" if g.target else "-> -", (x + 92, y), DIM, self.small)
            self.text(f"{len(g.path)} steps", (x + 196, y), DIM, self.small)
            y += 16

    def help_panel(self, x, y):
        self.text("LANTERN HOLLOW", (x, y), ORANGE, self.mid)
        y += 36
        intro = ("Grab every piece of candy to unlock the gate in the bottom right, then get out. "
                 "Your lantern only lights up a little bit of the maze.")
        for line in wrap(self.font, intro, PANEL - 32):
            self.text(line, (x, y), TEXT)
            y += 19
        y += 14
        legend = [
            ("candy", "candy, collect it all"),
            ("potion", "potion, +1 heart"),
            ("spider", "spider, bites for 1 heart"),
            ("web", "cobweb, you get stuck"),
        ]
        for kind, label in legend:
            self.item(kind, x + 12, y + 9)
            self.text(label, (x + 32, y + 1), TEXT, self.small)
            y += 26
        y += 8
        notes = [
            "Ghosts wander around until they see or hear you. Touching one costs a heart.",
            "The Warden wakes up after a few seconds. It learns your habits and tries to cut you off. If it touches you, it's over.",
        ]
        for note in notes:
            for line in wrap(self.small, note, PANEL - 32):
                self.text(line, (x, y), DIM, self.small)
                y += 16
            y += 8
        y += 6
        for line in ["WASD / arrows   move", "F1 or `   AI debug view", "P   pause", "R   new maze", "Esc   menu"]:
            key, _, what = line.partition("   ")
            self.text(key, (x, y), GOLD, self.small)
            self.text(what, (x + 120, y), TEXT, self.small)
            y += 18

    def game_over(self, game):
        self.s.blit(self.shade, (0, BAR))
        won, title, detail = game.outcome
        cx, cy = MAP_W // 2, BAR + MAP_H // 2
        self.text(title, (cx, cy - 70), GREEN if won else RED, self.big, "center")
        self.text(detail, (cx, cy - 18), TEXT, self.mid, "center")
        p = game.player
        mins, secs = divmod(int(game.elapsed), 60)
        self.text(f"candy {p.candy}/{game.world.total_candy}     time {mins}:{secs:02d}", (cx, cy + 22), DIM, self.font, "center")
        acc = game.predictor.accuracy()
        self.text(f"the Warden guessed your next move {acc:.0%} of the time", (cx, cy + 46), DIM, self.font, "center")
        self.text("R  new maze      M  menu" + QUIT_HINT, (cx, cy + 90), GOLD, self.font, "center")

    def menu(self, game, t):
        self.s.fill(BG)
        cx = WIDTH // 2
        bob = math.sin(t * 2) * 3
        self.text("LANTERN HOLLOW", (cx + 3, 93 + bob), (70, 24, 8), self.big, "center")
        self.text("LANTERN HOLLOW", (cx, 90 + bob), ORANGE, self.big, "center")
        self.text("Grab the candy, find the gate. The Warden is learning how you move.", (cx, 140), DIM, self.font, "center")
        total = sum(game.odds.values())
        for i, key in enumerate(game.menu_rows):
            y = 190 + i * 58
            on = i == game.pick
            color = TEXT if on else DIM
            if on:
                pygame.draw.rect(self.s, (32, 25, 46), (cx - 320, y - 8, 640, 50), border_radius=8)
            self.text(MENU_LABELS[key], (cx - 300, y), color, self.mid)
            self.text(MENU_NOTES[key], (cx - 300, y + 24), DIM, self.small)
            if key == "ghosts":
                for g in range(4):
                    gx = cx - 100 + g * 34
                    if g < game.ghost_count:
                        pygame.draw.circle(self.s, GHOST_COLORS[g], (gx, y + 11), 10)
                    else:
                        pygame.draw.circle(self.s, (60, 52, 76), (gx, y + 11), 10, 2)
                self.text(str(game.ghost_count), (cx + 70, y), color, self.mid)
                continue
            val = game.odds[key]
            bar = pygame.Rect(cx - 110, y + 5, 220, 14)
            pygame.draw.rect(self.s, (48, 40, 62), bar, border_radius=7)
            fill = bar.copy()
            fill.width = int(bar.width * val / MAX_ODDS)
            pygame.draw.rect(self.s, ORANGE if key in ("candy", "potion") else PURPLE, fill, border_radius=7)
            self.text(f"{val}%", (cx + 125, y), color, self.mid)
            self.text(f"about {round(val / 100 * ROOM_SLOTS)} per maze", (cx + 190, y + 6), DIM, self.small)
        y = 190 + len(game.menu_rows) * 58 + 4
        self.text(f"chance a room gets something: {total}%  (max {MAX_TOTAL}%)", (cx, y), DIM, self.small, "center")
        self.text("Up/Down pick    Left/Right change    Enter start" + QUIT_HINT, (cx, HEIGHT - 40), GOLD, self.font, "center")
