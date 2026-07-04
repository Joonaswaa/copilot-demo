"""
slow_moving_analysis.py
-----------------------
Finds products where capital is tied up in inventory that is not selling:

  * low stock turnover
  * many weeks of cover (stock far above what demand justifies)
  * flat or declining recent demand

Each flagged product gets a suggested action (campaign, discount,
bundle, channel move or stop reordering), which the dashboard and the
weekly report surface directly.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

# Thresholds — deliberately simple and visible so they can be tuned
# together with the business.
TURNOVER_THRESHOLD = 4.0      # annual turns below this = slow
COVER_THRESHOLD_WEEKS = 12.0  # more than ~a quarter of stock on hand
TREND_THRESHOLD_PCT = -5.0    # demand declining


def find_slow_movers(df: pd.DataFrame) -> pd.DataFrame:
    """
    Return slow-moving SKUs with tied-up capital and a suggested action,
    sorted by tied capital (largest first).

    A product is flagged when at least two of the three conditions hold:
    low turnover, excessive weeks of cover, declining demand. Requiring
    two signals avoids flagging healthy strategic buffer stock.
    """
    df = df.copy()

    low_turnover = df["stock_turnover_rate"] < TURNOVER_THRESHOLD
    high_cover = df["weeks_of_cover"] > COVER_THRESHOLD_WEEKS
    declining = df["demand_trend_pct"] < TREND_THRESHOLD_PCT

    signal_count = (
        low_turnover.astype(int) + high_cover.astype(int) + declining.astype(int)
    )
    slow = df[signal_count >= 2].copy()
    if slow.empty:
        return pd.DataFrame(columns=[
            "sku", "product_name", "category", "current_stock",
            "inventory_value", "stock_turnover_rate", "weeks_of_cover",
            "demand_trend_pct", "suggested_action",
        ])

    # Excess stock beyond ~8 weeks of demand is what a campaign should clear.
    weekly = slow["forecast_4wk_total"] / 4
    slow["excess_units"] = (
        (slow["current_stock"] - weekly * 8).clip(lower=0).round(0).astype(int)
    )
    slow["tied_capital"] = (slow["excess_units"] * slow["unit_cost"]).round(2)

    slow["suggested_action"] = slow.apply(_suggest_action, axis=1)

    return slow[[
        "sku", "product_name", "category", "current_stock", "inventory_value",
        "tied_capital", "excess_units", "stock_turnover_rate",
        "weeks_of_cover", "demand_trend_pct", "suggested_action",
    ]].sort_values("tied_capital", ascending=False).reset_index(drop=True)


def _suggest_action(row: pd.Series) -> str:
    """Rule-based action suggestion in plain business language."""
    if row["margin_percentage"] >= 25 and row["demand_trend_pct"] < -10:
        return ("Run a price campaign: margin allows a discount and demand "
                "is clearly declining.")
    if row["category"] == "Returns and refurbished":
        return ("Push through the outlet/refurb channel with a visible "
                "price cut; refurb value erodes fast.")
    if row["category"] == "Accessories":
        return ("Bundle with high-demand devices (e.g. attach to phone "
                "sales) to clear excess units.")
    if row["weeks_of_cover"] > 26:
        return ("Stop reordering and plan a clearance campaign — stock "
                "covers over half a year of demand.")
    return ("Include in next campaign planning round and pause "
            "replenishment until cover normalises.")


def slow_mover_summary(slow: pd.DataFrame) -> dict:
    """Small summary dict for KPIs and the weekly report."""
    if slow.empty:
        return {"count": 0, "tied_capital": 0.0, "top_product": None}
    return {
        "count": int(len(slow)),
        "tied_capital": float(slow["tied_capital"].sum().round(2)),
        "top_product": str(slow.iloc[0]["product_name"]),
    }
