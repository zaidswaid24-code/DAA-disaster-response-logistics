"""
metrics.py - Evaluation metrics for a dispatch execution.

A delivery event is a tuple (time_minutes, demand_node, units).

Metrics
-------
pct_demand   : % of ALL demanded units delivered on time (the headline metric)
pct_value    : % of total priority-weighted value delivered on time
pct_critical : % of critical (priority 5) units delivered on time
avg_latency  : mean delivery time (minutes) of the delivered demands
resilience   : pct_demand under X% link failure / pct_demand with no failure
"""
from __future__ import annotations

import math
from typing import Dict, List, Sequence, Tuple

from network import Scenario

Event = Tuple[float, int, int]


def summarise(scn: Scenario, events: Sequence[Event]) -> Dict[str, float]:
    total_units = scn.total_demand
    total_value = sum(d.value for d in scn.demands.values())
    crit_units = sum(d.amount for d in scn.demands.values() if d.priority == 5)
    served_units = sum(u for _, _, u in events)
    served_value = sum(scn.demands[n].value for _, n, _ in events)
    crit_served = sum(u for _, n, u in events if scn.demands[n].priority == 5)
    lat = [t for t, _, _ in events]
    return {
        "pct_demand": 100.0 * served_units / total_units if total_units else 0.0,
        "pct_value": 100.0 * served_value / total_value if total_value else 0.0,
        "pct_critical": 100.0 * crit_served / crit_units if crit_units else 0.0,
        "avg_latency": sum(lat) / len(lat) if lat else float("nan"),
        "n_served": float(len(events)),
    }


def cumulative_series(scn: Scenario, events: Sequence[Event], grid: Sequence[float]) -> List[float]:
    """Cumulative % of total demand delivered at each time in `grid`."""
    total = scn.total_demand
    evs = sorted(events)
    out, k, acc = [], 0, 0
    for t in grid:
        while k < len(evs) and evs[k][0] <= t:
            acc += evs[k][2]
            k += 1
        out.append(100.0 * acc / total if total else 0.0)
    return out


def aggregate(rows: Sequence[Dict[str, float]]) -> Dict[str, float]:
    """Mean, standard deviation and 95% CI half-width of every metric over Monte Carlo runs."""
    out: Dict[str, float] = {}
    for key in rows[0]:
        vals = [r[key] for r in rows if not math.isnan(r[key])]
        if not vals:
            out[key], out[key + "_std"], out[key + "_ci"] = float("nan"), 0.0, 0.0
            continue
        mean = sum(vals) / len(vals)
        var = sum((v - mean) ** 2 for v in vals) / max(len(vals) - 1, 1)
        out[key] = mean
        out[key + "_std"] = math.sqrt(var)
        out[key + "_ci"] = 1.96 * math.sqrt(var / len(vals))
    return out


def resilience(stressed_pct: float, baseline_pct: float) -> float:
    """Fraction of the undisturbed service level that is preserved."""
    return stressed_pct / baseline_pct if baseline_pct > 0 else 0.0
