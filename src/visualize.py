"""
visualize.py - All figures of the project (matplotlib).

Every plot_* function draws on a given Axes so the same code is used for the individual
PNG files and for the combined dashboard.png.
"""
from __future__ import annotations

import os
from typing import Dict, List, Sequence

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib.gridspec import GridSpec  # noqa: E402

COLORS = {
    "static": "#8c8c8c",
    "static+buffer": "#e0a030",
    "adaptive": "#5b8fd0",
    "adaptive+realloc": "#2f9e8f",
    "buffer+adaptive+realloc": "#c0392b",
}
ROUTE_COLORS = ["#1f77b4", "#ff7f0e", "#2ca02c", "#9467bd", "#8c564b", "#e377c2", "#17becf",
                "#bcbd22", "#d62728", "#7f7f7f"]
PRIORITY_COLORS = {1: "#c7d6e8", 2: "#9dbbd8", 3: "#6a9ac4", 4: "#e8a33d", 5: "#c0392b"}

plt.rcParams.update({
    "font.size": 9, "axes.titlesize": 10.5, "axes.titleweight": "bold",
    "axes.spines.top": False, "axes.spines.right": False, "axes.grid": True,
    "grid.alpha": 0.25, "figure.dpi": 110, "legend.fontsize": 8,
})


# --------------------------------------------------------------------------- #
# Network / spatial plots
# --------------------------------------------------------------------------- #
def plot_network(ax, scn, plan, backbone_edges, tt, title="Network, backbone and delivery routes"):
    xy = scn.coords
    for (u, v) in scn.graph.w:
        ax.plot([xy[u][0], xy[v][0]], [xy[u][1], xy[v][1]], color="#d5d5d5", lw=0.7, zorder=1)
    for u, v in backbone_edges:
        ax.plot([xy[u][0], xy[v][0]], [xy[u][1], xy[v][1]], color="#1b3a57", lw=3.2, alpha=0.35, zorder=2,
                solid_capstyle="round")
    for idx, r in enumerate(plan.routes):
        col = ROUTE_COLORS[idx % len(ROUTE_COLORS)]
        seq = [r.depot] + r.stops + [r.depot]
        for a, b in zip(seq, seq[1:]):
            p = tt.path(a, b)
            ax.plot([xy[i][0] for i in p], [xy[i][1] for i in p], color=col, lw=1.8, zorder=3, alpha=0.9)
    planned = set(plan.routing.served_nodes)
    for node, dem in scn.demands.items():
        served = node in planned
        ax.scatter(*xy[node], s=18 + 7 * dem.amount, c=PRIORITY_COLORS[dem.priority],
                   edgecolors="black" if served else "#999999", linewidths=1.2 if served else 0.6,
                   marker="o" if served else "X", zorder=4)
    for dpt in scn.depots:
        ax.scatter(*xy[dpt], s=170, marker="s", c="#111111", zorder=5)
        ax.annotate(f"D{dpt}", xy[dpt], xytext=(6, 6), textcoords="offset points", fontsize=8, weight="bold")
    ax.set_aspect("equal")
    ax.set_xlabel("x (km)")
    ax.set_ylabel("y (km)")
    ax.set_title(title)
    ax.grid(False)
    handles = [
        plt.Line2D([], [], marker="s", ls="", c="#111111", ms=8, label="Depot"),
        plt.Line2D([], [], color="#1b3a57", lw=3.2, alpha=0.4, label="Steiner backbone"),
        plt.Line2D([], [], marker="o", ls="", mfc="#c0392b", mec="black", ms=7, label="Served demand (size = units)"),
        plt.Line2D([], [], marker="X", ls="", mfc="#9dbbd8", mec="#999999", ms=7, label="Not served"),
    ]
    ax.legend(handles=handles, loc="upper left", bbox_to_anchor=(0, -0.12), ncol=2, frameon=False)


