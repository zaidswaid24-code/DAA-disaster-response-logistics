# Viva questions and model answers

Every team member should be able to answer every question here: the examiner can ask anyone about any part.
Numbers are from the default run (`python main.py`, seed 7, 60 runs per Monte Carlo cell); open `outputs/results.json` to check them.

---
## A. Whole system

**A1. Walk me through the whole pipeline.**
Generate a scenario; build a Steiner backbone linking depots and critical nodes; filter out demands that cannot be reached before their deadline;
choose the most valuable subset within the supply with a knapsack DP; assign the chosen demands to depots; route each depot's demands with
Clarke-Wright plus local search; then stress the plan with random delays and closed roads and compare execution strategies using Monte Carlo.

**A2. Why split the problem into these stages?**
The joint problem (selection + assignment + routing + uncertainty) is NP-hard. Each stage is a classical problem with a known algorithm, so we can
justify the choice, analyse complexity, and test each stage separately. The price is that the combination is not guaranteed to be globally optimal.

**A3. Why synthetic data, and is it realistic?**
The assignment allows real or synthetic data. Synthetic data lets us control size, density, supply and deadlines, and reproduce every number from a seed.
Roads come from nearest-neighbour links with detour factors, depots are spread by farthest-point sampling, critical nodes have tight deadlines.
It shows how policies behave relative to each other, not absolute predictions for a particular city.

**A4. What are your main assumptions?**
One commodity; travel time equals road weight; 5 minutes unloading per stop; vehicles leave at t = 0 with their planned load; a delivery counts only if it arrives before the deadline;
adaptive strategies see live closures and delays; supply covers 55% of demand.

**A5. Why can the result never reach 100%?**
Supply is only 55% of demand. The nominal plan delivers 52.7%; the 2-point gap comes from demands no depot can reach in time, stock fragmented across depots, and demands dropped because of fleet limits.

**A6. How do you make sure results are reproducible?**
Every random choice uses a seeded `random.Random`. The Monte Carlo draws are generated once per setting and shared by all strategies (common random numbers).

---
## B. Backbone

**B1. What is the backbone and why do we need it?**
The set of roads that connects every depot to every critical node. It is where repair and protection effort goes first.

**B2. Kruskal vs Prim: complexity and when to use which?**
Kruskal O(m log m) with union-find; Prim O(m log n) with a binary heap. Kruskal is natural for sparse graphs and edge lists, Prim for dense graphs.
Both return the same cost (835.4 min here); the unit tests check this on random graphs.

**B3. Why is Kruskal correct?**
Cut property: the lightest edge crossing any cut belongs to some MST. Each edge Kruskal adds is the lightest edge leaving the component it joins.

**B4. Why a Steiner tree and not just an MST?**
The MST spans all 60 nodes (835 min). We only need depots and critical nodes connected. The Steiner tree does that with 432 min: 52% of the MST, 20% of all road time.

**B5. How does KMB work and what is its guarantee?**
Metric closure on the terminals, MST of the closure, expand edges into shortest paths, MST again to remove cycles, prune non-terminal leaves.
Cost is at most 2(1 - 1/|T|) times the optimum. Exact Steiner tree is NP-hard.

**B6. Do you verify the approximation?**
Yes: a unit test compares KMB with a brute-force optimum (all subsets of extra nodes) on small random graphs and checks the bound.

**B7. How is the backbone used in the results?**
In the hardening study, closures never hit backbone roads. At 30% closures the robust policy delivers 50.1% instead of 42.3%.
Caveat: the same number of roads still closes, so the failures concentrate on the other roads.

**B8. What does union-find with path compression and union by rank cost?**
Practically constant: O(alpha(n)) amortised per operation.

---
## C. Prioritization

**C1. Why a knapsack?**
Supply is limited (capacity W), each demand needs a fixed number of units (weight) and gives a value (priority x population). We must choose a subset: 0-1 knapsack.

**C2. Explain the DP and its complexity.**
dp[c] = best value with capacity c. For each item, for c from W down to its weight: dp[c] = max(dp[c], dp[c - w] + v). Time O(kW), keep-table of kW bits for reconstruction.
At 1,280 nodes (2.45 million cells) it takes about 0.2 s.

**C3. Why scan capacity downward?**
So that dp[c - w] still refers to the state before the current item; otherwise the item could be used several times (unbounded knapsack).

