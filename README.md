# Care Transition Efficiency & Placement Outcome Analytics

Process-efficiency and outcome analytics for the **HHS Unaccompanied Alien Children (UAC)**
programme, reframed as a three-stage care pipeline:

```
Apprehension ──▶ [ CBP custody ] ──transfer──▶ [ HHS (ORR) care ] ──discharge──▶ Sponsor placement
     entry                 queue 1                    queue 2                    exit
```

Capacity counts tell you *how many* children are held. This project measures *how well they move*:
handoff speed, discharge velocity, backlog growth and the consistency of reunification outcomes.

---

## Deliverables

| Deliverable | Location |
|---|---|
| **Research paper** (EDA, insights, recommendations) | `docs/research_paper.pdf` · `docs/research_paper.md` |
| **Executive summary** for government stakeholders | `docs/executive_summary.pdf` · `docs/executive_summary.md` |
| **Streamlit dashboard** (live analytics) | `app.py` |
| Analysis library (metrics + detectors) | `src/care_pipeline.py` |
| Analysis runner (figures, tables, insights) | `src/run_analysis.py` |
| Source dataset | `data/HHS_Unaccompanied_Alien_Children_Program.csv` |
| Figures (8 publication charts) | `outputs/figures/` |
| Metric tables (KPI, monthly, bottlenecks, alerts, …) | `outputs/tables/` |
| Machine-readable findings | `outputs/insights.json` |
| Markdown → HTML/PDF renderer | `scripts/make_pdfs.py` |
| Pre-deployment smoke check | `scripts/smoke_check.py` |

**Hosted links**

| | |
|---|---|
| Repository | https://github.com/swaroopa790/care-transition-analytics |
| **Live dashboard (Streamlit Cloud)** | https://care-transition-analytics-cudp5axebefwvq7pxeiov9.streamlit.app |
| Research paper (hosted) | https://swaroopa790.github.io/care-transition-analytics/docs/research_paper.pdf |
| Executive summary (hosted) | https://swaroopa790.github.io/care-transition-analytics/docs/executive_summary.pdf |
| Landing page (GitHub Pages) | https://swaroopa790.github.io/care-transition-analytics/ |

---

## Quick start

```bash
pip install -r requirements.txt

# 1. Regenerate every figure, table and insight (writes outputs/)
python src/run_analysis.py

# 2. Launch the dashboard (http://localhost:8501)
python -m streamlit run app.py

# 3. Rebuild the PDF deliverables from the Markdown sources
python scripts/make_pdfs.py

# 4. Verify everything a deployment needs is present (optional)
python scripts/smoke_check.py
```

Python 3.11+ (developed on 3.13), `streamlit`, `pandas`, `numpy`, `plotly`, `matplotlib`, `markdown`.

---

## Deploying (Streamlit Community Cloud)

Everything the hosted app needs is inside the repository — the dataset (`data/`), the generated
`outputs/` bundle and the pinned `requirements.txt`, so the cloud build runs `streamlit run app.py`
with **no build step**.

