"""Wind vector calculations and temporal aggregation."""

from __future__ import annotations
import numpy as np
import pandas as pd


def wind_speed(u, v):
    return np.hypot(u, v)


def meteorological_direction(u, v):
    """Direction FROM which wind blows, degrees clockwise from north."""
    return (np.degrees(np.arctan2(-np.asarray(u), -np.asarray(v))) + 360) % 360


def mathematical_direction(u, v):
    """Direction TO which wind blows, degrees counter-clockwise from east."""
    return (np.degrees(np.arctan2(np.asarray(v), np.asarray(u))) + 360) % 360


def add_wind_components(
    data: pd.DataFrame,
    u_column: str = "u_m_s",
    v_column: str = "v_m_s",
) -> pd.DataFrame:
    required = {u_column, v_column}
    missing = required.difference(data.columns)
    if missing:
        raise KeyError("Missing columns: %s" % sorted(missing))
    result = data.copy()
    result["wind_speed_m_s"] = wind_speed(result[u_column], result[v_column])
    result["wind_direction_deg"] = meteorological_direction(
        result[u_column], result[v_column]
    )
    return result


def add_calendar_columns(data: pd.DataFrame) -> pd.DataFrame:
    if "datetime" not in data:
        raise KeyError("datetime column is required")
    result = data.copy()
    dt = pd.to_datetime(result["datetime"], utc=True)
    result["year"] = dt.dt.year
    result["month"] = dt.dt.month
    result["day"] = dt.dt.day
    result["hour"] = dt.dt.hour
    return result


def daily_vector_means(data: pd.DataFrame) -> pd.DataFrame:
    """Average u and v by day, then recompute speed/direction.

    This avoids directly averaging circular directions.
    """
    result = add_calendar_columns(data)
    grouping = ["year", "month", "day"]
    if "pressure_level_hpa" in result:
        grouping.append("pressure_level_hpa")
    grouped = result.groupby(grouping, as_index=False).agg(
        u_m_s=("u_m_s", "mean"),
        v_m_s=("v_m_s", "mean"),
        datetime=("datetime", "min"),
        latitude=("latitude", "first"),
        longitude=("longitude", "first"),
    )
    return add_wind_components(grouped)
