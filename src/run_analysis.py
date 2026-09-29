"""
Analysis runner
===============

Executes the full Care Transition Efficiency & Placement Outcome analysis and
writes every artefact consumed by the research paper, the executive summary and
the Streamlit dashboard:

    outputs/figures/*.png   publication-ready charts
    outputs/tables/*.csv    metric tables
    outputs/insights.json   headline findings + KPI snapshots

Usage::

    python src/run_analysis.py
"""

from __future__ import annotations

import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:  # pragma: no cover
        pass

import matplotlib
matplotlib.use("Agg")

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.patches import FancyArrowPatch, Rectangle

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import care_pipeline as cp  # noqa: E402

FIG_DIR = ROOT / "outputs" / "figures"
TABLE_DIR = ROOT / "outputs" / "tables"
FIG_DIR.mkdir(parents=True, exist_ok=True)
TABLE_DIR.mkdir(parents=True, exist_ok=True)

# --------------------------------------------------------------------------- #
# Presentation constants
# --------------------------------------------------------------------------- #
C_CBP = "#D9534F"      # stage 1 - CBP custody
C_HHS = "#4C78A8"      # stage 2 - HHS / ORR care
C_EXIT = "#54A24B"     # stage 3 - sponsor placement
C_ENTRY = "#72B7B2"    # system entry - apprehensions
C_WARN = "#E4A11B"     # alerts / bottlenecks
C_GREY = "#7A7A7A"

plt.rcParams.update(
    {
        "figure.dpi": 130,
        "savefig.dpi": 130,
        "savefig.bbox": "tight",
        "font.size": 10,
        "axes.titlesize": 12,
        "axes.titleweight": "bold",
        "axes.labelsize": 10,
        "axes.grid": True,
        "grid.alpha": 0.25,
        "grid.linestyle": "--",
        "axes.spines.top": False,
        "axes.spines.right": False,
        "legend.frameon": False,
        "figure.facecolor": "white",
    }
)

CAPTIONS: dict[str, str] = {}

#: Default visual-alert thresholds applied to the analysis run (the dashboard
#: exposes the same four controls as interactive sliders).
ALERT_THRESHOLDS: dict[str, float] = {
    "min_discharge_effectiveness": 0.01,
    "max_cbp_clearance_days": 4.0,
    "max_hhs_release_days": 150.0,
    "max_backlog_rel": 0.01,
}


def save(fig, name: str, caption: str) -> None:
    path = FIG_DIR / f"{name}.png"
    fig.savefig(path, facecolor="white")
    plt.close(fig)
    CAPTIONS[name] = caption
    print(f"  figure  {path.relative_to(ROOT)}")


def _date_axis(ax, interval: int = 3):
    ax.xaxis.set_major_locator(mdates.MonthLocator(interval=interval))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b\n%Y"))
    ax.xaxis.set_minor_locator(mdates.MonthLocator())


# --------------------------------------------------------------------------- #
# Figure 1 - pipeline overview
# --------------------------------------------------------------------------- #
def fig_overview(df: pd.DataFrame) -> None:
    fig, axes = plt.subplots(3, 1, figsize=(11, 8.5), sharex=True)

    ax = axes[0]
    ax.plot(df["date"], df["intake"], color=C_ENTRY, lw=1, alpha=0.55, label="Apprehensions (entry)")
    ax.plot(df["date"], df["transfers"], color=C_WARN, lw=1, alpha=0.75, label="Transferred CBP \u2192 HHS")
    ax.plot(df["date"], df["discharges"], color=C_EXIT, lw=1, alpha=0.85, label="Discharged to sponsor (exit)")
    ax.set_ylim(0, float(df[list(cp.FLOW_COLS)].max().max()) * 1.45)
    ax.set_ylabel("Children / day")
    ax.set_title("Daily pipeline flows: entry, handoff and exit")
    ax.legend(ncol=3, loc="upper right", fontsize=9)

    ax = axes[1]
    ax.fill_between(df["date"], df["cbp_stock"], color=C_CBP, alpha=0.35, label="In CBP custody")
    ax.set_ylabel("Children")
    ax.set_title("Queue 1 - children held in CBP custody")
    ax.legend(loc="upper right", fontsize=9)

    ax = axes[2]
    ax.fill_between(df["date"], df["hhs_stock"], color=C_HHS, alpha=0.35, label="In HHS (ORR) care")
    ax.set_ylabel("Children")
    ax.set_title("Queue 2 - children in HHS care awaiting sponsor placement")
    ax.legend(loc="upper right", fontsize=9)
    _date_axis(ax)

    fig.subplots_adjust(top=0.94, hspace=0.34)
    fig.suptitle("UAC care pipeline: stocks and flows, Jan 2023 \u2013 Dec 2025", fontsize=13, fontweight="bold", y=0.995)
    save(fig, "fig01_pipeline_overview",
         "Figure 1. The three-stage care pipeline. Upper: daily flows (entry, handoff, exit). "
         "Middle and lower: the two queues the system must drain. Volumes collapse after "
         "January 2025, but queue-drain speed must be judged on ratios, not absolute counts.")


