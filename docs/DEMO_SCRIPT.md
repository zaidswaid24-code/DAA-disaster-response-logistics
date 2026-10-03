# Demo script (15 to 20 minutes)

The assignment asks for a 15 to 20 minute presentation with a demo. This script uses the live run (`python main.py --demo`) as the backbone
and the pre-generated figures as visual support. Every person should be able to deliver any part.

## Before you start (5 minutes of setup)

1. Open a terminal in the project folder. Check: `python main.py --quick` finishes without errors (6 seconds).
2. Run `python main.py` once so `outputs/` is fresh. Keep this as a fallback.
3. Open in separate tabs/windows, in this order: `outputs/dashboard.html`, `outputs/network_map.png`, `outputs/algorithm_quality.png`,
   `outputs/sensitivity.png`, `outputs/resilience.png`, `outputs/delivery_timeseries.png`, `outputs/scalability.png`, `outputs/policy_studies.png`.
4. Make the terminal font large. Run `python main.py --demo` when you reach Stage 1.

If the live run fails: say so calmly, show `outputs/` and `results.json`, and continue with the figures. Never debug in front of the audience.

## Timeline

| Time | Part | Show | Run |
|---|---|---|---|
| 0:00 to 1:30 | Problem and objective | slide-free: say it, or show `network_map.png` | |
| 1:30 to 3:00 | Model, data and assumptions | `network_map.png` | `--demo` Stage 1 |
| 3:00 to 5:00 | Backbone | terminal | Stage 2 |
| 5:00 to 7:30 | Prioritization | terminal | Stage 3 |
| 7:30 to 10:00 | Routing | terminal + `algorithm_quality.png` | Stage 4 |
| 10:00 to 14:00 | Robustness | terminal + `sensitivity.png`, `resilience.png`, `delivery_timeseries.png` | Stage 5 |
| 14:00 to 16:00 | Scalability and quality | `scalability.png`, `algorithm_quality.png` | Stage 6 |
| 16:00 to 18:00 | Interactive dashboard | `dashboard.html` | |
| 18:00 to 19:30 | Recommendations and conclusion | `policy_studies.png`, `policy_recommendations.md` | |
| 19:30 to 20:00 | Questions | | |

## What to say

### 0:00 Problem and objective
"After a disaster we have a few depots with limited supplies and many places that need them before a deadline: hospitals, shelters, villages.
Roads are slow and some are closed. We must decide what to serve, from which depot and along which route, to maximise the demand delivered on time,
and the plan must still work when travel times are uncertain."
State the five components: backbone, prioritization, routing, robustness, metrics.

### 1:30 Model and data (Stage 1)
- The network is synthetic and reproducible from a seed: 60 nodes, 118 roads, 3 depots, 34 demand nodes of which 5 are critical (priority 5, tight deadlines).
- Supply covers only 55% of demand, so choosing what to serve is the real problem.
- Point at the map: black squares are depots, circles are demands (size = units), crosses are demands we will not serve.
- Mention the assumptions: one commodity, travel time = road weight, 5 minutes unloading per stop, a delivery only counts if it arrives before the deadline.

### 3:00 Backbone (Stage 2)
- "Kruskal and Prim give the same minimum spanning tree cost, 835 minutes, as they must."
- "But we do not need to connect every node. We need depots and critical nodes connected. A Steiner tree does that with 432 minutes, 52% of the MST and 20% of all roads."
- "KMB is a 2-approximation because Steiner tree is NP-hard." Later we use this backbone as the set of roads to protect.

### 5:00 Prioritization (Stage 3)
- Two steps: a deadline filter removes demands that no depot can reach in time (2 of 34); then a 0-1 knapsack DP picks the most valuable set within the supply.
- Value = priority x population, weight = units. DP value 45,110, greedy 45,088, LP upper bound 45,306.
- "On this scenario the gap is tiny, but over random scenarios greedy loses up to 7.9% in the worst case, and the DP is always optimal and takes milliseconds."
- Honest note: the DP is optimal for the pooled supply; the allocation to depots is a heuristic.

### 7:30 Routing (Stage 4)
- Read two or three vehicle lines from the terminal: depot, load, stops and arrival times. All arrivals are before the deadline.
- "Clarke-Wright merges routes by savings, and a merge is only accepted if every deadline still holds. Local search then applies 2-opt and relocate."
- Show `algorithm_quality.png` (right): "We check the heuristic against an exact DP on small instances: Clarke-Wright is within 2 to 6% on average, with local search within 0.2 to 2%."

### 10:00 Robustness (Stage 5)
- Explain the disruption: every road gets a random delay, and some roads are closed.
- Walk down the terminal table at +50% delay: the static plan falls from 26% to 7% as closures grow; the robust policy goes from 52% to 36%.
- `sensitivity.png`: "Each heat map is one strategy; rows are closures, columns are delay."
- `resilience.png`: "The buffer helps most for delays; live re-routing helps most for closures; together they are best."
- `delivery_timeseries.png`: "Most deliveries happen in the first two hours; the robust policy delivers the most by every time."
- Say the limitation: critical demand stays low (19 to 24%) under stress because its deadlines are shorter than the delays allow.

### 14:00 Scalability and quality (Stage 6)
- `scalability.png`: "Up to 1,280 nodes the whole planning runs in about half a second including shortest paths. The knapsack DP is the biggest single cost there; the spanning trees cost almost nothing."
- Clarke-Wright grows roughly quadratically with the number of customers served by one depot (100 customers: about 8 ms, 800 customers: about 550 ms).

### 16:00 Dashboard
- Open `dashboard.html`. Move the "Roads closed" slider and show the numbers changing. Switch strategy. Tick "protect backbone".
- Click the Robustness tab for the heat map selector and the Algorithms tab for scalability.

### 18:00 Recommendations and conclusion
1. Plan with a safety buffer (the sweep plateaus from about 30%; no penalty when nothing goes wrong).
2. Re-route and re-allocate during execution.
3. Harden the backbone: 50.1% against 42.3% delivered at 30% closures.
4. Use DP for selection.
Closing: "The combination of a buffered plan and adaptive execution keeps 48% of demand delivered under conditions where the static plan delivers 14%."

## Tips
- Rehearse once with a timer; the live run takes about 20 seconds in total, so pauses are what take the time.
- Do not read the terminal output line by line; point at the three numbers that matter in each stage.
- If asked something you do not know, say what the code does and where it is. Honest limits (see README) are better than guesses.
