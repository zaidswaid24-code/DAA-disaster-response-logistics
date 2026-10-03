"""
prioritization.py - Decide WHICH demands to serve with the limited supply.

Pipeline
--------
Stage 1  deadline filter : drop demands that no depot can reach before their deadline.
Stage 2  0-1 knapsack DP : choose the subset of feasible demands that maximises total
                           value (priority x population) within the total supply.
Stage 3  allocation      : assign every chosen demand to a depot that has stock and can
                           meet the deadline; leftover stock is used for extra demands.

Baselines for comparison: greedy by value/weight ratio and the fractional-knapsack
upper bound.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from itertools import combinations
from typing import Dict, List, Optional, Sequence, Tuple

from network import Demand, Scenario, TravelTimes


# --------------------------------------------------------------------------- #
# Knapsack algorithms
# --------------------------------------------------------------------------- #
def knapsack_dp(weights: Sequence[int], values: Sequence[int], capacity: int) -> Tuple[int, List[int]]:
    """
    Exact 0-1 knapsack by dynamic programming, O(n * W) time, O(n * W) bits for traceback.

    dp[c] = best value achievable with capacity c using the items processed so far.
    Items are processed one by one and capacity is scanned downward so that each item
    is used at most once.
    """
    n = len(weights)
    dp = [0] * (capacity + 1)
    keep = [bytearray(capacity + 1) for _ in range(n)]
    for i in range(n):
        w, v, ki = weights[i], values[i], keep[i]
        for c in range(capacity, w - 1, -1):
            cand = dp[c - w] + v
            if cand > dp[c]:
                dp[c] = cand
                ki[c] = 1
    chosen: List[int] = []
    c = capacity
    for i in range(n - 1, -1, -1):
        if keep[i][c]:
            chosen.append(i)
            c -= weights[i]
    chosen.reverse()
    return dp[capacity], chosen


def knapsack_greedy(weights: Sequence[int], values: Sequence[int], capacity: int) -> Tuple[int, List[int]]:
    """Greedy by value/weight ratio (heuristic, O(n log n))."""
    order = sorted(range(len(weights)), key=lambda i: values[i] / weights[i], reverse=True)
    left, total, chosen = capacity, 0, []
    for i in order:
        if weights[i] <= left:
            chosen.append(i)
            left -= weights[i]
            total += values[i]
    return total, sorted(chosen)


def knapsack_fractional_bound(weights: Sequence[int], values: Sequence[int], capacity: int) -> float:
    """Fractional knapsack = LP relaxation = upper bound on the 0-1 optimum."""
    order = sorted(range(len(weights)), key=lambda i: values[i] / weights[i], reverse=True)
    left, total = capacity, 0.0
    for i in order:
        if weights[i] <= left:
            left -= weights[i]
            total += values[i]
        else:
            total += values[i] * left / weights[i]
            break
    return total


def knapsack_bruteforce(weights: Sequence[int], values: Sequence[int], capacity: int) -> int:
    """Exhaustive search, O(2^n). Only used by the unit tests."""
    n, best = len(weights), 0
    for r in range(n + 1):
        for comb in combinations(range(n), r):
            if sum(weights[i] for i in comb) <= capacity:
                best = max(best, sum(values[i] for i in comb))
    return best


# --------------------------------------------------------------------------- #
# Deadline filter + allocation
# --------------------------------------------------------------------------- #
def _tt_for(dem: Demand, tt: TravelTimes, tt_crit: Optional[TravelTimes]) -> TravelTimes:
    """Tiered safety buffer: critical demands (priority 5) may use a different (smaller) buffer."""
    return tt_crit if (tt_crit is not None and dem.priority == 5) else tt


def deadline_filter(scn: Scenario, tt: TravelTimes, tt_crit: Optional[TravelTimes] = None
                    ) -> Tuple[List[Demand], List[Demand]]:
    """Stage 1: keep demands reachable from at least one depot before their deadline."""
    feasible, rejected = [], []
    for dem in scn.demands.values():
        t_ = _tt_for(dem, tt, tt_crit)
        earliest = min(t_.d(dp, dem.node) for dp in scn.depots)
        (feasible if earliest <= dem.deadline else rejected).append(dem)
    return feasible, rejected


@dataclass
class PriorityPlan:
    method: str
    feasible: List[Demand]
    rejected: List[Demand]
    selected: List[int]                       # demand nodes chosen by the knapsack
    assignment: Dict[int, List[int]]          # depot -> demand nodes it will serve
    unassigned: List[int]                     # chosen but no depot could take them
    extra: List[int]                          # added by the leftover-stock repair step
    knapsack_value: int
    bound: float
    greedy_value: int
    stock_left: Dict[int, int] = field(default_factory=dict)

    @property
    def planned_nodes(self) -> List[int]:
        return [n for lst in self.assignment.values() for n in lst]


def allocate(scn: Scenario, tt: TravelTimes, selected: List[Demand], pool: List[Demand],
             tt_crit: Optional[TravelTimes] = None):
    """
    Stage 3: depot assignment.

    Selected demands are handled by priority (high first) then deadline (tight first);
    each goes to the closest depot that still has enough stock and meets the deadline.
    Afterwards, leftover stock is used for unselected feasible demands (best ratio first).
    """
    stock = dict(scn.stock)
    assign: Dict[int, List[int]] = {d: [] for d in scn.depots}

    def try_assign(dem: Demand) -> bool:
        t_ = _tt_for(dem, tt, tt_crit)
        for d in sorted(scn.depots, key=lambda x: t_.d(x, dem.node)):
            if stock[d] >= dem.amount and t_.d(d, dem.node) <= dem.deadline:
                assign[d].append(dem.node)
                stock[d] -= dem.amount
                return True
        return False

    unassigned: List[int] = []
    for dem in sorted(selected, key=lambda x: (-x.priority, x.deadline)):
        if not try_assign(dem):
            unassigned.append(dem.node)
    chosen = {d.node for d in selected}
    extra: List[int] = []
    for dem in sorted((x for x in pool if x.node not in chosen), key=lambda x: x.value / x.amount, reverse=True):
        if try_assign(dem):
            extra.append(dem.node)
    return assign, unassigned, extra, stock


def plan_priorities(scn: Scenario, tt: TravelTimes, method: str = "dp",
                    tt_crit: Optional[TravelTimes] = None) -> PriorityPlan:
    """Run the full prioritization pipeline with method 'dp' or 'greedy'."""
    feasible, rejected = deadline_filter(scn, tt, tt_crit)
    weights = [d.amount for d in feasible]
    values = [d.value for d in feasible]
    cap = scn.total_stock
    dp_val, dp_idx = knapsack_dp(weights, values, cap) if feasible else (0, [])
    gr_val, gr_idx = knapsack_greedy(weights, values, cap) if feasible else (0, [])
    bound = knapsack_fractional_bound(weights, values, cap) if feasible else 0.0
    idx = dp_idx if method == "dp" else gr_idx
    selected = [feasible[i] for i in idx]
    assign, unassigned, extra, left = allocate(scn, tt, selected, feasible, tt_crit)
    return PriorityPlan(
        method=method, feasible=feasible, rejected=rejected,
        selected=[d.node for d in selected], assignment=assign, unassigned=unassigned,
        extra=extra, knapsack_value=dp_val if method == "dp" else gr_val, bound=bound,
        greedy_value=gr_val, stock_left=left,
    )
