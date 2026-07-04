"""
data_cleaning.py
----------------
Cleans and normalises the raw ERP export so the analytics modules can
rely on consistent types and no missing values.

Typical real-world ERP export problems handled here:
  * numeric columns arriving as text (thousand separators, blanks)
  * missing optional columns
  * inconsistent capitalisation in status fields
  * demand history stored as a string ("12;14;9;...")
"""

from __future__ import annotations

import numpy as np
import pandas as pd

NUMERIC_COLUMNS = [
    "current_stock", "reorder_point", "safety_stock", "monthly_demand",
    "lead_time_days", "unit_cost", "selling_price", "inventory_value",
    "margin_percentage", "stock_turnover_rate", "supplier_on_time_rate",
    "supplier_average_delay_days", "return_rate",
]

VALID_CRITICALITY = ["low", "medium", "high", "critical"]


def parse_demand_history(value) -> list[int]:
    """
    Parse a weekly demand history cell into a list of ints.
    Accepts "12;14;9", "12,14,9" or an actual list. Returns [] if unusable.
    """
    if isinstance(value, (list, tuple)):
        return [int(v) for v in value]
    if pd.isna(value):
        return []
    text = str(value).replace(",", ";")
    parts = [p.strip() for p in text.split(";") if p.strip()]
    try:
        return [int(float(p)) for p in parts]
    except ValueError:
        return []


def clean_data(df: pd.DataFrame) -> pd.DataFrame:
    """
    Return a cleaned copy of the DataFrame. Never mutates the input.
    """
    df = df.copy()

    # --- 1. Ensure optional columns exist -------------------------------
    defaults = {
        "brand": "Unknown",
        "delivery_status": "Unknown",
        "expected_delivery_date": "",
        "actual_delivery_date": "",
        "return_rate": 0.0,
        "refurbished_status": "New",
        "margin_percentage": np.nan,
        "inventory_value": np.nan,
        "stock_turnover_rate": np.nan,
    }
    for col, default in defaults.items():
        if col not in df.columns:
            df[col] = default

    # --- 2. Coerce numeric columns --------------------------------------
    for col in NUMERIC_COLUMNS:
        if col in df.columns:
            # Remove common formatting artefacts before converting.
            df[col] = (
                df[col].astype(str)
                .str.replace(" ", "", regex=False)
                .str.replace("€", "", regex=False)
            )
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # --- 3. Fill or derive missing numeric values -----------------------
    df["current_stock"] = df["current_stock"].fillna(0).clip(lower=0)
    df["safety_stock"] = df["safety_stock"].fillna(0).clip(lower=0)
    df["reorder_point"] = df["reorder_point"].fillna(df["safety_stock"] * 2)
    df["lead_time_days"] = df["lead_time_days"].fillna(14).clip(lower=1)
    df["monthly_demand"] = df["monthly_demand"].fillna(0).clip(lower=0)
    df["return_rate"] = df["return_rate"].fillna(0).clip(0, 100)

    # Derive inventory value and margin where missing.
    df["inventory_value"] = df["inventory_value"].fillna(
        df["current_stock"] * df["unit_cost"]
    )
    derived_margin = np.where(
        df["selling_price"] > 0,
        (df["selling_price"] - df["unit_cost"]) / df["selling_price"] * 100,
        0,
    )
    df["margin_percentage"] = df["margin_percentage"].fillna(
        pd.Series(derived_margin, index=df.index)
    ).round(1)

    # Derive turnover where missing (annual COGS / inventory value).
    annual_cogs = df["monthly_demand"] * 12 * df["unit_cost"]
    derived_turnover = np.where(
        df["inventory_value"] > 0, annual_cogs / df["inventory_value"], 0
    )
    df["stock_turnover_rate"] = df["stock_turnover_rate"].fillna(
        pd.Series(derived_turnover, index=df.index)
    ).round(2)

    # On-time rate may arrive as 96 (%) or 0.96 (fraction) — normalise to fraction.
    otr = df["supplier_on_time_rate"].fillna(0.9)
    df["supplier_on_time_rate"] = np.where(otr > 1.5, otr / 100, otr).clip(0, 1)
    df["supplier_average_delay_days"] = (
        df["supplier_average_delay_days"].fillna(0).clip(lower=0)
    )

    # --- 4. Normalise text columns --------------------------------------
    df["category"] = df["category"].astype(str).str.strip()
    df["supplier"] = df["supplier"].astype(str).str.strip()
    df["delivery_status"] = (
        df["delivery_status"].astype(str).str.strip().str.capitalize()
    )
    df["criticality_level"] = (
        df["criticality_level"].astype(str).str.strip().str.lower()
    )
    df.loc[~df["criticality_level"].isin(VALID_CRITICALITY), "criticality_level"] = "medium"

    # --- 5. Parse demand history into a real list column ----------------
    df["demand_history_list"] = df["weekly_demand_history"].apply(parse_demand_history)

    # Drop rows that cannot be analysed at all (no SKU or no cost).
    df = df.dropna(subset=["sku", "unit_cost"]).reset_index(drop=True)

    return df
