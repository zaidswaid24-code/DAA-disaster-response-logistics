"""
network.py - Network model, shortest-path algorithms and synthetic scenario generator.

Contents
--------
* Graph            : undirected weighted graph stored as adjacency lists
* dijkstra         : binary-heap SSSP (supports blocked links and per-link delay multipliers)
* bellman_ford     : SSSP reference implementation (used for validation)
* floyd_warshall   : APSP reference implementation (used for validation)
* TravelTimes      : cached shortest-path oracle between any two nodes
* Scenario         : depots, demand nodes, fleet and stock for one disaster instance
* generate_scenario: reproducible synthetic scenario generator

Units: travel time is in minutes, coordinates are in km, supply in "units".
"""
from __future__ import annotations

import heapq
import json
import math
import random
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

INF = float("inf")


def ekey(u: int, v: int) -> Tuple[int, int]:
    """Canonical key of an undirected edge."""
    return (u, v) if u < v else (v, u)


# --------------------------------------------------------------------------- #
# Graph
# --------------------------------------------------------------------------- #
class Graph:
    """Undirected weighted graph (adjacency lists + edge-weight dictionary)."""

    def __init__(self, n: int):
        self.n = n
        self.adj: List[List[Tuple[int, float]]] = [[] for _ in range(n)]
        self.w: Dict[Tuple[int, int], float] = {}

    def add_edge(self, u: int, v: int, w: float) -> bool:
        k = ekey(u, v)
        if u == v or k in self.w:
            return False
        self.w[k] = w
        self.adj[u].append((v, w))
        self.adj[v].append((u, w))
        return True

    @property
    def m(self) -> int:
        return len(self.w)

    def edges(self) -> List[Tuple[int, int, float]]:
        return [(u, v, w) for (u, v), w in self.w.items()]

    def is_connected(self) -> bool:
        seen = {0}
        stack = [0]
        while stack:
            u = stack.pop()
            for v, _ in self.adj[u]:
                if v not in seen:
                    seen.add(v)
                    stack.append(v)
        return len(seen) == self.n

    # ---- Dijkstra ---------------------------------------------------------- #
    def dijkstra(self, src: int, blocked=None, scale=None, target: Optional[int] = None):
        """
        Single-source shortest paths with a binary heap, O((n + m) log n).

        blocked : set of edge keys that are unusable (link failures)
        scale   : dict edge key -> multiplier of the nominal travel time (delays)
        target  : stop early once this node is settled
        Returns (dist, prev).
        """
        dist = [INF] * self.n
        prev = [-1] * self.n
        dist[src] = 0.0
        pq = [(0.0, src)]
        modified = bool(blocked) or bool(scale)
        while pq:
            d, u = heapq.heappop(pq)
            if d > dist[u]:
                continue
            if u == target:
                break
            for v, w in self.adj[u]:
                if modified:
                    k = (u, v) if u < v else (v, u)
                    if blocked and k in blocked:
                        continue
                    if scale:
                        w = w * scale.get(k, 1.0)
                nd = d + w
                if nd < dist[v]:
                    dist[v] = nd
                    prev[v] = u
                    heapq.heappush(pq, (nd, v))
        return dist, prev


def path_from_prev(prev: List[int], src: int, dst: int) -> List[int]:
    """Reconstruct the node path src -> dst from a predecessor array."""
    if src == dst:
        return [src]
    if prev[dst] == -1:
        return []
    path = [dst]
    while path[-1] != src:
        path.append(prev[path[-1]])
    return path[::-1]


def bellman_ford(g: Graph, src: int) -> List[float]:
    """Reference SSSP, O(n*m). Used only to cross-check Dijkstra in the tests."""
    dist = [INF] * g.n
    dist[src] = 0.0
    for _ in range(g.n - 1):
        changed = False
        for (u, v), w in g.w.items():
            if dist[u] + w < dist[v]:
                dist[v] = dist[u] + w
                changed = True
            if dist[v] + w < dist[u]:
                dist[u] = dist[v] + w
                changed = True
        if not changed:
            break
    return dist