# --------------------------------------------------------------------------- #
# Figure 2 - transition efficiency
# --------------------------------------------------------------------------- #
def fig_efficiency(df: pd.DataFrame) -> None:
    roll = cp.rolling_metrics(df, window=30)
    fig, axes = plt.subplots(3, 1, figsize=(11, 8.5), sharex=True)

    ax = axes[0]
    ax.plot(df["date"], df["transfer_efficiency"] * 100, color=C_GREY, lw=0.7, alpha=0.5, label="Daily")
    ax.plot(roll["date"], roll["te_roll"] * 100, color=C_CBP, lw=2, label="30-report mean")
    ax.axhline(np.nanmean(df["transfer_efficiency"]) * 100, color=C_CBP, ls=":", lw=1.2,
               label=f"Period mean {np.nanmean(df['transfer_efficiency']) * 100:.0f}%")
    ax.set_ylim(0, 240)
    ax.set_ylabel("% of CBP queue / day")
    ax.set_title("Transfer Efficiency Ratio \u2013 CBP \u2192 HHS handoff speed (daily values above 100% "
                 "mean same-day transfers exceeded the reported queue)")
    ax.legend(ncol=3, fontsize=9, loc="upper right")

    ax = axes[1]
    ax.plot(df["date"], df["discharge_effectiveness"] * 100, color=C_GREY, lw=0.7, alpha=0.5, label="Daily")
    ax.plot(roll["date"], roll["de_roll"] * 100, color=C_EXIT, lw=2, label="30-report mean")
    ax.axhline(np.nanmean(df["discharge_effectiveness"]) * 100, color=C_EXIT, ls=":", lw=1.2,
               label=f"Period mean {np.nanmean(df['discharge_effectiveness']) * 100:.1f}%")
    ax.set_ylabel("% of HHS caseload / day")
    ax.set_title("Discharge Effectiveness \u2013 daily share of the HHS caseload released to sponsors")
    ax.legend(ncol=3, fontsize=9, loc="upper right")

    ax = axes[2]
    ax.plot(roll["date"], roll["clearance_days_roll"], color=C_CBP, lw=1.8, label="CBP clearance time")
    ax.plot(roll["date"], roll["release_days_roll"], color=C_HHS, lw=1.8, label="HHS release time")
    ax.set_ylim(0.8, 700)
    ax.set_ylabel("Days (log scale)")
    ax.set_yscale("log")
    ax.set_title("Implied days to clear each queue at the observed flow rate")
    ax.legend(ncol=2, fontsize=9, loc="center left", bbox_to_anchor=(0.02, 0.55))
    _date_axis(ax)

    fig.suptitle("Transition efficiency: the pipeline's pace", fontsize=13, fontweight="bold", y=1.01)
    save(fig, "fig02_transition_efficiency",
         "Figure 2. Transition efficiency metrics. Both ratios are flow-over-stock, so they are "
         "invariant to programme scale. The lower panel converts them into operationally meaningful "
         "'days to clear' figures - the two queues move at very different speeds.")


# --------------------------------------------------------------------------- #
# Figure 3 - backlog and sustained imbalance
# --------------------------------------------------------------------------- #
def fig_backlog(df: pd.DataFrame) -> None:
    runs = [r for r in cp.detect_backlog_runs(df, min_reports=3) if r.stage == "HHS"]
    fig, axes = plt.subplots(3, 1, figsize=(11, 9), sharex=True)

    ax = axes[0]
    colors = [C_EXIT if v <= 0 else C_WARN for v in df["backlog_accumulation"]]
    ax.bar(df["date"], df["backlog_accumulation"], color=colors, width=1.6, alpha=0.85)
    ax.axhline(0, color="black", lw=0.9)
    for r in runs:
        ax.axvspan(pd.Timestamp(r.start), pd.Timestamp(r.end), color=C_WARN, alpha=0.16, lw=0)
    ax.set_ylabel("Children / report")
    ax.set_title("Net HHS backlog (transfers \u2212 discharges); amber bands = sustained growth runs")
    ax.legend(handles=[
        plt.Rectangle((0, 0), 1, 1, color=C_EXIT, alpha=0.85),
        plt.Rectangle((0, 0), 1, 1, color=C_WARN, alpha=0.85)],
        labels=["Queue draining (discharges > transfers)", "Queue accumulating"], fontsize=9, loc="upper right")

    ax = axes[1]
    colors = [C_EXIT if v <= 0 else C_CBP for v in df["cbp_net_backlog"]]
    ax.bar(df["date"], df["cbp_net_backlog"], color=colors, width=1.6, alpha=0.85)
    ax.axhline(0, color="black", lw=0.9)
    ax.set_ylabel("Children / report")
    ax.set_title("Net CBP backlog (intake \u2212 transfers); positive = children held longer")
    ax.legend(handles=[
        plt.Rectangle((0, 0), 1, 1, color=C_EXIT, alpha=0.85),
        plt.Rectangle((0, 0), 1, 1, color=C_CBP, alpha=0.85)],
        labels=["CBP queue draining", "CBP queue accumulating"], fontsize=9, loc="upper right")

    ax = axes[2]
    cum = df["backlog_accumulation"].cumsum()
    ax.plot(df["date"], cum, color=C_HHS, lw=2)
    ax.fill_between(df["date"], 0, cum, color=C_HHS, alpha=0.18)
    ax.axhline(0, color="black", lw=0.9)
    ax.set_ylabel("Cumulative children")
    ax.set_title("Cumulative net HHS imbalance (children accumulated beyond observed exits)")
    _date_axis(ax)

    fig.suptitle("Backlog and delay identification", fontsize=13, fontweight="bold", y=1.01)
    save(fig, "fig03_backlog_identification",
         "Figure 3. Where the pipeline stalls. Positive bars mean the queue grew that day. "
         "The cumulative series is a pure imbalance indicator (inflow minus outflow as published), "
         "not a census of children.")


