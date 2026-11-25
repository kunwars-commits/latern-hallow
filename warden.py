from actors import Mover
from astar import astar
from settings import PLAYER_STEP, WARDEN_STEP, WAKE_TIME

W_PROB = 100
W_DIST = 2.0
W_LATE = 6.0
CHASE_TRUST = 0.35
BORED = 15
HORIZON = 10
RETHINK = 0.5
WEB_COST = 4
WEB_DELAY = 0.3


class Option:
    def __init__(self, cell, ahead, prob, kind):
        self.cell = cell
        self.ahead = ahead
        self.prob = prob
        self.kind = kind
        self.cost = 0
        self.late = 0.0
        self.score = 0.0
        self.route = None


class Warden(Mover):
    def __init__(self, pos):
        super().__init__(pos, WARDEN_STEP)
        self.state = "DORMANT"
        self.clock = 0.0
        self.rethink = 0.0
        self.wait = 0.0
        self.options = []
        self.choice = None
        self.path = []
        self.forecast = []

    @property
    def target(self):
        return self.choice.cell if self.choice else None

    def update(self, dt, world, player, predictor):
        self.clock += dt
        self.tick(dt)
        if self.state == "DORMANT":
            if self.clock < WAKE_TIME:
                return None
            self.state = "HUNT"
            event = "awake"
        else:
            event = None
        self.rethink -= dt
        if self.rethink <= 0:
            self.decide(world, player, predictor)
            self.rethink = RETHINK
        if self.path and self.cooldown <= 0:
            nxt = self.path.pop(0)
            slow = WEB_DELAY if world.items.get(nxt) == "web" else 0
            self.move(nxt, self.step_time + slow)
        self.state = self.label()
        self.wait = self.wait + dt if self.state == "AMBUSH" else 0.0
        return event

    def label(self):
        if not self.choice or self.choice.kind == "chase":
            return "HUNT"
        return "AMBUSH" if self.pos == self.choice.cell else "INTERCEPT"

    def decide(self, world, player, predictor):
        maze = world.maze
        self.forecast = predictor.forecast(maze, player.pos, HORIZON)
        options = [Option(player.pos, 0, 1.0, "chase")]
        used = {player.pos}
        for ahead, layer in enumerate(self.forecast, 1):
            if not layer:
                break
            cell = max(layer, key=layer.get)
            if cell not in used:
                used.add(cell)
                options.append(Option(cell, ahead, layer[cell], "ambush"))
        def terrain(cell):
            return WEB_COST if world.items.get(cell) == "web" else 1

        for o in options:
            o.route = astar(maze, self.pos, o.cell, terrain)
            o.cost = o.route.cost
            if not o.route.path:
                o.score = float("-inf")
                continue
            if o.kind == "chase":
                o.score = W_PROB * CHASE_TRUST - W_DIST * o.cost
            else:
                o.late = max(0.0, o.cost * self.step_time - o.ahead * PLAYER_STEP)
                o.score = W_PROB * o.prob - W_DIST * o.cost - W_LATE * o.late
            if o.cell == self.pos:
                o.score -= BORED * self.wait
        self.options = sorted(options, key=lambda o: o.score, reverse=True)
        self.choice = self.options[0]
        self.path = self.choice.route.path[1:]
