from collections import defaultdict

from maze import step

MOVES = "UDLR"


class Predictor:
    def __init__(self, smoothing=0.5, trust=3):
        self.first = {a: dict.fromkeys(MOVES, 0) for a in MOVES}
        self.second = defaultdict(lambda: dict.fromkeys(MOVES, 0))
        self.smoothing = smoothing
        self.trust = trust
        self.history = []
        self.pending = {}
        self.hits = {"active": 0, "first": 0}
        self.checked = 0

    @property
    def transitions(self):
        return sum(sum(row.values()) for row in self.first.values())

    def accuracy(self, name="active"):
        return self.hits[name] / self.checked if self.checked else 0.0

    def last_two(self):
        h = self.history
        return (h[-2] if len(h) > 1 else None), (h[-1] if h else None)

    def distribution(self, before, last, exits):
        row, model = None, "uniform"
        pair = self.second.get((before, last))
        if pair and sum(pair.values()) >= self.trust:
            row, model = pair, "2-gram"
        elif last and sum(self.first[last].values()):
            row, model = self.first[last], "1st-order"
        weights = {d: (row[d] if row else 0) + self.smoothing for d in exits}
        total = sum(weights.values())
        return {d: w / total for d, w in weights.items()}, model

    def next_move(self, exits):
        return self.distribution(*self.last_two(), exits)

    def best(self, before, last, exits):
        dist, _ = self.distribution(before, last, exits)
        return max(dist, key=dist.get) if dist else None

    def record(self, move, exits):
        if self.pending.get("active"):
            self.checked += 1
            for name, guess in self.pending.items():
                self.hits[name] += guess == move
        before, last = self.last_two()
        if last:
            self.first[last][move] += 1
        if before:
            self.second[(before, last)][move] += 1
        self.history = (self.history + [move])[-12:]
        before, last = self.last_two()
        self.pending = {
            "active": self.best(before, last, exits),
            "first": self.best(None, last, exits),
        }

    def forecast(self, maze, pos, steps):
        before, last = self.last_two()
        states = {(pos, before, last): 1.0}
        layers = []
        for _ in range(steps):
            grown = defaultdict(float)
            for (cell, a, b), p in states.items():
                dist, _ = self.distribution(a, b, maze.exits(cell))
                for d, q in dist.items():
                    if p * q >= 0.003:
                        grown[(step(cell, d), b, d)] += p * q
            states = grown
            layer = defaultdict(float)
            for (cell, _, _), p in states.items():
                layer[cell] += p
            layers.append(dict(layer))
        return layers