# --------------------------------------------------------------------------- #
# Figure 4 - bottleneck runs
# --------------------------------------------------------------------------- #
def fig_bottlenecks(df: pd.DataFrame, runs: list) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(12, 5), gridspec_kw={"width_ratios": [1.15, 1]})

    top = sorted(runs, key=lambda r: -r.reports)[:12]
    ax = axes[0]
    if top:
        labels = [f"{r.start} \u2192 {r.end}" for r in top][::-1]
        vals = [r.reports for r in top][::-1]
        sev = [r.severity for r in top][::-1]
        y = np.arange(len(labels))
        ax.barh(y, vals, color=[C_CBP if r.stage == "CBP" else C_HHS for r in top][::-1], alpha=0.85)
        for i, (v, s) in enumerate(zip(vals, sev)):
            ax.text(v + 0.3, i, f"{s:+d} children", va="center", fontsize=8, color=C_GREY)
        ax.set_yticks(y)
        ax.set_yticklabels(labels, fontsize=8)
        ax.set_xlabel("Consecutive reporting days")
        ax.set_xlim(0, max(vals) * 1.45)
    ax.set_title("Longest sustained-imbalance runs")

    ax = axes[1]
    monthly = cp.monthly_summary(df)
    bar_colors = [C_EXIT if v <= 0 else C_WARN for v in monthly["backlog_accumulation"]]
    ax.bar(range(len(monthly)), monthly["backlog_accumulation"], color=bar_colors, alpha=0.9)
    ax.axhline(0, color="black", lw=0.9)
    ax.set_xticks(range(len(monthly)))
    tick_idx = list(range(0, len(monthly), 3))
    ax.set_xticks(tick_idx)
    ax.set_xticklabels(
        [pd.Period(monthly["year_month"].iloc[i]).strftime("%b\n%y") for i in tick_idx],
        fontsize=7, rotation=0,
    )
    ax.set_ylabel("Children per month")
    ax.set_title("Monthly net HHS imbalance")
    ax.legend(handles=[plt.Rectangle((0, 0), 1, 1, color=C_EXIT, alpha=0.9),
                       plt.Rectangle((0, 0), 1, 1, color=C_WARN, alpha=0.9)],
              labels=["Draining", "Accumulating"], fontsize=9, loc="upper right")

    fig.suptitle("Bottleneck detection: when and where backlogs persist", fontsize=13, fontweight="bold", y=1.02)
    save(fig, "fig04_bottleneck_detection",
         "Figure 4. Bottlenecks are defined as runs of at least three consecutive reports in which "
         "a queue grew. Left: the twelve longest runs. Right: monthly net imbalance - accumulation "
         "is concentrated in the high-volume 2023-2024 regime.")


