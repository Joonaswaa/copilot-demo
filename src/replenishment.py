"""
replenishment.py
----------------
Recommends purchase quantities per SKU using an order-up-to logic:

    target level = demand during (lead time + review period) + safety stock
    order qty    = target level - current stock - (assumed inbound if a
                   delivery is already in transit)

The review period is one week (the report cadence). Critical products get
an extra safety uplift because a stockout there blocks installations.

The output is a purchase order proposal table a buyer could act on:
quantity, cost, reason and priority.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

REVIEW_PERIOD_DAYS = 7

# Extra buffer on top of safety stock, by criticality.
CRITICALITY_UPLIFT = {"low": 0.0, "medium": 0.05, "high": 0.10, "critical": 0.20}


def recommend_purchases(df: pd.DataFrame) -> pd.DataFrame:
    """
    Return a DataFrame of recommended purchase orders (one row per SKU
    that needs replenishment), sorted by priority.
    """
    df = df.copy()

    weekly_demand = df["forecast_4wk_total"] / 4
    horizon_weeks = (df["lead_time_days"] + REVIEW_PERIOD_DAYS) / 7
    uplift = df["criticality_level"].map(CRITICALITY_UPLIFT).fillna(0.05)

    target_level = (
        weekly_demand * horizon_weeks
        + df["safety_stock"] * (1 + uplift)
    )

    # If a PO is already in transit, assume roughly 4 weeks of demand
    # is inbound (a simplification — a real system would read PO lines).
    inbound = np.where(
        df["delivery_status"].isin(["In transit"]),
        weekly_demand * 4,
        0,
    )

    raw_qty = target_level - df["current_stock"] - inbound
    df["recommended_qty"] = np.ceil(raw_qty.clip(lower=0)).astype(int)

    orders = df[df["recommended_qty"] > 0].copy()
    if orders.empty:
        return pd.DataFrame(columns=[
            "sku", "product_name", "category", "supplier", "recommended_qty",
            "estimated_cost", "priority", "reason",
        ])

    orders["estimated_cost"] = (orders["recommended_qty"] * orders["unit_cost"]).round(2)

    # Priority: urgent if the stockout flag is up, high for high risk score,
    # normal otherwise.
    orders["priority"] = np.select(
        [
            orders["stockout_flag"] & orders["criticality_level"].isin(["critical", "high"]),
            orders["stockout_flag"],
            orders["risk_score"] >= 50,
        ],
        ["Urgent", "High", "Medium"],
        default="Normal",
    )

    orders["reason"] = orders.apply(_build_reason, axis=1)

    priority_rank = {"Urgent": 0, "High": 1, "Medium": 2, "Normal": 3}
    orders["_rank"] = orders["priority"].map(priority_rank)
    orders = orders.sort_values(["_rank", "risk_score"], ascending=[True, False])

    return orders[[
        "sku", "product_name", "category", "supplier", "current_stock",
        "recommended_qty", "estimated_cost", "priority", "reason",
        "lead_time_days", "risk_score",
    ]].reset_index(drop=True)


def _build_reason(row: pd.Series) -> str:
    """Plain-language explanation of why the order is recommended."""
    parts = []
    if row["stockout_flag"]:
        parts.append(
            f"stock covers ~{row['weeks_of_cover']:.1f} weeks but lead time is "
            f"{int(row['lead_time_days'])} days"
        )
    if row["current_stock"] <= row["reorder_point"]:
        parts.append("stock is at or below the reorder point")
    if row["demand_trend_pct"] > 10:
        parts.append(f"demand is up {row['demand_trend_pct']:.0f}% over 4 weeks")
    if row["criticality_level"] == "critical":
        parts.append("product is installation-critical")
    if not parts:
        parts.append("stock is below the order-up-to target level")
    return "Recommended because " + " and ".join(parts) + "."