def plot_demand_heatmap(ax, scn, plan, title="Demand heatmap and service coverage"):
    g = 40
    grid = np.zeros((g, g))
    region = scn.params.get("region", 100.0)
    for node, dem in scn.demands.items():
        x, y = scn.coords[node]
        grid[min(int(y / region * g), g - 1), min(int(x / region * g), g - 1)] += dem.amount
    # separable gaussian blur (no scipy dependency)
    k = np.exp(-0.5 * (np.arange(-6, 7) / 2.2) ** 2)
    k /= k.sum()
    grid = np.apply_along_axis(lambda r: np.convolve(r, k, mode="same"), 0, grid)
    grid = np.apply_along_axis(lambda r: np.convolve(r, k, mode="same"), 1, grid)
    im = ax.imshow(grid, origin="lower", extent=[0, region, 0, region], cmap="YlOrRd", alpha=0.85)
    planned = set(plan.routing.served_nodes)
    for node in scn.demands:
        x, y = scn.coords[node]
        ax.scatter(x, y, s=22, marker="o" if node in planned else "x",
                   c="#1b3a57" if node in planned else "#555555", linewidths=1.0, zorder=3)
    for dpt in scn.depots:
        ax.scatter(*scn.coords[dpt], s=110, marker="s", c="#111111", zorder=4)
    ax.set_title(title)
    ax.set_xlabel("x (km)")
    ax.set_ylabel("y (km)")
    ax.grid(False)
    plt.colorbar(im, ax=ax, fraction=0.046, pad=0.03, label="demand density (units)")


# --------------------------------------------------------------------------- #
# Robustness plots
# --------------------------------------------------------------------------- #
def _grid(res, strategy, fails, delays, metric):
    return np.array([[res[strategy][str(f)][str(d)][metric] for d in delays] for f in fails])


def plot_sensitivity_heatmaps(axes, res, fails, delays, strategies, metric="pct_demand", vmax=None):
    vmax = vmax or max(_grid(res, s, fails, delays, metric).max() for s in strategies)
    im = None
    for ax, s in zip(axes, strategies):
        data = _grid(res, s, fails, delays, metric)
        im = ax.imshow(data, cmap="viridis", vmin=0, vmax=vmax, aspect="auto", origin="lower")
        for i in range(len(fails)):
            for j in range(len(delays)):
                ax.text(j, i, f"{data[i, j]:.0f}", ha="center", va="center",
                        color="white" if data[i, j] < 0.6 * vmax else "black", fontsize=8)
        ax.set_xticks(range(len(delays)))
        ax.set_xticklabels([f"+{int(d * 100)}%" for d in delays])
        ax.set_yticks(range(len(fails)))
        ax.set_yticklabels([f"{int(f * 100)}%" for f in fails])
        ax.set_xlabel("max delay on every road")
        ax.set_title(s, fontsize=9)
        ax.grid(False)
    axes[0].set_ylabel("roads closed")
    return im


def plot_resilience(ax, res, fails, delay, strategies, metric="pct_demand",
                    title="Service level under link failures"):
    for s in strategies:
        y = [res[s][str(f)][str(delay)][metric] for f in fails]
        ci = [res[s][str(f)][str(delay)][metric + "_ci"] for f in fails]
        ax.errorbar([f * 100 for f in fails], y, yerr=ci, marker="o", ms=4, lw=1.8, capsize=2,
                    color=COLORS[s], label=s)
    ax.set_xlabel("roads closed (%)")
    ax.set_ylabel("% of total demand delivered on time")
    ax.set_title(f"{title} (delay up to +{int(delay * 100)}%)")
    ax.set_ylim(bottom=0)
    ax.legend(frameon=False)


def plot_timeseries(ax, ts, strategies, title="Delivered demand over time (20% roads closed, delay up to +50%)"):
    for s in strategies:
        ax.plot(ts["grid"], ts["series"][s], color=COLORS[s], lw=2, label=s)
    ax.set_xlabel("time since response start (min)")
    ax.set_ylabel("cumulative % of demand delivered")
    ax.set_title(title)
    ax.legend(frameon=False, loc="upper left")