# --------------------------------------------------------------------------- #
# Figure 5 - temporal patterns
# --------------------------------------------------------------------------- #
def fig_temporal(df: pd.DataFrame) -> None:
    day = cp.daytype_summary(df)
    monthly = cp.monthly_summary(df)

    fig, axes = plt.subplots(2, 2, figsize=(12, 8))

    ax = axes[0][0]
    wd = day[day["day_type"] == "weekday"].iloc[0]
    we = day[day["day_type"] == "weekend"].iloc[0]
    period_te = float(df["transfer_efficiency"].mean())
    period_de = float(df["discharge_effectiveness"].mean())
    metrics = ["Transfer efficiency", "Discharge effectiveness"]
    raw = [
        (float(wd["transfer_efficiency"]) * 100, float(we["transfer_efficiency"]) * 100),
        (float(wd["discharge_effectiveness"]) * 100, float(we["discharge_effectiveness"]) * 100),
    ]
    norm = [period_te * 100, period_de * 100]
    idx = [[r[0] / norm[i] * 100, r[1] / norm[i] * 100] for i, r in enumerate(raw)]

    x = np.arange(2)
    w = 0.36
    ax.bar(x - w / 2, [v[0] for v in idx], w, color=C_HHS,
           label=f"Weekday reports (n={int(wd['reporting_days'])})")
    ax.bar(x + w / 2, [v[1] for v in idx], w, color=C_WARN,
           label=f"Weekend reports (n={int(we['reporting_days'])})")
    ax.axhline(100, color="black", lw=1.1, ls="--")
    ax.text(1.52, 88, "period average = 100", fontsize=8, ha="right", color=C_GREY)
    for i in x:
        ax.text(i - w / 2, idx[i][0], f"{raw[i][0]:.2f}%\n(idx {idx[i][0]:.0f})",
                ha="center", va="bottom", fontsize=8)
        ax.text(i + w / 2, idx[i][1], f"{raw[i][1]:.2f}%\n(idx {idx[i][1]:.0f})",
                ha="center", va="bottom", fontsize=8)
    ax.set_xticks(x)
    ax.set_xticklabels(metrics)
    ax.set_ylim(0, max(max(v) for v in idx) * 1.35)
    ax.set_ylabel("Index (period average = 100)")
    ax.set_title("Transition speed: weekday vs weekend reports")
    ax.legend(fontsize=8, loc="upper right")

    ax = axes[0][1]
    dow = df.groupby("weekday", as_index=False).agg(
        de=("discharge_effectiveness", "mean"), te=("transfer_efficiency", "mean"), n=("date", "size")
    )
    order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    dow["o"] = dow["weekday"].map({d: i for i, d in enumerate(order)})
    dow = dow.sort_values("o")
    ax.bar(dow["weekday"], dow["de"] * 100, color=C_EXIT, alpha=0.9)
    for i, (v, n) in enumerate(zip(dow["de"] * 100, dow["n"])):
        ax.text(i, v, f"{v:.1f}\nn={n}", ha="center", va="bottom", fontsize=8)
    ax.set_ylabel("Discharge effectiveness (%)")
    ax.set_title("Release velocity by weekday")
    ax.tick_params(axis="x", rotation=40)
    ax.tick_params(axis="x", labelsize=9)
    for label in ax.get_xticklabels():
        label.set_horizontalalignment("right")

    ax = axes[1][0]
    ax.plot(pd.to_datetime(monthly["first"]), monthly["discharge_effectiveness"] * 100,
            marker="o", ms=4, color=C_EXIT, lw=1.8, label="Discharge effectiveness")
    ax.plot(pd.to_datetime(monthly["first"]), monthly["transfer_efficiency"] * 100,
            marker="s", ms=4, color=C_CBP, lw=1.8, label="Transfer efficiency")
    ax.set_ylabel("% per day")
    ax.set_title("Month-over-month efficiency trend")
    ax.legend(fontsize=9)
    _date_axis(ax, interval=6)

    ax = axes[1][1]
    ax2 = ax.twinx()
    ax.bar(pd.to_datetime(monthly["first"]), monthly["discharges_per_day"],
           width=24, color=C_EXIT, alpha=0.75, label="Discharges / reporting day")
    ax2.plot(pd.to_datetime(monthly["first"]), monthly["hhs_stock_mean"],
             color=C_HHS, lw=2, marker="o", ms=3, label="Mean HHS caseload")
    ax.set_ylabel("Discharges per reporting day")
    ax2.set_ylabel("Children in HHS care")
    ax.set_title("Placement output vs caseload")
    ax2.grid(False)
    for a in (ax, ax2):
        a.xaxis.set_major_locator(mdates.MonthLocator(interval=6))
        a.xaxis.set_major_formatter(mdates.DateFormatter("%b\n%y"))
    h1, l1 = ax.get_legend_handles_labels()
    h2, l2 = ax2.get_legend_handles_labels()
    ax.legend(h1 + h2, l1 + l2, fontsize=8, loc="upper right")

    fig.subplots_adjust(hspace=0.42, wspace=0.2)
    fig.suptitle("Temporal and pattern analysis", fontsize=13, fontweight="bold", y=1.02)
    save(fig, "fig05_temporal_patterns",
         "Figure 5. Temporal patterns. The cadence is Mon-Thu plus Sundays (no Saturday reports, "
         "only two Fridays), so weekend comparisons rest on Sunday reports. Efficiency trends are "
         "shown month over month against the caseload they serve.")


