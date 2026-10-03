"""
main.py - Runs the whole Disaster Response Logistics project end to end.

    python main.py              full run (about a minute)
    python main.py --quick      fast run for testing (a few seconds)
    python main.py --demo       pauses between stages (for the live demonstration)

Stages
    1. Generate the disaster scenario (network, depots, demands, fleet)
    2. Backbone: Kruskal vs Prim, Steiner-tree approximation
    3. Prioritization: deadline filter + knapsack DP (vs greedy and LP bound)
    4. Routing: Clarke-Wright + local search (checked against the exact DP)
    5. Robustness: Monte Carlo under delays and link failures, strategy comparison
    6. Algorithm experiments: scalability, density, capacity, quality
    7. Figures, dashboard, policy tables
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import os
import sys
import time

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, ROOT)

import experiments as ex  # noqa: E402
from backbone import backbone_report  # noqa: E402
from dashboard_html import build_dashboard  # noqa: E402
from metrics import summarise  # noqa: E402
from network import TravelTimes, generate_scenario  # noqa: E402
from planner import build_plan  # noqa: E402
from visualize import save_all  # noqa: E402

BUFFER = 0.25


def banner(text: str) -> None:
    print("\n" + "=" * 78)
    print(text)
    print("=" * 78)


def sanitize(obj):
    """Make the result tree JSON-safe (NaN -> None, tuples -> lists)."""
    if isinstance(obj, dict):
        return {str(k): sanitize(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [sanitize(v) for v in obj]
    if isinstance(obj, float) and (math.isnan(obj) or math.isinf(obj)):
        return None
    return obj


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true", help="fewer Monte Carlo runs / smaller experiments")
    ap.add_argument("--demo", action="store_true", help="pause between stages")
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--nodes", type=int, default=60)
    ap.add_argument("--outdir", default=os.path.join(ROOT, "outputs"))
    args = ap.parse_args()
    os.makedirs(args.outdir, exist_ok=True)
    os.makedirs(os.path.join(ROOT, "data"), exist_ok=True)

    def pause():
        if args.demo:
            input("\n[press Enter to continue] ")

    runs = 12 if args.quick else 60
    t_start = time.time()

    # 1 -------------------------------------------------------------------- #
    banner("STAGE 1 - Scenario")
    scn = generate_scenario(n_nodes=args.nodes, seed=args.seed)
    scn.save(os.path.join(ROOT, "data", "sample_scenario.json"))
    tt = TravelTimes(scn.graph)
    print(f"Network: {scn.graph.n} nodes, {scn.graph.m} roads (connected: {scn.graph.is_connected()})")
    print(f"Depots: {scn.depots}   stock per depot: {scn.stock}")
    print(f"Demand nodes: {len(scn.demands)} ({len(scn.critical)} critical)   "
          f"total demand {scn.total_demand} units vs supply {scn.total_stock} units "
          f"({100 * scn.total_stock / scn.total_demand:.0f}%)")
    print(f"Fleet: {scn.total_vehicles} vehicles, capacity {next(iter(scn.fleet.values()))[1]} units each")
    pause()

    # 2 -------------------------------------------------------------------- #
    banner("STAGE 2 - Backbone (MST and Steiner tree)")
    terminals = scn.depots + scn.critical
    bb = backbone_report(scn.graph, terminals, tt)
    print(f"Kruskal MST cost : {bb['kruskal_cost']:.1f} min   Prim MST cost: {bb['prim_cost']:.1f} min "
          f"(identical: {bb['kruskal_equals_prim']})")
    print(f"Steiner backbone connecting {bb['n_terminals']} terminals (depots + critical nodes): "
          f"{bb['steiner_cost']:.1f} min = {bb['steiner_vs_mst_pct']:.0f}% of the full MST, "
          f"{bb['steiner_vs_all_pct']:.0f}% of all roads")
    pause()

    # 3 -------------------------------------------------------------------- #
    banner("STAGE 3 - Prioritization (deadline filter + knapsack DP)")
    plan = build_plan(scn, tt, 0.0)
    plan_buf = build_plan(scn, tt, BUFFER)
    pr = plan.priority
    print(f"Deadline filter : {len(pr.feasible)} feasible, {len(pr.rejected)} unreachable in time")
    print(f"Knapsack DP value {pr.knapsack_value}   greedy {pr.greedy_value}   LP upper bound {pr.bound:.0f}")
    print(f"DP selected {len(pr.selected)} demands, +{len(pr.extra)} added from leftover stock, "
          f"{len(pr.unassigned)} could not be assigned to a depot")
    pause()

    # 4 -------------------------------------------------------------------- #
    banner("STAGE 4 - Routing (Clarke-Wright + local search)")
    nominal_events = ex._nominal_events(scn, plan)
    nominal = summarise(scn, nominal_events)
    for i, r in enumerate(plan.routes, 1):
        arr = ", ".join(f"{s}@{a:.0f}" for s, a in zip(r.stops, r.arrivals))
        print(f" vehicle {i:2d} from depot {r.depot:2d}: load {r.load:2d}  duration {r.duration:5.0f} min  stops [{arr}]")
    print(f"Nominal result: {nominal['pct_demand']:.1f}% of demand delivered, "
          f"avg latency {nominal['avg_latency']:.0f} min")
    pause()

    # 5 -------------------------------------------------------------------- #
    banner("STAGE 5 - Robustness (Monte Carlo)")
    fails = [0.0, 0.05, 0.10, 0.20, 0.30, 0.40]
    delays = [0.25, 0.50, 1.00]
    rob = ex.robustness_experiments(scn, tt, bb["steiner_edges"], runs, fails, delays, BUFFER)
    sens = rob["sensitivity"]
    print(f"{runs} Monte Carlo runs per cell. % of demand delivered on time "
          f"(delay up to +50%):")
    print(f"{'closed roads':>14} " + " ".join(f"{s:>24}" for s in sens))
    for f in fails:
        print(f"{int(f * 100):>13}% " + " ".join(f"{sens[s][str(f)]['0.5']['pct_demand']:>23.1f}%" for s in sens))
    pause()

    # 6 -------------------------------------------------------------------- #
    banner("STAGE 6 - Algorithm experiments")
    sizes = [20, 40, 80, 160, 320] if args.quick else [20, 40, 80, 160, 320, 640, 1280]
    R = {
        "scalability": ex.scalability_experiment(sizes),
        "routing_scalability": ex.routing_scalability([10, 25, 50, 100] if args.quick else [10, 25, 50, 100, 200, 400, 800]),
        "density": ex.density_experiment([2, 3, 4, 6, 8]),
        "capacity": ex.capacity_experiment([15, 20, 30, 45, 60]),
        "knapsack_quality": ex.knapsack_quality(trials=6 if args.quick else 25),
        "routing_gap": ex.routing_gap_study(sizes=(5, 6, 7, 8, 9) if args.quick else (5, 6, 7, 8, 9, 10),
                                            instances=6 if args.quick else 25),
        "buffer_sweep": ex.buffer_sweep(scn, tt, [0.0, 0.1, 0.2, 0.3, 0.4, 0.5], runs),
    }
    last = R["scalability"][-1]
    print(f"Largest network n={last['n']}: Kruskal {last['kruskal_ms']:.1f} ms, DP {last['knapsack_dp_ms']:.1f} ms, "
          f"CW+LS {last['plan_cw_ls_ms']:.0f} ms")
    g = R["routing_gap"]
    print("Routing vs exact DP (avg gap): " + ", ".join(
        f"{r['customers']} cust: CW {r['cw_gap_pct']:.1f}% / CW+LS {r['ls_gap_pct']:.1f}%" for r in g))
    pause()

    # 7 -------------------------------------------------------------------- #
    banner("STAGE 7 - Figures, dashboard and policy tables")
    robust_cell = sens["buffer+adaptive+realloc"]["0.2"]["0.5"]
    static_cell = sens["static"]["0.2"]["0.5"]
    R.update({
        "sensitivity": sens, "timeseries": rob["timeseries"], "hardening": rob["hardening"],
        "fail_levels": fails, "delay_levels": delays, "backbone": {k: v for k, v in bb.items() if "edges" not in k},
        "runs": runs, "buffer": BUFFER,
        "kpis": {
            "pct_demand_nominal": nominal["pct_demand"], "avg_latency_nominal": nominal["avg_latency"],
            "pct_critical_nominal": nominal["pct_critical"],
            "supply_pct_of_demand": 100 * scn.total_stock / scn.total_demand,
            "n_routes": len(plan.routes), "total_route_time": plan.routing.total_duration,
            "robust_pct": robust_cell["pct_demand"], "static_pct": static_cell["pct_demand"],
            "knapsack_dp": pr.knapsack_value, "knapsack_greedy": pr.greedy_value, "knapsack_bound": pr.bound,
        },
        "scenario": scn.params,
    })

    R["decisions"] = [{"node": d.node, "priority": d.priority, "amount": d.amount, "population": d.population,
                       "deadline": d.deadline, "status": st, "reason": why} for d, st, why in decision_rows(scn, plan)]
    files = save_all(R, scn, plan, tt, bb["steiner_edges"], args.outdir)
    viz = build_viz(scn, plan, tt, bb["steiner_edges"])
    write_policy_tables(scn, plan, R, args.outdir)
    with open(os.path.join(args.outdir, "policy_recommendations.md")) as f:
        policy_md = f.read()
    dash = build_dashboard(R, viz, os.path.join(args.outdir, "dashboard.html"), policy_md)

    with open(os.path.join(args.outdir, "results.json"), "w") as f:
        json.dump(sanitize(R), f, indent=1)

    print("Written to", args.outdir)
    for p in files + [dash]:
        print("  -", os.path.basename(p))
    print("  - results.json, routes.csv, demand_decisions.csv, policy_recommendations.md")
    print(f"\nDone in {time.time() - t_start:.1f} s")


# --------------------------------------------------------------------------- #
def build_viz(scn, plan, tt, backbone_edges) -> dict:
    """Geometry needed by the HTML dashboard."""
    planned = set(plan.routing.served_nodes)
    routes = []
    for idx, r in enumerate(plan.routes):
        seq = [r.depot] + r.stops + [r.depot]
        path = []
        for a, b in zip(seq, seq[1:]):
            p = tt.path(a, b)
            path += p if not path else p[1:]
        routes.append({"depot": r.depot, "stops": r.stops, "path": path, "load": r.load,
                       "duration": round(r.duration, 1), "arrivals": [round(a, 1) for a in r.arrivals]})
    return {
        "coords": [[round(x, 2), round(y, 2)] for x, y in scn.coords],
        "edges": [[u, v] for u, v, _ in scn.graph.edges()],
        "backbone": [list(e) for e in backbone_edges],
        "depots": scn.depots,
        "demands": [{"node": d.node, "amount": d.amount, "priority": d.priority, "deadline": d.deadline,
                     "population": d.population, "planned": d.node in planned}
                    for d in scn.demands.values()],
        "routes": routes,
    }


def decision_rows(scn, plan):
    pr = plan.priority
    rej = {d.node for d in pr.rejected}
    dropped = set(plan.routing.dropped)
    selected = set(pr.selected)
    extra = set(pr.extra)
    unassigned = set(pr.unassigned)
    served = {s for r in plan.routes for s in r.stops}
    rows = []
    for d in sorted(scn.demands.values(), key=lambda x: (-x.priority, x.deadline)):
        if d.node in served:
            status, reason = "SERVED", "knapsack choice" if d.node in selected else "leftover stock"
        elif d.node in rej:
            status, reason = "NOT SERVED", "no depot can arrive before the deadline"
        elif d.node in dropped:
            status, reason = "NOT SERVED", "no vehicle left / route infeasible"
        elif d.node in unassigned:
            status, reason = "NOT SERVED", "no depot with enough stock in time"
        else:
            status, reason = "NOT SERVED", "supply exhausted (lower value per unit)"
        rows.append((d, status, reason))
    return rows


def write_policy_tables(scn, plan, R, outdir) -> None:
    with open(os.path.join(outdir, "routes.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["vehicle", "depot", "load_units", "route_minutes", "stop_node", "arrival_min", "deadline_min"])
        for i, r in enumerate(plan.routes, 1):
            for s, a in zip(r.stops, r.arrivals):
                w.writerow([i, r.depot, r.load, round(r.duration, 1), s, round(a, 1), scn.demands[s].deadline])
    with open(os.path.join(outdir, "demand_decisions.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["node", "priority", "units", "population", "deadline_min", "status", "reason"])
        for d, status, reason in decision_rows(scn, plan):
            w.writerow([d.node, d.priority, d.amount, d.population, d.deadline, status, reason])

    from collections import Counter
    k, sens, bs = R["kpis"], R["sensitivity"], R["buffer_sweep"]
    best_buf = max(bs, key=lambda r: r["pct_stressed"])
    hard = R["hardening"]
    i30 = R["fail_levels"].index(0.3)
    strat = "buffer+adaptive+realloc"
    hp, hu = hard["protected"][i30][strat], hard["unprotected"][i30][strat]
    gain = hp["pct_demand"] - hu["pct_demand"]
    gain_txt = (f"a gain of {gain:.1f} percentage points" if gain > 1.0
                else "no measurable gain in this scenario" if gain > -1.0 else f"a loss of {-gain:.1f} points")
    cell = lambda s, f, d: sens[s][str(f)][str(d)]["pct_demand"]
    dcalm = best_buf["pct_no_disruption"] - bs[0]["pct_no_disruption"]
    buffer_cost = ("so the buffer carries no penalty here" if dcalm > -1.0
                   else f"a cost of {-dcalm:.0f} points in calm conditions")
    served_units = sum(scn.demands[s].amount for r in plan.routes for s in r.stops)
    bb = R["backbone"]
    reasons = Counter(r for _, st, r in decision_rows(scn, plan) if st != "SERVED")
    unserved = sum(reasons.values())
    reason_txt = "; ".join(f"{n} {why}" for why, n in reasons.most_common()) or "none"
    quality = R["knapsack_quality"]
    mean_gap = sum(r["greedy_gap_pct"] for r in quality) / len(quality)
    max_gap = max(r["max_greedy_gap_pct"] for r in quality)
    lines = [
        "# Policy recommendations",
        "",
        f"Scenario: {scn.graph.n} nodes, {scn.graph.m} roads, {len(scn.depots)} depots, "
        f"{len(scn.demands)} demand nodes ({len(scn.critical)} critical), supply covers "
        f"{k['supply_pct_of_demand']:.0f}% of demand. Monte Carlo runs per cell: {R['runs']}.",
        "",
        "## 1. Plan with a safety buffer",
        f"With no buffer, the static plan delivers {cell('static', 0.2, 0.5):.0f}% of demand when 20% of roads are closed "
        f"and delays reach +50%. Planning with a {int(R['buffer'] * 100)}% travel-time buffer raises this to "
        f"{cell('static+buffer', 0.2, 0.5):.0f}%. In the buffer sweep (robust policy under the same stress), the best buffer was "
        f"{int(best_buf['buffer'] * 100)}% ({best_buf['pct_stressed']:.0f}% delivered, versus {bs[0]['pct_stressed']:.0f}% with no buffer). "
        f"Without any disruption the buffered plan delivers {best_buf['pct_no_disruption']:.0f}% against "
        f"{bs[0]['pct_no_disruption']:.0f}% for the unbuffered plan, {buffer_cost}.",
        "",
        "## 2. Re-route and re-allocate during execution",
        f"Adding live re-routing and a shared re-allocation pool on top of the buffered plan gives "
        f"{cell('buffer+adaptive+realloc', 0.2, 0.5):.0f}% under the same stress "
        f"(static + buffer: {cell('static+buffer', 0.2, 0.5):.0f}%). At 40% closures the robust policy delivers "
        f"{cell('buffer+adaptive+realloc', 0.4, 0.5):.0f}% against {cell('static', 0.4, 0.5):.0f}% for the static plan.",
        "",
        "## 3. Harden the backbone",
        f"The Steiner backbone connects all depots and critical nodes with {bb['steiner_vs_all_pct']:.0f}% of the total "
        f"road length. If closures never hit these roads, the robust policy delivers {hp['pct_demand']:.0f}% of demand at "
        f"30% closures versus {hu['pct_demand']:.0f}% when any road can close ({gain_txt}); critical demand: "
        f"{hp['pct_critical']:.0f}% versus {hu['pct_critical']:.0f}%.",
        "",
        "## 4. What limits the plan",
        f"The nominal schedule delivers {served_units} of {scn.total_demand} demanded units ({k['pct_demand_nominal']:.0f}%). "
        f"Of the {unserved} demand nodes left unserved: {reason_txt}.",
        "",
        "## 5. Use DP for the selection step",
        f"On this scenario the knapsack DP selects value {k['knapsack_dp']} versus {k['knapsack_greedy']} for greedy "
        f"(LP upper bound {k['knapsack_bound']:.0f}). Across the random scenarios tested, greedy loses {mean_gap:.2f}% of value on "
        f"average and up to {max_gap:.1f}% in the worst case; the DP is exact and takes only milliseconds even at 1,000+ nodes.",
        "",
    ]
    with open(os.path.join(outdir, "policy_recommendations.md"), "w") as f:
        f.write("\n".join(lines))


if __name__ == "__main__":
    main()