def plot_hardening(ax, hard, strategy="buffer+adaptive+realloc", metric="pct_demand",
                   title="Protecting the backbone: demand delivered"):
    fl = [f * 100 for f in hard["fail_levels"]]
    for key, ls, lab in (("unprotected", "--", "backbone not protected"), ("protected", "-", "backbone protected")):
        ax.plot(fl, [row[strategy][metric] for row in hard[key]], ls=ls, marker="o", ms=4, lw=2,
                color="#c0392b" if key == "protected" else "#8c8c8c", label=lab)
    ax.set_xlabel("roads closed (%)")
    ax.set_ylabel("% of total demand delivered")
    ax.set_title(title)
    ax.legend(frameon=False)


def plot_buffer(ax, rows, title="Planning safety buffer trade-off"):
    b = [r["buffer"] * 100 for r in rows]
    ax.plot(b, [r["pct_no_disruption"] for r in rows], marker="s", color="#8c8c8c", lw=2, label="no disruption")
    ax.errorbar(b, [r["pct_stressed"] for r in rows], yerr=[r["pct_stressed_ci"] for r in rows], marker="o",
                color="#c0392b", lw=2, capsize=2, label="20% roads closed, delay up to +50%")
    ax.set_xlabel("safety buffer added to planned travel times (%)")
    ax.set_ylabel("% of total demand delivered")
    ax.set_title(title)
    ax.legend(frameon=False)


# --------------------------------------------------------------------------- #
# Scalability / quality plots
# --------------------------------------------------------------------------- #
def plot_scalability(ax, rows, title="Runtime vs network size"):
    n = [r["n"] for r in rows]
    series = [("kruskal_ms", "Kruskal", "#5b8fd0"), ("prim_ms", "Prim", "#2f9e8f"),
              ("steiner_ms", "Steiner (KMB)", "#9467bd"), ("knapsack_dp_ms", "Knapsack DP", "#c0392b"),
              ("knapsack_greedy_ms", "Knapsack greedy", "#e0a030"),
              ("routing_cw_ms", "Routing: Clarke-Wright", "#17becf"),
              ("routing_ls_ms", "Routing: CW + local search", "#7f7f7f"),
              ("plan_cw_ls_ms", "Full planning", "#111111")]
    for key, lab, col in series:
        ax.plot(n, [max(r[key], 1e-3) for r in rows], marker="o", ms=3.5, lw=1.8, color=col, label=lab)
    ax.set_xscale("log", base=2)
    ax.set_yscale("log")
    ax.set_xlabel("number of network nodes n")
    ax.set_ylabel("runtime (ms)")
    ax.set_title(title)
    ax.legend(frameon=False, ncol=2, fontsize=7)


def plot_routing_scalability(ax, rows, title="Routing heuristics vs number of customers"):
    m = [r["customers"] for r in rows]
    ax.plot(m, [r["cw_ms"] for r in rows], marker="o", color="#17becf", lw=2, label="Clarke-Wright")
    ls = [(r["customers"], r["ls_ms"]) for r in rows if "ls_ms" in r]
    if ls:
        ax.plot(*zip(*ls), marker="s", color="#7f7f7f", lw=2, label="Local search (after CW)")
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlabel("customers served from one depot")
    ax.set_ylabel("runtime (ms)")
    ax.set_title(title)
    ax.legend(frameon=False)


def plot_routing_gap(ax, rows, title="Heuristic quality vs exact DP"):
    m = np.array([r["customers"] for r in rows])
    w = 0.38
    ax.bar(m - w / 2, [r["cw_gap_pct"] for r in rows], w, color="#17becf", label="Clarke-Wright")
    ax.bar(m + w / 2, [r["ls_gap_pct"] for r in rows], w, color="#7f7f7f", label="CW + local search")
    ax.set_xlabel("customers per instance")
    ax.set_ylabel("average gap to optimum (%)")
    ax.set_title(title)
    ax.legend(frameon=False)


def plot_knapsack(ax, rows, title="Knapsack: greedy gap to the DP optimum"):
    sizes = sorted({r["n"] for r in rows})
    fr = sorted({r["stock_frac"] for r in rows})
    w = 0.8 / len(sizes)
    for k, n in enumerate(sizes):
        vals = [next(r["greedy_gap_pct"] for r in rows if r["n"] == n and r["stock_frac"] == f) for f in fr]
        ax.bar(np.arange(len(fr)) + k * w - 0.4 + w / 2, vals, w, label=f"{n} nodes")
    ax.set_xticks(range(len(fr)))
    ax.set_xticklabels([f"{int(f * 100)}% of demand in stock" for f in fr])
    ax.set_ylabel("average value lost by greedy (%)")
    ax.set_title(title)
    ax.legend(frameon=False)


