"""
supplier_analysis.py
--------------------
Aggregates SKU-level data into a supplier scorecard:

  * on-time delivery rate
  * average delay in days
  * number of currently delayed deliveries
  * inventory value and number of SKUs sourced from the supplier
  * affected product categories
  * a 0–100 supplier risk score and Low/Medium/High risk level

Used by the Supplier performance dashboard page, the AI Copilot panel
and the weekly report.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def supplier_scorecard(df: pd.DataFrame) -> pd.DataFrame:
    """Return one row per supplier with aggregated KPIs, sorted worst-first."""
    grouped = df.groupby("supplier")

    scorecard = grouped.agg(
        skus=("sku", "count"),
        on_time_rate=("supplier_on_time_rate", "mean"),
        avg_delay_days=("supplier_average_delay_days", "mean"),
        inventory_value=("inventory_value", "sum"),
    )

    scorecard["delayed_deliveries"] = grouped.apply(
        lambda g: int((g["delivery_status"] == "Delayed").sum()),
        include_groups=False,
    )
    scorecard["categories"] = grouped["category"].apply(
        lambda s: ", ".join(sorted(s.unique()))
    )
    # Highest-criticality product served — a weak supplier matters more
    # when it delivers installation-critical items.
    crit_rank = {"low": 0, "medium": 1, "high": 2, "critical": 3}
    scorecard["max_criticality"] = grouped["criticality_level"].apply(
        lambda s: s.map(crit_rank).max()
    )

    # Supplier risk score: mostly reliability, partly current delays,
    # partly what is at stake (criticality of sourced products).
    otr_risk = (1 - scorecard["on_time_rate"]) * 100
    delay_risk = scorecard["avg_delay_days"].clip(upper=10) * 10
    open_delay_risk = (scorecard["delayed_deliveries"].clip(upper=5)) * 20
    stake = scorecard["max_criticality"] / 3 * 100

    scorecard["supplier_risk_score"] = (
        0.45 * otr_risk + 0.20 * delay_risk + 0.20 * open_delay_risk + 0.15 * stake
    ).round(1)

    scorecard["risk_level"] = pd.cut(
        scorecard["supplier_risk_score"],
        bins=[-1, 25, 50, 101],
        labels=["Low", "Medium", "High"],
    ).astype(str)

    scorecard["on_time_rate"] = (scorecard["on_time_rate"] * 100).round(1)
    scorecard["avg_delay_days"] = scorecard["avg_delay_days"].round(1)
    scorecard["inventory_value"] = scorecard["inventory_value"].round(0)

    return (
        scorecard.sort_values("supplier_risk_score", ascending=False)
        .reset_index()
        .drop(columns=["max_criticality"])
    )


def supplier_warnings(scorecard: pd.DataFrame,
                      on_time_threshold: float = 88.0,
                      delay_threshold: float = 3.0) -> list[str]:
    """Plain-language warnings for the Copilot panel and weekly report."""
    warnings = []
    for _, row in scorecard.iterrows():
        issues = []
        if row["on_time_rate"] < on_time_threshold:
            issues.append(f"on-time rate is only {row['on_time_rate']:.0f}%")
        if row["avg_delay_days"] > delay_threshold:
            issues.append(f"average delay is {row['avg_delay_days']:.1f} days")
        if row["delayed_deliveries"] >= 2:
            issues.append(f"{int(row['delayed_deliveries'])} deliveries are currently delayed")
        if issues:
            warnings.append(
                f"{row['supplier']}: " + ", ".join(issues)
                + f". Affected categories: {row['categories']}."
            )
    return warnings