def floyd_warshall(g: Graph) -> List[List[float]]:
    """Reference APSP, O(n^3). Used only to cross-check Dijkstra in the tests."""
    n = g.n
    d = [[INF] * n for _ in range(n)]
    for i in range(n):
        d[i][i] = 0.0
    for (u, v), w in g.w.items():
        d[u][v] = min(d[u][v], w)
        d[v][u] = min(d[v][u], w)
    for k in range(n):
        dk = d[k]
        for i in range(n):
            dik = d[i][k]
            if dik == INF:
                continue
            di = d[i]
            for j in range(n):
                nd = dik + dk[j]
                if nd < di[j]:
                    di[j] = nd
    return d


class TravelTimes:
    """
    Shortest-path oracle with per-source caching.

    `inflate` multiplies every returned time; it is used to plan with a safety buffer
    (robust planning). `scaled()` returns a view that shares the Dijkstra cache.
    """

    def __init__(self, graph: Graph, inflate: float = 1.0, _rows=None):
        self.g = graph
        self.inflate = inflate
        self._rows = _rows if _rows is not None else {}

    def scaled(self, inflate: float) -> "TravelTimes":
        return TravelTimes(self.g, inflate, self._rows)

    def row(self, src: int):
        if src not in self._rows:
            self._rows[src] = self.g.dijkstra(src)
        return self._rows[src]

    def d(self, u: int, v: int) -> float:
        return self.row(u)[0][v] * self.inflate

    def path(self, u: int, v: int) -> List[int]:
        return path_from_prev(self.row(u)[1], u, v)


# --------------------------------------------------------------------------- #
# Scenario
# --------------------------------------------------------------------------- #
@dataclass
class Demand:
    node: int
    amount: int        # supply units required (knapsack weight)
    priority: int      # 1 (low) .. 5 (critical)
    population: int    # people served
    deadline: float    # minutes after the disaster response starts

    @property
    def value(self) -> int:
        """Knapsack value = priority-weighted population."""
        return self.priority * self.population


@dataclass
class Scenario:
    graph: Graph
    coords: List[Tuple[float, float]]
    depots: List[int]
    stock: Dict[int, int]                  # depot -> supply units
    demands: Dict[int, Demand]             # node -> demand
    fleet: Dict[int, Tuple[int, int]]      # depot -> (vehicle count, vehicle capacity)
    service_time: float = 5.0
    seed: int = 0
    params: dict = field(default_factory=dict)

    @property
    def critical(self) -> List[int]:
        """Critical demand nodes (priority 5: hospitals, shelters)."""
        return sorted(n for n, d in self.demands.items() if d.priority == 5)

    @property
    def total_demand(self) -> int:
        return sum(d.amount for d in self.demands.values())

    @property
    def total_stock(self) -> int:
        return sum(self.stock.values())

    @property
    def total_vehicles(self) -> int:
        return sum(c for c, _ in self.fleet.values())

    # ---- persistence ------------------------------------------------------- #
    def to_dict(self) -> dict:
        return {
            "seed": self.seed,
            "params": self.params,
            "service_time": self.service_time,
            "coords": self.coords,
            "edges": [[u, v, round(w, 3)] for u, v, w in self.graph.edges()],
            "depots": self.depots,
            "stock": {str(k): v for k, v in self.stock.items()},
            "fleet": {str(k): list(v) for k, v in self.fleet.items()},
            "demands": [vars(d) for d in self.demands.values()],
        }

    def save(self, path: str) -> None:
        with open(path, "w") as f:
            json.dump(self.to_dict(), f, indent=1)

    @staticmethod
    def load(path: str) -> "Scenario":
        with open(path) as f:
            s = json.load(f)
        g = Graph(len(s["coords"]))
        for u, v, w in s["edges"]:
            g.add_edge(u, v, w)
        demands = {d["node"]: Demand(**d) for d in s["demands"]}
        return Scenario(
            graph=g,
            coords=[tuple(c) for c in s["coords"]],
            depots=s["depots"],
            stock={int(k): v for k, v in s["stock"].items()},
            demands=demands,
            fleet={int(k): tuple(v) for k, v in s["fleet"].items()},
            service_time=s["service_time"],
            seed=s["seed"],
            params=s["params"],
        )


