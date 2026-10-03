"""
robustness.py - Uncertain travel times, link failures and re-allocation strategies.

Disruption model (one random draw per Monte Carlo run)
    * every road gets a delay multiplier 1 + U(0, delay_max)
    * a fraction `fail_frac` of the roads is closed (optionally never the backbone links)

Execution strategies (what the fleet does once the disruption is revealed)
    static                    follow the planned paths; a closed road strands the vehicle
    static+buffer             same, but the plan was built with a safety time buffer
    adaptive                  re-route on the live network before every leg; skip stops that
                              became unreachable or too late
    adaptive+realloc          adaptive + skipped stops go to a shared pool; any vehicle that has
                              cargo left and time before the deadline picks them up
    buffer+adaptive+realloc   buffered plan + adaptive + re-allocation (full robust policy)

All strategies are evaluated on the SAME random disruptions (common random numbers), so
differences between them are not sampling noise.
"""
from __future__ import annotations

import heapq
import random
from typing import Dict, List, Optional, Sequence, Set, Tuple

from metrics import aggregate, cumulative_series, summarise
from network import INF, Scenario, TravelTimes, ekey
from planner import Plan

STRATEGIES: Dict[str, Tuple[str, str]] = {
    "static": ("nominal", "static"),
    "static+buffer": ("buffered", "static"),
    "adaptive": ("nominal", "adaptive"),
    "adaptive+realloc": ("nominal", "realloc"),
    "buffer+adaptive+realloc": ("buffered", "realloc"),
}

Disruption = Tuple[Set[Tuple[int, int]], Dict[Tuple[int, int], float]]


def sample_disruption(scn: Scenario, rng: random.Random, fail_frac: float, delay_max: float,
                      protected: Optional[Set[Tuple[int, int]]] = None) -> Disruption:
    g = scn.graph
    eligible = [k for k in g.w if not protected or k not in protected]
    n_fail = min(len(eligible), round(fail_frac * g.m))
    blocked = set(rng.sample(eligible, n_fail)) if n_fail else set()
    scale = {k: 1.0 + rng.uniform(0.0, delay_max) for k in g.w}
    return blocked, scale


def make_disruptions(scn: Scenario, fail_frac: float, delay_max: float, runs: int, seed: int,
                     protected: Optional[Set[Tuple[int, int]]] = None) -> List[Disruption]:
    rng = random.Random(seed)
    return [sample_disruption(scn, rng, fail_frac, delay_max, protected) for _ in range(runs)]


# --------------------------------------------------------------------------- #
# Executors
# --------------------------------------------------------------------------- #
def run_static(scn: Scenario, plan: Plan, tt: TravelTimes, disruption: Disruption):
    """Follow the nominal shortest paths; a closed road on the way ends that vehicle's route."""
    blocked, scale = disruption
    w = scn.graph.w
    events = []
    for r in plan.routes:
        t, pos = 0.0, r.depot
        for s in r.stops:
            path = tt.path(pos, s)
            stuck = False
            for a, b in zip(path, path[1:]):
                k = ekey(a, b)
                if k in blocked:
                    stuck = True
                    break
                t += w[k] * scale[k]
            if stuck:
                break
            dem = scn.demands[s]
            if t <= dem.deadline:
                events.append((t, s, dem.amount))
            t += scn.service_time
            pos = s
    return events


