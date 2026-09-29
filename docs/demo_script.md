# Project feedback video — shot list & narration cues

A 3–5 minute recording that covers *what was built, what it shows, and what you learned*.
Record the screen while you talk; keep it to one take if you can.

## Setup (2 minutes)

* **What to record:** the live app at its direct URL, so the sidebar controls are visible:
  `https://care-transition-analytics-cudp5axebefwvq7pxeiov9.streamlit.app/~/+/`
  (the plain `/` URL hides the sidebar inside Cloud's iframe wrapper).
* **Recorder:** press `Win + G` (Xbox Game Bar) → capture the window, or use Clipchamp/OBS.
* **Audio:** a short intro and outro in your own words is enough; narrate the clicks as you go.

## Structure

| # | Time | What to show | Say |
|---|---|---|---|
| 1 | 0:00–0:20 | Repo page `github.com/swaroopa790/care-transition-analytics` | The problem: the HHS UAC programme as a three-stage pipeline — CBP custody → HHS care → sponsor placement — and why *movement speed*, not headcount, is the metric that matters. |
| 2 | 0:20–0:50 | Paper PDF on GitHub Pages | Deliverables: research paper, executive summary, live dashboard; 720 reports over 1,075 days (67% coverage). |
| 3 | 0:50–1:30 | Dashboard → **📊 Care Pipeline Flow** | The flow-conserving Sankey: entries, handoffs, exits and the two queues. Point out the KPI strip (Transfer Efficiency 69.1%, Discharge Effectiveness 2.37%, Throughput 1.85×, Backlog −45/day, Stability 44). |
| 4 | 1:30–2:10 | Sidebar: change the **date range**, toggle **metric mode** to *Days to clear* | How every panel recomputes on the selected window; the reciprocal metrics (31 → 227 days to place a child). |
| 5 | 2:10–2:50 | **⚡ Efficiency** tab, then **🚨 Bottleneck Detection** | The collapse: transfer efficiency 83% → 46%; 36 sustained accumulation runs, 27 of them in 2024; move the threshold sliders and watch breach markers appear. |
| 6 | 2:50–3:30 | **🌱 Outcome Trend** tab | Outcome Stability 77.7 → 0.0, 9 sudden drops, stagnation window 11–31 Mar 2025; weekday vs weekend discharge speed (+61/day on Sundays). |
| 7 | 3:30–4:10 | **📑 Data & Method** tab | The honest caveats: 67% reporting coverage, the 2023 mass-balance gap (~151 children/day unexplained), and how alerts are defined (`ALERT_THRESHOLDS`). |
| 8 | 4:10–5:00 | Back to the repo / your face | **Learnings:** reframing a count dataset as a pipeline, ratio-based KPIs vs raw volumes, why data coverage limits conclusions, and what you'd do next (gap-aware reporting, sponsor-level breakdown). |

## Learnings to mention (pick 3–4)

1. Turning a headcount table into a *process* — queues, handoffs, dwell time — changed the conclusion from "backlog is fine" to "placement time grew 31 → 227 days".
2. Ratios travel better than absolute volumes: the stock/flow identity doesn't close in 2023, so comparisons across years must be ratio-based.
3. Coverage is a result in itself — 67% of days, no Saturday reports, a 10-day blind spot; every chart carries that caveat.
4. Alerting design: thresholds are user-controlled sliders, standardized in `run_analysis.py::ALERT_THRESHOLDS`, so the same rules drive the paper, the dashboard and `insights.json`.
5. Reproducibility: one library (`src/care_pipeline.py`) feeds the paper, the figures, the JSON and the app, so the numbers cannot drift apart.

## Getting a valid `https://` link

* **YouTube (recommended):** upload → visibility **Unlisted** → copy the `https://youtu.be/…` link.
* **Google Drive:** upload → *Share* → *Anyone with the link* → **Viewer** → copy link.
* Both must be openable without signing in — the submission form validates `https://` URLs.