**C4. Is O(kW) polynomial?**
Pseudo-polynomial: polynomial in the value of W, exponential in its bit-length. Fine here because W is a few hundred to a few thousand units.

**C5. Why the deadline filter before the DP?**
A demand no depot can reach in time has no value, but would consume supply if selected. Filtering is exact for single-demand reachability.

**C6. Is the whole thing "knapsack with deadlines" solved optimally?**
No, be honest. The filter handles each demand's own reachability; the DP is optimal for the pooled supply of all depots. Deadlines that interact through shared vehicles
(a vehicle serving one demand arrives later at the next) and per-depot stock fragmentation are handled by the allocation and routing heuristics.

**C7. Greedy vs DP: how different are they?**
On the default scenario: DP 45,110, greedy 45,088, LP bound 45,306. Over random scenarios greedy loses 0.07% to 0.67% on average and up to 7.9% in the worst case (30 nodes, 30% supply).
Greedy is good when there are many small items; it fails with few large items and tight capacity.

**C8. What is the fractional knapsack for?**
Its optimum (LP relaxation) is an upper bound for the 0-1 problem. The DP value is within 0.04% to 2.4% of it, which shows the selection is close to the best possible.

**C9. What does the allocation step do?**
Assigns each chosen demand to the closest depot with enough stock that can arrive in time (highest priority and tightest deadline first), then uses leftover stock for extra feasible demands.

---
## D. Routing

**D1. Why heuristics for routing?**
Capacitated VRP with deadlines is NP-hard. Exact methods do not scale; Clarke-Wright is fast and usually near-optimal.

**D2. Explain Clarke-Wright.**
Start with one route per customer. The saving of joining i and j is d(0,i) + d(0,j) - d(i,j). Process savings in decreasing order and merge routes whose endpoints are i and j.
Complexity O(c^2 log c).

**D3. How do you handle deadlines in Clarke-Wright?**
A merge is only accepted if the merged route keeps capacity and every arrival at most its deadline. Both orientations of each route are tried because direction changes arrival times.

**D4. What does local search add?**
2-opt inside routes and relocate between routes, accepted only if feasible and strictly better. Average gap to the optimum falls from 2.1% to 6.0% (Clarke-Wright) to 0.2% to 2.0%.

**D5. How do you know how good the heuristics are?**
An exact DP solves instances of 5 to 10 customers. Clarke-Wright is optimal in 44% to 76% of instances, with local search in 52% to 92%. Worst single instance: 43.6% gap for plain Clarke-Wright.

**D6. Explain the exact DP.**
Held-Karp over subsets: f[S][j] = earliest time to have served S ending at j (O(2^n n^2)); then a set-partition DP chooses at most K routes covering all customers (O(K 3^n)).

**D7. Why is "earliest time" a valid DP state with deadlines?**
Arriving earlier never breaks a deadline and never makes the route longer, because a vehicle never has to wait. So among partial routes with the same set and end, the earliest dominates.

**D8. Why Dijkstra instead of Floyd-Warshall?**
The graph is sparse and we need distances from about T + c sources, not all pairs: O(T (n+m) log n) against O(n^3). We also need to recompute on the disrupted graph during execution.
Floyd-Warshall and Bellman-Ford exist in the code as references; the tests check that all three agree.

**D9. What happens if a depot needs more routes than it has vehicles?**
The routes with the lowest value per minute are dropped and their demands are reported as not served.

**D10. How does Clarke-Wright scale?**
Roughly quadratically: 100 customers about 8 ms, 800 customers about 550 ms (8x the customers, about 68x the time).

---
## E. Robustness

**E1. How do you model uncertainty?**
Per Monte Carlo run: each road's travel time is multiplied by 1 + U(0, d_max) with d_max in {25%, 50%, 100%}, and a fraction (0 to 40%) of roads is closed at random.

**E2. Describe the strategies.**
Static (follow the plan; a closed road strands the vehicle); static with a 25% planning buffer; adaptive (re-run Dijkstra on the live network before each leg, skip stops that became unreachable or late);
adaptive with re-allocation (skipped stops go to a shared pool and any vehicle with cargo and time can pick them up); buffered plan with adaptive re-allocation.

**E3. Why do all strategies see the same disruptions?**
Common random numbers: differences between strategies are then due to the strategies, not to luck. Results are means with 95% confidence intervals.

