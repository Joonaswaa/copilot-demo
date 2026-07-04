"""
demand_forecasting.py
---------------------
Forecasts weekly demand for the next 4 weeks per SKU.

Method choice (deliberately simple and explainable):
  1. Exponential smoothing with a small trend component (Holt's method,
     implemented in a few lines) — the primary method.
  2. Moving average — used as a fallback for very short histories.

A placeholder shows where a proper ML model (e.g. scikit-learn gradient
boosting or a time-series library) could be plugged in later. In a real
supply chain setting, explainability usually beats a small accuracy gain,
which is why the simple methods come first.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

FORECAST_WEEKS = 4


def moving_average_forecast(history: list[int], weeks: int = FORECAST_WEEKS,
                            window: int = 4) -> list[float]:
    """Flat forecast: the mean of the last `window` observations."""
    if not history:
        return [0.0] * weeks
    window = min(window, len(history))
    level = float(np.mean(history[-window:]))
    return [round(level, 1)] * weeks


def exponential_smoothing_forecast(history: list[int],
                                   weeks: int = FORECAST_WEEKS,
                                   alpha: float = 0.4,
                                   beta: float = 0.2) -> list[float]:
    """
    Holt's linear (double) exponential smoothing.

    alpha: how quickly the level reacts to new data.
    beta:  how quickly the trend reacts to new data.
    The trend is damped slightly in the projection so a couple of strong
    weeks do not explode the 4-week forecast.
    """
    if len(history) < 4:
        return moving_average_forecast(history, weeks)

    level = float(history[0])
    trend = float(history[1] - history[0])

    for value in history[1:]:
        prev_level = level
        level = alpha * value + (1 - alpha) * (level + trend)
        trend = beta * (level - prev_level) + (1 - beta) * trend

    damping = 0.9
    forecast = []
    for step in range(1, weeks + 1):
        projected = level + trend * sum(damping ** i for i in range(1, step + 1))
        forecast.append(round(max(0.0, projected), 1))
    return forecast


def ml_forecast_placeholder(history: list[int], weeks: int = FORECAST_WEEKS) -> list[float]:
    """
    PLACEHOLDER for a machine-learning forecaster.

    In production this could be, for example:
      * sklearn.ensemble.GradientBoostingRegressor on lag features
        (t-1..t-8, week-of-month, promo flags), or
      * statsmodels SARIMAX / Prophet for seasonal series, or
      * a shared model trained across all SKUs with product features.

    Kept as a thin wrapper so the rest of the app does not need to change
    when a real model is added.
    """
    return exponential_smoothing_forecast(history, weeks)


def demand_volatility(history: list[int]) -> float:
    """
    Coefficient of variation of weekly demand (std / mean).
    0 = perfectly stable, >0.5 = very volatile. Used by risk scoring.
    """
    if len(history) < 2:
        return 0.0
    mean = float(np.mean(history))
    if mean == 0:
        return 0.0
    return round(float(np.std(history)) / mean, 3)


def add_forecasts(df: pd.DataFrame, method: str = "exponential") -> pd.DataFrame:
    """
    Add forecast columns to the cleaned DataFrame:
      * forecast_list            – list of 4 weekly values
      * forecasted_demand_next_4_weeks – readable "a; b; c; d" string
      * forecast_4wk_total       – sum over the horizon (used everywhere)
      * demand_volatility        – CV of the history
      * demand_trend_pct         – % change, last 4 weeks vs previous 4
    """
    df = df.copy()

    forecaster = {
        "moving_average": moving_average_forecast,
        "exponential": exponential_smoothing_forecast,
        "ml": ml_forecast_placeholder,
    }.get(method, exponential_smoothing_forecast)

    forecasts, totals, vols, trends = [], [], [], []
    for history in df["demand_history_list"]:
        fc = forecaster(history)
        forecasts.append(fc)
        totals.append(round(sum(fc), 1))
        vols.append(demand_volatility(history))

        if len(history) >= 8:
            prev = np.mean(history[-8:-4])
            recent = np.mean(history[-4:])
            trends.append(round((recent - prev) / prev * 100, 1) if prev > 0 else 0.0)
        else:
            trends.append(0.0)

    df["forecast_list"] = forecasts
    df["forecasted_demand_next_4_weeks"] = [
        "; ".join(f"{v:g}" for v in fc) for fc in forecasts
    ]
    df["forecast_4wk_total"] = totals
    df["demand_volatility"] = vols
    df["demand_trend_pct"] = trends
    return df
