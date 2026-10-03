# Algorithm reference

For every algorithm: what it does, pseudocode, complexity, and a correctness argument.
Notation: n = nodes, m = roads, T = terminals (depots + critical nodes), W = total supply (units),
k = items in the knapsack, c = customers of one depot, K = vehicles of one depot.

## 0. Shortest paths (`network.py`)

**Dijkstra with a binary heap**, O((n + m) log n). Used for all travel times (graph is sparse, weights are positive).
The same routine accepts a set of closed roads and per-road delay multipliers, so vehicles can re-plan on the live network.

*Correctness:* when a node is popped from the heap its distance is final, because all weights are non-negative so any other path to it
passes through a node with a distance at least as large.

Bellman-Ford O(nm) and Floyd-Warshall O(n^3) are included only as references; the unit tests check that all three agree.
Why not Floyd-Warshall in production: we need distances from about T + c sources, not all n^2 pairs, and we must recompute on the
disrupted graph, so n Dijkstra runs on demand are cheaper and simpler.

## 1. Backbone (`backbone.py`)

### Kruskal, O(m log m)
```
sort edges by weight
for (u, v) in edges: if find(u) != find(v): add edge, union(u, v)
```
*Correctness (cut property):* for any cut, the lightest edge crossing it belongs to some MST. When Kruskal adds an edge it is the lightest
edge crossing the cut between the two components it joins, so the result is an MST. Union-find with path compression and union by rank
costs O(alpha(n)) per operation.

### Prim, O(m log n)
Grow one tree from a start node, always adding the cheapest edge leaving the tree (binary heap). Same cut-property argument.
Kruskal and Prim return the same cost (the tests check it); Prim is preferable on dense graphs, Kruskal on sparse graphs or edge lists.

### Steiner tree, Kou-Markowsky-Berman (KMB), cost <= 2(1 - 1/|T|) x optimum
```
1. closure = complete graph on T, weight = shortest-path time
2. M = MST of closure
3. replace every edge of M by its shortest path in G  -> subgraph H
4. S = MST of H            (removes cycles)
5. repeatedly delete leaves of S that are not terminals
```
Cost: T Dijkstra runs + O(T^2) for the closure MST.
*Why a Steiner tree and not an MST:* the MST spans all n nodes, but only depots and critical nodes must be connected. Steiner is NP-hard,
KMB is the standard polynomial approximation.
*Approximation sketch:* a depth-first tour of the optimal Steiner tree visits all terminals and costs at most 2 x OPT; shortcutting the tour
gives a spanning tree of the closure with cost <= 2 x OPT (the 1 - 1/|T| factor comes from dropping the longest tour segment). The closure MST
is no more expensive, and steps 3 to 5 never increase the cost. The unit tests compare KMB with a brute-force optimum on small graphs.

**Use in the project:** the backbone roads are the first candidates for repair and protection. The hardening study removes them from the set
of roads that can close.

## 2. Prioritization (`prioritization.py`)

### Stage 1: deadline filter, O(D (n + m) log n) for D depots
Keep a demand only if the shortest travel time from some depot is at most its deadline. Items that fail can never be served on time and
would only waste supply.

### Stage 2: 0-1 knapsack DP, O(k W) time
`dp[c]` = best value with capacity c. For each item (weight w, value v): for c from W down to w: `dp[c] = max(dp[c], dp[c - w] + v)`.
A keep-table of k x W bits allows reconstruction of the chosen set.

*Correctness:* optimal substructure. The best set for capacity c using the first i items either leaves item i out (value from i - 1 items)
or takes it (v plus the best for capacity c - w from i - 1 items). Scanning c downward guarantees each item is used at most once.
The DP is pseudo-polynomial (W is a number, not its bit-length); here W is a few hundred to a few thousand units, so it is cheap.

Baselines: greedy by value/weight ratio (O(k log k), not optimal) and the fractional knapsack (LP relaxation), which is an upper bound.
Always: greedy <= DP <= LP bound (checked in the tests).

### Stage 3: depot allocation, O(k D log D)
Selected demands, highest priority and tightest deadline first, go to the closest depot that has enough stock and can arrive in time.
Leftover stock is then given to unselected feasible demands in order of value/weight.
This is a heuristic: the DP optimises over the pooled supply, while stock is fragmented across depots.

