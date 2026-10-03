"""
experiments.py - All experiments of the project.

    scalability_experiment   runtime of every algorithm vs network size
    routing_scalability      Clarke-Wright / local search vs number of customers
    density_experiment       effect of road density (k nearest neighbours)
    capacity_experiment      effect of vehicle capacity
    knapsack_quality         DP vs greedy vs LP upper bound
    routing_gap_study        Clarke-Wright / local search vs exact DP
    buffer_sweep             trade-off of the planning safety buffer
    robustness_experiments   sensitivity grid, time series, backbone hardening
"""
from __future__ import annotations

import dataclasses
import os
import random
import sys
import time
from typing import Dict, List

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))

from backbone import backbone_report, kruskal, prim, steiner_kmb  # noqa: E402
from metrics import summarise  # noqa: E402
from network import Scenario, TravelTimes, generate_scenario  # noqa: E402
from planner import build_plan  # noqa: E402
from prioritization import (deadline_filter, knapsack_dp, knapsack_fractional_bound,  # noqa: E402
                            knapsack_greedy, plan_priorities)
from robustness import STRATEGIES, execute, make_disruptions, monte_carlo, sensitivity_study  # noqa: E402
from routing import clarke_wright, evaluate_route, exact_routes, local_search, plan_routes  # noqa: E402


def _time(fn, repeat: int = 1):
    best = float("inf")
    out = None
    for _ in range(repeat):
        t0 = time.perf_counter()
        out = fn()
        best = min(best, time.perf_counter() - t0)
    return best * 1000.0, out        # milliseconds


