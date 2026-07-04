"""
data_validation.py
------------------
Row-level ERP export validation for the RPA workflow.
Column presence is checked by data_loader.validate_columns().
"""

from __future__ import annotations

import pandas as pd

from src.data_cleaning import parse_demand_history
from src.data_loader import REQUIRED_COLUMNS, validate_columns

VALID_CRITICALITY = {"low", "medium", "high", "critical"}
MAX_ERRORS = 10


class ErpValidationError(Exception):
    """Raised when ERP data fails validation."""

    def __init__(self, errors: list[str]):
        self.errors = errors
        preview = "; ".join(errors[:MAX_ERRORS])
        extra = f" (+{len(errors) - MAX_ERRORS} more)" if len(errors) > MAX_ERRORS else ""
        super().__init__(preview + extra)


def validate_erp_dataframe(df: pd.DataFrame) -> list[str]:
    """
    Validate loaded ERP data. Returns a list of error messages (empty = OK).
    """
    errors: list[str] = []

    try:
        validate_columns(df)
    except Exception as exc:
        errors.append(str(exc))
        return errors

    if df.empty:
        errors.append("The file contains no data rows.")
        return errors

    for idx, row in df.iterrows():
        sku = row.get("sku", f"row {idx}")
        prefix = f"SKU {sku}"

        hist = parse_demand_history(row.get("weekly_demand_history"))
        if len(hist) != 12:
            errors.append(
                f"{prefix}: weekly_demand_history must contain exactly 12 "
                f"values (found {len(hist)})"
            )

        for col in ("current_stock", "reorder_point", "safety_stock", "monthly_demand"):
            val = row.get(col)
            if pd.isna(val):
                errors.append(f"{prefix}: {col} is missing")
            elif float(val) < 0:
                errors.append(f"{prefix}: {col} must be >= 0 (got {val})")

        lt = row.get("lead_time_days")
        if pd.isna(lt) or float(lt) < 1:
            errors.append(f"{prefix}: lead_time_days must be >= 1 (got {lt})")

        unit_cost = row.get("unit_cost")
        selling = row.get("selling_price")
        if not pd.isna(unit_cost) and not pd.isna(selling):
            if float(selling) <= float(unit_cost):
                errors.append(
                    f"{prefix}: selling_price must be > unit_cost "
                    f"({selling} <= {unit_cost})"
                )

        otr = row.get("supplier_on_time_rate")
        if not pd.isna(otr):
            rate = float(otr)
            if rate > 1.5:
                rate /= 100
            if rate < 0 or rate > 1:
                errors.append(
                    f"{prefix}: supplier_on_time_rate must be between 0 and 1 "
                    f"(got {row.get('supplier_on_time_rate')})"
                )

        crit = str(row.get("criticality_level", "")).strip().lower()
        if crit not in VALID_CRITICALITY:
            errors.append(
                f"{prefix}: criticality_level must be one of "
                f"{sorted(VALID_CRITICALITY)} (got {row.get('criticality_level')})"
            )

        if len(errors) >= MAX_ERRORS:
            break

    return errors