def generate_scenario(
    n_nodes: int = 60,
    n_depots: int = 3,
    k_neighbors: int = 3,
    seed: int = 7,
    demand_frac: float = 0.6,
    stock_frac: float = 0.55,
    vehicles_per_depot: int = 3,
    vehicle_capacity: int = 30,
    service_time: float = 5.0,
    region: float = 100.0,
    minutes_per_km: float = 1.5,
) -> Scenario:
    """
    Build a reproducible synthetic post-disaster scenario.

    * Nodes are random points in a region x region km square.
    * Roads: each node is linked to its k nearest neighbours; remaining components are
      stitched together by their closest pair, so the network is always connected.
      Travel time = Euclidean km * minutes_per_km * detour factor in [1.0, 1.3].
    * Depots are chosen by farthest-point sampling so they are spread out.
    * demand_frac of the non-depot nodes have demand; the others are road junctions.
    * Critical nodes (priority 5) get tight deadlines and larger demands.
    * Total depot stock covers only stock_frac of the total demand, so choosing
      *which* demands to serve is a real optimisation problem.
    """
    rng = random.Random(seed)
    coords = [(rng.uniform(0, region), rng.uniform(0, region)) for _ in range(n_nodes)]

    def dist(i: int, j: int) -> float:
        return math.hypot(coords[i][0] - coords[j][0], coords[i][1] - coords[j][1])

    g = Graph(n_nodes)

    def add_road(i: int, j: int) -> None:
        g.add_edge(i, j, dist(i, j) * minutes_per_km * rng.uniform(1.0, 1.3))

    for i in range(n_nodes):
        near = sorted(range(n_nodes), key=lambda j: dist(i, j))[1 : k_neighbors + 1]
        for j in near:
            add_road(i, j)

    # connect components (closest pair between a component and the rest)
    def components() -> List[List[int]]:
        seen, comps = set(), []
        for s in range(n_nodes):
            if s in seen:
                continue
            comp, stack = [], [s]
            seen.add(s)
            while stack:
                u = stack.pop()
                comp.append(u)
                for v, _ in g.adj[u]:
                    if v not in seen:
                        seen.add(v)
                        stack.append(v)
            comps.append(comp)
        return comps

    comps = components()
    while len(comps) > 1:
        comps.sort(key=len)
        small, rest = comps[0], [x for c in comps[1:] for x in c]
        best = min(((dist(a, b), a, b) for a in small for b in rest))
        add_road(best[1], best[2])
        comps = components()

    # depots: farthest-point sampling
    center = min(range(n_nodes), key=lambda i: math.hypot(coords[i][0] - region / 2, coords[i][1] - region / 2))
    depots = [center]
    while len(depots) < n_depots:
        nxt = max((i for i in range(n_nodes) if i not in depots), key=lambda i: min(dist(i, d) for d in depots))
        depots.append(nxt)

    others = [i for i in range(n_nodes) if i not in depots]
    rng.shuffle(others)
    n_dem = int(demand_frac * len(others))
    demand_nodes = others[:n_dem]

    pr_choices = [1, 2, 3, 4, 5]
    pr_weights = [0.20, 0.25, 0.25, 0.15, 0.15]
    demands: Dict[int, Demand] = {}
    for node in demand_nodes:
        pr = rng.choices(pr_choices, pr_weights)[0]
        if pr == 5:
            amount = rng.randint(8, 18)
            deadline = rng.uniform(45, 150)
        elif pr == 4:
            amount = rng.randint(4, 12)
            deadline = rng.uniform(60, 200)
        else:
            amount = rng.randint(2, 12)
            deadline = rng.uniform(90, 360)
        population = amount * rng.randint(40, 100)
        demands[node] = Demand(node, amount, pr, population, round(deadline, 1))

    total = sum(d.amount for d in demands.values())
    total_stock = int(stock_frac * total)
    shares = [rng.uniform(0.2, 0.5) for _ in depots]
    ssum = sum(shares)
    stock = {d: int(total_stock * s / ssum) for d, s in zip(depots, shares)}
    stock[depots[0]] += total_stock - sum(stock.values())

    fleet = {d: (vehicles_per_depot, vehicle_capacity) for d in depots}
    params = dict(
        n_nodes=n_nodes, n_depots=n_depots, k_neighbors=k_neighbors, demand_frac=demand_frac,
        stock_frac=stock_frac, vehicles_per_depot=vehicles_per_depot,
        vehicle_capacity=vehicle_capacity, region=region, minutes_per_km=minutes_per_km,
    )
    return Scenario(g, coords, depots, stock, demands, fleet, service_time, seed, params)
