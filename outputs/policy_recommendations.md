# Policy recommendations

Scenario: 60 nodes, 118 roads, 3 depots, 34 demand nodes (5 critical), supply covers 55% of demand. Monte Carlo runs per cell: 60.

## 1. Plan with a safety buffer
With no buffer, the static plan delivers 14% of demand when 20% of roads are closed and delays reach +50%. Planning with a 25% travel-time buffer raises this to 27%. In the buffer sweep (robust policy under the same stress), the best buffer was 40% (49% delivered, versus 28% with no buffer). Without any disruption the buffered plan delivers 54% against 53% for the unbuffered plan, so the buffer carries no penalty here.

## 2. Re-route and re-allocate during execution
Adding live re-routing and a shared re-allocation pool on top of the buffered plan gives 48% under the same stress (static + buffer: 27%). At 40% closures the robust policy delivers 36% against 7% for the static plan.

## 3. Harden the backbone
The Steiner backbone connects all depots and critical nodes with 20% of the total road length. If closures never hit these roads, the robust policy delivers 50% of demand at 30% closures versus 42% when any road can close (a gain of 7.9 percentage points); critical demand: 24% versus 21%.

## 4. What limits the plan
The nominal schedule delivers 148 of 281 demanded units (53%). Of the 20 demand nodes left unserved: 15 supply exhausted (lower value per unit); 2 no depot can arrive before the deadline; 2 no vehicle left / route infeasible; 1 no depot with enough stock in time.

## 5. Use DP for the selection step
On this scenario the knapsack DP selects value 45110 versus 45088 for greedy (LP upper bound 45306). Across the random scenarios tested, greedy loses 0.31% of value on average and up to 7.9% in the worst case; the DP is exact and takes only milliseconds even at 1,000+ nodes.
