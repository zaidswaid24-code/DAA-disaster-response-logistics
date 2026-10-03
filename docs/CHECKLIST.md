# Final checklist

## 1. Assignment coverage (from the professor's PDF, project 4)

Required algorithmic components
- [x] 1. Network model and backbone (Kruskal, Prim, Steiner approximation): `src/network.py`, `src/backbone.py`
- [x] 2. Prioritization with knapsack DP and deadlines: `src/prioritization.py`
- [x] 3. Multi-vehicle routing from depots (Clarke-Wright, local search, exact small-instance DP): `src/routing.py`
- [x] 4. Robustness: random delays, re-allocation strategies: `src/robustness.py`
- [x] 5. Metrics: % demand satisfied, average latency, resilience under X% closures: `src/metrics.py`

Deliverables
- [x] Simulator with demand scenarios and resource constraints
- [x] Algorithm implementations (backbone, selection DP, routing heuristics)
- [x] Robustness experiments and sensitivity studies (`experiments.py`, `outputs/sensitivity.png`)
- [x] Visualizations: map, heat maps, time series of delivered demand
- [x] Dashboard (`outputs/dashboard.html`, `outputs/dashboard.png`) and policy recommendations (`outputs/policy_recommendations.md`)
- [x] Sample dataset (`data/sample_scenario.json`)
- [ ] Git repository: create it and push (see section 3)
- [x] Technical report, IEEE format (`docs/Final_Report_IEEE_Disaster_Response_Logistics.docx`, IEEE two-column format). Before submitting: fill in the author names, institution, e-mails and repository URL on the title block
- [ ] Presentation, 15 to 20 minutes with demo (`docs/DEMO_SCRIPT.md`). Confirm with the professor whether slides are required or a live demo is enough.

## 2. Technical checks (run these the day before)

- [ ] `pip install -r requirements.txt` works on the presenting laptop
- [ ] `python -m unittest discover -s tests -v` shows 16 tests OK
- [ ] `python main.py --quick` runs without errors (about 6 s)
- [ ] `python main.py` runs without errors (about 20 s) and regenerates `outputs/`
- [ ] `outputs/dashboard.html` opens in the browser you will present with; slider, strategy selector and tabs respond
- [ ] Terminal font is large enough to read from the back of the room
- [ ] A copy of `outputs/` exists as a fallback in case the live run fails

## 3. Git repository

```bash
git init
git add .
git commit -m "Disaster response logistics: routing and resource allocation"
git branch -M main
git remote add origin <your repository URL>
git push -u origin main
```
Commit `data/` and `outputs/` so the examiner can see results without running anything.

## 4. Everyone must be able to explain

- [ ] The pipeline end to end (VIVA A1) and the reason for the decomposition (A2)
- [ ] Why Steiner and not MST, and the KMB guarantee (B4, B5)
- [ ] The knapsack recurrence, its complexity and why it is pseudo-polynomial (C2 to C4)
- [ ] Clarke-Wright savings and how deadlines are enforced (D2, D3)
- [ ] What the exact DP does and why it validates the heuristic (D6, D7)
- [ ] The five robustness strategies and why all see the same disruptions (E2, E3)
- [ ] The honest limitations (README, VIVA G1, G2)

## 5. Things to say if asked about gaps

- Single commodity only; the synopsis mentions multi-commodity flow, which is a documented extension (VIVA G2).
- The knapsack is optimal for pooled supply only (VIVA C6).
- Critical demand stays low under stress because of its tight deadlines (VIVA E10).
- Data is synthetic by design.
