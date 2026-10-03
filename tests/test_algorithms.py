"""
Unit tests. Run from the project root with:   python -m unittest discover -s tests -v

Each algorithm is checked against an independent reference (brute force, a second algorithm
or a mathematical property), not only against itself.
"""
import dataclasses
import itertools
import os
import random
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from backbone import DSU, kruskal, prim, steiner_kmb  # noqa: E402
from metrics import summarise  # noqa: E402
from network import (Graph, Scenario, TravelTimes, bellman_ford, floyd_warshall,  # noqa: E402
                     generate_scenario)
from planner import build_plan  # noqa: E402
from prioritization import (deadline_filter, knapsack_bruteforce, knapsack_dp,  # noqa: E402
                            knapsack_fractional_bound, knapsack_greedy)
from robustness import STRATEGIES, execute, make_disruptions, monte_carlo  # noqa: E402
from routing import clarke_wright, evaluate_route, exact_routes  # noqa: E402


def random_graph(n, extra, seed):
    rng = random.Random(seed)
    g = Graph(n)
    for i in range(1, n):
        g.add_edge(i, rng.randrange(i), rng.uniform(1, 10))
    for _ in range(extra):
        g.add_edge(rng.randrange(n), rng.randrange(n), rng.uniform(1, 10))
    return g


class TestShortestPaths(unittest.TestCase):
    def test_dijkstra_matches_bellman_ford_and_floyd_warshall(self):
        for seed in range(5):
            g = random_graph(25, 30, seed)
            fw = floyd_warshall(g)
            for s in range(g.n):
                dist, _ = g.dijkstra(s)
                bf = bellman_ford(g, s)
                for t in range(g.n):
                    self.assertAlmostEqual(dist[t], bf[t], places=9)
                    self.assertAlmostEqual(dist[t], fw[s][t], places=9)

    def test_blocked_edge_is_never_used(self):
        g = Graph(3)
        g.add_edge(0, 1, 1)
        g.add_edge(1, 2, 1)
        g.add_edge(0, 2, 10)
        dist, _ = g.dijkstra(0, blocked={(0, 1)})
        self.assertEqual(dist[2], 10)
        dist, _ = g.dijkstra(0, scale={(0, 1): 20.0})
        self.assertEqual(dist[2], 10)


class TestBackbone(unittest.TestCase):
    def test_kruskal_equals_prim_and_spans(self):
        for seed in range(8):
            g = random_graph(30, 40, seed)
            kt, kc = kruskal(g.n, g.edges())
            pt, pc = prim(g)
            self.assertAlmostEqual(kc, pc, places=9)
            self.assertEqual(len(kt), g.n - 1)
            self.assertEqual(len(pt), g.n - 1)
            dsu = DSU(g.n)
            for u, v, _ in kt:
                dsu.union(u, v)
            self.assertEqual(len({dsu.find(i) for i in range(g.n)}), 1)

    def test_steiner_within_two_approximation_of_brute_force_optimum(self):
        for seed in range(6):
            g = random_graph(9, 8, seed)
            tt = TravelTimes(g)
            terminals = [0, 3, 5, 8]
            others = [x for x in range(g.n) if x not in terminals]
            best = float("inf")
            for r in range(len(others) + 1):
                for extra in itertools.combinations(others, r):
                    nodes = set(terminals) | set(extra)
                    sub = [(u, v, w) for u, v, w in g.edges() if u in nodes and v in nodes]
                    tree, cost = kruskal(g.n, sub)
                    dsu = DSU(g.n)
                    for u, v, _ in tree:
                        dsu.union(u, v)
                    if len({dsu.find(t) for t in terminals}) == 1:
                        best = min(best, cost)
            edges, cost = steiner_kmb(g, terminals, tt)
            dsu = DSU(g.n)
            for u, v, _ in edges:
                dsu.union(u, v)
            self.assertEqual(len({dsu.find(t) for t in terminals}), 1, "terminals must be connected")
            self.assertLessEqual(cost, 2 * (1 - 1 / len(terminals)) * best + 1e-9)
            self.assertGreaterEqual(cost, best - 1e-9)


