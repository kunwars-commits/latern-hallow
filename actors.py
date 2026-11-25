from maze import step
from settings import TILE, BAR, PLAYER_STEP, MAX_HEARTS


class Mover:
    def __init__(self, pos, step_time):
        self.pos = pos
        self.prev = pos
        self.step_time = step_time
        self.cooldown = 0.0
        self.duration = step_time

    def move(self, cell, duration=None):
        self.prev, self.pos = self.pos, cell
        self.duration = duration or self.step_time
        self.cooldown = self.duration

    def tick(self, dt):
        self.cooldown = max(0.0, self.cooldown - dt)

    def pixel(self):
        t = 1 - self.cooldown / self.duration
        x = self.prev[0] + (self.pos[0] - self.prev[0]) * t
        y = self.prev[1] + (self.pos[1] - self.prev[1]) * t
        return x * TILE + TILE / 2, y * TILE + TILE / 2 + BAR


class Player(Mover):
    def __init__(self, pos):
        super().__init__(pos, PLAYER_STEP)
        self.hearts = MAX_HEARTS
        self.candy = 0
        self.stuck = 0.0
        self.safe = 0.0
        self.facing = "R"

    def update(self, dt):
        self.tick(dt)
        self.stuck = max(0.0, self.stuck - dt)
        self.safe = max(0.0, self.safe - dt)

    def ready(self):
        return self.cooldown <= 0 and self.stuck <= 0

    def try_move(self, maze, d):
        target = step(self.pos, d)
        if not maze.is_open(target):
            return False
        self.facing = d
        self.move(target)
        return True