# --------------------------------------------------------------------------- #
def scalability_experiment(sizes: List[int], seed: int = 11) -> List[dict]:
    """Runtime (ms) of each stage of the pipeline as the network grows."""
    rows = []
    for n in sizes:
        n_dep = max(3, n // 50)
        scn = generate_scenario(n_nodes=n, n_depots=n_dep, seed=seed, vehicles_per_depot=3 + n // 150)
        tt = TravelTimes(scn.graph)
        terminals = scn.depots + scn.critical
        row = {"n": n, "m": scn.graph.m, "demands": len(scn.demands), "terminals": len(set(terminals))}
        row["dijkstra_all_ms"], _ = _time(lambda: [scn.graph.dijkstra(s) for s in set(terminals)])
        for s in set(terminals):
            tt.row(s)
        row["kruskal_ms"], _ = _time(lambda: kruskal(scn.graph.n, scn.graph.edges()), 3)
        row["prim_ms"], _ = _time(lambda: prim(scn.graph), 3)
        row["steiner_ms"], _ = _time(lambda: steiner_kmb(scn.graph, terminals, tt), 3)
        feas, _ = deadline_filter(scn, tt)
        w = [d.amount for d in feas]
        v = [d.value for d in feas]
        row["knapsack_dp_ms"], _ = _time(lambda: knapsack_dp(w, v, scn.total_stock))
        row["knapsack_greedy_ms"], _ = _time(lambda: knapsack_greedy(w, v, scn.total_stock), 3)
        row["plan_cold_ms"], plan0 = _time(lambda: build_plan(scn, tt, 0.0, improve=False))   # includes shortest paths
        row["plan_cw_ms"], _ = _time(lambda: build_plan(scn, tt, 0.0, improve=False), 3)      # full planning, CW routing
        row["plan_cw_ls_ms"], plan = _time(lambda: build_plan(scn, tt, 0.0, improve=True), 3)  # full planning, CW + LS
        assignment = plan0.priority.assignment
        row["routing_cw_ms"], _ = _time(lambda: plan_routes(scn, tt, tt, assignment, improve=False), 3)
        row["routing_ls_ms"], _ = _time(lambda: plan_routes(scn, tt, tt, assignment, improve=True), 3)
        row["routes"] = len(plan.routes)
        row["knapsack_cells"] = len(w) * scn.total_stock
        rows.append(row)
    return rows


def routing_scalability(sizes: List[int], ls_limit: int = 120, seed: int = 5) -> List[dict]:
    """One depot, m customers, no binding deadlines: how do CW and CW+LS scale with m?"""
    scn = generate_scenario(n_nodes=900, n_depots=3, seed=seed, demand_frac=0.9)
    tt = TravelTimes(scn.graph)
    depot = scn.depots[0]
    relaxed = {k: dataclasses.replace(d, deadline=1e9) for k, d in scn.demands.items()}
    nodes = sorted(relaxed)
    random.Random(seed).shuffle(nodes)
    rows = []
    for m in sizes:
        cust = nodes[:m]
        for c in cust + [depot]:
            tt.row(c)                       # shortest paths are preprocessing, not part of CW itself
        row = {"customers": m}
        row["cw_ms"], cw = _time(lambda: clarke_wright(depot, cust, tt, relaxed, scn.service_time, 30))
        row["cw_routes"] = len(cw)
        row["cw_total"] = sum(evaluate_route(depot, r, tt, relaxed, scn.service_time, 30)[2] for r in cw)
        if m <= ls_limit:
            row["ls_ms"], ls = _time(lambda: local_search(depot, cw, tt, relaxed, scn.service_time, 30))
            row["ls_total"] = sum(evaluate_route(depot, r, tt, relaxed, scn.service_time, 30)[2] for r in ls)
            row["ls_routes"] = len(ls)
        rows.append(row)
    return rows


def density_experiment(ks: List[int], n: int = 100, seed: int = 21) -> List[dict]:
    rows = []
    for k in ks:
        scn = generate_scenario(n_nodes=n, k_neighbors=k, seed=seed)
        tt = TravelTimes(scn.graph)
        rep = backbone_report(scn.graph, scn.depots + scn.critical, tt)
        plan = build_plan(scn, tt, 0.0)
        met = summarise(scn, _nominal_events(scn, plan))
        avg_sp = sum(tt.d(scn.depots[0], x) for x in range(n)) / n
        rows.append({"k": k, "edges": scn.graph.m, "mst_cost": rep["kruskal_cost"],
                     "steiner_cost": rep["steiner_cost"], "avg_depot_time": avg_sp,
                     "pct_demand": met["pct_demand"], "avg_latency": met["avg_latency"]})
    return rows


def _nominal_events(scn: Scenario, plan) -> list:
    """Deliveries of a plan with no disruption at all (planned arrival times)."""
    return [(a, s, scn.demands[s].amount) for r in plan.routes for s, a in zip(r.stops, r.arrivals)]


def capacity_experiment(caps: List[int], n: int = 100, seed: int = 31) -> List[dict]:
    rows = []
    for cap in caps:
        scn = generate_scenario(n_nodes=n, seed=seed, vehicle_capacity=cap, vehicles_per_depot=4)
        tt = TravelTimes(scn.graph)
        plan = build_plan(scn, tt, 0.0)
        met = summarise(scn, _nominal_events(scn, plan))
        rows.append({"capacity": cap, "routes": len(plan.routes), "dropped": len(plan.routing.dropped),
                     "pct_demand": met["pct_demand"], "avg_latency": met["avg_latency"],
                     "total_route_time": plan.routing.total_duration})
    return rows


def knapsack_quality(sizes=(30, 60, 120), stock_fracs=(0.3, 0.5, 0.7), trials: int = 20) -> List[dict]:
    rows = []
    for n in sizes:
        for sf in stock_fracs:
            gaps_g, gaps_b, dp_wins = [], [], 0
            for t in range(trials):
                scn = generate_scenario(n_nodes=n, seed=1000 + t, stock_frac=sf)
                tt = TravelTimes(scn.graph)
                feas, _ = deadline_filter(scn, tt)
                if not feas:
                    continue
                w = [d.amount for d in feas]
                v = [d.value for d in feas]
                dpv, _ = knapsack_dp(w, v, scn.total_stock)
                grv, _ = knapsack_greedy(w, v, scn.total_stock)
                ub = knapsack_fractional_bound(w, v, scn.total_stock)
                gaps_g.append(100.0 * (dpv - grv) / dpv)
                gaps_b.append(100.0 * (ub - dpv) / ub)
                dp_wins += dpv > grv
            rows.append({"n": n, "stock_frac": sf, "trials": len(gaps_g),
                         "greedy_gap_pct": sum(gaps_g) / len(gaps_g),
                         "max_greedy_gap_pct": max(gaps_g),
                         "dp_better_pct": 100.0 * dp_wins / len(gaps_g),
                         "dp_to_bound_gap_pct": sum(gaps_b) / len(gaps_b)})
    return rows


def routing_gap_study(sizes=(5, 6, 7, 8, 9, 10), instances: int = 20, seed: int = 41) -> List[dict]:
    """Compare heuristics with the exact optimum (same number of vehicles) on small instances."""
    rows = []
    for m in sizes:
        gaps_cw, gaps_ls, opt_cw, opt_ls, t_cw, t_ls, t_ex = [], [], 0, 0, [], [], []
        used = 0
        for inst in range(instances):
            scn = generate_scenario(n_nodes=50, seed=seed + 100 * m + inst, demand_frac=0.9)
            tt = TravelTimes(scn.graph)
            depot = scn.depots[0]
            relaxed = {k: dataclasses.replace(d, deadline=d.deadline * 2.5) for k, d in scn.demands.items()}
            cap = 30
            rng = random.Random(inst + m)
            pool = [c for c in relaxed if evaluate_route(depot, [c], tt, relaxed, scn.service_time, cap)[0]]
            if len(pool) < m:
                continue
            cust = rng.sample(pool, m)
            t1, cw = _time(lambda: clarke_wright(depot, cust, tt, relaxed, scn.service_time, cap))
            if sorted(s for r in cw for s in r) != sorted(cust):
                continue                      # CW could not route everyone: skip this instance
            t2, ls = _time(lambda: local_search(depot, cw, tt, relaxed, scn.service_time, cap))
            t3, ex = _time(lambda: exact_routes(depot, cust, tt, relaxed, scn.service_time, cap, len(cw)))
            if ex is None:
                continue
            tot = lambda rs: sum(evaluate_route(depot, r, tt, relaxed, scn.service_time, cap)[2] for r in rs)
            c_cw, c_ls, c_ex = tot(cw), tot(ls), ex[0]
            gaps_cw.append(100.0 * (c_cw - c_ex) / c_ex)
            gaps_ls.append(100.0 * (c_ls - c_ex) / c_ex)
            opt_cw += c_cw - c_ex < 1e-6
            opt_ls += c_ls - c_ex < 1e-6
            t_cw.append(t1); t_ls.append(t2); t_ex.append(t3)
            used += 1
        if used:
            rows.append({"customers": m, "instances": used,
                         "cw_gap_pct": sum(gaps_cw) / used, "ls_gap_pct": sum(gaps_ls) / used,
                         "cw_max_gap_pct": max(gaps_cw), "ls_max_gap_pct": max(gaps_ls),
                         "cw_optimal_pct": 100.0 * opt_cw / used, "ls_optimal_pct": 100.0 * opt_ls / used,
                         "cw_ms": sum(t_cw) / used, "ls_ms": sum(t_ls) / used, "exact_ms": sum(t_ex) / used})
    return rows


def buffer_sweep(scn: Scenario, tt: TravelTimes, buffers, runs: int, seed: int = 77,
                 fail: float = 0.2, delay: float = 0.5) -> List[dict]:
    """How much safety buffer should the planner use? (robust policy = adaptive + realloc)."""
    rows = []
    for b in buffers:
        plan = build_plan(scn, tt, b)
        plans = {"nominal": plan, "buffered": plan}
        calm = monte_carlo(scn, plans, tt, ["buffer+adaptive+realloc"], 0.0, 0.0, 5, seed)["buffer+adaptive+realloc"]
        stress = monte_carlo(scn, plans, tt, ["buffer+adaptive+realloc"], fail, delay, runs, seed)["buffer+adaptive+realloc"]
        rows.append({"buffer": b, "pct_no_disruption": calm["pct_demand"],
                     "pct_stressed": stress["pct_demand"], "pct_stressed_ci": stress["pct_demand_ci"],
                     "latency_stressed": stress["avg_latency"], "planned_demands": len(plan.priority.planned_nodes)})
    return rows


def robustness_experiments(scn: Scenario, tt: TravelTimes, backbone_edges, runs: int, fail_levels, delay_levels,
                           buffer: float = 0.25, seed: int = 1) -> dict:
    plans = {"nominal": build_plan(scn, tt, 0.0), "buffered": build_plan(scn, tt, buffer)}
    sens = sensitivity_study(scn, plans, tt, fail_levels, delay_levels, runs, seed)

    # time series at a representative disruption
    horizon = 400
    grid = list(range(0, horizon + 1, 10))
    series = monte_carlo(scn, plans, tt, list(STRATEGIES), 0.2, 0.5, runs, seed + 5, grid=grid)
    ts = {"grid": grid, "series": {s: v["series"] for s, v in series.items()}}

    # backbone hardening: closures never hit the Steiner backbone
    protected = {tuple(sorted(e)) for e in backbone_edges}
    hardening = {"fail_levels": list(fail_levels), "delay": 0.25, "unprotected": [], "protected": []}
    for fl in fail_levels:
        for key, prot in (("unprotected", None), ("protected", protected)):
            res = monte_carlo(scn, plans, tt, ["adaptive+realloc", "buffer+adaptive+realloc"], fl, 0.25, runs, seed + 9, protected=prot)
            hardening[key].append({s: {"pct_demand": v["pct_demand"], "pct_critical": v["pct_critical"]} for s, v in res.items()})
    return {"plans": plans, "sensitivity": sens, "timeseries": ts, "hardening": hardening,
            "fail_levels": list(fail_levels), "delay_levels": list(delay_levels)}
