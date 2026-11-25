from actors import Mover
from astar import astar
from maze import manhattan

PACE = {"PATROL": 0.32, "CHASE": 0.17, "SEARCH": 0.24, "STUNNED": 0.3}


class Ghost(Mover):
    sight = 7
    hearing = 2

    def __init__(self, pos, color, rng):
        super().__init__(pos, PACE["PATROL"])
        self.home = pos
        self.color = color
        self.rng = rng
        self.last_seen = None
        self.enter("PATROL")

    def enter(self, state, anchor=None):
        self.state = state
        self.step_time = PACE[state]
        self.clock = 0.0
        self.replan = 0.0
        self.unseen = 0.0
        self.path = []
        self.target = anchor
        self.anchor = anchor

    def notices(self, maze, player):
        if manhattan(self.pos, player.pos) <= self.hearing:
            return True
        return maze.can_see(self.pos, player.pos, self.sight)

    def head_to(self, maze, goal):
        self.target = goal
        self.path = astar(maze, self.pos, goal).path[1:]

    def alert(self, spot):
        if self.state == "PATROL" and manhattan(self.pos, spot) <= 14:
            self.enter("SEARCH", spot)

    def update(self, dt, maze, player):
        self.clock += dt
        self.replan -= dt
        self.tick(dt)
        event = getattr(self, self.state.lower())(dt, maze, player)
        if self.path and self.cooldown <= 0:
            self.move(self.path.pop(0))
        return event

    def spot(self, player):
        self.enter("CHASE")
        self.last_seen = player.pos
        return "spotted"

    def patrol(self, dt, maze, player):
        if self.notices(maze, player):
            return self.spot(player)
        if not self.path:
            nearby = [c for c in maze.rooms if manhattan(c, self.home) <= 8 and c != self.pos]
            self.head_to(maze, self.rng.choice(nearby))

    def chase(self, dt, maze, player):
        if self.notices(maze, player):
            self.last_seen = player.pos
            self.unseen = 0.0
        else:
            self.unseen += dt
            if self.unseen > 1.5:
                self.enter("SEARCH", self.last_seen)
                return
        if self.replan <= 0:
            self.head_to(maze, self.last_seen)
            self.replan = 0.4

    def search(self, dt, maze, player):
        if self.notices(maze, player):
            return self.spot(player)
        if self.clock > 5.0:
            self.enter("PATROL")
            return
        if not self.path:
            if self.pos != self.target:
                self.head_to(maze, self.target)
            else:
                around = [c for c in maze.floor if manhattan(c, self.anchor) <= 3 and c != self.pos]
                self.head_to(maze, self.rng.choice(around))

    def stunned(self, dt, maze, player):
        if self.clock > 2.0:
            self.enter("PATROL")
