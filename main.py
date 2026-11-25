import asyncio
import random
import sys

import pygame

from actors import Player
from draw import Painter
from ghost import Ghost
from markov import Predictor
from settings import *
from warden import Warden
from world import World, KINDS

KEYS = {
    pygame.K_w: "U", pygame.K_UP: "U",
    pygame.K_s: "D", pygame.K_DOWN: "D",
    pygame.K_a: "L", pygame.K_LEFT: "L",
    pygame.K_d: "R", pygame.K_RIGHT: "R",
}
WEB = sys.platform == "emscripten"


class Game:
    menu_rows = list(KINDS) + ["ghosts"]

    def __init__(self):
        pygame.init()
        self.display = pygame.display.set_mode((WIDTH, HEIGHT))
        pygame.display.set_caption("Lantern Hollow")
        self.canvas = pygame.Surface((WIDTH, HEIGHT))
        self.paint = Painter(self.canvas)
        self.clock = pygame.time.Clock()
        self.odds = dict(DEFAULT_ODDS)
        self.ghost_count = 3
        self.pick = 0
        self.debug = False
        self.running = True
        self.held = []
        self.shake = 0.0
        self.to_menu()

    @property
    def gate_open(self):
        return self.player.candy >= self.world.total_candy

    def to_menu(self):
        self.mode = "menu"
        self.held = []
        pygame.key.set_repeat(220, 45)

    def new_run(self):
        pygame.key.set_repeat()
        self.world = World(self.odds)
        self.paint.bake(self.world)
        self.player = Player(self.world.start)
        self.predictor = Predictor()
        taken = {self.world.start}
        self.ghosts = []
        for color in GHOST_COLORS[:self.ghost_count]:
            spot = self.world.free_spot(10, taken)
            taken.add(spot)
            self.ghosts.append(Ghost(spot, color, self.world.rng))
        self.warden = Warden(self.world.free_spot(20, taken))
        self.held = []
        self.elapsed = 0.0
        self.popups = []
        self.shake = 0.0
        self.paused = False
        self.outcome = None
        self.mode = "play"

    def handle(self, event):
        if event.type == pygame.QUIT:
            self.running = False
        elif event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_F1, pygame.K_BACKQUOTE):
                self.debug = not self.debug
            elif self.mode == "menu":
                self.menu_key(event.key)
            elif self.mode == "play":
                self.play_key(event.key)
            elif event.key == pygame.K_r:
                self.new_run()
            elif event.key == pygame.K_m:
                self.to_menu()
            elif event.key == pygame.K_ESCAPE:
                self.quit()
        elif event.type == pygame.KEYUP and event.key in KEYS and KEYS[event.key] in self.held:
            self.held.remove(KEYS[event.key])

    def play_key(self, key):
        if key in KEYS:
            self.held.append(KEYS[key])
        elif key == pygame.K_p:
            self.paused = not self.paused
        elif key == pygame.K_r:
            self.new_run()
        elif key == pygame.K_ESCAPE:
            self.to_menu()

    def menu_key(self, key):
        row = self.menu_rows[self.pick]
        if key in (pygame.K_UP, pygame.K_w):
            self.pick = (self.pick - 1) % len(self.menu_rows)
        elif key in (pygame.K_DOWN, pygame.K_s):
            self.pick = (self.pick + 1) % len(self.menu_rows)
        elif key in (pygame.K_LEFT, pygame.K_a, pygame.K_RIGHT, pygame.K_d):
            change = 1 if key in (pygame.K_RIGHT, pygame.K_d) else -1
            if row == "ghosts":
                self.ghost_count = max(0, min(4, self.ghost_count + change))
            elif change < 0 or sum(self.odds.values()) < MAX_TOTAL:
                self.odds[row] = max(0, min(MAX_ODDS, self.odds[row] + change))
        elif key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_KP_ENTER):
            self.new_run()
        elif key == pygame.K_ESCAPE:
            self.quit()

    def quit(self):
        if WEB:
            self.to_menu()
        else:
            self.running = False

    def popup(self, msg, cell, color):
        self.popups.append([msg, cell, 0.0, color])

    def update(self, dt):
        if self.mode != "play" or self.paused:
            return
        self.elapsed += dt
        self.shake = max(0.0, self.shake - dt)
        for pop in self.popups:
            pop[2] += dt
        self.popups = [pop for pop in self.popups if pop[2] < 0.9]

        maze = self.world.maze
        p = self.player
        p.update(dt)
        if p.ready():
            for d in reversed(self.held):
                if p.try_move(maze, d):
                    self.after_step(d)
                    break
        if self.mode != "play":
            return

        for g in self.ghosts:
            if g.update(dt, maze, p) == "spotted":
                self.popup("!", g.pos, g.color)
                for other in self.ghosts:
                    if other is not g:
                        other.alert(p.pos)
        if self.warden.update(dt, self.world, p, self.predictor) == "awake":
            self.popup("the Warden rises...", self.warden.pos, RED)
        self.check_contacts()

    def after_step(self, d):
        p = self.player
        self.predictor.record(d, self.world.maze.exits(p.pos))
        kind = self.world.items.pop(p.pos, None)
        if kind == "candy":
            p.candy += 1
            self.popup("+1", p.pos, GOLD)
            if self.gate_open:
                self.popup("the gate opened!", self.world.gate, PURPLE)
        elif kind == "potion":
            p.hearts = min(MAX_HEARTS, p.hearts + 1)
            self.popup("+1 heart", p.pos, GREEN)
        elif kind == "spider":
            self.hurt("A spider got the last bite.")
        elif kind == "web":
            p.stuck = 0.7
            self.popup("stuck!", p.pos, DIM)
        if p.pos == self.world.gate and self.gate_open:
            self.finish(True, "YOU ESCAPED", "Made it out with the whole haul.")

    def touching(self, mover):
        ax, ay = mover.pixel()
        bx, by = self.player.pixel()
        return abs(ax - bx) + abs(ay - by) < TILE * 0.7

    def check_contacts(self):
        for g in self.ghosts:
            if g.state != "STUNNED" and self.touching(g):
                g.enter("STUNNED")
                self.hurt("A ghost took your last heart.")
        if self.mode == "play" and self.warden.state != "DORMANT" and self.touching(self.warden):
            self.finish(False, "CAUGHT", "The Warden saw you coming.")

    def hurt(self, reason):
        p = self.player
        if p.safe > 0:
            return
        p.hearts -= 1
        p.safe = 1.2
        self.shake = 0.25
        self.popup("-1", p.pos, RED)
        if p.hearts <= 0:
            self.finish(False, "OUT OF HEARTS", reason)

    def finish(self, won, title, detail):
        self.outcome = (won, title, detail)
        self.mode = "over"
        self.held = []

    def draw(self):
        t = pygame.time.get_ticks() / 1000
        if self.mode == "menu":
            self.paint.menu(self, t)
        else:
            self.paint.scene(self, t)
        offset = (random.randint(-4, 4), random.randint(-4, 4)) if self.shake > 0 else (0, 0)
        self.display.fill(BG)
        self.display.blit(self.canvas, offset)
        pygame.display.flip()

    async def run(self):
        while self.running:
            dt = min(self.clock.tick(FPS) / 1000, 0.05)
            for event in pygame.event.get():
                self.handle(event)
            self.update(dt)
            self.draw()
            await asyncio.sleep(0)
        pygame.quit()


if __name__ == "__main__":
    asyncio.run(Game().run())
