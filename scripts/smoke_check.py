"""Pre-deployment smoke check.

Verifies that everything Streamlit Community Cloud needs is present in the
repository and that every analytics entry point app.py calls still works, so a
broken build is caught before it is pushed.

Run::

    python scripts/smoke_check.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import care_pipeline as cp  # noqa: E402

# Files the hosted dashboard / docs reference. Everything must ship in the repo.
REQUIRED_FILES = [
    "app.py",
    "requirements.txt",
    ".streamlit/config.toml",
    "data/HHS_Unaccompanied_Alien_Children_Program.csv",
    "outputs/insights.json",
    "outputs/coverage.json",
    "docs/research_paper.pdf",
    "docs/executive_summary.pdf",
    "docs/research_paper.md",
    "docs/executive_summary.md",
]

# (label, callable) pairs mirroring the exact cp.* calls made by app.py.
def checks(df):
    return [
        ("prepare / features", lambda: cp.prepare()),
        ("window KPIs", lambda: cp.compute_window_kpis(df, label="Full")),
        ("filter_range", lambda: cp.filter_range(df, df["date"].min(), df["date"].max())),
        ("rolling metrics", lambda: cp.rolling_metrics(df, window=30)),
        ("monthly summary", lambda: cp.monthly_summary(df)),
        ("period summary", lambda: cp.period_summary(df)),
        ("day-type summary", lambda: cp.daytype_summary(df)),
        ("coverage report", lambda: cp.coverage_report(df)),
        ("backlog runs", lambda: cp.detect_backlog_runs(df, min_reports=3)),
        ("stagnation", lambda: cp.detect_stagnation(df, threshold_pct=0.6, min_reports=4)),
        ("discharge drops", lambda: cp.detect_discharge_drops(df, z=2.0, window=60, min_reports=10)),
        (
            "threshold alerts",
            lambda: cp.threshold_alerts(
                df,
                min_discharge_effectiveness=0.01,
                max_cbp_clearance_days=4.0,
                max_hhs_release_days=150.0,
                max_backlog_rel=0.01,
            ),
        ),
        ("mass balance", lambda: cp.mass_balance(df)),
        ("metric definitions", lambda: cp.METRIC_DEFINITIONS),
    ]


def main() -> int:
    failures: list[str] = []

    print("== Required files ==")
    for rel in REQUIRED_FILES:
        if (ROOT / rel).exists():
            print(f"[ok]   {rel}")
        else:
            failures.append(f"missing {rel}")
            print(f"[FAIL] missing {rel}")

    print("\n== Analytics entry points ==")
    try:
        df = cp.prepare()
        print(f"[ok]   dataset: {len(df):,} reports, "
              f"{df['date'].min().date()} -> {df['date'].max().date()}")
    except Exception as exc:  # noqa: BLE001
        failures.append(f"dataset load failed: {exc}")
        print(f"[FAIL] dataset load: {exc}")
        df = None

    if df is not None:
        for label, fn in checks(df):
            try:
                fn()
                print(f"[ok]   {label}")
            except Exception as exc:  # noqa: BLE001
                failures.append(f"{label}: {exc}")
                print(f"[FAIL] {label}: {exc}")

    print("\n== insights.json ==")
    try:
        insights = json.loads((ROOT / "outputs" / "insights.json").read_text(encoding="utf-8"))
        print(f"[ok]   {len(insights)} top-level keys: {', '.join(list(insights)[:6])} ...")
    except Exception as exc:  # noqa: BLE001
        failures.append(f"insights.json unreadable: {exc}")
        print(f"[FAIL] insights.json: {exc}")

    if failures:
        print("\nDeployment check FAILED:")
        for item in failures:
            print(f"  - {item}")
        return 1

    print("\nDeployment check passed - repository is ready to push.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
