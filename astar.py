import heapq

from maze import manhattan


class Route:
    def __init__(self, path, cost, explored):
        self.path = path
        self.cost = cost
        self.explored = explored


def astar(maze, start, goal, cost=None):
    if not maze.is_open(goal):
        return Route([], float("inf"), set())
    g = {start: 0}
    parent = {start: None}
    heap = [(manhattan(start, goal), manhattan(start, goal), 0, start)]
    closed = set()
    while heap:
        _, _, here_g, here = heapq.heappop(heap)
        if here in closed:
            continue
        closed.add(here)
        if here == goal:
            path = []
            while here is not None:
                path.append(here)
                here = parent[here]
            path.reverse()
            return Route(path, g[goal], closed)
        for nxt in maze.neighbors(here):
            new_g = here_g + (cost(nxt) if cost else 1)
            if new_g < g.get(nxt, float("inf")):
                g[nxt] = new_g
                parent[nxt] = here
                h = manhattan(nxt, goal)
                heapq.heappush(heap, (new_g + h, h, new_g, nxt))
    return Route([], float("inf"), closed)
