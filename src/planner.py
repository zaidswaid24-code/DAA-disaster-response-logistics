"""
planner.py - Chains the algorithmic components into one dispatch plan.

    scenario -> deadline filter -> knapsack DP -> depot allocation -> routing

`safety` > 0 plans with travel times inflated by (1 + safety). This leaves slack in every
route and is the "buffered" robust-planning policy evaluated in robustness.py.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from network import Scenario, TravelTimes
from prioritization import PriorityPlan, plan_priorities
from routing import RoutePlan, plan_routes


@dataclass
class Plan:
    safety: float
    priority: PriorityPlan
    routing: RoutePlan

    @property
    def routes(self):
        return self.routing.routes


def build_plan(scn: Scenario, tt_base: TravelTimes, safety: float = 0.0,
               selection: str = "dp", improve: bool = True, critical_safety: Optional[float] = None) -> Plan:
    """
    Plan the dispatch. `safety` is the planning buffer applied to all demands.

    Optional tiered buffer: if `critical_safety` is given, critical demands (priority 5) are planned
    with that buffer instead (e.g. 0.0). We tested this variant; under the same random disruptions
    it gave no benefit over the uniform buffer (see docs), so it is off by default.
    """
    tt_plan = tt_base.scaled(1.0 + safety)
    tt_crit = (tt_base.scaled(1.0 + critical_safety)
               if critical_safety is not None and critical_safety != safety else None)
    prio = plan_priorities(scn, tt_plan, method=selection, tt_crit=tt_crit)
    routing = plan_routes(scn, tt_plan, tt_base, prio.assignment, improve=improve, tt_crit=tt_crit)
    return Plan(safety, prio, routing)