# --------------------------------------------------------------------------- #
# Figure 6 - outcome stability
# --------------------------------------------------------------------------- #
def fig_stability(df: pd.DataFrame) -> None:
    roll = cp.rolling_metrics(df, window=30)
    drops = cp.detect_discharge_drops(df, z=2.0, window=60, min_reports=10)
    stagnation = cp.detect_stagnation(df, threshold_pct=0.6, min_reports=4)
    monthly = cp.monthly_summary(df)

    fig, axes = plt.subplots(3, 1, figsize=(11, 9), sharex=True)

    ax = axes[0]
    ax.plot(df["date"], df["discharge_effectiveness"] * 100, color=C_GREY, lw=0.7, alpha=0.5)
    ax.plot(roll["date"], roll["de_roll"] * 100, color=C_EXIT, lw=2, label="30-report rolling mean")
    for s in stagnation:
        ax.axvspan(pd.Timestamp(s["start"]), pd.Timestamp(s["end"]), color=C_WARN, alpha=0.22, lw=0)
    if drops:
        dts = [pd.Timestamp(d["date"]) for d in drops]
        ax.scatter(dts, [d["discharge_effectiveness"] * 100 for d in drops],
                   marker="v", s=45, color=C_CBP, zorder=5, label="Sudden drop (\u2265 2\u03c3 below trailing mean)")
    ax.set_ylabel("% per day")
    ax.set_title("Discharge effectiveness with detected sudden drops and stagnation windows")
    ax.legend(fontsize=9, loc="upper right", ncol=2)

    ax = axes[1]
    ax.plot(roll["date"], roll["stability_roll"], color=C_HHS, lw=1.8)
    ax.axhline(50, color=C_WARN, ls="--", lw=1.2, label="Alert threshold: 50")
    ax.fill_between(roll["date"], 0, roll["stability_roll"], color=C_HHS, alpha=0.15)
    ax.set_ylim(0, 100)
    ax.set_ylabel("Score (0-100)")
    ax.set_title("Outcome Stability Score (30-report window): 100 = perfectly consistent daily release velocity")
    ax.legend(fontsize=9, loc="lower right")

    ax = axes[2]
    ax.bar(pd.to_datetime(monthly["first"]), monthly["outcome_stability"],
           width=24, color=C_HHS, alpha=0.85)
    ax.axhline(50, color=C_WARN, ls="--", lw=1.2)
    ax.set_ylim(0, 100)
    ax.set_ylabel("Monthly score")
    ax.set_title("Monthly Outcome Stability Score")
    _date_axis(ax)

    fig.suptitle("Outcome stability analysis", fontsize=13, fontweight="bold", y=1.01)
    save(fig, "fig06_outcome_stability",
         "Figure 6. Consistency of reunification outcomes. Amber bands mark prolonged "
         "low-release periods, red markers sudden drops in discharge effectiveness, and the lower "
         "panel scores each month's consistency (100 - coefficient of variation).")


# --------------------------------------------------------------------------- #
# Figure 7 - throughput funnel
# --------------------------------------------------------------------------- #
def fig_funnel(df: pd.DataFrame) -> None:
    totals = {c: float(df[c].sum()) for c in cp.FLOW_COLS}

    fig, axes = plt.subplots(1, 2, figsize=(12, 5), gridspec_kw={"width_ratios": [1.3, 1]})

    ax = axes[0]
    stages = ["Entered CBP\ncustody", "Transferred to\nHHS care", "Discharged to\nsponsor"]
    vals = [totals["intake"], totals["transfers"], totals["discharges"]]
    colors = [C_ENTRY, C_WARN, C_EXIT]
    x = np.arange(len(stages))
    ax.bar(x, vals, color=colors, alpha=0.9, width=0.6)
    for i, v in enumerate(vals):
        ax.text(i, v, f"{int(v):,}", ha="center", va="bottom", fontsize=11, fontweight="bold")
    for i in range(len(vals) - 1):
        ratio = vals[i + 1] / vals[i]
        ax.annotate(f"{ratio:.2f}", xy=(i + 0.5, max(vals) * 0.55), ha="center",
                    fontsize=11, fontweight="bold", color=C_GREY,
                    bbox=dict(boxstyle="round,pad=0.3", fc="white", ec=C_GREY, lw=0.8))
    ax.set_xticks(x)
    ax.set_xticklabels(stages, fontsize=10)
    ax.set_ylabel("Children (period total)")
    ax.set_title("Stage-to-stage completion ratios, full period")

    ax = axes[1]
    labels = ["Clear CBP queue", "Clear HHS queue"]
    cbp_days = float(np.nanmean(df["cbp_clearance_days"]))
    hhs_days = float(np.nanmean(df["hhs_release_days"]))
    if not np.isfinite(cbp_days) or not np.isfinite(hhs_days):
        cbp_days = float(np.nanmedian(df["cbp_clearance_days"]))
        hhs_days = float(np.nanmedian(df["hhs_release_days"]))
    bars = ax.barh(labels, [cbp_days, hhs_days], color=[C_CBP, C_HHS], alpha=0.9)
    for b, v in zip(bars, [cbp_days, hhs_days]):
        ax.text(v + max(cbp_days, hhs_days) * 0.02, b.get_y() + b.get_height() / 2,
                f"{v:.0f} days", va="center", fontsize=11, fontweight="bold")
    ax.set_xlabel("Days (mean stock / mean daily flow)")
    ax.set_xlim(0, max(cbp_days, hhs_days) * 1.35)
    ax.set_title("Implied queue-drain time by stage")

    fig.suptitle("Pipeline throughput: entries, handoffs and exits", fontsize=13, fontweight="bold", y=1.02)
    save(fig, "fig07_throughput_funnel",
         "Figure 7. End-to-end throughput. The ratio labels are stage-completion rates; the right "
         "panel shows how long each queue takes to drain at observed flow rates.")


