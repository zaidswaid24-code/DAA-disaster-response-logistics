"""
backbone.py - Backbone design for the disaster network.

The backbone is the set of road links that must stay open (and are first in line for
repair / hardening) so that every depot can reach every critical node.

Algorithms
----------
* kruskal : MST with union-find with path compression + union by rank, O(m log m)
* prim    : MST with a binary heap, O(m log n)
* steiner_kmb : Kou-Markowsky-Berman Steiner-tree approximation connecting the
                terminals (depots + critical nodes) using only the roads needed.
                Cost <= 2 (1 - 1/|T|) * OPT.
"""
from __future__ import annotations

import heapq
from typing import Dict, List, Sequence, Set, Tuple

from network import Graph, TravelTimes, ekey

Edge = Tuple[int, int, float]


class DSU:
    """Disjoint-set union (union by rank + path compression)."""

    def __init__(self, n: int):
        self.parent = list(range(n))
        self.rank = [0] * n

    def find(self, x: int) -> int:
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, a: int, b: int) -> bool:
        ra, rb = self.find(a), self.find(b)
        if ra == rb:
            return False
        if self.rank[ra] < self.rank[rb]:
            ra, rb = rb, ra
        self.parent[rb] = ra
        if self.rank[ra] == self.rank[rb]:
            self.rank[ra] += 1
        return True


def kruskal(n: int, edges: Sequence[Edge]) -> Tuple[List[Edge], float]:
    """Minimum spanning forest of the given edge list (greedy by weight)."""
    dsu = DSU(n)
    tree: List[Edge] = []
    cost = 0.0
    for u, v, w in sorted(edges, key=lambda e: e[2]):
        if dsu.union(u, v):
            tree.append((u, v, w))
            cost += w
    return tree, cost


def prim(g: Graph, start: int = 0) -> Tuple[List[Edge], float]:
    """Minimum spanning tree of the component containing `start` (binary heap)."""
    in_tree = [False] * g.n
    tree: List[Edge] = []
    cost = 0.0
    pq: List[Tuple[float, int, int]] = [(0.0, start, -1)]
    while pq:
        w, u, parent = heapq.heappop(pq)
        if in_tree[u]:
            continue
        in_tree[u] = True
        if parent != -1:
            tree.append((parent, u, w))
            cost += w
        for v, wv in g.adj[u]:
            if not in_tree[v]:
                heapq.heappush(pq, (wv, v, u))
    return tree, cost


def _prune_leaves(edges: List[Edge], terminals: Set[int]) -> List[Edge]:
    """Repeatedly delete leaf nodes that are not terminals (they only add cost)."""
    adj: Dict[int, Set[int]] = {}
    wt: Dict[Tuple[int, int], float] = {}
    for u, v, w in edges:
        adj.setdefault(u, set()).add(v)
        adj.setdefault(v, set()).add(u)
        wt[ekey(u, v)] = w
    leaves = [x for x, nb in adj.items() if len(nb) == 1 and x not in terminals]
    while leaves:
        x = leaves.pop()
        if x not in adj or len(adj[x]) != 1:
            continue
        (y,) = adj[x]
        adj[y].discard(x)
        del adj[x]
        wt.pop(ekey(x, y), None)
        if len(adj[y]) == 1 and y not in terminals:
            leaves.append(y)
    return [(u, v, w) for (u, v), w in wt.items()]


def steiner_kmb(g: Graph, terminals: Sequence[int], tt: TravelTimes) -> Tuple[List[Edge], float]:
    """
    Kou-Markowsky-Berman 2-approximation of the minimum Steiner tree.

    1. Build the metric closure on the terminals (shortest-path times).
    2. Take an MST of the closure.
    3. Replace every closure edge by its shortest path in G.
    4. Take an MST of the resulting subgraph (removes cycles).
    5. Prune non-terminal leaves.
    """
    terms = list(dict.fromkeys(terminals))
    if len(terms) <= 1:
        return [], 0.0
    # steps 1-2: Prim on the complete closure graph
    in_t = {terms[0]}
    best = {t: (tt.d(terms[0], t), terms[0]) for t in terms[1:]}
    closure_edges: List[Tuple[int, int]] = []
    while len(in_t) < len(terms):
        t = min((x for x in terms if x not in in_t), key=lambda x: best[x][0])
        closure_edges.append((best[t][1], t))
        in_t.add(t)
        for x in terms:
            if x not in in_t and tt.d(t, x) < best[x][0]:
                best[x] = (tt.d(t, x), t)
    # step 3: expand paths
    sub: Dict[Tuple[int, int], float] = {}
    for a, b in closure_edges:
        path = tt.path(a, b)
        for u, v in zip(path, path[1:]):
            sub[ekey(u, v)] = g.w[ekey(u, v)]
    # step 4: MST of the subgraph
    sub_edges = [(u, v, w) for (u, v), w in sub.items()]
    tree, _ = kruskal(g.n, sub_edges)
    # step 5: prune
    tree = _prune_leaves(tree, set(terms))
    return tree, sum(w for _, _, w in tree)


def backbone_report(g: Graph, terminals: Sequence[int], tt: TravelTimes) -> dict:
    """Compute and compare the backbone options (used by main.py and the dashboard)."""
    k_edges, k_cost = kruskal(g.n, g.edges())
    p_edges, p_cost = prim(g, 0)
    s_edges, s_cost = steiner_kmb(g, terminals, tt)
    total = sum(w for _, _, w in g.edges())
    return {
        "kruskal_cost": k_cost,
        "prim_cost": p_cost,
        "kruskal_equals_prim": abs(k_cost - p_cost) < 1e-6,
        "steiner_cost": s_cost,
        "steiner_edges": [(u, v) for u, v, _ in s_edges],
        "mst_edges": [(u, v) for u, v, _ in k_edges],
        "all_links_cost": total,
        "n_terminals": len(set(terminals)),
        "steiner_vs_mst_pct": 100.0 * s_cost / k_cost if k_cost else 0.0,
        "steiner_vs_all_pct": 100.0 * s_cost / total if total else 0.0,
    }
