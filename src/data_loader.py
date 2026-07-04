"""
data_loader.py
--------------
Loads the ERP export file (CSV or Excel) into a pandas DataFrame and
validates that it contains the columns the analytics modules need.

Design goal: fail early with a clear, human-readable message instead of
crashing somewhere deep in the analysis.
"""

from __future__ import annotations

import io
from pathlib import Path

import pandas as pd

# Columns the analytics pipeline requires to run.
REQUIRED_COLUMNS = [
    "sku",
    "product_name",
    "category",
    "supplier",
    "current_stock",
    "reorder_point",
    "safety_stock",
    "monthly_demand",
    "weekly_demand_history",
    "lead_time_days",
    "unit_cost",
    "selling_price",
    "supplier_on_time_rate",
    "supplier_average_delay_days",
    "criticality_level",
]

# Columns that are nice to have; missing ones are filled with defaults
# by data_cleaning.py.
OPTIONAL_COLUMNS = [
    "brand",
    "inventory_value",
    "margin_percentage",
    "stock_turnover_rate",
    "delivery_status",
    "expected_delivery_date",
    "actual_delivery_date",
    "return_rate",
    "refurbished_status",
    "risk_score",
    "forecasted_demand_next_4_weeks",
]


class DataValidationError(Exception):
    """Raised when the uploaded file cannot be used for analysis."""


def load_file(source) -> pd.DataFrame:
    """
    Load a CSV or Excel file into a DataFrame.

    `source` can be:
      * a file path (str / Path), or
      * a file-like object (e.g. a Streamlit UploadedFile).

    The file type is decided by the file extension (.csv / .xlsx / .xls).
    """
    name = getattr(source, "name", str(source)).lower()

    if name.endswith(".csv"):
        df = pd.read_csv(source)
    elif name.endswith((".xlsx", ".xls")):
        df = pd.read_excel(source)  # requires openpyxl for .xlsx
    else:
        raise DataValidationError(
            "Unsupported file type. Please upload a .csv or .xlsx file."
        )

    validate_columns(df)
    return df


def validate_columns(df: pd.DataFrame) -> None:
    """Raise DataValidationError listing any missing required columns."""
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise DataValidationError(
            "The file is missing required columns: "
            + ", ".join(missing)
            + ". Compare your export with data/sample_telecom_supply_chain_data.csv."
        )
    if df.empty:
        raise DataValidationError("The file contains no data rows.")


def load_sample_data(path: str | Path = "data/sample_telecom_supply_chain_data.csv") -> pd.DataFrame:
    """Load the bundled sample dataset (regenerating it if missing)."""
    path = Path(path)
    if not path.exists():
        # Lazy import to avoid a hard dependency when the file exists.
        from src.data_generator import save_sample_csv
        save_sample_csv(path)
    return load_file(path)