# --------------------------------------------------------------------------- #
# Figure 8 - year-on-year regime comparison
# --------------------------------------------------------------------------- #
def fig_regimes(df: pd.DataFrame) -> None:
    rows = []
    for year, g in df.groupby("year"):
        rows.append(
            {
                "year": year,
                "intake": g["intake"].mean(),
                "discharges": g["discharges"].mean(),
                "te": g["transfer_efficiency"].mean(),
                "de": g["discharge_effectiveness"].mean(),
                "stability": cp.outcome_stability(g["discharge_effectiveness"].dropna()),
                "hhs": g["hhs_stock"].mean(),
                "backlog": g["backlog_accumulation"].mean(),
            }
        )
    yearly = pd.DataFrame(rows).set_index("year")
    years = list(yearly.index)

    fig, axes = plt.subplots(1, 3, figsize=(12, 4.4))
    x = np.arange(len(years))
    w = 0.26

    ax = axes[0]
    ax.bar(x - w, yearly["te"].values * 100, w, color=C_CBP, label="Transfer eff.")
    ax.bar(x, yearly["de"].values * 100, w, color=C_EXIT, label="Discharge eff.")
    ax.bar(x + w, yearly["stability"].values, w, color=C_HHS, label="Stability score")
    ax.set_xticks(x)
    ax.set_xticklabels(years)
    ax.set_ylabel("% or score")
    ax.set_title("KPI levels by year")
    ax.legend(fontsize=8)

    ax = axes[1]
    ax.bar(x - w / 2, yearly["intake"].values, w, color=C_ENTRY, label="Intake/day")
    ax.bar(x + w / 2, yearly["discharges"].values, w, color=C_EXIT, label="Discharges/day")
    ax.set_xticks(x)
    ax.set_xticklabels(years)
    ax.set_ylabel("Children per day")
    ax.set_title("Flow volumes by year")
    ax.legend(fontsize=8)

    ax = axes[2]
    ax.bar(x, yearly["hhs"].values, w * 1.4, color=C_HHS, label="Mean HHS caseload")
    ax.set_xticks(x)
    ax.set_xticklabels(years)
    ax.set_ylabel("Children in HHS care")
    ax.set_title("Caseload and net imbalance by year")
    ax2 = ax.twinx()
    ax2.plot(x, yearly["backlog"].values, marker="o", color=C_WARN, lw=2, label="Net backlog / day")
    ax2.axhline(0, color=C_WARN, ls="--", lw=1)
    ax2.set_ylabel("Children/day net imbalance")
    ax2.grid(False)
    h1, l1 = ax.get_legend_handles_labels()
    h2, l2 = ax2.get_legend_handles_labels()
    ax.legend(h1 + h2, l1 + l2, fontsize=8, loc="upper right")

    fig.suptitle("Three operating regimes: 2023 build-up, 2024 plateau, 2025 contraction",
                 fontsize=13, fontweight="bold", y=1.03)
    save(fig, "fig08_regime_comparison",
         "Figure 8. Year-on-year regime comparison. Ratios are scale-invariant, so KPI levels can "
         "be compared across regimes even though volumes differ by an order of magnitude.")


# --------------------------------------------------------------------------- #
# Tables + insights
# --------------------------------------------------------------------------- #
def build_tables(df: pd.DataFrame, runs, stagnation, drops, alerts) -> dict:
    tables = {}

    overall = cp.compute_window_kpis(df, label="Full period")
    yearly_rows = []
    for year, g in df.groupby("year"):
        win = cp.compute_window_kpis(g, label=str(year))
        row = {"period": str(year), "reporting_days": win.reporting_days,
               "coverage_pct": win.coverage_pct, **{k: round(v, 4) for k, v in win.kpis.items()}}
        yearly_rows.append(row)
    tables["kpi_year"] = pd.DataFrame(yearly_rows)
    tables["kpi_overall"] = pd.DataFrame(overall.as_rows())
    tables["monthly"] = cp.monthly_summary(df)
    tables["daytype"] = cp.daytype_summary(df)
    tables["bottlenecks"] = pd.DataFrame([r.as_dict() for r in runs])
    tables["stagnation"] = pd.DataFrame(stagnation)
    tables["drops"] = pd.DataFrame(drops)
    tables["alerts"] = pd.DataFrame(alerts)
    tables["mass_balance"] = pd.DataFrame(cp.mass_balance(df)["rows"])

    for name, tbl in tables.items():
        path = TABLE_DIR / f"{name}.csv"
        tbl.to_csv(path, index=False)
        print(f"  table   {path.relative_to(ROOT)}")

    return tables