def run_adaptive(scn: Scenario, plan: Plan, disruption: Disruption, reallocate: bool):
    """Event-driven simulation with live re-routing and optional re-allocation pool."""
    blocked, scale = disruption
    g = scn.graph
    events = []
    vehicles = []
    heap: List[Tuple[float, int]] = []
    for idx, r in enumerate(plan.routes):
        vehicles.append({"t": 0.0, "pos": r.depot, "queue": list(r.stops),
                         "cargo": sum(scn.demands[s].amount for s in r.stops)})
        heapq.heappush(heap, (0.0, idx))
    pool: List[int] = []
    idle: List[int] = []
    served: Set[int] = set()

    def wake(now: float) -> None:
        while idle:
            j = idle.pop()
            vehicles[j]["t"] = max(vehicles[j]["t"], now)
            heapq.heappush(heap, (vehicles[j]["t"], j))

    while heap:
        _, idx = heapq.heappop(heap)
        v = vehicles[idx]
        if v["queue"]:
            s = v["queue"].pop(0)
            dem = scn.demands[s]
            dist, _ = g.dijkstra(v["pos"], blocked, scale, target=s)
            arr = v["t"] + dist[s]
            if dist[s] == INF or arr > dem.deadline or dem.amount > v["cargo"]:
                if reallocate:
                    pool.append(s)
                    wake(v["t"])
            else:
                events.append((arr, s, dem.amount))
                served.add(s)
                v["cargo"] -= dem.amount
                v["pos"] = s
                v["t"] = arr + scn.service_time
            heapq.heappush(heap, (v["t"], idx))
        elif reallocate and pool and v["cargo"] > 0:
            dist, _ = g.dijkstra(v["pos"], blocked, scale)
            best, best_score = None, -1.0
            for s in pool:
                dem = scn.demands[s]
                if s in served or dist[s] == INF:
                    continue
                if v["t"] + dist[s] <= dem.deadline and dem.amount <= v["cargo"]:
                    score = dem.value / (dist[s] + scn.service_time + 1.0)
                    if score > best_score:
                        best, best_score = s, score
            if best is None:
                idle.append(idx)
            else:
                pool.remove(best)
                v["queue"] = [best]
                heapq.heappush(heap, (v["t"], idx))
        else:
            idle.append(idx)
    return events


def execute(scn: Scenario, plans: Dict[str, Plan], tt_base: TravelTimes, strategy: str,
            disruption: Disruption):
    plan_key, mode = STRATEGIES[strategy]
    plan = plans[plan_key]
    if mode == "static":
        return run_static(scn, plan, tt_base, disruption)
    return run_adaptive(scn, plan, disruption, reallocate=(mode == "realloc"))


# --------------------------------------------------------------------------- #
# Monte Carlo
# --------------------------------------------------------------------------- #
def monte_carlo(scn: Scenario, plans: Dict[str, Plan], tt_base: TravelTimes,
                strategies: Sequence[str], fail_frac: float, delay_max: float, runs: int, seed: int,
                protected: Optional[Set[Tuple[int, int]]] = None, grid: Optional[Sequence[float]] = None):
    """
    Evaluate each strategy on the same `runs` random disruptions.
    Returns {strategy: aggregate metrics (+ optional mean time series)}.
    """
    disruptions = make_disruptions(scn, fail_frac, delay_max, runs, seed, protected)
    out = {}
    for strat in strategies:
        rows, series = [], []
        for dis in disruptions:
            ev = execute(scn, plans, tt_base, strat, dis)
            rows.append(summarise(scn, ev))
            if grid is not None:
                series.append(cumulative_series(scn, ev, grid))
        agg = aggregate(rows)
        if grid is not None:
            agg["series"] = [sum(col) / len(col) for col in zip(*series)]
        out[strat] = agg
    return out


def sensitivity_study(scn: Scenario, plans: Dict[str, Plan], tt_base: TravelTimes,
                      fail_levels: Sequence[float], delay_levels: Sequence[float], runs: int, seed: int,
                      strategies: Optional[Sequence[str]] = None):
    """Grid study: failure level x delay range x strategy -> aggregated metrics."""
    strategies = list(strategies or STRATEGIES)
    res: Dict[str, Dict[str, Dict[str, dict]]] = {s: {} for s in strategies}
    for fi, ff in enumerate(fail_levels):
        for di, dm in enumerate(delay_levels):
            cell = monte_carlo(scn, plans, tt_base, strategies, ff, dm, runs, seed + 1000 * fi + di)
            for s in strategies:
                res[s].setdefault(str(ff), {})[str(dm)] = cell[s]
    return res
