# Executive Summary — Care Transition Efficiency & Placement Outcome Analytics

**Audience:** HHS / programme leadership and government stakeholders
**Dataset:** HHS Unaccompanied Alien Children (UAC) daily reporting file · 12 Jan 2023 – 21 Dec 2025 · 720 reports over 1,075 calendar days
**Deliverables:** this summary · full research paper (PDF) · live Streamlit dashboard

---

## Bottom line

The programme is usually described by **how many** children are in care. This analysis measures **how well children move through care**: border handoff speed, discharge velocity, backlog growth and the consistency of reunification outcomes.

On that basis the pipeline is structurally sound at stage 1 and weak at stage 2, and **the most recent year is the weakest on record for process — not because it is busier, but because it is slower**:

> Between 2023 and 2025 the transfer of children from CBP to HHS slowed from **83% to 46%** of the border queue per day (1.3 → 3.3 days to clear), and the daily discharge of children to sponsors fell from **3.34% to 0.90%** of the HHS caseload — stretching the implied reunification cycle from **31 days to a median of 177 days**. Meanwhile the Outcome Stability Score, which measures how consistent daily release performance is, fell from **77.7 to 0.0**.

Capacity counts alone would have reported "caseload down, numbers good." Process metrics show reunification speed deteriorating roughly six-fold over the same period.

---

## What was measured

The programme is modelled as a three-stage pipeline with two queues:

**Apprehension → [CBP custody] → transfer → [HHS care] → discharge → sponsor placement**

Five headline KPIs, all scale-invariant so years with very different volumes are comparable:

| KPI | Definition | Full period |
|---|---|---:|
| Transfer Efficiency Ratio | Transfers ÷ children in CBP custody | **69.1%**/day (≈2.0 days to clear) |
| Discharge Effectiveness Index | Discharges ÷ children in HHS care | **2.37%**/day (≈98 days to place) |
| Pipeline Throughput | Total exits ÷ total entries | **1.85×** |
| Backlog Accumulation Rate | Transfers − discharges, per report | **−45/day** (net drain) |
| Outcome Stability Score | 100 × (1 − variation in discharge effectiveness) | **43.9 / 100** |

Window totals: **67,337 apprehensions → 92,641 transfers → 124,853 sponsor placements**.

---

## Five findings

**1. The border handoff is fast; the placement stage is 50× slower.**
Children leave CBP custody in about **2 days**; the HHS caseload takes about **98 days** to place at observed rates. Reform effort belongs at stage 2.

**2. 2024 was the backlog year.**
It is the only year in which discharges failed to keep pace with transfers (placement completion **98%**, net **+3.4 children/day**). The detector found **36 sustained accumulation runs** covering 170 reports and a cumulative 7,787 children — **27 of those 36 runs, and 7,595 of those children, fall in 2024**. The single worst episode: **+1,028 children accumulated between 21 April and 2 May 2024 (12 days)** — an event invisible in monthly averages.

**3. 2025 lost speed, not just volume.**
Intake fell from 148 to 13 children/day and the caseload fell ~64% — but transfer efficiency halved, discharge effectiveness fell ~4×, the implied placement cycle stretched to **227 days (mean)**, and **every one of the 190 sub-threshold release reports and 141 slow-release alerts in the entire three-year record occurred in 2025**. The worst single month-over-month move was **−73.4% (March 2025)**.

**4. Two prolonged low-reunification windows and nine sudden drops were located precisely.**
Longest stagnation: **11–31 March 2025** — 15 consecutive reports at 0.30%/day against a 1.19% baseline (a 74% shortfall sustained 21 days). Second: **17–26 February 2025**. Nine sudden drops (≥2σ below the trailing mean) cluster in Jan–Feb and Nov 2025.

**5. Releases appear to be batched at weekends — and the data cannot confirm it.**
Sunday reports carry **+61 more discharges** than weekday reports at equal caseload, gap and trend (t = 9.7). But the file has **no Saturday reports and only two Friday reports**, so weekend activity and a wider weekend counting window cannot be told apart. **33% of calendar days (355 of 1,075) carry no report at all.**

---

## Recommended actions

| # | Action | Trigger / target | Why |
|---|---|---|---|
| 1 | Publish a **discharge-velocity floor** | Discharge Effectiveness ≥ **2.5%/day** (≈40-day cycle) with automatic alert below 1% | 2025 median cycle is 177 days; all 190 breaches are in 2025 |
| 2 | Set a **CBP handoff service level** | Transfer Efficiency ≥ 60% / clearance ≤ 2 days | Actual 2025: 46% and 3.3 days |
| 3 | **Three-report accumulation trigger** | Intervene on the 3rd consecutive report of queue growth | Every one of the 36 runs began as a 3-day streak; worst added 1,028 children in 12 days |
| 4 | **Move to seven-day reporting** and publish a **data dictionary** | Coverage 67% → ≥95%; close the 2023 reconciliation gap | 355 unobserved days; 2023 flow columns leave **≈151 children/day unexplained** vs the stock change |
| 5 | **Review any month scoring < 50 on stability** | March 2025 scored 14.4 | Erratic release cadence disrupts shelter staffing, transport and school enrolment downstream |

---

## Data caveats a decision-maker should know

* **Stock and flow columns do not reconcile in 2023.** Reported transfers minus discharges predict a 30,120-child drawdown while the queue actually grew by 4,664 — an unexplained **+34,784 children (≈151/day)**. The identity closes to ±4/day by 2025. Within-period ratios are unaffected, but absolute 2023 volumes should not be audited against each other until a data dictionary exists.
* **Reporting is Monday–Thursday plus Sundays** — no Saturdays, two Fridays, a longest blind spot of 10 days.
* **No child-level data.** True length-of-stay, sponsor type and post-discharge outcomes are out of scope; "release time" is a flow/stock proxy.
* **The analysis is descriptive, not causal.** The 2025 break is documented, not attributed to any specific policy.

---

## What the dashboard delivers

`streamlit run app.py` opens five modules: **Care Pipeline Flow** (stocks, flows and a flow-conserving pipeline map), **Transfer & Discharge Efficiency** (with a *counts / ratios / days-to-clear* toggle), **Bottleneck Detection** (sustained runs, alert histogram), **Outcome Trend Analysis** (month-over-month placements, stability, weekday/weekend) and **Data & Method** (coverage, mass balance, definitions, CSV downloads).

Controls: **date-range selection**, **ratio-based metric toggles**, **rolling-window smoothing** and four **threshold-based visual alerts** — every chart marks the reports that breach the thresholds you set.

---

*All figures are regenerated from the source CSV by `python src/run_analysis.py`; supporting tables are in `outputs/tables/` and machine-readable findings in `outputs/insights.json`.*