def build_diagnostics(df: pd.DataFrame, coverage: dict) -> dict:
    """Methodological checks that qualify how the metrics should be read."""
    n = len(df)
    t = np.arange(n, dtype=float)

    def ols(X: np.ndarray, y: np.ndarray):
        beta, *_ = np.linalg.lstsq(X, y, rcond=None)
        resid = y - X @ beta
        k = X.shape[1]
        s2 = float((resid ** 2).sum()) / max(n - k, 1)
        se = np.sqrt(np.diag(s2 * np.linalg.inv(X.T @ X)))
        r2 = 1 - float((resid ** 2).sum()) / float(((y - y.mean()) ** 2).sum())
        return beta, se, r2

    # Test 1 - are published flows daily counts or sums over the reporting gap?
    gap_test = {}
    for col in cp.FLOW_COLS:
        X = np.column_stack([np.ones(n), df["gap"].values, t, t ** 2])
        beta, se, _ = ols(X, df[col].values.astype(float))
        gap_test[col] = {
            "gap_coefficient_children_per_extra_gap_day": round(float(beta[1]), 2),
            "t_stat": round(float(beta[1] / se[1]), 1),
            "period_sum_expectation": round(float(df[col].mean()), 1),
        }

    # Test 2 - weekend (Sunday) release effect, controlling for gap, caseload
    # and a quadratic time trend.
    X = np.column_stack(
        [
            np.ones(n),
            (df["day_type"] == "weekend").astype(float).values,
            df["gap"].values,
            t,
            t ** 2,
            df["hhs_stock"].values / 1000.0,
        ]
    )
    beta, se, r2 = ols(X, df["discharges"].values.astype(float))

    return {
        "flow_is_daily_count": {
            "regression": "flow ~ reporting_gap + quadratic_time_trend",
            "results": gap_test,
            "interpretation": (
                "Gap coefficients are an order of magnitude below the values expected if reports "
                "summed flows over the gap, so published flows are treated as daily counts."
            ),
        },
        "weekend_release_effect": {
            "regression": "discharges ~ sunday + reporting_gap + quadratic_time_trend + hhs_caseload",
            "sunday_coefficient_children": round(float(beta[1]), 1),
            "t_stat": round(float(beta[1] / se[1]), 1),
            "r_squared": round(r2, 3),
            "interpretation": (
                "Sunday reports carry this many additional discharges versus weekday reports at "
                "equal caseload, gap and trend. Because the file contains no Saturday reports and "
                "only two Friday reports, genuine weekend placement activity cannot be separated "
                "from a wider weekend counting window."
            ),
        },
        "reporting_gaps": {
            "calendar_days_without_report": int(coverage["calendar_days"] - coverage["reporting_days"]),
            "multi_day_gap_reports": int((df["gap"] > 1).sum()),
            "multi_day_gap_share_pct": round(float((df["gap"] > 1).mean() * 100), 1),
            "zero_discharge_reports": int((df["discharges"] == 0).sum()),
        },
        "queue_drain_time_by_year": {
            str(year): {
                "release_days_mean": round(float(g["hhs_release_days"].mean()), 1),
                "release_days_median": round(float(g["hhs_release_days"].median()), 1),
                "clearance_days_mean": round(float(g["cbp_clearance_days"].mean()), 2),
            }
            for year, g in df.groupby("year")
        },
    }


