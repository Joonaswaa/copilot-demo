"""Shared KPI mask helpers for dashboard and reports."""

from __future__ import annotations

import pandas as pd


def stockout_mask(df: pd.DataFrame) -> pd.Series:
    """True when on-hand stock is below the reorder point."""
    return df["current_stock"] < df["reorder_point"]


def high_risk_product_mask(df: pd.DataFrame) -> pd.Series:
    """Stockout risk on a high- or critical-impact SKU."""
    return stockout_mask(df) & df["criticality_level"].isin(["high", "critical"])
