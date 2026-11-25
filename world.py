import random

from maze import Maze, manhattan
from settings import CELLS_W, CELLS_H, START

KINDS = ("candy", "potion", "spider", "web")


class World:
    def __init__(self, odds, seed=None):
        self.seed = seed if seed is not None else random.randrange(1_000_000)
        self.rng = random.Random(self.seed)
        self.maze = Maze(CELLS_W, CELLS_H, self.rng)
        self.start = START
        self.gate = (self.maze.w - 2, self.maze.h - 2)
        self.reach = self.maze.reachable(self.start)
        self.items = {}
        self.roll_items(odds)
        self.total_candy = sum(kind == "candy" for kind in self.items.values())

    def spawnable(self):
        return [c for c in self.maze.rooms
                if c in self.reach and c != self.gate and manhattan(c, self.start) >= 4]

    def roll_items(self, odds):
        for cell in self.spawnable():
            roll = self.rng.random() * 100
            for kind in KINDS:
                if roll < odds[kind]:
                    self.items[cell] = kind
                    break
                roll -= odds[kind]
        if "candy" not in self.items.values():
            empty = [c for c in self.spawnable() if c not in self.items]
            self.items[self.rng.choice(empty)] = "candy"

    def free_spot(self, min_dist, taken):
        spots = [c for c in self.spawnable()
                 if c not in taken and c not in self.items and manhattan(c, self.start) >= min_dist]
        if not spots:
            spots = [c for c in self.spawnable() if c not in taken]
        return self.rng.choice(spots)