def build_insights(df, runs, stagnation, drops, coverage, tables) -> dict:
    overall = cp.compute_window_kpis(df, label="Full period")
    yearly = tables["kpi_year"]
    daytype = tables["daytype"]
    monthly = tables["monthly"]
    alerts_tbl = tables["alerts"]

    y2023 = yearly[yearly["period"] == "2023"].iloc[0]
    y2024 = yearly[yearly["period"] == "2024"].iloc[0]
    y2025 = yearly[yearly["period"] == "2025"].iloc[0]
    wd = daytype[daytype["day_type"] == "weekday"].iloc[0]
    we = daytype[daytype["day_type"] == "weekend"].iloc[0]

    peak_month = monthly.loc[monthly["discharges_per_day"].idxmax()]
    trough_month = monthly.loc[monthly["discharges_per_day"].idxmin()]
    worst_stability = monthly.loc[monthly["outcome_stability"].idxmin()]

    longest_run = max(runs, key=lambda r: r.reports) if runs else None
    worst_stagnation = max(stagnation, key=lambda s: s["reports"]) if stagnation else None

    insights = {
        "generated_for": "Care Transition Efficiency & Placement Outcome Analytics",
        "period": {
            "start": overall.start,
            "end": overall.end,
            "reporting_days": overall.reporting_days,
            "calendar_days": overall.calendar_days,
            "coverage_pct": overall.coverage_pct,
        },
        "coverage": coverage,
        "overall_kpis": {k: round(v, 4) if isinstance(v, float) else v for k, v in overall.kpis.items()},
        "overall_totals": {k: int(v) for k, v in overall.totals.items()},
        "kpi_by_year": yearly.to_dict(orient="records"),
        "headlines": {
            "transfer_efficiency_full": round(overall.kpis["transfer_efficiency"] * 100, 2),
            "discharge_effectiveness_full": round(overall.kpis["discharge_effectiveness"] * 100, 3),
            "pipeline_throughput_full": round(overall.kpis["pipeline_throughput"], 3),
            "outcome_stability_full": round(overall.kpis["outcome_stability"], 1),
            "cbp_clearance_days_full": round(overall.kpis["cbp_clearance_days"], 1),
            "hhs_release_days_full": round(overall.kpis["hhs_release_days"], 1),
            "transfer_efficiency_2023": round(float(y2023["transfer_efficiency"]) * 100, 2),
            "transfer_efficiency_2025": round(float(y2025["transfer_efficiency"]) * 100, 2),
            "discharge_effectiveness_2023": round(float(y2023["discharge_effectiveness"]) * 100, 3),
            "discharge_effectiveness_2025": round(float(y2025["discharge_effectiveness"]) * 100, 3),
            "stability_2023": round(float(y2023["outcome_stability"]), 1),
            "stability_2024": round(float(y2024["outcome_stability"]), 1),
            "stability_2025": round(float(y2025["outcome_stability"]), 1),
            "throughput_2023": round(float(y2023["pipeline_throughput"]), 3),
            "throughput_2024": round(float(y2024["pipeline_throughput"]), 3),
            "throughput_2025": round(float(y2025["pipeline_throughput"]), 3),
            "weekday_discharge_effectiveness": round(float(wd["discharge_effectiveness"]) * 100, 3),
            "weekend_discharge_effectiveness": round(float(we["discharge_effectiveness"]) * 100, 3),
            "peak_placement_month": peak_month["year_month"],
            "peak_discharges_per_day": round(float(peak_month["discharges_per_day"]), 1),
            "trough_placement_month": trough_month["year_month"],
            "trough_discharges_per_day": round(float(trough_month["discharges_per_day"]), 1),
            "weakest_stability_month": worst_stability["year_month"],
            "weakest_stability_score": round(float(worst_stability["outcome_stability"]), 1),
        },
        "bottlenecks": [r.as_dict() for r in runs[:15]],
        "longest_backlog_run": longest_run.as_dict() if longest_run else None,
        "stagnation_periods": stagnation[:10],
        "longest_stagnation": worst_stagnation,
        "discharge_drops": drops[:25],
        "drop_count": len(drops),
        "alert_thresholds": dict(ALERT_THRESHOLDS),
        "alert_count": int(len(alerts_tbl)),
        "alerts_by_type": (
            alerts_tbl.groupby("alert").size().astype(int).to_dict() if len(alerts_tbl) else {}
        ),
        "diagnostics": build_diagnostics(df, coverage),
        "mass_balance": cp.mass_balance(df)["rows"],
        "metric_definitions": cp.METRIC_DEFINITIONS,
        "captions": CAPTIONS,
    }
    return insights


# --------------------------------------------------------------------------- #
def main() -> None:
    print("Loading dataset ...")
    df = cp.prepare()
    print(f"  {len(df)} reporting days, {df['date'].min().date()} \u2192 {df['date'].max().date()}")

    coverage = cp.coverage_report(df)
    runs = cp.detect_backlog_runs(df, min_reports=3)
    stagnation = cp.detect_stagnation(df, threshold_pct=0.6, min_reports=4)
    drops = cp.detect_discharge_drops(df, z=2.0, window=60, min_reports=10)
    alerts = cp.threshold_alerts(df, **ALERT_THRESHOLDS)

    print("Rendering figures ...")
    fig_overview(df)
    fig_efficiency(df)
    fig_backlog(df)
    fig_bottlenecks(df, runs)
    fig_temporal(df)
    fig_stability(df)
    fig_funnel(df)
    fig_regimes(df)

    print("Writing tables ...")
    tables = build_tables(df, runs, stagnation, drops, alerts)

    print("Building insights ...")
    insights = build_insights(df, runs, stagnation, drops, coverage, tables)
    path = cp.dump_json(insights, ROOT / "outputs" / "insights.json")
    cp.dump_json(coverage, ROOT / "outputs" / "coverage.json")
    print(f"  insights {path.relative_to(ROOT)}")
    print("\nHeadline KPIs:")
    for k, v in insights["overall_kpis"].items():
        print(f"  {k:<28} {v}")


if __name__ == "__main__":
    main()
