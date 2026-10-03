# Disaster Response Logistics: Multi-Depot Routing and Resource Allocation

After a disaster, several depots hold limited supplies and many demand nodes (shelters, hospitals,
neighbourhoods) need them before a deadline. Roads are slow and some are closed. This project decides
**what to serve, from which depot, along which route**, and how to stay robust when travel times are uncertain.

Everything is pure Python (standard library + matplotlib) and fully reproducible from a random seed.

## Quick start

```bash
pip install -r requirements.txt
python main.py            # full run, about 20 seconds
python main.py --quick    # fast run for testing (about 6 seconds)
python main.py --demo     # pauses between stages, for the live demonstration
python -m unittest discover -s tests -v    # 16 unit tests
```

Open `outputs/dashboard.html` in any browser (works offline) for the interactive dashboard.

## How the project covers the assignment

| Requirement | Where |
|---|---|
| Network model (adjacency lists, priority queue) | `src/network.py` (`Graph`, binary-heap `dijkstra`) |
| Dataset: synthetic scenarios with depots, demands, deadlines, fleet | `src/network.py` (`generate_scenario`), sample in `data/sample_scenario.json` |
| 1. Backbone: MST or Steiner approximation | `src/backbone.py` (Kruskal, Prim, Kou-Markowsky-Berman Steiner tree) |
| 2. Prioritization: 0-1 knapsack with deadlines, DP | `src/prioritization.py` (deadline filter + knapsack DP, greedy and LP bound as baselines) |
| 3. Routing: Clarke-Wright, local search, exact small-instance DP | `src/routing.py` |
| 4. Robustness: random delays, robust and greedy re-allocation | `src/robustness.py` (5 strategies, Monte Carlo) |
| 5. Metrics: % demand satisfied, latency, resilience under X% link failure | `src/metrics.py` |
| Simulator with demand scenarios and resource constraints | `src/network.py` (scenarios) + `src/robustness.py` (event-driven execution) |
| Robustness experiments and sensitivity studies | `experiments.py` |
| SSSP / APSP algorithms | Dijkstra (production), Bellman-Ford and Floyd-Warshall (reference implementations, cross-checked in the tests) |
| Visualizations: maps, heatmaps, time series of delivered demand | `src/visualize.py` -> `outputs/*.png`, `outputs/dashboard.html` |
| Policy outputs: routes, schedules, cost/benefit | `outputs/routes.csv`, `outputs/demand_decisions.csv`, `outputs/policy_recommendations.md` |

## Pipeline

```
scenario ──> backbone (Steiner tree: depots + critical nodes)
   │
   └──> deadline filter ──> knapsack DP ──> depot allocation ──> Clarke-Wright ──> local search
                                                                        │
                                   Monte Carlo: random delays + closed roads
                                   static | static+buffer | adaptive | adaptive+realloc | buffer+adaptive+realloc
```

## Project layout

```
main.py                  runs everything end to end (stages 1-7)
experiments.py           scalability, density, capacity, quality and robustness studies
src/network.py           graph, shortest paths, scenario generator
src/backbone.py          Kruskal, Prim, Steiner tree (KMB)
src/prioritization.py    deadline filter, knapsack DP / greedy / LP bound, depot allocation
src/routing.py           Clarke-Wright, 2-opt + relocate, exact DP (Held-Karp + set partition)
src/planner.py           chains the stages into one dispatch plan
src/robustness.py        disruptions, execution strategies, Monte Carlo
src/metrics.py           evaluation metrics
src/visualize.py         all figures
src/dashboard_html.py    interactive HTML dashboard
tests/                   unit tests against brute force and reference algorithms
data/                    sample scenario (JSON)
outputs/                 figures, dashboard, CSV tables, results.json
docs/                    algorithm reference, demo script, viva questions, checklist
```

## Headline results (seed 7: 60 nodes, 3 depots, 34 demand nodes, supply = 55% of demand)

| Result | Value |
|---|---|
| Nominal plan (no disruption) | 52.7% of demand delivered on time, average latency 87 min, 8 vehicle routes |
| Static plan, 20% roads closed, delay up to +50% | 13.5% delivered |
| Robust policy (25% buffer + re-routing + re-allocation), same stress | 47.7% delivered |
| Same comparison at 40% roads closed | 36.4% (robust) against 7.3% (static) |
| Steiner backbone | 431.9 min of road: 52% of the full MST (835.4 min) and 20% of all roads |
| Backbone protected, 30% closures | 50.1% delivered against 42.3% when any road can close |
| Knapsack on this scenario | DP 45110, greedy 45088, LP upper bound 45306 |
| Knapsack over random scenarios | greedy loses 0.07% to 0.67% on average, up to 7.9% in the worst case |
| Clarke-Wright vs exact DP (5 to 10 customers) | average gap 2.1% to 6.0%; with local search 0.2% to 2.0% |
| Largest network tested (1,280 nodes) | knapsack DP about 0.2 s, routing (Clarke-Wright + local search) about 30 ms, Kruskal about 2 ms; full planning about 0.45 s including shortest paths |

Exact numbers for every experiment are in `outputs/results.json`.

## Model and assumptions

* Travel time on a road = Euclidean distance x 1.5 min/km x detour factor in [1.0, 1.3]; unloading takes 5 min per stop.
* Demand has units (knapsack weight), priority 1 to 5, population and a deadline. Knapsack value = priority x population.
  Critical nodes (priority 5) have larger demands and tight deadlines (45 to 150 min).
* Supply covers 55% of total demand, so *which* demands to serve is a real decision.
* One commodity ("supply units"). Vehicles leave their depot at t = 0 with their planned load.
* A delivery counts only if the vehicle arrives before the deadline.
* Disruption: each road gets a delay multiplier 1 + U(0, d_max); a fraction of roads is closed at random.
* Adaptive strategies assume the fleet sees live road closures and current delays (real-time information).
* All strategies are compared on identical random disruptions (common random numbers).

## Known limitations (be ready to discuss them)

* The knapsack optimises over the pooled supply of all depots; the depot allocation and routing stages are heuristics,
  so the final plan is not guaranteed optimal as a whole.
* Critical demand is hard to protect: with deadlines of 45 to 150 min and delays up to +50%, only about 19% to 24% of critical
  demand arrives on time under stress (20% closures, +50% delay), whatever the strategy. Moving supplies closer to critical nodes would be the natural remedy (not tested here).
* Exact routing is limited to 13 customers per depot (3^n set-partition DP), so heuristic quality is measured on small instances only.
* Synthetic data: results show relative behaviour of the policies, not absolute predictions for a real city.
