"""
Care Transition Efficiency & Placement Outcome Analytics
=========================================================

Core library: data ingestion, pipeline feature engineering, transition-efficiency
metrics, bottleneck/stagnation detection and outcome-stability scoring for the
HHS Unaccompanied Alien Children (UAC) Program reporting file.

The UAC programme is modelled as a three-stage serial pipeline:

    Stage 1              Stage 2                 Stage 3
    CBP custody   --->   HHS (ORR) care   --->   Sponsor placement
    (queue)              (queue)                  (exit / reunification)

Entry flow : "Children apprehended and placed in CBP custody"  (system entry)
Handoff    : "Children transferred out of CBP custody"          (stage 1 -> 2)
Exit flow  : "Children discharged from HHS Care"                (stage 2 -> 3)
Queues     : "Children in CBP custody"  and  "Children in HHS Care" (stock)

Every derived quantity in this module is defined in `METRIC_DEFINITIONS` so the
dashboard, the research paper and the executive summary all cite identical
formulas.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence

import numpy as np
import pandas as pd

# --------------------------------------------------------------------------- #
# Column contract
# --------------------------------------------------------------------------- #

RAW_COLUMNS: Dict[str, str] = {
    "Date": "date",
    "Children apprehended and placed in CBP custody*": "intake",
    "Children in CBP custody": "cbp_stock",
    "Children transferred out of CBP custody": "transfers",
    "Children in HHS Care": "hhs_stock",
    "Children discharged from HHS Care": "discharges",
}

FLOW_COLS: Sequence[str] = ("intake", "transfers", "discharges")
STOCK_COLS: Sequence[str] = ("cbp_stock", "hhs_stock")
ALL_METRIC_COLS: Sequence[str] = tuple(sorted(set(FLOW_COLS) | set(STOCK_COLS)))

DEFAULT_DATA_PATH = (
    Path(__file__).resolve().parents[1] / "data" / "HHS_Unaccompanied_Alien_Children_Program.csv"
)

#: Human-readable formulas published alongside every KPI.
METRIC_DEFINITIONS: Dict[str, str] = {
    "transfer_efficiency": "Transfers out of CBP custody / children in CBP custody "
    "(daily turnover of the CBP queue; higher = faster handoff)",
    "cbp_clearance_days": "Children in CBP custody / Transfers out of CBP custody "
    "(days needed to clear the CBP queue at the observed transfer rate)",
    "discharge_effectiveness": "Discharges from HHS care / children in HHS care "
    "(daily release velocity; higher = faster reunification)",
    "hhs_release_days": "Children in HHS care / Discharges from HHS care "
    "(days needed to place the active HHS caseload at the observed discharge rate)",
    "pipeline_throughput": "Sum(discharges) / Sum(intake) over the window "
    "(total exits divided by total entries)",
    "handoff_completion": "Sum(transfers) / Sum(intake) over the window "
    "(share of apprehensions that reached HHS care)",
    "placement_completion": "Sum(discharges) / Sum(transfers) over the window "
    "(share of transferred children discharged to a sponsor)",
    "backlog_accumulation": "Transfers - Discharges (children/day) "
    "(positive = HHS queue growing faster than it empties)",
    "backlog_accumulation_rel": "(Transfers - Discharges) / HHS care stock "
    "(relative growth rate of the HHS queue)",
    "cbp_net_backlog": "Intake - Transfers (children/day) "
    "(positive = CBP queue growing faster than it empties)",
    "outcome_stability": "100 * (1 - clamp(CV of discharge effectiveness, 0, 1)) "
    "(100 = perfectly consistent daily release velocity)",
}

REPORTING_DAYS: Dict[str, str] = {
    "Monday": "weekday",
    "Tuesday": "weekday",
    "Wednesday": "weekday",
    "Thursday": "weekday",
    "Friday": "weekday",
    "Saturday": "weekend",
    "Sunday": "weekend",
}


# --------------------------------------------------------------------------- #
# Loading / cleaning
# --------------------------------------------------------------------------- #
def load_data(path: str | Path | None = None, *, drop_empty_rows: bool = True) -> pd.DataFrame:
    """Load the raw HHS UAC reporting CSV and return a clean, chronologically
    sorted frame with canonical column names.

    The published file contains a six-column header followed by ~720 populated
    reporting days and a tail of fully blank records which are discarded.
    Values such as ``"2,484"`` are coerced to integers.
    """
    path = Path(path) if path else DEFAULT_DATA_PATH
    if not path.exists():
        raise FileNotFoundError(f"Dataset not found: {path}")

    df = pd.read_csv(path)
    missing = [c for c in RAW_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"Input file is missing expected columns: {missing}")

    df = df[list(RAW_COLUMNS)].rename(columns=RAW_COLUMNS)
    if drop_empty_rows:
        df = df.dropna(how="all")

    df["date"] = pd.to_datetime(df["date"], format="%B %d, %Y", errors="coerce")
    df = df.dropna(subset=["date"])

    for col in ALL_METRIC_COLS:
        df[col] = (
            pd.to_numeric(df[col].astype(str).str.replace(",", "", regex=False), errors="coerce")
            .astype("float64")
        )

    df = df.dropna(subset=list(ALL_METRIC_COLS)).copy()
    df = df.sort_values("date").drop_duplicates(subset="date").reset_index(drop=True)
    return df


# --------------------------------------------------------------------------- #
# Feature engineering
# --------------------------------------------------------------------------- #
def add_features(df: pd.DataFrame) -> pd.DataFrame:
    """Add reporting-cadence, temporal and transition-metric features."""
    out = df.copy()
    out["date"] = pd.to_datetime(out["date"])
    out = out.sort_values("date").reset_index(drop=True)

    # Reporting cadence ----------------------------------------------------- #
    out["gap"] = out["date"].diff().dt.days.fillna(1).astype(int).clip(lower=1)
    out["weekday_num"] = out["date"].dt.weekday
    out["weekday"] = out["date"].dt.day_name()
    out["day_type"] = out["weekday"].map(REPORTING_DAYS).fillna("weekday")
    out["year"] = out["date"].dt.year
    out["month"] = out["date"].dt.month
    out["year_month"] = out["date"].dt.to_period("M").astype(str)
    out["month_label"] = out["date"].dt.strftime("%b %Y")
    out["quarter"] = out["date"].dt.to_period("Q").astype(str)

    # Day-over-day stock deltas -------------------------------------------- #
    out["delta_cbp"] = out["cbp_stock"].diff()
    out["delta_hhs"] = out["hhs_stock"].diff()

    # --- Transition efficiency (stage 1 -> 2) ------------------------------ #
    out["transfer_efficiency"] = np.where(
        out["cbp_stock"] > 0, out["transfers"] / out["cbp_stock"], np.nan
    )
    out["cbp_clearance_days"] = np.where(
        out["transfers"] > 0, out["cbp_stock"] / out["transfers"], np.nan
    )

    # --- Discharge / placement effectiveness (stage 2 -> 3) --------------- #
    out["discharge_effectiveness"] = np.where(
        out["hhs_stock"] > 0, out["discharges"] / out["hhs_stock"], np.nan
    )
    out["hhs_release_days"] = np.where(
        out["discharges"] > 0, out["hhs_stock"] / out["discharges"], np.nan
    )

    # --- Backlog / delay --------------------------------------------------- #
    out["backlog_accumulation"] = out["transfers"] - out["discharges"]
    out["backlog_accumulation_rel"] = np.where(
        out["hhs_stock"] > 0, out["backlog_accumulation"] / out["hhs_stock"], np.nan
    )
    out["cbp_net_backlog"] = out["intake"] - out["transfers"]
    out["cbp_net_backlog_rel"] = np.where(
        out["cbp_stock"] > 0, out["cbp_net_backlog"] / out["cbp_stock"], np.nan
    )
    out["hhs_growing"] = out["backlog_accumulation"] > 0
    out["cbp_growing"] = out["cbp_net_backlog"] > 0

    # --- Streaks of sustained imbalance ----------------------------------- #
    out["hhs_growth_streak"] = _run_length(out["hhs_growing"])
    out["cbp_growth_streak"] = _run_length(out["cbp_growing"])

    # --- Reporting-interval sensitivity flag ------------------------------ #
    # A regression of each flow on the reporting gap (controlling for a
    # quadratic time trend) yields gap coefficients of +9.7, -0.9 and -3.2
    # children/day for discharges, transfers and intake, against period-sum
    # expectations of +173, +129 and +94. Published flows are therefore treated
    # as *daily counts*; `long_gap` marks the ~20% of reports that follow a
    # multi-day break for sensitivity filtering.
    out["long_gap"] = out["gap"] > 1

    return out


def _run_length(mask: pd.Series) -> pd.Series:
    """Length of the current consecutive ``True`` run (resets on ``False``)."""
    mask = mask.astype(bool)
    grp = (~mask).cumsum()
    return mask.groupby(grp).cumsum().where(mask, 0).astype(int)


def prepare(path: str | Path | None = None) -> pd.DataFrame:
    """Convenience: load + engineer features in one call."""
    return add_features(load_data(path))


def filter_range(df: pd.DataFrame, start=None, end=None) -> pd.DataFrame:
    """Return rows inside an inclusive reporting-date window."""
    out = df
    if start is not None:
        out = out[out["date"] >= pd.Timestamp(start)]
    if end is not None:
        out = out[out["date"] <= pd.Timestamp(end)]
    return out.reset_index(drop=True)


# --------------------------------------------------------------------------- #
# Window-level KPIs
# --------------------------------------------------------------------------- #
@dataclass
class KPIWindow:
    """Transition KPIs aggregated over an arbitrary date window."""

    label: str = "window"
    start: Optional[str] = None
    end: Optional[str] = None
    reporting_days: int = 0
    calendar_days: int = 0
    coverage_pct: float = 0.0
    totals: Dict[str, float] = field(default_factory=dict)
    means: Dict[str, float] = field(default_factory=dict)
    kpis: Dict[str, float] = field(default_factory=dict)

    def as_rows(self) -> List[Dict[str, object]]:
        """Flatten to a list of KPI rows (name, value, definition)."""
        rows = []
        for name, value in self.kpis.items():
            rows.append(
                {
                    "window": self.label,
                    "start": self.start,
                    "end": self.end,
                    "kpi": name,
                    "value": value,
                    "definition": METRIC_DEFINITIONS.get(name, ""),
                }
            )
        return rows


def clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    if value is None or (isinstance(value, float) and not np.isfinite(value)):
        return np.nan
    return float(min(max(value, lo), hi))


def coefficient_of_variation(values: Iterable[float]) -> float:
    """Population CV (std/mean); ``nan`` when the mean is 0 or n < 2."""
    s = pd.Series(list(values), dtype="float64").dropna()
    if len(s) < 2:
        return np.nan
    mean = s.mean()
    if not np.isfinite(mean) or mean == 0:
        return np.nan
    return float(s.std(ddof=1) / mean)


def outcome_stability(values: Iterable[float]) -> float:
    """Outcome Stability Score: 100 * (1 - clamp(CV, 0, 1))."""
    cv = coefficient_of_variation(values)
    if not np.isfinite(cv):
        return np.nan
    return float(100.0 * (1.0 - clamp(cv)))


def compute_window_kpis(df: pd.DataFrame, label: str = "window") -> KPIWindow:
    """Compute the five published KPIs plus supporting stage ratios."""
    if df.empty:
        return KPIWindow(label=label)

    totals = {c: float(df[c].sum()) for c in FLOW_COLS}
    means = {c: float(df[c].mean()) for c in ALL_METRIC_COLS}

    entries = totals["intake"]
    exits = totals["discharges"]

    kpis: Dict[str, float] = {
        "transfer_efficiency": float(
            np.nanmean(np.where(df["cbp_stock"] > 0, df["transfers"] / df["cbp_stock"], np.nan))
        ),
        "cbp_clearance_days": float(
            np.nanmean(np.where(df["transfers"] > 0, df["cbp_stock"] / df["transfers"], np.nan))
        ),
        "discharge_effectiveness": float(
            np.nanmean(np.where(df["hhs_stock"] > 0, df["discharges"] / df["hhs_stock"], np.nan))
        ),
        "hhs_release_days": float(
            np.nanmean(np.where(df["discharges"] > 0, df["hhs_stock"] / df["discharges"], np.nan))
        ),
        "pipeline_throughput": float(exits / entries) if entries else np.nan,
        "handoff_completion": float(totals["transfers"] / entries) if entries else np.nan,
        "placement_completion": float(exits / totals["transfers"]) if totals["transfers"] else np.nan,
        "backlog_accumulation": float(df["backlog_accumulation"].mean()),
        "backlog_accumulation_rel": float(
            np.nanmean(
                np.where(df["hhs_stock"] > 0, (df["transfers"] - df["discharges"]) / df["hhs_stock"], np.nan)
            )
        ),
        "cbp_net_backlog": float(df["cbp_net_backlog"].mean()),
        "outcome_stability": outcome_stability(
            np.where(df["hhs_stock"] > 0, df["discharges"] / df["hhs_stock"], np.nan)
        ),
    }

    start, end = df["date"].min(), df["date"].max()
    calendar_days = int((end - start).days) + 1
    reporting_days = int(len(df))
    return KPIWindow(
        label=label,
        start=str(start.date()),
        end=str(end.date()),
        reporting_days=reporting_days,
        calendar_days=calendar_days,
        coverage_pct=round(100.0 * reporting_days / calendar_days, 1) if calendar_days else 0.0,
        totals=totals,
        means=means,
        kpis=kpis,
    )


# --------------------------------------------------------------------------- #
# Rolling / temporal analytics
# --------------------------------------------------------------------------- #
def rolling_metrics(df: pd.DataFrame, window: int = 30) -> pd.DataFrame:
    """Rolling (reporting-day) transition metrics used by the trend module."""
    out = df[["date"]].copy()
    de = df["discharge_effectiveness"]
    te = df["transfer_efficiency"]
    out["de_roll"] = de.rolling(window, min_periods=max(2, window // 3)).mean()
    out["te_roll"] = te.rolling(window, min_periods=max(2, window // 3)).mean()
    out["release_days_roll"] = df["hhs_release_days"].rolling(
        window, min_periods=max(2, window // 3)
    ).mean()
    out["clearance_days_roll"] = df["cbp_clearance_days"].rolling(
        window, min_periods=max(2, window // 3)
    ).mean()
    cv = (
        de.rolling(window, min_periods=max(2, window // 3))
        .apply(coefficient_of_variation, raw=False)
    )
    out["stability_roll"] = cv.map(lambda v: 100.0 * (1.0 - clamp(v)) if pd.notna(v) else np.nan)
    out["backlog_roll"] = (
        df["backlog_accumulation"].rolling(window, min_periods=1).sum()
    )
    return out


def monthly_summary(df: pd.DataFrame) -> pd.DataFrame:
    """Month-over-month placement and efficiency trends."""
    grp = df.groupby("year_month", as_index=False).agg(
        reporting_days=("date", "size"),
        first=("date", "min"),
        last=("date", "max"),
        intake=("intake", "sum"),
        transfers=("transfers", "sum"),
        discharges=("discharges", "sum"),
        cbp_stock_mean=("cbp_stock", "mean"),
        cbp_stock_max=("cbp_stock", "max"),
        hhs_stock_mean=("hhs_stock", "mean"),
        hhs_stock_max=("hhs_stock", "max"),
        transfer_efficiency=("transfer_efficiency", "mean"),
        discharge_effectiveness=("discharge_effectiveness", "mean"),
        backlog_accumulation=("backlog_accumulation", "sum"),
        cbp_net_backlog=("cbp_net_backlog", "sum"),
        intake_per_day=("intake", "mean"),
        transfers_per_day=("transfers", "mean"),
        discharges_per_day=("discharges", "mean"),
    )
    # Month lengths and reporting-day counts differ, so trend comparisons use
    # the per-reporting-day rates while `*_sum` columns remain available for
    # absolute placement volumes.
    grp["pipeline_throughput"] = np.where(grp["intake"] > 0, grp["discharges"] / grp["intake"], np.nan)
    grp["placement_completion"] = np.where(
        grp["transfers"] > 0, grp["discharges"] / grp["transfers"], np.nan
    )
    grp["outcome_stability"] = [
        outcome_stability(
            df.loc[df["year_month"] == ym, "discharge_effectiveness"].dropna()
        )
        for ym in grp["year_month"]
    ]
    grp["discharges_mom_pct"] = grp["discharges"].pct_change() * 100.0
    grp["hhs_stock_mom_pct"] = grp["hhs_stock_mean"].pct_change() * 100.0
    return grp


def period_summary(df: pd.DataFrame) -> pd.DataFrame:
    """Year / quarter roll-up of the same KPI set."""
    frames = []
    for freq, col in (("year", "year"), ("quarter", "quarter")):
        for key, g in df.groupby(col):
            win = compute_window_kpis(g, label=f"{freq} {key}")
            rows = win.as_rows()
            for r in rows:
                r["period_type"] = freq
                r["period"] = str(key)
            frames.extend(rows)
    return pd.DataFrame(frames)


def daytype_summary(df: pd.DataFrame) -> pd.DataFrame:
    """Weekday vs weekend transition speed on reported days only."""
    rows = []
    for day_type, g in df.groupby("day_type"):
        win = compute_window_kpis(g, label=day_type)
        rows.append(
            {
                "day_type": day_type,
                "reporting_days": len(g),
                "mean_intake": g["intake"].mean(),
                "mean_transfers": g["transfers"].mean(),
                "mean_discharges": g["discharges"].mean(),
                "mean_cbp_stock": g["cbp_stock"].mean(),
                "mean_hhs_stock": g["hhs_stock"].mean(),
                "transfer_efficiency": win.kpis["transfer_efficiency"],
                "cbp_clearance_days": win.kpis["cbp_clearance_days"],
                "discharge_effectiveness": win.kpis["discharge_effectiveness"],
                "hhs_release_days": win.kpis["hhs_release_days"],
                "outcome_stability": win.kpis["outcome_stability"],
                "backlog_accumulation": win.kpis["backlog_accumulation"],
            }
        )
    return pd.DataFrame(rows).sort_values("day_type").reset_index(drop=True)


def coverage_report(df: pd.DataFrame) -> Dict[str, object]:
    """Reporting-cadence diagnostics (how observable the process actually is)."""
    start, end = df["date"].min(), df["date"].max()
    calendar_days = int((end - start).days) + 1
    gaps = df["gap"]
    gap_counts = gaps.value_counts().sort_index()
    return {
        "first_report": str(start.date()),
        "last_report": str(end.date()),
        "reporting_days": int(len(df)),
        "calendar_days": calendar_days,
        "coverage_pct": round(100.0 * len(df) / calendar_days, 1),
        "mean_gap_days": round(float(gaps.mean()), 2),
        "median_gap_days": float(gaps.median()),
        "max_gap_days": int(gaps.max()),
        "gap_distribution": {int(k): int(v) for k, v in gap_counts.items()},
        "weekday_counts": {k: int(v) for k, v in df["weekday"].value_counts().items()},
        "missing_weekdays": sorted(
            set(["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"])
            - set(df["weekday"].unique())
        ),
    }


# --------------------------------------------------------------------------- #
# Bottleneck / anomaly detection
# --------------------------------------------------------------------------- #
@dataclass
class BottleneckPeriod:
    stage: str            # "CBP" | "HHS"
    start: str
    end: str
    reports: int
    calendar_days: int
    severity: int         # children accumulated over the run
    mean_per_day: float

    def as_dict(self) -> Dict[str, object]:
        return {
            "stage": self.stage,
            "start": self.start,
            "end": self.end,
            "reports": self.reports,
            "calendar_days": self.calendar_days,
            "severity": self.severity,
            "mean_per_day": round(self.mean_per_day, 1),
        }


def detect_backlog_runs(df: pd.DataFrame, min_reports: int = 3) -> List[BottleneckPeriod]:
    """Consecutive reporting days on which a stage's queue grew
    (inflow > outflow). Runs shorter than ``min_reports`` are ignored so that
    single-day noise does not register as a bottleneck."""
    periods: List[BottleneckPeriod] = []
    for stage, growing, net in (
        ("HHS", "hhs_growing", "backlog_accumulation"),
        ("CBP", "cbp_growing", "cbp_net_backlog"),
    ):
        run: List[int] = []
        for i in range(len(df) + 1):
            is_growing = bool(df[growing].iloc[i]) if i < len(df) else False
            if is_growing:
                run.append(i)
                continue
            if len(run) >= min_reports:
                periods.append(_make_run(df, stage, run, net))
            run = []
    return sorted(periods, key=lambda p: (-p.reports, p.start))


def _make_run(df: pd.DataFrame, stage: str, run: List[int], net: str) -> BottleneckPeriod:
    sub = df.iloc[run]
    start, end = sub["date"].iloc[0], sub["date"].iloc[-1]
    severity = float(sub[net].sum())
    calendar_days = int((end - start).days) + 1
    return BottleneckPeriod(
        stage=stage,
        start=str(start.date()),
        end=str(end.date()),
        reports=len(sub),
        calendar_days=calendar_days,
        severity=int(round(severity)),
        mean_per_day=severity / max(calendar_days, 1),
    )


def detect_stagnation(
    df: pd.DataFrame,
    threshold_pct: float = 0.5,
    min_reports: int = 4,
) -> List[Dict[str, object]]:
    """Prolonged low-reunification periods: discharge effectiveness stays below
    ``threshold_pct`` (fraction of the trailing median) for at least
    ``min_reports`` consecutive reports."""
    de = df["discharge_effectiveness"]
    baseline = de.rolling(30, min_periods=5).median().shift(1)
    flag = (de < threshold_pct * baseline) & baseline.notna()

    periods: List[Dict[str, object]] = []
    run: List[int] = []
    for i in range(len(df) + 1):
        active = bool(flag.iloc[i]) if i < len(df) else False
        if active:
            run.append(i)
            continue
        if len(run) >= min_reports:
            sub = df.iloc[run]
            periods.append(
                {
                    "start": str(sub["date"].iloc[0].date()),
                    "end": str(sub["date"].iloc[-1].date()),
                    "reports": len(sub),
                    "calendar_days": int((sub["date"].iloc[-1] - sub["date"].iloc[0]).days) + 1,
                    "mean_discharge_effectiveness": float(sub["discharge_effectiveness"].mean()),
                    "mean_baseline": float(baseline.iloc[run].mean()),
                }
            )
        run = []
    return sorted(periods, key=lambda p: -p["reports"])


def detect_discharge_drops(
    df: pd.DataFrame, z: float = 2.0, window: int = 60, min_reports: int = 10
) -> List[Dict[str, object]]:
    """Sudden drops in reunification success: discharge effectiveness more than
    ``z`` trailing standard deviations below its rolling mean."""
    de = df["discharge_effectiveness"]
    mean = de.rolling(window, min_periods=min_reports).mean().shift(1)
    std = de.rolling(window, min_periods=min_reports).std().shift(1)
    zscore = (de - mean) / std.replace(0, np.nan)
    hits = df[zscore.notna() & (zscore <= -z)]
    return [
        {
            "date": str(row["date"].date()),
            "discharge_effectiveness": float(row["discharge_effectiveness"]),
            "z_score": float(zscore.loc[idx]),
            "rolling_mean": float(mean.loc[idx]),
        }
        for idx, row in hits.iterrows()
    ]


def threshold_alerts(
    df: pd.DataFrame,
    *,
    min_discharge_effectiveness: Optional[float] = None,
    max_cbp_clearance_days: Optional[float] = None,
    max_hhs_release_days: Optional[float] = None,
    max_backlog_rel: Optional[float] = None,
) -> List[Dict[str, object]]:
    """Visual alert table: every reporting day that breaches a user threshold."""
    alerts: List[Dict[str, object]] = []

    def add(mask: pd.Series, name: str, column: str, threshold: float) -> None:
        for _, row in df[mask.fillna(False)].iterrows():
            alerts.append(
                {
                    "date": str(row["date"].date()),
                    "alert": name,
                    "metric": column,
                    "value": float(row[column]),
                    "threshold": threshold,
                }
            )

    if min_discharge_effectiveness is not None:
        add(
            df["discharge_effectiveness"] < min_discharge_effectiveness,
            "Discharge effectiveness below threshold",
            "discharge_effectiveness",
            min_discharge_effectiveness,
        )
    if max_cbp_clearance_days is not None:
        add(
            df["cbp_clearance_days"] > max_cbp_clearance_days,
            "CBP clearance time above threshold",
            "cbp_clearance_days",
            max_cbp_clearance_days,
        )
    if max_hhs_release_days is not None:
        add(
            df["hhs_release_days"] > max_hhs_release_days,
            "HHS release time above threshold",
            "hhs_release_days",
            max_hhs_release_days,
        )
    if max_backlog_rel is not None:
        add(
            df["backlog_accumulation_rel"] > max_backlog_rel,
            "Backlog accumulation above threshold",
            "backlog_accumulation_rel",
            max_backlog_rel,
        )
    return sorted(alerts, key=lambda a: a["date"])


# --------------------------------------------------------------------------- #
# Data-integrity diagnostics (mass balance)
# --------------------------------------------------------------------------- #
def mass_balance(df: pd.DataFrame) -> Dict[str, object]:
    """Stock-vs-flow reconciliation.

    For a closed pipeline the identity ``delta stock = inflow - outflow`` should
    hold. Departures from it quantify movement that the published columns do
    not observe (or definitional mismatches between the flow and stock columns).
    """
    rows = []
    for label, g in [("all", df)] + [(str(y), x) for y, x in df.groupby("year")]:
        delta_hhs = float(g["hhs_stock"].diff().sum())
        predicted_hhs = float((g["transfers"] - g["discharges"]).sum())
        delta_cbp = float(g["cbp_stock"].diff().sum())
        predicted_cbp = float((g["intake"] - g["transfers"]).sum())
        rows.append(
            {
                "period": label,
                "observed_hhs_change": round(delta_hhs),
                "predicted_hhs_change": round(predicted_hhs),
                "hhs_residual": round(delta_hhs - predicted_hhs),
                "hhs_residual_per_day": round((delta_hhs - predicted_hhs) / max(len(g), 1), 1),
                "observed_cbp_change": round(delta_cbp),
                "predicted_cbp_change": round(predicted_cbp),
                "cbp_residual": round(delta_cbp - predicted_cbp),
                "cbp_residual_per_day": round((delta_cbp - predicted_cbp) / max(len(g), 1), 1),
            }
        )
    return {"rows": rows}


def json_default(obj):
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        return float(obj)
    if isinstance(obj, (np.ndarray,)):
        return obj.tolist()
    if isinstance(obj, pd.Period):
        return str(obj)
    if isinstance(obj, Path):
        return str(obj)
    raise TypeError(f"Object of type {type(obj)} is not JSON serialisable")


def dump_json(data, path: str | Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, default=json_default), encoding="utf-8")
    return path