1. Push this folder to GitHub (branch `main`, `app.py` at the repository root).
2. Open [share.streamlit.io](https://share.streamlit.io) → **New app** → pick the repository,
   branch `main`, main file path `app.py`.
3. Deploy. Runtime configuration lives in `.streamlit/config.toml`; the Python version is pinned in
   `.python-version`. `.streamlit/secrets.toml` is git-ignored if the app is later extended with
   secrets.

**Live app:** https://care-transition-analytics-cudp5axebefwvq7pxeiov9.streamlit.app

To reproduce the deployment checks locally:

```bash
python -m streamlit run app.py --server.headless true --server.port 8501
```

---

## The five KPIs

| KPI | Formula | Reads as |
|---|---|---|
| **Transfer Efficiency Ratio** | `transfers ÷ children in CBP custody` | Daily share of the border queue handed to HHS (reciprocal = days to clear) |
| **Discharge Effectiveness Index** | `discharges ÷ children in HHS care` | Daily share of the caseload released to a sponsor (reciprocal = days to place) |
| **Pipeline Throughput** | `Σ discharges ÷ Σ intake` | Total exits ÷ total entries over the window |
| **Backlog Accumulation Rate** | `transfers − discharges` | Positive = the HHS queue grew faster than it emptied |
| **Outcome Stability Score** | `100 × (1 − clamp(CV(discharge effectiveness), 0, 1))` | 100 = perfectly consistent daily release velocity |

Supporting metrics: `handoff_completion` (transfers ÷ intake), `placement_completion`
(discharges ÷ transfers), `cbp_net_backlog` (intake − transfers), `cbp_clearance_days` and
`hhs_release_days` (the reciprocals of the two efficiency ratios).

Every formula is published programmatically in `care_pipeline.METRIC_DEFINITIONS` so the paper,
the dashboard tooltips and `insights.json` cannot drift apart.

---

## Dashboard modules

1. **📊 Care Pipeline Flow** — stage stocks and daily flows, a flow-conserving Sankey of the
   selected window, and per-report queue imbalance.
2. **⚡ Transfer & Discharge Efficiency** — the two efficiency ratios with a
   *counts / flow-stock ratios / days-to-clear* toggle, plus month-over-month ratios.
3. **🚨 Bottleneck Detection** — sustained accumulation runs, threshold-alert histogram and
   monthly net imbalance.
4. **🌱 Outcome Trend Analysis** — month-over-month placements, sudden-drop and stagnation
   detection, rolling stability score, weekday vs weekend speed.
5. **📑 Data & Method** — reporting coverage, mass-balance diagnostic, KPI definitions and CSV
   downloads.

**Sidebar controls:** date-range selection · ratio-based metric toggle · rolling-window slider ·
four threshold sliders that mark breaching reports on every chart.

---

## Data notes (read before interpreting numbers)

* 720 populated reporting days out of 1,075 calendar days (**67% coverage**); 450 trailing blank
  rows discarded; no duplicates, no negatives, no missing values.
* Reporting runs **Monday–Thursday plus Sundays**: no Saturday reports, two Friday reports, a
  longest blind spot of 10 days.
* Flows are **daily counts**, not sums over the reporting gap (validated by regressing each flow
  on the gap with a quadratic time trend — see `insights.json → diagnostics`).
* The stock/flow identity does **not** close in 2023 (≈151 children/day unexplained) but does by
  2025 (±4/day). Use ratios across periods; treat absolute 2023 volumes with care.

---

## Headline results (2023-01-12 → 2025-12-21)

| KPI | Full period | 2023 | 2024 | 2025 |
|---|---:|---:|---:|---:|
| Transfer Efficiency Ratio | 69.1% | 83.0% | 78.3% | **46.0%** |
| Discharge Effectiveness Index | 2.37%/day | 3.34% | 2.90% | **0.90%** |
| Implied HHS release time | 98 d | 31 d | 37 d | **227 d** |
| Pipeline Throughput | 1.85× | 2.45× | 1.39× | 2.22× |
| Net HHS backlog | −45/day | −131/day | **+3.4/day** | −12/day |
| Outcome Stability Score | 44 | 77.7 | 75.2 | **0.0** |

36 sustained accumulation runs (27 of them in 2024), 2 prolonged stagnation windows and 9 sudden
drops in reunification success were detected; default thresholds fire 445 alerts, all
discharge-velocity alerts falling in 2025.

---

## Repository layout

```
care-transition-analytics/
├── app.py                        # Streamlit dashboard
├── requirements.txt
├── data/
│   └── HHS_Unaccompanied_Alien_Children_Program.csv
├── docs/
│   ├── research_paper.md|.html|.pdf
│   └── executive_summary.md|.html|.pdf
├── outputs/
│   ├── figures/                  # fig01 … fig08 (PNG, 130 dpi)
│   ├── tables/                   # kpi_year, monthly, bottlenecks, alerts, …
│   └── insights.json             # headline findings + diagnostics + captions
├── scripts/
│   └── make_pdfs.py              # Markdown → HTML → headless-Chrome PDF
└── src/
    ├── care_pipeline.py          # loading, features, KPIs, detectors
    └── run_analysis.py           # figures + tables + insights
```