class TestKnapsack(unittest.TestCase):
    def test_dp_is_optimal(self):
        rng = random.Random(1)
        for _ in range(40):
            n = rng.randint(1, 12)
            w = [rng.randint(1, 10) for _ in range(n)]
            v = [rng.randint(1, 50) for _ in range(n)]
            cap = rng.randint(1, 40)
            val, chosen = knapsack_dp(w, v, cap)
            self.assertEqual(val, knapsack_bruteforce(w, v, cap))
            self.assertEqual(val, sum(v[i] for i in chosen))
            self.assertLessEqual(sum(w[i] for i in chosen), cap)

    def test_ordering_greedy_dp_bound(self):
        rng = random.Random(2)
        for _ in range(40):
            n = rng.randint(2, 30)
            w = [rng.randint(1, 15) for _ in range(n)]
            v = [rng.randint(1, 100) for _ in range(n)]
            cap = rng.randint(5, 80)
            dp, _ = knapsack_dp(w, v, cap)
            gr, _ = knapsack_greedy(w, v, cap)
            self.assertLessEqual(gr, dp)
            self.assertLessEqual(dp, knapsack_fractional_bound(w, v, cap) + 1e-9)


class TestScenarioAndPlan(unittest.TestCase):
    def setUp(self):
        self.scn = generate_scenario(seed=7)
        self.tt = TravelTimes(self.scn.graph)

    def test_scenario_connected_and_reproducible(self):
        self.assertTrue(self.scn.graph.is_connected())
        again = generate_scenario(seed=7)
        self.assertEqual(self.scn.graph.edges(), again.graph.edges())
        self.assertEqual(self.scn.stock, again.stock)

    def test_save_load_roundtrip(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "s.json")
            self.scn.save(p)
            back = Scenario.load(p)
        self.assertEqual(back.depots, self.scn.depots)
        self.assertEqual(back.stock, self.scn.stock)
        self.assertEqual(set(back.demands), set(self.scn.demands))
        self.assertEqual(back.graph.m, self.scn.graph.m)

    def test_deadline_filter_is_exact(self):
        feas, rej = deadline_filter(self.scn, self.tt)
        for d in feas:
            self.assertLessEqual(min(self.tt.d(dp, d.node) for dp in self.scn.depots), d.deadline)
        for d in rej:
            self.assertGreater(min(self.tt.d(dp, d.node) for dp in self.scn.depots), d.deadline)

    def test_plan_respects_stock_capacity_and_deadlines(self):
        for safety in (0.0, 0.25):
            plan = build_plan(self.scn, self.tt, safety)
            served = [s for r in plan.routes for s in r.stops]
            self.assertEqual(len(served), len(set(served)), "a demand must be served by one vehicle only")
            per_depot = {}
            for r in plan.routes:
                per_depot[r.depot] = per_depot.get(r.depot, 0) + r.load
                cap = self.scn.fleet[r.depot][1]
                ok, _, _ = evaluate_route(r.depot, r.stops, self.tt, self.scn.demands, self.scn.service_time, cap)
                self.assertTrue(ok)
                self.assertLessEqual(r.load, cap)
            for d, used in per_depot.items():
                self.assertLessEqual(used, self.scn.stock[d])
            for d in self.scn.depots:
                n_routes = sum(1 for r in plan.routes if r.depot == d)
                self.assertLessEqual(n_routes, self.scn.fleet[d][0])


