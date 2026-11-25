from collections import deque

DIRS = {"U": (0, -1), "D": (0, 1), "L": (-1, 0), "R": (1, 0)}


def step(pos, d):
    dx, dy = DIRS[d]
    return pos[0] + dx, pos[1] + dy


def manhattan(a, b):
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


class Maze:
    def __init__(self, cells_w, cells_h, rng, loop_chance=0.12):
        self.w = cells_w * 2 + 1
        self.h = cells_h * 2 + 1
        self.rng = rng
        self.walls = [[True] * self.w for _ in range(self.h)]
        self.carve(cells_w, cells_h)
        self.add_loops(loop_chance)
        self.floor = [(x, y) for y in range(self.h) for x in range(self.w) if not self.walls[y][x]]
        self.rooms = [(x, y) for x, y in self.floor if x % 2 and y % 2]

    def carve(self, cells_w, cells_h):
        stack = [(0, 0)]
        visited = {(0, 0)}
        self.walls[1][1] = False
        while stack:
            cx, cy = stack[-1]
            options = []
            for dx, dy in DIRS.values():
                nx, ny = cx + dx, cy + dy
                if 0 <= nx < cells_w and 0 <= ny < cells_h and (nx, ny) not in visited:
                    options.append((nx, ny))
            if not options:
                stack.pop()
                continue
            nx, ny = self.rng.choice(options)
            self.walls[cy + ny + 1][cx + nx + 1] = False
            self.walls[ny * 2 + 1][nx * 2 + 1] = False
            visited.add((nx, ny))
            stack.append((nx, ny))

    def add_loops(self, chance):
        for y in range(1, self.h - 1):
            for x in range(1, self.w - 1):
                if self.walls[y][x] and x % 2 != y % 2 and self.rng.random() < chance:
                    self.walls[y][x] = False

    def is_open(self, pos):
        x, y = pos
        return 0 <= x < self.w and 0 <= y < self.h and not self.walls[y][x]

    def exits(self, pos):
        return [d for d in DIRS if self.is_open(step(pos, d))]

    def neighbors(self, pos):
        return [step(pos, d) for d in self.exits(pos)]

    def can_see(self, a, b, reach):
        if (a[0] != b[0] and a[1] != b[1]) or manhattan(a, b) > reach:
            return False
        dx = (b[0] > a[0]) - (b[0] < a[0])
        dy = (b[1] > a[1]) - (b[1] < a[1])
        x, y = a
        while (x, y) != b:
            x, y = x + dx, y + dy
            if self.walls[y][x]:
                return False
        return True

    def reachable(self, start):
        seen = {start}
        queue = deque([start])
        while queue:
            for nxt in self.neighbors(queue.popleft()):
                if nxt not in seen:
                    seen.add(nxt)
                    queue.append(nxt)
        return seen