## 3. Routing (`routing.py`)

Capacitated VRP with deadlines is NP-hard, so large instances use heuristics and small ones are solved exactly to measure the gap.
Route cost = departure from depot until return (travel + 5 min service per stop). A route is feasible if the load fits the vehicle and
every arrival time is at most the deadline.

### Clarke-Wright savings, O(c^2 log c)
```
one route per customer
s(i, j) = d(0, i) + d(0, j) - d(i, j)         # distance saved by visiting j right after i
for pairs in decreasing savings:
    if i and j are endpoints of different routes and the merged route is feasible: merge
```
A merge is accepted only if capacity and all deadlines still hold; both orientations of each route are tried because direction matters for deadlines.
*Correctness* (feasibility): every route is feasible at the start (checked) and only feasible merges are accepted, so the final solution is feasible.
It is a heuristic, so optimality is not guaranteed.

### Local search
* 2-opt inside a route: reverse a segment if the route gets shorter and stays feasible.
* Relocate between routes: move one stop to another route or position if the total time decreases and both routes stay feasible.
Each accepted move strictly lowers the total time, so the search terminates.

### Exact DP for small instances: O(2^n n^2 + K 3^n)
Phase 1 (Held-Karp with deadlines): `f[S][j]` = earliest time at which a vehicle has served set S and finished at j.
`f[S + j][j] = min over i in S of f[S][i] + d(i, j) + service`, allowed only if arrival <= deadline(j).
Earliest time is a valid state because arriving earlier never violates a deadline and never makes the route longer (a vehicle never needs to wait).
Phase 2 (set partition): `g[k][S]` = cheapest way to cover S with at most k routes = min over subsets T of S containing the lowest-numbered customer of
`cost[T] + g[k-1][S minus T]`.
*Correctness:* exhaustive over all subsets with dominance only on the dimension that cannot matter. Tests compare it with brute-force permutations.
Limited to 13 customers per depot.

## 4. Robustness (`robustness.py`)

Disruption (one draw per Monte Carlo run): every road gets a delay multiplier `1 + U(0, d_max)`, and a fraction of roads is closed at random.

| Strategy | Plan | Execution |
|---|---|---|
| static | nominal | follow planned paths; a closed road strands the vehicle |
| static+buffer | planned with all travel times x 1.25 | same |
| adaptive | nominal | re-run Dijkstra on the live network before every leg; skip stops that are unreachable or too late |
| adaptive+realloc | nominal | skipped stops go to a shared pool; a vehicle that finished its route and still has cargo and time picks the best pool stop (value per minute) |
| buffer+adaptive+realloc | buffered | adaptive + re-allocation |

All strategies see the same random disruptions, so differences are not sampling noise. Results are reported as mean and 95% confidence
interval over the runs.

## 5. Metrics (`metrics.py`)

* **% demand satisfied** = units delivered on time / total demanded units x 100
* **average delivery latency** = mean arrival time of delivered demands (minutes)
* **resilience** = % satisfied under X% closed roads / % satisfied with no closures (same delay level)
* also: % of priority-weighted value, % of critical demand, cumulative delivered demand over time

## Complexity summary

| Component | Time | Observed (n = 1,280 nodes) |
|---|---|---|
| Dijkstra from one source | O((n + m) log n) | about 1 ms per source (140 ms for 156 sources) |
| Kruskal / Prim | O(m log m) / O(m log n) | about 1.5 ms each |
| Steiner (KMB) | O(T (n + m) log n + T^2) | about 8 ms |
| Knapsack DP | O(k W) | about 0.2 s (2.45 million cells) |
| Knapsack greedy | O(k log k) | about 0.2 ms |
| Clarke-Wright routing (all depots, about 10 customers each) | O(c^2 log c) per depot | about 5 ms |
| CW + local search (same instance) | CW + O(c^2) per pass | about 30 ms |
| Full planning (filter, DP, allocation, routing) | sum of the above | about 0.24 s; 0.45 s including shortest paths |
| Exact routing DP | O(2^c c^2 + K 3^c) | 20 ms at 10 customers |