class TestRouting(unittest.TestCase):
    def test_exact_never_worse_than_clarke_wright_and_is_feasible(self):
        checked = 0
        for inst in range(12):
            scn = generate_scenario(n_nodes=50, seed=500 + inst, demand_frac=0.9)
            tt = TravelTimes(scn.graph)
            depot = scn.depots[0]
            dem = {k: dataclasses.replace(d, deadline=d.deadline * 2.5) for k, d in scn.demands.items()}
            pool = [c for c in dem if evaluate_route(depot, [c], tt, dem, scn.service_time, 30)[0]]
            cust = random.Random(inst).sample(pool, 7)
            cw = clarke_wright(depot, cust, tt, dem, scn.service_time, 30)
            if sorted(s for r in cw for s in r) != sorted(cust):
                continue
            res = exact_routes(depot, cust, tt, dem, scn.service_time, 30, len(cw))
            self.assertIsNotNone(res)
            total, routes = res
            cw_total = sum(evaluate_route(depot, r, tt, dem, scn.service_time, 30)[2] for r in cw)
            self.assertLessEqual(total, cw_total + 1e-6)
            self.assertEqual(sorted(s for r in routes for s in r), sorted(cust))
            recomputed = 0.0
            for r in routes:
                ok, _, dur = evaluate_route(depot, r, tt, dem, scn.service_time, 30)
                self.assertTrue(ok)
                recomputed += dur
            self.assertAlmostEqual(recomputed, total, places=6)
            checked += 1
        self.assertGreater(checked, 5)

    def test_exact_matches_brute_force_on_tiny_instance(self):
        scn = generate_scenario(n_nodes=40, seed=9, demand_frac=0.9)
        tt = TravelTimes(scn.graph)
        depot = scn.depots[0]
        dem = {k: dataclasses.replace(d, deadline=1e9) for k, d in scn.demands.items()}
        cust = sorted(dem)[:5]
        total, _ = exact_routes(depot, cust, tt, dem, scn.service_time, 10 ** 6, 1)
        best = min(evaluate_route(depot, list(p), tt, dem, scn.service_time, 10 ** 6)[2]
                   for p in itertools.permutations(cust))
        self.assertAlmostEqual(total, best, places=6)


class TestRobustness(unittest.TestCase):
    def setUp(self):
        self.scn = generate_scenario(seed=7)
        self.tt = TravelTimes(self.scn.graph)
        self.plans = {"nominal": build_plan(self.scn, self.tt, 0.0), "buffered": build_plan(self.scn, self.tt, 0.25)}

    def test_no_disruption_reproduces_the_nominal_plan(self):
        dis = make_disruptions(self.scn, 0.0, 0.0, 1, 0)[0]
        plan = self.plans["nominal"]
        nominal = sorted((round(a, 6), s) for r in plan.routes for s, a in zip(r.stops, r.arrivals))
        got = sorted((round(t, 6), s) for t, s, _ in execute(self.scn, self.plans, self.tt, "static", dis))
        self.assertEqual(got, nominal)
        for strat in ("adaptive", "adaptive+realloc"):
            ev = execute(self.scn, self.plans, self.tt, strat, dis)
            self.assertEqual(sorted(s for _, s, _ in ev), sorted(s for _, s in nominal))

    def test_events_respect_deadlines_and_unique_service(self):
        for strat in STRATEGIES:
            for dis in make_disruptions(self.scn, 0.3, 0.5, 8, 3):
                ev = execute(self.scn, self.plans, self.tt, strat, dis)
                nodes = [s for _, s, _ in ev]
                self.assertEqual(len(nodes), len(set(nodes)))
                for t, s, _ in ev:
                    self.assertLessEqual(t, self.scn.demands[s].deadline + 1e-9)
                self.assertLessEqual(summarise(self.scn, ev)["pct_demand"], 100.0)

    def test_monte_carlo_is_reproducible(self):
        a = monte_carlo(self.scn, self.plans, self.tt, ["adaptive+realloc"], 0.2, 0.5, 10, 42)
        b = monte_carlo(self.scn, self.plans, self.tt, ["adaptive+realloc"], 0.2, 0.5, 10, 42)
        self.assertEqual(a["adaptive+realloc"]["pct_demand"], b["adaptive+realloc"]["pct_demand"])

    def test_more_failures_never_help_on_average(self):
        lo = monte_carlo(self.scn, self.plans, self.tt, ["static"], 0.0, 0.5, 40, 1)["static"]["pct_demand"]
        hi = monte_carlo(self.scn, self.plans, self.tt, ["static"], 0.4, 0.5, 40, 1)["static"]["pct_demand"]
        self.assertGreater(lo, hi)


if __name__ == "__main__":
    unittest.main()