def plot_density(ax, rows, title="Road density"):
    k = [r["k"] for r in rows]
    ax.plot(k, [r["mst_cost"] for r in rows], marker="o", color="#5b8fd0", lw=2, label="MST cost")
    ax.plot(k, [r["steiner_cost"] for r in rows], marker="o", color="#9467bd", lw=2, label="Steiner backbone cost")
    ax.set_xlabel("neighbours per node (k)")
    ax.set_ylabel("tree cost (minutes of road)")
    ax.legend(frameon=False, loc="upper left")
    ax2 = ax.twinx()
    ax2.plot(k, [r["pct_demand"] for r in rows], marker="s", color="#c0392b", lw=2, label="% demand served")
    ax2.set_ylabel("% demand served (nominal)")
    ax2.spines["right"].set_visible(True)
    ax2.legend(frameon=False, loc="lower right")
    ax.set_title(title)


def plot_capacity(ax, rows, title="Vehicle capacity"):
    c = [r["capacity"] for r in rows]
    ax.plot(c, [r["pct_demand"] for r in rows], marker="o", color="#c0392b", lw=2, label="% demand served")
    ax.set_xlabel("vehicle capacity (units)")
    ax.set_ylabel("% demand served (nominal)")
    ax2 = ax.twinx()
    ax2.plot(c, [r["avg_latency"] for r in rows], marker="s", color="#5b8fd0", lw=2, label="avg latency")
    ax2.set_ylabel("average delivery latency (min)")
    ax2.spines["right"].set_visible(True)
    ax.legend(frameon=False, loc="lower left")
    ax2.legend(frameon=False, loc="lower right")
    ax.set_title(title)


