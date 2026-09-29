"""
Care Transition Efficiency & Placement Outcome Analytics - Streamlit dashboard
=============================================================================

Run with::

    streamlit run app.py

Modules
-------
1. Care Pipeline Flow Visualization  - stage stocks, flows and a flow-conserving Sankey
2. Transfer & Discharge Efficiency   - ratio / days-to-clear panels with metric toggles
3. Bottleneck Detection              - sustained imbalance runs and threshold alerts
4. Outcome Trend Analysis            - month-over-month placement trends and stability
5. Data & Method                     - coverage, mass balance, definitions, downloads

Sidebar controls (date range, metric toggle, rolling window, alert thresholds)
recalculate every module against the selected reporting window.
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

import care_pipeline as cp  # noqa: E402

st.set_page_config(
    page_title="UAC Care Transition Analytics",
    page_icon="\U0001F9ED",
    layout="wide",
    initial_sidebar_state="expanded",
)

# --------------------------------------------------------------------------- #
# Presentation constants (mirrors src/run_analysis.py)
# --------------------------------------------------------------------------- #
C_CBP = "#D9534F"
C_HHS = "#4C78A8"
C_EXIT = "#54A24B"
C_ENTRY = "#72B7B2"
C_WARN = "#E4A11B"
C_GREY = "#7A7A7A"

COLORS = {
    "intake": C_ENTRY,
    "transfers": C_WARN,
    "discharges": C_EXIT,
    "cbp_stock": C_CBP,
    "hhs_stock": C_HHS,
}

MODES = ["Absolute counts", "Flow/stock ratios", "Days to clear"]


# --------------------------------------------------------------------------- #
# Data
# --------------------------------------------------------------------------- #
@st.cache_data(show_spinner="Loading care-transition dataset ...")
def load_frame() -> pd.DataFrame:
    return cp.prepare()


@st.cache_data(show_spinner=False)
def load_insights() -> dict:
    import json

    path = ROOT / "outputs" / "insights.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {}


DF = load_frame()
INSIGHTS = load_insights()

MIN_DATE = DF["date"].min().date()
MAX_DATE = DF["date"].max().date()

# --------------------------------------------------------------------------- #
# Sidebar
# --------------------------------------------------------------------------- #
st.sidebar.title("\U0001F9ED Care Transition Analytics")
st.sidebar.caption(
    "Process-efficiency and outcome analytics for the HHS Unaccompanied Alien "
    "Children programme pipeline."
)

st.sidebar.markdown("### Reporting window")
window = st.sidebar.date_input(
    "Select date range",
    value=(MIN_DATE, MAX_DATE),
    min_value=MIN_DATE,
    max_value=MAX_DATE,
    label_visibility="collapsed",
)
if isinstance(window, tuple) and len(window) == 2:
    start_date, end_date = window
else:  # single date picked so far
    start_date = end_date = window[0] if window else MIN_DATE

if start_date > end_date:
    st.sidebar.error("Start date must be on or before the end date.")
    st.stop()

view = cp.filter_range(DF, start_date, end_date)
if view.empty:
    st.sidebar.warning("No reports fall inside that window.")
    st.stop()

st.sidebar.markdown("### Metric presentation")
mode = st.sidebar.radio(
    "Toggle ratio-based metrics",
    MODES,
    index=0,
    help="Absolute counts show volume; ratios are scale-invariant flow/stock "
    "measures; days-to-clear converts a ratio into an operational time-to-drain.",
)

rolling_window = st.sidebar.slider(
    "Rolling window (reports)",
    min_value=5,
    max_value=90,
    value=30,
    step=5,
    help="Smoothing window for trend lines and the Outcome Stability Score.",
)

st.sidebar.markdown("### Threshold-based alerts")
use_de = st.sidebar.checkbox("Discharge effectiveness below", value=True)
thr_de = st.sidebar.slider("minimum (%/day)", 0.1, 3.0, 1.0, 0.1) / 100.0
use_cbp = st.sidebar.checkbox("CBP clearance time above", value=True)
thr_cbp = st.sidebar.slider("maximum (days)", 1.0, 12.0, 4.0, 0.5)
use_hhs = st.sidebar.checkbox("HHS release time above", value=True)
thr_hhs = st.sidebar.slider("maximum (days)", 30, 300, 150, 10)
use_backlog = st.sidebar.checkbox("Backlog accumulation rate above", value=True)
thr_backlog = st.sidebar.slider("maximum (% of caseload/day)", 0.1, 3.0, 1.0, 0.1) / 100.0

alerts = cp.threshold_alerts(
    view,
    min_discharge_effectiveness=thr_de if use_de else None,
    max_cbp_clearance_days=thr_cbp if use_cbp else None,
    max_hhs_release_days=thr_hhs if use_hhs else None,
    max_backlog_rel=thr_backlog if use_backlog else None,
)
alert_dates = {a["date"] for a in alerts}
view = view.assign(is_alert=view["date"].dt.strftime("%Y-%m-%d").isin(alert_dates))

st.sidebar.markdown("---")
_multi_gap = int(view["gap"].gt(1).sum())
st.sidebar.metric("Reports in window", f"{len(view):,}")
st.sidebar.caption(
    f"{_multi_gap} reports follow a multi-day break; the rest are consecutive daily reports."
)
st.sidebar.caption(
    f"{start_date.strftime('%d %b %Y')} \u2192 {end_date.strftime('%d %b %Y')}  |  "
    f"{int((end_date - start_date).days) + 1} calendar days"
)
st.sidebar.download_button(
    "\u2B07\uFE0F Download filtered data",
    view.to_csv(index=False).encode("utf-8"),
    file_name="care_transition_filtered.csv",
    mime="text/csv",
)

# --------------------------------------------------------------------------- #
# Derived window analytics
# --------------------------------------------------------------------------- #
kpis = cp.compute_window_kpis(view, label="Selected window")
rolling = cp.rolling_metrics(view, window=rolling_window)
monthly = cp.monthly_summary(view)
daytype = cp.daytype_summary(view)
runs = cp.detect_backlog_runs(view, min_reports=3)
stagnation = cp.detect_stagnation(view, threshold_pct=0.6, min_reports=4)
drops = cp.detect_discharge_drops(view, z=2.0, window=60, min_reports=10)

# Previous equal-length window, for KPI deltas.
span = (pd.Timestamp(end_date) - pd.Timestamp(start_date)).days
prev = cp.filter_range(DF, pd.Timestamp(start_date) - pd.Timedelta(days=span + 1),
                       pd.Timestamp(start_date) - pd.Timedelta(days=1))
prev_kpis = cp.compute_window_kpis(prev, label="Previous") if len(prev) >= 5 else None


def delta(kpi: str, higher_is_better: bool = True):
    """Percent change versus the immediately preceding equal-length window."""
    if not prev_kpis or not np.isfinite(prev_kpis.kpis.get(kpi, np.nan)):
        return None
    a, b = prev_kpis.kpis[kpi], kpis.kpis[kpi]
    if not np.isfinite(a) or a == 0:
        return None
    pct = (b - a) / abs(a) * 100.0
    good = pct >= 0 if higher_is_better else pct <= 0
    return f"{pct:+.1f}% vs prior {span}d", "normal" if good else "inverse"


def delta_kwargs(kpi: str, higher_is_better: bool = True) -> dict:
    """Keyword arguments for ``st.metric`` (delta text + colour direction)."""
    result = delta(kpi, higher_is_better)
    if result is None:
        return {"delta": None, "delta_color": "off"}
    return {"delta": result[0], "delta_color": result[1]}


def fmt_pct(value: float, digits: int = 2) -> str:
    return f"{value * 100:.{digits}f}%"


def _rgba(hex_color: str, alpha: float = 0.45) -> str:
    h = hex_color.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    return f"rgba({r},{g},{b},{alpha})"


def build_sankey(kpis: cp.KPIWindow) -> go.Figure:
    """Flow-conserving Sankey of the selected window.

    Node inflows equal outflows by construction: any excess of entries over
    transfers is labelled as queue drawdown / unobserved outflow, and any
    excess of discharges over transfers is drawn from the opening HHS caseload
    (and vice versa for the opposite signs).
    """
    intake = float(kpis.totals["intake"])
    transfers = float(kpis.totals["transfers"])
    discharges = float(kpis.totals["discharges"])

    labels = [
        "Apprehensions (entry)",
        "CBP custody queue",
        "HHS (ORR) care queue",
        "Sponsor placement (exit)",
    ]
    colors = [C_ENTRY, C_CBP, C_HHS, C_EXIT]
    source: list[int] = []
    target: list[int] = []
    values: list[float] = []
    link_colors: list[str] = []

    def add_node(label: str, color: str) -> int:
        labels.append(label)
        colors.append(color)
        return len(labels) - 1

    def link(s: int, t: int, v: float) -> None:
        if v > 0:
            source.append(s)
            target.append(t)
            values.append(float(v))
            link_colors.append(_rgba(colors[s]))

    link(0, 1, intake)
    link(1, 2, transfers)
    link(2, 3, discharges)

    if intake >= transfers:
        link(1, add_node("CBP queue drawdown / unobserved outflow", "#B9B9B9"), intake - transfers)
    else:
        link(add_node("Opening CBP caseload drawdown", "#9BB4D1"), 1, transfers - intake)

    if transfers >= discharges:
        link(2, add_node("Net HHS queue growth", "#F0C36D"), transfers - discharges)
    else:
        link(add_node("Opening HHS caseload drawdown", "#9BB4D1"), 2, discharges - transfers)

    fig = go.Figure(
        go.Sankey(
            arrangement="snap",
            node=dict(
                pad=14,
                thickness=18,
                line=dict(color="#DADADA", width=0.6),
                label=labels,
                color=colors,
            ),
            link=dict(source=source, target=target, value=values, color=link_colors),
        )
    )
    fig.update_layout(
        title=dict(text="Flow-conserving pipeline map (window totals)", font=dict(size=13)),
        height=520,
        margin=dict(l=10, r=10, t=50, b=10),
        font=dict(size=11),
    )
    return fig


# --------------------------------------------------------------------------- #
# Header
# --------------------------------------------------------------------------- #
st.title("Care Transition Efficiency & Placement Outcome Analytics")
st.caption(
    "The UAC programme modelled as a three-stage pipeline: **CBP custody \u2192 HHS (ORR) care "
    "\u2192 sponsor placement**. Every panel below is computed on the reporting window selected "
    "in the sidebar."
)

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Transfer Efficiency Ratio", fmt_pct(kpis.kpis["transfer_efficiency"], 1),
          help=cp.METRIC_DEFINITIONS["transfer_efficiency"],
          **delta_kwargs("transfer_efficiency"))
c2.metric("Discharge Effectiveness Index", fmt_pct(kpis.kpis["discharge_effectiveness"], 2),
          help=cp.METRIC_DEFINITIONS["discharge_effectiveness"],
          **delta_kwargs("discharge_effectiveness"))
c3.metric("Pipeline Throughput", f"{kpis.kpis['pipeline_throughput']:.2f}\u00d7",
          help=cp.METRIC_DEFINITIONS["pipeline_throughput"],
          **delta_kwargs("pipeline_throughput"))
c4.metric("Backlog Accumulation Rate",
          f"{kpis.kpis['backlog_accumulation']:+.0f}/day",
          help=cp.METRIC_DEFINITIONS["backlog_accumulation"],
          **delta_kwargs("backlog_accumulation", higher_is_better=False))
c5.metric("Outcome Stability Score", f"{kpis.kpis['outcome_stability']:.0f}",
          help="100 \u00d7 (1 \u2212 clamp(CV of discharge effectiveness)) - higher is more consistent",
          **delta_kwargs("outcome_stability"))

alert_note = f"**{len(alerts)}** threshold breaches in window" if alerts else "No threshold breaches in window"
st.caption(
    f"Coverage: **{len(view)}** reports over **{int((pd.Timestamp(end_date) - pd.Timestamp(start_date)).days) + 1}** "
    f"calendar days ({kpis.coverage_pct:.0f}%) \u00b7 \U0001F6A8 {alert_note}"
)

tab_flow, tab_eff, tab_bottleneck, tab_outcome, tab_method = st.tabs(
    [
        "\U0001F4CA Care Pipeline Flow",
        "\u26A1 Transfer & Discharge Efficiency",
        "\U0001F6A8 Bottleneck Detection",
        "\U0001F331 Outcome Trend Analysis",
        "\U0001F4D1 Data & Method",
    ]
)


# --------------------------------------------------------------------------- #
# Shared helpers
# --------------------------------------------------------------------------- #
def series_frame() -> pd.DataFrame:
    """Frame used by the time-series charts (features + rolling metrics)."""
    out = view.copy()
    for col in ("de_roll", "te_roll", "release_days_roll", "clearance_days_roll",
                "stability_roll", "backlog_roll"):
        out[col] = rolling[col]
    return out


def add_alert_markers(fig: go.Figure, data: pd.DataFrame, y_col: str, name: str = "Threshold breach") -> go.Figure:
    flagged = data[data["is_alert"]]
    if flagged.empty:
        return fig
    fig.add_trace(
        go.Scatter(
            x=flagged["date"],
            y=flagged[y_col],
            mode="markers",
            marker=dict(color="#C0392B", size=7, symbol="x", line=dict(width=1.4)),
            name=name,
            hovertemplate="%{x|%d %b %Y}<br>" + name + "<extra></extra>",
        )
    )
    return fig


def style(fig: go.Figure, height: int = 380) -> go.Figure:
    fig.update_layout(
        height=height,
        margin=dict(l=40, r=20, t=60, b=40),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
        hovermode="x unified",
        plot_bgcolor="white",
        font=dict(size=12),
    )
    fig.update_xaxes(showgrid=True, gridwidth=1, gridcolor="#EDEDED")
    fig.update_yaxes(showgrid=True, gridwidth=1, gridcolor="#EDEDED")
    return fig


# --------------------------------------------------------------------------- #
# Tab 1 - Care Pipeline Flow
# --------------------------------------------------------------------------- #
with tab_flow:
    st.subheader("Care pipeline flow visualization")

    left, right = st.columns([3, 2])

    with left:
        if mode == "Absolute counts":
            y_cbp, y_hhs, y_flow = "cbp_stock", "hhs_stock", None
            labels = ("Children in CBP custody", "Children in HHS care", "Children / report")
        elif mode == "Flow/stock ratios":
            y_cbp, y_hhs, y_flow = "transfer_efficiency", "discharge_effectiveness", None
            labels = ("Transfer efficiency (CBP/day)", "Discharge effectiveness (HHS/day)",
                      "Ratio per report")
        else:
            y_cbp, y_hhs, y_flow = "cbp_clearance_days", "hhs_release_days", None
            labels = ("CBP clearance time (days)", "HHS release time (days)", "Days")

        fig = make_subplots(
            rows=3, cols=1, shared_xaxes=True, vertical_spacing=0.09,
            subplot_titles=(
                "Queue 1 \u2013 children held in CBP custody",
                "Queue 2 \u2013 children in HHS care awaiting sponsor placement",
                "Daily flows \u2013 entry, handoff, exit",
            ),
        )
        fig.add_trace(go.Bar(x=view["date"], y=view["intake"], name="Apprehensions (entry)",
                             marker_color=C_ENTRY, width=86400000), row=3, col=1)
        fig.add_trace(go.Bar(x=view["date"], y=view["transfers"], name="Transferred CBP \u2192 HHS",
                             marker_color=C_WARN, width=86400000), row=3, col=1)
        fig.add_trace(go.Bar(x=view["date"], y=view["discharges"], name="Discharged to sponsor",
                             marker_color=C_EXIT, width=86400000), row=3, col=1)
        fig.add_trace(go.Scatter(x=view["date"], y=view[y_cbp], name=labels[0],
                                 line=dict(color=C_CBP, width=1.6)), row=1, col=1)
        fig.add_trace(go.Scatter(x=view["date"], y=view[y_hhs], name=labels[1],
                                 line=dict(color=C_HHS, width=1.6)), row=2, col=1)
        fig.update_yaxes(title_text=labels[0], row=1, col=1)
        fig.update_yaxes(title_text=labels[1], row=2, col=1)
        fig.update_yaxes(title_text="Children / report", row=3, col=1)
        fig.update_layout(barmode="overlay", height=720)
        fig.update_traces(opacity=0.75, selector=dict(type="bar"))
        st.plotly_chart(style(fig, 720), width="stretch")

    with right:
        st.markdown("#### Stage movement in window")
        stage = pd.DataFrame(
            [
                {"Stage": "1. Apprehension \u2192 CBP custody", "Entering": kpis.totals["intake"],
                 "Leaving": kpis.totals["transfers"]},
                {"Stage": "2. CBP custody \u2192 HHS care", "Entering": kpis.totals["transfers"],
                 "Leaving": kpis.totals["discharges"]},
            ]
        )
        st.dataframe(
            stage.style.format({"Entering": "{:,.0f}", "Leaving": "{:,.0f}"}),
            width="stretch", hide_index=True,
        )

        s1, s2, s3 = st.columns(3)
        s1.metric("Handoff completion", fmt_pct(kpis.kpis["handoff_completion"], 0),
                  help="Transfers \u00f7 apprehensions over the window")
        s2.metric("Placement completion", fmt_pct(kpis.kpis["placement_completion"], 0),
                  help="Discharges \u00f7 transfers over the window")
        s3.metric("Throughput", f"{kpis.kpis['pipeline_throughput']:.2f}\u00d7",
                  help="Total exits \u00f7 total entries over the window")

        # Flow-conserving Sankey ------------------------------------------- #
        st.plotly_chart(build_sankey(kpis), width="stretch")
        st.caption(
            "Links balance: if transfers fall short of entries the residual is shown as queue "
            "drawdown/unobserved outflow; if discharges exceed transfers the difference is drawn "
            "from the opening HHS caseload."
        )

    st.markdown("#### Net queue imbalance by report")
    imbalance = pd.DataFrame(
        {
            "date": view["date"],
            "CBP (intake \u2212 transfers)": view["cbp_net_backlog"],
            "HHS (transfers \u2212 discharges)": view["backlog_accumulation"],
        }
    ).melt(id_vars="date", var_name="Queue", value_name="Net change")
    fig = px.bar(
        imbalance, x="date", y="Net change", color="Queue", barmode="overlay",
        color_discrete_map={"CBP (intake \u2212 transfers)": C_CBP,
                            "HHS (transfers \u2212 discharges)": C_WARN},
        labels={"date": "Reporting date"},
    )
    fig.add_hline(y=0, line_color="black", line_width=1)
    fig.update_traces(opacity=0.75)
    st.plotly_chart(style(fig, 340), width="stretch")
    st.caption("Positive = queue grew that report (inflow exceeded outflow). Negative = queue drained.")


# --------------------------------------------------------------------------- #
# Tab 2 - Transfer & discharge efficiency
# --------------------------------------------------------------------------- #
with tab_eff:
    st.subheader("Transfer & discharge efficiency panels")
    st.caption(
        f"Metric presentation: **{mode}** \u00b7 smoothed with a {rolling_window}-report rolling window."
    )

    data = series_frame()

    if mode == "Absolute counts":
        left_series, right_series = "transfers", "discharges"
        titles = ("Transferred out of CBP custody", "Discharged from HHS care")
        ylabel = "Children / report"
    elif mode == "Flow/stock ratios":
        left_series, right_series = "transfer_efficiency", "discharge_effectiveness"
        titles = ("Transfer Efficiency Ratio", "Discharge Effectiveness Index")
        ylabel = "Share of queue turned over / report"
    else:
        left_series, right_series = "cbp_clearance_days", "hhs_release_days"
        titles = ("CBP clearance time", "HHS release time")
        ylabel = "Days to clear queue"

    left, right = st.columns(2)
    if mode == "Absolute counts":
        left_roll = view["transfers"].rolling(rolling_window, min_periods=3).mean()
        right_roll = view["discharges"].rolling(rolling_window, min_periods=3).mean()
    elif mode == "Flow/stock ratios":
        left_roll, right_roll = rolling["te_roll"], rolling["de_roll"]
    else:
        left_roll, right_roll = rolling["clearance_days_roll"], rolling["release_days_roll"]

    with left:
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=data["date"], y=data[left_series], name="Report value",
                                 line=dict(color=C_GREY, width=0.8), opacity=0.45))
        fig.add_trace(go.Scatter(x=data["date"], y=left_roll,
                                 name=f"{rolling_window}-report mean",
                                 line=dict(color=C_CBP, width=2.4)))
        fig.update_layout(title=titles[0], yaxis_title=ylabel)
        fig = add_alert_markers(fig, data, left_series)
        st.plotly_chart(style(fig), width="stretch")

    with right:
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=data["date"], y=data[right_series], name="Report value",
                                 line=dict(color=C_GREY, width=0.8), opacity=0.45))
        fig.add_trace(go.Scatter(x=data["date"], y=right_roll,
                                 name=f"{rolling_window}-report mean",
                                 line=dict(color=C_EXIT, width=2.4)))
        fig.update_layout(title=titles[1], yaxis_title=ylabel)
        fig = add_alert_markers(fig, data, right_series)
        st.plotly_chart(style(fig), width="stretch")

    st.markdown("#### Month-over-month efficiency and stage completion")
    m = monthly.copy()
    m["first"] = pd.to_datetime(m["first"])
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(go.Bar(x=m["first"], y=m["transfer_efficiency"] * 100,
                         name="Transfer efficiency", marker_color=C_CBP), secondary_y=False)
    fig.add_trace(go.Bar(x=m["first"], y=m["discharge_effectiveness"] * 100,
                         name="Discharge effectiveness", marker_color=C_EXIT), secondary_y=False)
    fig.add_trace(go.Scatter(x=m["first"], y=m["placement_completion"] * 100,
                             name="Placement completion (\u00d7100)",
                             line=dict(color=C_HHS, width=2, dash="dot")), secondary_y=True)
    fig.update_yaxes(title_text="% per reporting day", secondary_y=False)
    fig.update_yaxes(title_text="Discharges \u00f7 transfers (%)", secondary_y=True)
    fig.update_layout(title="Monthly ratios \u2013 scale-invariant view of the same window")
    st.plotly_chart(style(fig, 420), width="stretch")

    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown("**CBP handoff speed**")
        st.write(
            f"Mean **{fmt_pct(kpis.kpis['transfer_efficiency'], 1)}** of the CBP queue moves per "
            f"report \u2192 **{kpis.kpis['cbp_clearance_days']:.1f} days** to clear at the observed rate."
        )
    with c2:
        st.markdown("**HHS release velocity**")
        st.write(
            f"Mean **{fmt_pct(kpis.kpis['discharge_effectiveness'], 2)}** of the HHS caseload leaves "
            f"per report \u2192 **{kpis.kpis['hhs_release_days']:.0f} days** to place the caseload."
        )
    with c3:
        st.markdown("**Consistency**")
        st.write(
            f"Outcome Stability Score **{kpis.kpis['outcome_stability']:.0f}** "
            f"(100 = perfectly consistent daily release velocity)."
        )


# --------------------------------------------------------------------------- #
# Tab 3 - Bottleneck detection
# --------------------------------------------------------------------------- #
with tab_bottleneck:
    st.subheader("Bottleneck detection charts")

    data = series_frame()
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=data["date"], y=data["backlog_accumulation"],
        name="HHS net imbalance",
        marker_color=[C_EXIT if v <= 0 else C_WARN for v in data["backlog_accumulation"]],
        width=86400000,
    ))
    for r in runs:
        fig.add_vrect(x0=r.start, x1=r.end, fillcolor=C_WARN, opacity=0.16, line_width=0)
    fig.add_hline(y=0, line_color="black", line_width=1)
    fig = add_alert_markers(fig, data, "backlog_accumulation")
    fig.update_layout(
        title=f"Net HHS backlog per report (transfers \u2212 discharges) \u00b7 "
              f"{len(runs)} sustained runs highlighted",
        yaxis_title="Children / report",
    )
    st.plotly_chart(style(fig, 400), width="stretch")
    st.caption("Amber bands mark runs of three or more consecutive reports in which the HHS queue grew.")

    left, right = st.columns([3, 2])

    with left:
        st.markdown("#### Longest sustained-imbalance runs")
        if runs:
            runs_df = pd.DataFrame([r.as_dict() for r in runs])
            st.dataframe(
                runs_df.style.format(
                    {"severity": "{:+,.0f}", "mean_per_day": "{:+.1f}"}
                ),
                width="stretch",
                hide_index=True,
                height=330,
            )
        else:
            st.info("No sustained accumulation runs inside this window.")

        st.markdown("#### Prolonged low-reunification (stagnation) periods")
        if stagnation:
            st.dataframe(pd.DataFrame(stagnation), width="stretch", hide_index=True)
        else:
            st.success("No stagnation periods detected \u2013 discharge effectiveness never stayed "
                       "below 60% of its trailing median for 4+ reports.")

    with right:
        st.markdown(f"#### \U0001F6A8 Threshold alerts \u2013 {len(alerts)}")
        if alerts:
            alert_df = pd.DataFrame(alerts)
            counts = alert_df["alert"].value_counts().rename_axis("Alert").reset_index(name="Reports")
            st.dataframe(counts, width="stretch", hide_index=True)

            fig = px.histogram(
                alert_df, x="date", color="alert", nbins=60,
                color_discrete_sequence=[C_WARN, C_CBP, C_HHS, C_EXIT],
                labels={"alert": "Alert type"},
            )
            fig.update_layout(title="Alerts over time", height=300,
                              legend=dict(orientation="h", y=1.15, yanchor="bottom"))
            st.plotly_chart(fig, width="stretch")

            st.download_button(
                "\u2B07\uFE0F Download alert table",
                alert_df.to_csv(index=False).encode("utf-8"),
                file_name="threshold_alerts.csv",
                mime="text/csv",
            )
            with st.expander("Preview alert rows"):
                st.dataframe(alert_df.tail(25), width="stretch", hide_index=True)
        else:
            st.success("No reporting day in this window breaches the configured thresholds.")

    st.markdown("#### Backlog severity by month")
    m = monthly.copy()
    m["first"] = pd.to_datetime(m["first"])
    m["direction"] = np.where(m["backlog_accumulation"] > 0, "Accumulating", "Draining")
    fig = px.bar(
        m, x="first", y="backlog_accumulation",
        color="direction",
        color_discrete_map={"Accumulating": C_WARN, "Draining": C_EXIT},
        labels={"first": "Month", "backlog_accumulation": "Children", "direction": ""},
        title="Monthly net HHS imbalance",
    )
    fig.add_hline(y=0, line_color="black", line_width=1)
    st.plotly_chart(style(fig, 340), width="stretch")


# --------------------------------------------------------------------------- #
# Tab 4 - Outcome trend analysis
# --------------------------------------------------------------------------- #
with tab_outcome:
    st.subheader("Outcome trend analysis")
    data = series_frame()

    left, right = st.columns([3, 2])

    with left:
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=data["date"], y=data["discharge_effectiveness"] * 100,
                                 name="Discharge effectiveness", line=dict(color=C_GREY, width=0.8),
                                 opacity=0.45))
        fig.add_trace(go.Scatter(x=data["date"], y=data["de_roll"] * 100,
                                 name=f"{rolling_window}-report mean",
                                 line=dict(color=C_EXIT, width=2.4)))
        for s in stagnation:
            fig.add_vrect(x0=s["start"], x1=s["end"], fillcolor=C_WARN, opacity=0.22, line_width=0)
        if drops:
            d = pd.DataFrame(drops)
            fig.add_trace(go.Scatter(
                x=pd.to_datetime(d["date"]), y=d["discharge_effectiveness"] * 100,
                mode="markers", marker=dict(color=C_CBP, size=10, symbol="triangle-down"),
                name="Sudden drop (\u2265 2\u03c3)",
            ))
        fig = add_alert_markers(fig, data, "discharge_effectiveness")
        fig.update_layout(title="Discharge effectiveness: sudden drops and stagnation windows",
                          yaxis_title="% of HHS caseload / report")
        st.plotly_chart(style(fig, 400), width="stretch")

        fig = go.Figure()
        fig.add_trace(go.Scatter(x=data["date"], y=data["stability_roll"],
                                 name="Outcome Stability Score",
                                 line=dict(color=C_HHS, width=2), fill="tozeroy"))
        fig.add_hline(y=50, line_color=C_WARN, line_dash="dash",
                      annotation_text="Alert threshold: 50")
        fig.update_layout(title=f"Outcome Stability Score ({rolling_window}-report window)",
                          yaxis_title="Score (0\u2013100)", yaxis_range=[0, 100])
        st.plotly_chart(style(fig, 340), width="stretch")

    with right:
        st.markdown("#### Month-over-month placements")
        m = monthly.copy()
        m["first"] = pd.to_datetime(m["first"])
        st.dataframe(
            pd.DataFrame(
                {
                    "Month": m["year_month"],
                    "Disch./day": m["discharges_per_day"].round(1),
                    "MoM %": m["discharges_mom_pct"].round(1),
                    "HHS mean": m["hhs_stock_mean"].round(0),
                    "Throughput": m["pipeline_throughput"].round(2),
                    "Stability": m["outcome_stability"].round(0),
                }
            ),
            width="stretch",
            hide_index=True,
            height=340,
        )

        st.markdown("#### Weekday vs weekend transition speed")
        st.dataframe(
            daytype.style.format(
                {
                    "mean_intake": "{:.0f}", "mean_transfers": "{:.0f}",
                    "mean_discharges": "{:.0f}", "mean_cbp_stock": "{:.0f}",
                    "mean_hhs_stock": "{:.0f}",
                    "transfer_efficiency": "{:.3f}", "discharge_effectiveness": "{:.4f}",
                    "cbp_clearance_days": "{:.1f}", "hhs_release_days": "{:.0f}",
                    "outcome_stability": "{:.0f}", "backlog_accumulation": "{:+.0f}",
                }
            ),
            width="stretch",
            hide_index=True,
        )
        st.caption(
            "The file is reported on weekdays plus Sundays \u2013 there are no Saturday reports and "
            "only two Friday reports \u2013 so 'weekend' means Sunday reports."
        )

    st.markdown("#### Placement output vs caseload")
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(go.Bar(x=m["first"], y=m["discharges_per_day"], name="Discharges / reporting day",
                         marker_color=C_EXIT), secondary_y=False)
    fig.add_trace(go.Scatter(x=m["first"], y=m["hhs_stock_mean"], name="Mean HHS caseload",
                             line=dict(color=C_HHS, width=2.4)), secondary_y=True)
    fig.update_yaxes(title_text="Discharges per reporting day", secondary_y=False)
    fig.update_yaxes(title_text="Children in HHS care", secondary_y=True)
    fig.update_layout(title="Monthly placement output against the caseload it serves")
    st.plotly_chart(style(fig, 400), width="stretch")

    if drops:
        with st.expander(f"Sudden drops in reunification success ({len(drops)})"):
            st.dataframe(pd.DataFrame(drops), width="stretch", hide_index=True)


# --------------------------------------------------------------------------- #
# Tab 5 - Data & method
# --------------------------------------------------------------------------- #
with tab_method:
    st.subheader("Data, coverage and method")

    left, right = st.columns(2)

    with left:
        st.markdown("#### Reporting coverage")
        coverage = cp.coverage_report(view)
        cov = pd.DataFrame(
            [
                {"Item": "First report", "Value": coverage["first_report"]},
                {"Item": "Last report", "Value": coverage["last_report"]},
                {"Item": "Reporting days", "Value": f"{coverage['reporting_days']:,}"},
                {"Item": "Calendar days", "Value": f"{coverage['calendar_days']:,}"},
                {"Item": "Coverage", "Value": f"{coverage['coverage_pct']}%"},
                {"Item": "Mean gap between reports", "Value": f"{coverage['mean_gap_days']} days"},
                {"Item": "Longest gap", "Value": f"{coverage['max_gap_days']} days"},
                {"Item": "Weekdays never reported", "Value": ", ".join(coverage["missing_weekdays"]) or "none"},
            ]
        )
        st.dataframe(cov, width="stretch", hide_index=True)

        gap_df = pd.DataFrame(
            {"Gap (days)": list(coverage["gap_distribution"].keys()),
             "Reports": list(coverage["gap_distribution"].values())}
        )
        fig = px.bar(gap_df, x="Gap (days)", y="Reports", text="Reports",
                     color_discrete_sequence=[C_HHS])
        fig.update_layout(title="Reporting cadence", height=300, showlegend=False)
        st.plotly_chart(fig, width="stretch")

        st.markdown("#### Daily-count validation")
        diag = INSIGHTS.get("diagnostics", {})
        gap_test = diag.get("flow_is_daily_count", {}).get("results", {})
        if gap_test:
            gt = pd.DataFrame(
                [
                    {
                        "Flow": k,
                        "Gap coefficient": v["gap_coefficient_children_per_extra_gap_day"],
                        "t-stat": v["t_stat"],
                        "Expected if period-sum": v["period_sum_expectation"],
                    }
                    for k, v in gap_test.items()
                ]
            )
            st.dataframe(gt, width="stretch", hide_index=True)
            st.caption(diag.get("flow_is_daily_count", {}).get("interpretation", ""))

    with right:
        st.markdown("#### Mass-balance diagnostics")
        mb = pd.DataFrame(cp.mass_balance(view)["rows"])
        st.dataframe(
            mb.style.format(
                {c: "{:+,.0f}" for c in mb.columns if c != "period"}
            ),
            width="stretch",
            hide_index=True,
        )
        st.caption(
            "A closed pipeline would show `hhs_residual = 0`: change in stock should equal inflow "
            "minus outflow. A non-zero residual quantifies movement the published columns do not "
            "observe (or definitional differences between flow and stock columns). Use ratios for "
            "cross-period comparison and treat absolute 2023 flow volumes with caution."
        )

        st.markdown("#### KPI definitions")
        st.dataframe(
            pd.DataFrame(
                [{"Metric": k, "Definition": v} for k, v in cp.METRIC_DEFINITIONS.items()]
            ),
            width="stretch",
            hide_index=True,
        )

    st.markdown("#### Window KPI summary")
    kpi_table = pd.DataFrame(kpis.as_rows())[["kpi", "value", "definition"]]
    st.dataframe(
        kpi_table.style.format({"value": "{:,.4f}"}),
        width="stretch",
        hide_index=True,
    )

    d1, d2, d3 = st.columns(3)
    d1.download_button(
        "\u2B07\uFE0F Window KPIs (CSV)",
        pd.DataFrame(kpis.as_rows()).to_csv(index=False).encode("utf-8"),
        file_name="window_kpis.csv",
        mime="text/csv",
        width="stretch",
    )
    d2.download_button(
        "\u2B07\uFE0F Monthly summary (CSV)",
        monthly.to_csv(index=False).encode("utf-8"),
        file_name="monthly_summary.csv",
        mime="text/csv",
        width="stretch",
    )
    d3.download_button(
        "\u2B07\uFE0F Bottleneck runs (CSV)",
        (pd.DataFrame([r.as_dict() for r in runs]).to_csv(index=False).encode("utf-8")
         if runs else b"stage,start,end\n"),
        file_name="bottleneck_runs.csv",
        mime="text/csv",
        width="stretch",
    )

    with st.expander("Analytical methodology (step by step)"):
        st.markdown(
            """
1. **Care pipeline modelling** - the programme is represented as a serial flow pipeline
   `CBP custody -> HHS care -> sponsor placement`, with daily movements recorded between stages
   and the two intermediate queues tracked as stock.
2. **Transition efficiency** - flow/stock ratios turn movement into speed:
   *Transfer Efficiency Ratio = transfers / CBP custody* and
   *Discharge Effectiveness = discharges / HHS care*; each has a reciprocal expressed in days.
3. **Backlog and delay** - inflow is compared with successful exits per report; runs of three or
   more consecutive accumulation reports are flagged as bottlenecks, and the cumulative imbalance
   series locates sustained accumulation.
4. **Temporal and pattern analysis** - weekday versus weekend reports, month-over-month placement
   output, and prolonged low-release (stagnation) periods.
5. **Outcome stability** - the coefficient of variation of discharge effectiveness is converted
   into a 0-100 score; trailing 2-sigma drops are flagged as sudden reunification setbacks.
        """
        )
