"""
risk_scoring.py
---------------
Computes a composite 0–100 risk score per SKU plus stockout-risk flags.

The score is a weighted sum of six sub-scores, each normalised to 0–100.
Weights reflect business impact for a telecom operator: running out of a
fiber modem blocks installations (revenue + customer experience), which
is why stockout coverage and criticality dominate.

    stockout coverage   35 %   (weeks of stock vs demand + lead time)
    supplier risk       20 %   (on-time rate, average delay)
    demand volatility   15 %   (hard-to-predict demand)
    criticality         15 %   (business impact of a stockout)
    lead time           10 %   (long pipelines react slowly)
    margin & returns     5 %   (low margin / high returns erode value)

Every sub-score is kept explainable on purpose: a category manager should
be able to see *why* a product is red.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

WEIGHTS = {
    "stockout": 0.35,
    "supplier": 0.20,
    "volatility": 0.15,
    "criticality": 0.15,
    "lead_time": 0.10,
    "margin_returns": 0.05,
}

CRITICALITY_SCORE = {"low": 15, "medium": 40, "high": 70, "critical": 100}


def weeks_of_cover(row: pd.Series) -> float:
    """Current stock expressed in weeks of forecasted demand."""
    weekly = row["forecast_4wk_total"] / 4 if row["forecast_4wk_total"] > 0 else 0
    if weekly <= 0:
        return 99.0  # no demand -> stockout impossible (slow mover instead)
    return round(row["current_stock"] / weekly, 2)


def stockout_subscore(row: pd.Series) -> float:
    """
    100 = will run out before a replenishment could arrive.
    Compares weeks of cover against the supplier lead time (in weeks)
    plus a one-week ordering buffer.
    """
    cover = weeks_of_cover(row)
    lead_weeks = row["lead_time_days"] / 7 + 1
    if cover >= 2 * lead_weeks:
        return 0.0
    if cover <= 0:
        return 100.0
    return round(100 * (1 - cover / (2 * lead_weeks)), 1)


def supplier_subscore(row: pd.Series) -> float:
    """Blend of on-time rate (dominant) and average delay days."""
    otr_component = (1 - row["supplier_on_time_rate"]) * 100        # 0–100
    delay_component = min(row["supplier_average_delay_days"], 10) * 10
    return round(0.7 * otr_component + 0.3 * delay_component, 1)


def volatility_subscore(row: pd.Series) -> float:
    """CV of 0.5+ counts as fully volatile."""
    return round(min(row["demand_volatility"] / 0.5, 1.0) * 100, 1)


def lead_time_subscore(row: pd.Series) -> float:
    """35+ day lead times count as maximum pipeline risk."""
    return round(min(row["lead_time_days"] / 35, 1.0) * 100, 1)


def margin_returns_subscore(row: pd.Series) -> float:
    """Low margin and high return rate both erode product value."""
    margin_component = max(0.0, (25 - row["margin_percentage"]) / 25) * 100
    returns_component = min(row["return_rate"] / 10, 1.0) * 100
    return round(0.5 * margin_component + 0.5 * returns_component, 1)


def add_risk_scores(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add risk columns to the DataFrame:
      weeks_of_cover, stockout_risk (subscore), supplier_risk,
      risk_score (0–100), risk_level (Low/Medium/High/Critical),
      stockout_flag (bool: needs action before lead time elapses).
    """
    df = df.copy()

    df["weeks_of_cover"] = df.apply(weeks_of_cover, axis=1)
    df["stockout_risk"] = df.apply(stockout_subscore, axis=1)
    df["supplier_risk"] = df.apply(supplier_subscore, axis=1)

    vol = df.apply(volatility_subscore, axis=1)
    crit = df["criticality_level"].map(CRITICALITY_SCORE).fillna(40)
    lead = df.apply(lead_time_subscore, axis=1)
    marg = df.apply(margin_returns_subscore, axis=1)

    df["risk_score"] = (
        WEIGHTS["stockout"] * df["stockout_risk"]
        + WEIGHTS["supplier"] * df["supplier_risk"]
        + WEIGHTS["volatility"] * vol
        + WEIGHTS["criticality"] * crit
        + WEIGHTS["lead_time"] * lead
        + WEIGHTS["margin_returns"] * marg
    ).round(1)

    df["risk_level"] = pd.cut(
        df["risk_score"],
        bins=[-1, 30, 50, 70, 101],
        labels=["Low", "Medium", "High", "Critical"],
    ).astype(str)

    # Actionable stockout flag: below reorder point (matches dashboard KPI).
    df["stockout_flag"] = df["current_stock"] < df["reorder_point"]

    return df