# --------------------------------------------------------------------------- #
# Saving figures
# --------------------------------------------------------------------------- #
def _save(fig, outdir, name):
    path = os.path.join(outdir, name)
    fig.savefig(path, dpi=140, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return path


def save_all(R: dict, scn, plan, tt, backbone_edges, outdir: str) -> List[str]:
    """Create every PNG from the results dictionary R and return the file names."""
    os.makedirs(outdir, exist_ok=True)
    strategies = list(R["sensitivity"].keys())
    fails, delays = R["fail_levels"], R["delay_levels"]
    mid_delay = delays[len(delays) // 2]
    files = []

    fig, ax = plt.subplots(figsize=(8, 8.4))
    plot_network(ax, scn, plan, backbone_edges, tt)
    files.append(_save(fig, outdir, "network_map.png"))

    fig, ax = plt.subplots(figsize=(7, 6))
    plot_demand_heatmap(ax, scn, plan)
    files.append(_save(fig, outdir, "demand_heatmap.png"))

    fig, axes = plt.subplots(1, len(strategies), figsize=(3.3 * len(strategies), 3.9), sharey=True)
    im = plot_sensitivity_heatmaps(axes, R["sensitivity"], fails, delays, strategies)
    fig.colorbar(im, ax=axes, fraction=0.02, pad=0.02, label="% of demand delivered on time")
    fig.suptitle("Sensitivity study: road closures x delay range (mean of Monte Carlo runs)", fontweight="bold")
    files.append(_save(fig, outdir, "sensitivity.png"))

    fig, ax = plt.subplots(figsize=(7.5, 5))
    plot_resilience(ax, R["sensitivity"], fails, mid_delay, strategies)
    files.append(_save(fig, outdir, "resilience.png"))

    fig, ax = plt.subplots(figsize=(7.5, 5))
    plot_timeseries(ax, R["timeseries"], strategies)
    files.append(_save(fig, outdir, "delivery_timeseries.png"))

    fig, axes = plt.subplots(1, 2, figsize=(13, 5))
    plot_scalability(axes[0], R["scalability"])
    plot_routing_scalability(axes[1], R["routing_scalability"])
    files.append(_save(fig, outdir, "scalability.png"))

    fig, axes = plt.subplots(1, 2, figsize=(13, 4.6))
    plot_knapsack(axes[0], R["knapsack_quality"])
    plot_routing_gap(axes[1], R["routing_gap"])
    files.append(_save(fig, outdir, "algorithm_quality.png"))

    fig, axes = plt.subplots(1, 2, figsize=(13, 4.6))
    plot_buffer(axes[0], R["buffer_sweep"])
    plot_hardening(axes[1], R["hardening"])
    files.append(_save(fig, outdir, "policy_studies.png"))

    fig, axes = plt.subplots(1, 2, figsize=(13, 4.6))
    plot_density(axes[0], R["density"])
    plot_capacity(axes[1], R["capacity"])
    files.append(_save(fig, outdir, "density_capacity.png"))

    files.append(_save(_dashboard(R, scn, plan, tt, backbone_edges, strategies, fails, delays, mid_delay),
                       outdir, "dashboard.png"))
    return files


def _dashboard(R, scn, plan, tt, backbone_edges, strategies, fails, delays, mid_delay):
    fig = plt.figure(figsize=(22, 15))
    gs = GridSpec(3, 4, figure=fig, hspace=0.42, wspace=0.34, left=0.04, right=0.97, top=0.92, bottom=0.05)
    k = R["kpis"]

    ax = fig.add_subplot(gs[0, 0])
    ax.axis("off")
    lines = [
        ("Disaster response dashboard", 14, "bold"),
        (f"{scn.graph.n} nodes, {scn.graph.m} roads, {len(scn.depots)} depots", 10, "normal"),
        (f"{len(scn.demands)} demand nodes, {len(scn.critical)} critical", 10, "normal"),
        ("", 6, "normal"),
        (f"Planned demand served:  {k['pct_demand_nominal']:.0f}%", 11, "bold"),
        (f"Supply available:  {k['supply_pct_of_demand']:.0f}% of demand", 10, "normal"),
        (f"Avg delivery latency:  {k['avg_latency_nominal']:.0f} min", 10, "normal"),
        (f"Routes: {k['n_routes']} vehicles, {k['total_route_time']:.0f} min total", 10, "normal"),
        ("", 6, "normal"),
        (f"Robust policy at 20% closures, +50% delay:", 10, "bold"),
        (f"   {k['robust_pct']:.0f}% delivered vs {k['static_pct']:.0f}% for the static plan", 10, "normal"),
    ]
    y = 0.98
    for text, size, weight in lines:
        ax.text(0, y, text, fontsize=size, weight=weight, va="top", transform=ax.transAxes)
        y -= 0.065 if size >= 10 else 0.03

    plot_network(fig.add_subplot(gs[0, 1:3]), scn, plan, backbone_edges, tt)
    plot_demand_heatmap(fig.add_subplot(gs[0, 3]), scn, plan)

    best = "buffer+adaptive+realloc"
    sub = gs[1, 0].subgridspec(1, 1)
    ax = fig.add_subplot(sub[0])
    plot_sensitivity_heatmaps([ax], R["sensitivity"], fails, delays, [best])
    ax.set_title(f"Delivered % by closures x delay\n({best})", fontsize=9)

    plot_resilience(fig.add_subplot(gs[1, 1]), R["sensitivity"], fails, mid_delay, strategies)
    plot_timeseries(fig.add_subplot(gs[1, 2]), R["timeseries"], strategies, title="Delivered demand over time")
    plot_hardening(fig.add_subplot(gs[1, 3]), R["hardening"])
    plot_scalability(fig.add_subplot(gs[2, 0:2]), R["scalability"])
    plot_routing_gap(fig.add_subplot(gs[2, 2]), R["routing_gap"])
    plot_buffer(fig.add_subplot(gs[2, 3]), R["buffer_sweep"])
    fig.suptitle("Disaster Response Logistics - Multi-Depot Routing & Resource Allocation", fontsize=17,
                 fontweight="bold")
    return fig