**E4. Why does the static plan lose half its service with only +50% delays?**
Clarke-Wright packs stops up to their deadlines, so there is no slack. Late arrivals do not count. The 25% buffer restores 52% when nothing is closed.

**E5. What does the buffer cost?**
In this scenario nothing measurable: without disruption the buffered plan delivers 54% against 53% unbuffered, because it picks a different set of demands. The sweep plateaus from about 30%.

**E6. Which component helps more, buffer or adaptive execution?**
Buffer helps against delays, adaptive execution against closures. At 20% closures and +50% delay: static 13.5%, static+buffer 26.9%, adaptive 26.1%, adaptive+realloc 28.5%, all three combined 47.7%.

**E7. Re-allocation adds only a little over re-routing. Why?**
A vehicle can only pick up a skipped stop if it still has cargo, time before the deadline, and is near enough. After closures or delays there is rarely much slack left.

**E8. How many Monte Carlo runs and how do you know that is enough?**
60 per cell. The 95% confidence half-widths are at most 2.4 percentage points (1.2 on average), much smaller than the differences between the robust policy and the static plan. `main.py` can use more runs by editing `runs`.

**E9. Define resilience.**
Service level under X% closed roads divided by the service level with no closures (same delay level). For the robust policy at +50% delay and 40% closures: 36.4 / 52.3 = 70%; for the static plan: 7.3 / 26.4 = 28%.

**E10. Critical demand stays low under stress. Why?**
Critical deadlines are 45 to 150 minutes, shorter than the delays allow. Under 20% closures and +50% delay only 19% to 24% of critical demand arrives on time for every strategy. We also tested a tiered buffer
(none for critical demands); it did not improve results, because the cause is physical, not planning.

**E11. What assumption favours the adaptive strategies?**
They see live closures and current delays when leaving a node. Real-time information may be incomplete, so the benefit is an upper bound.

---
## F. Complexity and experiments

**F1. Which stage dominates the runtime?**
At 1,280 nodes the knapsack DP (about 0.2 s) dominates the planning time; the routing stage is only about 5 ms (30 ms with local search) there because each depot has only about 10 customers. Clarke-Wright becomes expensive only when one depot serves hundreds of customers (about 550 ms for 800). Kruskal and Prim take about 1.5 ms, and shortest-path preprocessing about 0.2 s.

**F2. What happens when road density changes?**
MST cost stays roughly constant (1,168 to 1,185 min) while the Steiner backbone cost generally falls as the network gets denser (672 min at k = 2, 461 min at k = 8; not strictly monotonic: 691 at k = 3), because more direct connections appear.

**F3. What happens when vehicle capacity changes?**
Below capacity 30 the fleet becomes the bottleneck: with capacity 15, 11 planned demands cannot be routed and only 33% of demand is served; from 30 upward all planned demands fit and service stays at 55%.

**F4. Where are your tests?**
`tests/test_algorithms.py`, 16 tests: Dijkstra against Bellman-Ford and Floyd-Warshall, Kruskal against Prim, KMB against brute force, DP against brute force, exact routing against permutations,
plan feasibility (stock, capacity, deadlines, fleet size), execution invariants (no delivery after its deadline, no duplicate delivery), and reproducibility.

---
## G. Critical and "what if" questions

**G1. What is the weakest part of your project?**
The selection DP is optimal only for pooled supply; allocation and routing are heuristics; exact routing is verified only on up to 10 customers; data is synthetic; only one commodity.

**G2. The synopsis mentions multi-commodity flow. Did you do it?**
We model a single commodity (supply units). The depot allocation step plays the role of the flow assignment. A multi-commodity extension would replace the single knapsack by a multi-dimensional knapsack
and give each commodity its own stock; it is a natural extension.

**G3. What would you do with more time?**
Per-depot (multiple) knapsack, time-dependent travel times, adaptive large-neighbourhood search for routing, re-optimisation at fixed intervals during execution, calibration on a real road network.

**G4. What if the network had negative edge weights?**
Not meaningful for travel times; Bellman-Ford would replace Dijkstra. It is implemented as a reference.

**G5. What if deadlines were soft?**
Replace the deadline test by a lateness penalty in the knapsack value and in the route cost; the DP structure stays the same, but earliest-time dominance no longer holds directly.

**G6. Why should the audience trust the comparison between strategies?**
Same random disruptions for all strategies, 60 runs per cell, confidence intervals, the nominal case reproduced exactly by the executors (unit test), and heuristic quality measured against exact solutions.
