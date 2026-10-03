"""
routing.py - Multi-vehicle routing from each depot (capacitated, with delivery deadlines).

Algorithms
----------
* clarke_wright : savings heuristic; a merge is accepted only if the merged route keeps
                  every deadline and the vehicle capacity.
* local_search  : 2-opt (inside a route) + relocate (between routes), feasibility-preserving.
* exact_routes  : exact DP for small instances (Held-Karp over subsets + set-partition DP);
                  used to measure how far the heuristics are from optimal.

Route cost = time from leaving the depot until returning to it (travel + service).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

from network import Demand, Scenario, TravelTimes

INF = float("inf")


@dataclass
class Route:
    depot: int
    stops: List[int]
    load: int = 0
    duration: float = 0.0
    arrivals: List[float] = field(default_factory=list)


@dataclass
class RoutePlan:
    routes: List[Route]
    dropped: List[int]          # planned demands that could not be routed (fleet limit)

    @property
    def total_duration(self) -> float:
        return sum(r.duration for r in self.routes)

    @property
    def served_nodes(self) -> List[int]:
        return [s for r in self.routes for s in r.stops]


def evaluate_route(depot: int, stops: Sequence[int], tt: TravelTimes, demands: Dict[int, Demand],
                   service: float, cap: int):
    """Return (feasible, arrival times, total duration) of visiting `stops` in order."""
    t, pos, load = 0.0, depot, 0
    arrivals: List[float] = []
    for s in stops:
        t += tt.d(pos, s)
        dem = demands[s]
        load += dem.amount
        if t > dem.deadline + 1e-9 or load > cap:
            return False, [], INF
        arrivals.append(t)
        t += service
        pos = s
    if stops:
        t += tt.d(pos, depot)
    return True, arrivals, t


def _duration(depot, stops, tt, demands, service, cap) -> float:
    return evaluate_route(depot, stops, tt, demands, service, cap)[2] if stops else 0.0


# --------------------------------------------------------------------------- #
# Clarke-Wright savings
# --------------------------------------------------------------------------- #
def clarke_wright(depot: int, customers: Sequence[int], tt: TravelTimes, demands: Dict[int, Demand],
                  service: float, cap: int) -> List[List[int]]:
    """
    Clarke-Wright parallel savings, O(n^2 log n).

    Start with one route per customer. The saving of linking i and j is
    s_ij = d(0,i) + d(0,j) - d(i,j). Savings are processed in decreasing order; routes are
    merged when i and j are route endpoints, the load fits the vehicle and all deadlines
    still hold (both orientations of each route are tried).
    """
    routes: Dict[int, List[int]] = {}
    load: Dict[int, int] = {}
    route_of: Dict[int, int] = {}
    for c in customers:
        ok, _, _ = evaluate_route(depot, [c], tt, demands, service, cap)
        if ok:
            routes[c] = [c]
            load[c] = demands[c].amount
            route_of[c] = c
    cs = list(routes)
    savings = []
    for a in range(len(cs)):
        for b in range(a + 1, len(cs)):
            i, j = cs[a], cs[b]
            s = tt.d(depot, i) + tt.d(depot, j) - tt.d(i, j)
            if s > 0:
                savings.append((s, i, j))
    savings.sort(reverse=True)
    for _, i, j in savings:
        ri, rj = route_of[i], route_of[j]
        if ri == rj or load[ri] + load[rj] > cap:
            continue
        A, B = routes[ri], routes[rj]
        if i not in (A[0], A[-1]) or j not in (B[0], B[-1]):
            continue
        merged: Optional[List[int]] = None
        for a_ in ([A, A[::-1]] if len(A) > 1 else [A]):
            if a_[-1] != i:
                continue
            for b_ in ([B, B[::-1]] if len(B) > 1 else [B]):
                if b_[0] != j:
                    continue
                cand = a_ + b_
                if evaluate_route(depot, cand, tt, demands, service, cap)[0]:
                    merged = cand
                    break
            if merged:
                break
        if merged is None:
            continue
        routes[ri] = merged
        load[ri] += load[rj]
        for s in B:
            route_of[s] = ri
        del routes[rj], load[rj]
    return list(routes.values())


# --------------------------------------------------------------------------- #
# Local search
# --------------------------------------------------------------------------- #
def local_search(depot: int, routes: List[List[int]], tt: TravelTimes, demands: Dict[int, Demand],
                 service: float, cap: int, max_passes: int = 30) -> List[List[int]]:
    """2-opt within routes + relocate between routes; only feasible, improving moves."""
    routes = [list(r) for r in routes if r]
    dur = [_duration(depot, r, tt, demands, service, cap) for r in routes]
    for _ in range(max_passes):
        improved = False
        # intra-route 2-opt
        for k, r in enumerate(routes):
            for i in range(len(r) - 1):
                for j in range(i + 1, len(r)):
                    cand = r[:i] + r[i : j + 1][::-1] + r[j + 1 :]
                    d = _duration(depot, cand, tt, demands, service, cap)
                    if d < dur[k] - 1e-9:
                        routes[k], dur[k], r = cand, d, cand
                        improved = True
        # inter-route relocate
        for a in range(len(routes)):
            moved = False
            for i in range(len(routes[a])):
                stop = routes[a][i]
                for b in range(len(routes)):
                    if a == b:
                        continue
                    new_a = routes[a][:i] + routes[a][i + 1 :]
                    da = _duration(depot, new_a, tt, demands, service, cap) if new_a else 0.0
                    for pos in range(len(routes[b]) + 1):
                        new_b = routes[b][:pos] + [stop] + routes[b][pos:]
                        db = _duration(depot, new_b, tt, demands, service, cap)
                        if da + db < dur[a] + dur[b] - 1e-9:
                            routes[a], routes[b], dur[a], dur[b] = new_a, new_b, da, db
                            improved = moved = True
                            break
                    if moved:
                        break
                if moved:
                    break
        keep = [k for k, r in enumerate(routes) if r]
        routes, dur = [routes[k] for k in keep], [dur[k] for k in keep]
        if not improved:
            break
    return routes


# --------------------------------------------------------------------------- #
# Exact DP for small instances
# --------------------------------------------------------------------------- #
def exact_routes(depot: int, customers: Sequence[int], tt: TravelTimes, demands: Dict[int, Demand],
                 service: float, cap: int, max_vehicles: int) -> Optional[Tuple[float, List[List[int]]]]:
    """
    Exact minimum-total-duration routing of ALL customers with at most `max_vehicles` vehicles,
    respecting capacity and deadlines. Returns None if no feasible solution exists.

    Phase 1 (Held-Karp with deadlines): f[S][j] = earliest time at which a vehicle has
    finished serving set S and ends at j. Earliest-time is the right state because arriving
    earlier never hurts a deadline and never increases the route cost.  O(2^n n^2).
    Phase 2 (set partition): g[k][S] = best cost of covering S with at most k routes,
    g[k][S] = min over sub-sets T of S containing S's lowest customer of cost[T] + g[k-1][S\\T].
    O(K 3^n).
    """
    n = len(customers)
    if n == 0:
        return 0.0, []
    if n > 13:
        raise ValueError("exact_routes is limited to 13 customers")
    full = 1 << n
    d0 = [tt.d(depot, c) for c in customers]
    dn = [[tt.d(a, b) for b in customers] for a in customers]
    dl = [demands[c].deadline for c in customers]
    am = [demands[c].amount for c in customers]
    load = [0] * full
    for mask in range(1, full):
        low = mask & -mask
        load[mask] = load[mask ^ low] + am[low.bit_length() - 1]

    f = [[INF] * n for _ in range(full)]
    par = [[-1] * n for _ in range(full)]
    for j in range(n):
        if d0[j] <= dl[j] and am[j] <= cap:
            f[1 << j][j] = d0[j] + service
    for mask in range(1, full):
        if load[mask] > cap:
            continue
        for i in range(n):
            fi = f[mask][i]
            if fi == INF:
                continue
            for j in range(n):
                if mask >> j & 1:
                    continue
                nm = mask | (1 << j)
                if load[nm] > cap:
                    continue
                arr = fi + dn[i][j]
                if arr > dl[j] + 1e-9:
                    continue
                if arr + service < f[nm][j]:
                    f[nm][j] = arr + service
                    par[nm][j] = i

    cost = [INF] * full
    last = [-1] * full
    for mask in range(1, full):
        for j in range(n):
            if f[mask][j] < INF:
                c = f[mask][j] + d0[j]
                if c < cost[mask]:
                    cost[mask], last[mask] = c, j

    g = [[INF] * full for _ in range(max_vehicles + 1)]
    choice = [[0] * full for _ in range(max_vehicles + 1)]
    for k in range(max_vehicles + 1):
        g[k][0] = 0.0
    for k in range(1, max_vehicles + 1):
        for mask in range(1, full):
            best, arg = g[k - 1][mask], 0
            low = mask & -mask
            sub = mask
            while sub:
                if sub & low and cost[sub] < INF:
                    cand = cost[sub] + g[k - 1][mask ^ sub]
                    if cand < best:
                        best, arg = cand, sub
                sub = (sub - 1) & mask
            g[k][mask], choice[k][mask] = best, arg
    if g[max_vehicles][full - 1] == INF:
        return None

    routes: List[List[int]] = []
    mask, k = full - 1, max_vehicles
    while mask and k > 0:
        sub = choice[k][mask]
        if sub == 0:
            k -= 1
            continue
        order, m, j = [], sub, last[sub]
        while j != -1:
            order.append(customers[j])
            pj = par[m][j]
            m ^= 1 << j
            j = pj
        routes.append(order[::-1])
        mask ^= sub
        k -= 1
    return g[max_vehicles][full - 1], routes


# --------------------------------------------------------------------------- #
# Plan builder
# --------------------------------------------------------------------------- #
def plan_routes(scn: Scenario, tt_plan: TravelTimes, tt_base: TravelTimes,
                assignment: Dict[int, List[int]], improve: bool = True,
                tt_crit: Optional[TravelTimes] = None) -> RoutePlan:
    """
    Route every depot's assigned demands.

    Routes are built with `tt_plan` (possibly inflated = safety buffer); the stored
    arrival times / durations are the nominal ones computed with `tt_base`.
    With a tiered buffer (`tt_crit` given) critical demands are routed separately, using
    their own (smaller) buffer, so that they are never dropped because of the safety margin.
    If a depot needs more routes than it has vehicles, the lowest value-per-minute routes
    are dropped (reported in `dropped`).
    """
    out: List[Route] = []
    dropped: List[int] = []
    for depot, customers in assignment.items():
        if not customers:
            continue
        n_veh, cap = scn.fleet[depot]
        if tt_crit is not None:
            crit = [c for c in customers if scn.demands[c].priority == 5]
            groups = [(crit, tt_crit), ([c for c in customers if c not in crit], tt_plan)]
        else:
            groups = [(customers, tt_plan)]
        cand: List[Tuple[List[int], TravelTimes]] = []
        for group, t_ in groups:
            if not group:
                continue
            rts = clarke_wright(depot, group, t_, scn.demands, scn.service_time, cap)
            routed = {s for r in rts for s in r}
            dropped += [c for c in group if c not in routed]
            if improve:
                rts = local_search(depot, rts, t_, scn.demands, scn.service_time, cap)
            cand += [(r, t_) for r in rts]
        if len(cand) > n_veh:
            def density(item):
                r, t_ = item
                val = sum(scn.demands[s].value for s in r)
                return val / max(_duration(depot, r, t_, scn.demands, scn.service_time, cap), 1e-9)
            cand.sort(key=density, reverse=True)
            for r, _ in cand[n_veh:]:
                dropped += r
            cand = cand[:n_veh]
        for r, _ in cand:
            ok, arr, dur = evaluate_route(depot, r, tt_base, scn.demands, scn.service_time, cap)
            out.append(Route(depot, list(r), sum(scn.demands[s].amount for s in r), dur, arr))
    return RoutePlan(out, dropped)
