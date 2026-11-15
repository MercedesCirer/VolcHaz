"""Typical Meteorological Year (TMY) selection.

This module reproduces the selection logic of the original
``calculate_tmy_ult.py`` workflow while preserving the public API used by the
current volcanic_toolbox preprocessing workflow.

For each calendar month:

1. The original sub-daily u/v series is reduced to daily vector means.
2. Wind speed and direction are calculated from the daily-mean u/v components.
   The direction convention used for TMY selection reproduces the original
   script: mathematical direction TO which the wind vector points, in degrees
   counter-clockwise from East, wrapped to [0, 360).
3. Long-term and year-specific empirical histogram CDFs are calculated for wind
   speed and direction.
4. Finkelstein-Schafer (FS) statistics are calculated for every candidate year.
5. A weighted FS score is computed:
       weighted_fs = speed_weight * fs_speed
                   + direction_weight * fs_direction
6. The ``number_of_fs_candidates`` years with the lowest weighted FS score are
   retained (5 by default, matching the original implementation).
7. For those candidates only, RMSD is calculated relative to the long-term
   monthly mean of each parameter.
8. A weighted RMSD score is computed using the same speed/direction weights.
9. The candidate with the lowest weighted RMSD is selected as the representative
   source month.
10. The final TMY is assembled from the ORIGINAL sub-daily records belonging to
    the twelve selected source months, matching the role of ``yearraw`` in the
    original script.

Notes
-----
The original implementation used ``np.histogram(data, bins=<integer>)``
independently for each long-term and candidate dataset. Therefore, histogram
edges were not forced to be identical between the compared samples. This module
retains that behavior intentionally in order to reproduce the original method.

The timestamp-based implementation used here replaces the original positional
``index // 4`` daily grouping. For ERA5 records sampled four times per day this
is equivalent in intent, while remaining safe for missing records and leap
years.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np
import pandas as pd

from .wind import add_calendar_columns, mathematical_direction, wind_speed


@dataclass(frozen=True)
class TMYConfig:
    """Configuration for the original two-stage TMY selection method."""

    speed_weight: float = 0.3
    direction_weight: float = 0.7
    speed_bins: int = 28
    direction_bins: int = 28
    use_daily_means: bool = True
    number_of_fs_candidates: int = 5

    def __post_init__(self) -> None:
        if self.speed_weight < 0 or self.direction_weight < 0:
            raise ValueError("weights cannot be negative")
        total = self.speed_weight + self.direction_weight
        if not np.isclose(total, 1.0):
            raise ValueError("speed_weight + direction_weight must equal 1")
        if self.speed_bins < 2 or self.direction_bins < 2:
            raise ValueError("at least two bins are required")
        if self.number_of_fs_candidates <= 0:
            raise ValueError("number_of_fs_candidates must be greater than zero")


def empirical_histogram_cdf(values, bins: int) -> np.ndarray:
    """Histogram-based CDF, matching the original ``calculate_cdf`` logic."""
    values = np.asarray(values, dtype=float)
    values = values[np.isfinite(values)]
    if values.size == 0:
        raise ValueError("CDF input cannot be empty")
    counts, _ = np.histogram(values, bins=int(bins))
    if counts.sum() == 0:
        raise ValueError("Histogram contains no observations")
    return np.cumsum(counts) / counts.sum()


def finkelstein_schafer(cdf_reference, cdf_candidate) -> float:
    """Mean absolute difference between two binned empirical CDFs."""
    ref = np.asarray(cdf_reference, dtype=float)
    cand = np.asarray(cdf_candidate, dtype=float)
    if ref.shape != cand.shape:
        raise ValueError("CDF arrays must have the same shape")
    return float(np.mean(np.abs(ref - cand)))


def root_mean_square_deviation_from_long_term_mean(values, long_term_mean: float) -> float:
    """RMSD used by the original TMY script."""
    values = np.asarray(values, dtype=float)
    values = values[np.isfinite(values)]
    if values.size == 0:
        raise ValueError("RMSD input cannot be empty")
    return float(np.sqrt(np.mean((values - float(long_term_mean)) ** 2)))


def _daily_mean_uv(data: pd.DataFrame) -> pd.DataFrame:
    """Average u/v by day, reproducing the original 4-to-1 reduction."""
    required = {"datetime", "u_m_s", "v_m_s"}
    missing = required.difference(data.columns)
    if missing:
        raise KeyError("TMY data are missing required columns: %s" % sorted(missing))

    frame = data.copy()
    frame["datetime"] = pd.to_datetime(frame["datetime"], utc=True, errors="coerce")
    frame["u_m_s"] = pd.to_numeric(frame["u_m_s"], errors="coerce")
    frame["v_m_s"] = pd.to_numeric(frame["v_m_s"], errors="coerce")
    frame = frame.dropna(subset=["datetime", "u_m_s", "v_m_s"])
    frame["date"] = frame["datetime"].dt.normalize()

    grouping = ["date"]
    if "pressure_level_hpa" in frame.columns:
        grouping.append("pressure_level_hpa")

    aggregation = {
        "u_m_s": "mean",
        "v_m_s": "mean",
        "datetime": "min",
    }
    if "latitude" in frame.columns:
        aggregation["latitude"] = "first"
    if "longitude" in frame.columns:
        aggregation["longitude"] = "first"

    return frame.groupby(grouping, as_index=False).agg(aggregation)


def prepare_tmy_data(data: pd.DataFrame, config: Optional[TMYConfig] = None) -> pd.DataFrame:
    """Prepare the meteorological series used for TMY month selection."""
    config = config or TMYConfig()

    if config.use_daily_means:
        result = _daily_mean_uv(data)
    else:
        required = {"datetime", "u_m_s", "v_m_s"}
        missing = required.difference(data.columns)
        if missing:
            raise KeyError("TMY data are missing required columns: %s" % sorted(missing))
        result = data.copy()
        result["datetime"] = pd.to_datetime(result["datetime"], utc=True, errors="coerce")
        result = result.dropna(subset=["datetime", "u_m_s", "v_m_s"])

    # Original convention:
    # speed = sqrt(u**2 + v**2)
    # direction = degrees(arctan2(v, u)) % 360
    result["wind_speed_m_s"] = wind_speed(result["u_m_s"], result["v_m_s"])
    result["wind_direction_deg"] = mathematical_direction(result["u_m_s"], result["v_m_s"])

    return add_calendar_columns(result)


def calculate_fs_table(data: pd.DataFrame, config: Optional[TMYConfig] = None) -> pd.DataFrame:
    """Calculate FS and RMSD diagnostics for every month/year candidate."""
    config = config or TMYConfig()
    prepared = prepare_tmy_data(data, config=config)
    all_months = []

    for month, month_data in prepared.groupby("month"):
        month = int(month)

        speed_ref = empirical_histogram_cdf(month_data["wind_speed_m_s"], config.speed_bins)
        direction_ref = empirical_histogram_cdf(month_data["wind_direction_deg"], config.direction_bins)

        month_rows = []
        for year, candidate in month_data.groupby("year"):
            year = int(year)
            speed_cdf = empirical_histogram_cdf(candidate["wind_speed_m_s"], config.speed_bins)
            direction_cdf = empirical_histogram_cdf(candidate["wind_direction_deg"], config.direction_bins)

            fs_speed = finkelstein_schafer(speed_ref, speed_cdf)
            fs_direction = finkelstein_schafer(direction_ref, direction_cdf)
            weighted_fs = (
                config.speed_weight * fs_speed
                + config.direction_weight * fs_direction
            )

            month_rows.append({
                "month": month,
                "candidate_year": year,
                "fs_speed": fs_speed,
                "fs_direction": fs_direction,
                "weighted_fs": weighted_fs,
                "fs_rank": np.nan,
                "is_fs_candidate": False,
                "rmsd_speed": np.nan,
                "rmsd_direction": np.nan,
                "weighted_rmsd": np.nan,
                "selected": False,
                "n_observations": int(len(candidate)),
            })

        month_table = pd.DataFrame(month_rows).sort_values(
            ["weighted_fs", "candidate_year"]
        ).reset_index(drop=True)
        month_table["fs_rank"] = np.arange(1, len(month_table) + 1)

        n_candidates = min(config.number_of_fs_candidates, len(month_table))
        candidate_years = (
            month_table.iloc[:n_candidates]["candidate_year"].astype(int).tolist()
        )
        month_table.loc[
            month_table["candidate_year"].isin(candidate_years),
            "is_fs_candidate",
        ] = True

        speed_lt_mean = float(month_data["wind_speed_m_s"].mean())
        direction_lt_mean = float(month_data["wind_direction_deg"].mean())

        for candidate_year in candidate_years:
            candidate = month_data.loc[month_data["year"] == candidate_year]

            rmsd_speed = root_mean_square_deviation_from_long_term_mean(
                candidate["wind_speed_m_s"], speed_lt_mean
            )
            rmsd_direction = root_mean_square_deviation_from_long_term_mean(
                candidate["wind_direction_deg"], direction_lt_mean
            )
            weighted_rmsd = (
                config.speed_weight * rmsd_speed
                + config.direction_weight * rmsd_direction
            )

            mask = month_table["candidate_year"] == candidate_year
            month_table.loc[mask, "rmsd_speed"] = rmsd_speed
            month_table.loc[mask, "rmsd_direction"] = rmsd_direction
            month_table.loc[mask, "weighted_rmsd"] = weighted_rmsd

        rmsd_candidates = month_table.loc[
            month_table["is_fs_candidate"]
        ].sort_values(["weighted_rmsd", "candidate_year"])

        if rmsd_candidates.empty:
            raise RuntimeError(f"No RMSD candidates available for month {month}")

        selected_year = int(rmsd_candidates.iloc[0]["candidate_year"])
        month_table.loc[
            month_table["candidate_year"] == selected_year,
            "selected",
        ] = True

        all_months.append(month_table)

    if not all_months:
        raise ValueError("No TMY candidate months could be evaluated")

    return pd.concat(all_months, ignore_index=True).sort_values(
        ["month", "fs_rank", "candidate_year"]
    ).reset_index(drop=True)


def select_typical_months(fs_table: pd.DataFrame) -> pd.DataFrame:
    """Return the final month/year selections after the FS -> RMSD procedure."""
    required = {
        "month",
        "candidate_year",
        "weighted_fs",
        "fs_rank",
        "is_fs_candidate",
        "rmsd_speed",
        "rmsd_direction",
        "weighted_rmsd",
        "selected",
    }
    missing = required.difference(fs_table.columns)
    if missing:
        raise KeyError("Missing TMY selection columns: %s" % sorted(missing))

    selected = fs_table.loc[fs_table["selected"].astype(bool)].copy()
    if selected.empty:
        raise ValueError("No months were marked as selected")

    duplicated = selected["month"].duplicated(keep=False)
    if duplicated.any():
        months = sorted(selected.loc[duplicated, "month"].astype(int).unique().tolist())
        raise ValueError("More than one selected year found for months: %s" % months)

    selected = selected.rename(columns={"candidate_year": "selected_year"})
    columns = [
        "month",
        "selected_year",
        "weighted_fs",
        "fs_rank",
        "rmsd_speed",
        "rmsd_direction",
        "weighted_rmsd",
        "n_observations",
    ]
    return selected[columns].sort_values("month").reset_index(drop=True)


def build_typical_meteorological_year(
    data: pd.DataFrame,
    selected_months: pd.DataFrame,
    synthetic_year: int = 2001,
) -> pd.DataFrame:
    """Build the TMY from ORIGINAL sub-daily records of selected source months."""
    required = {"datetime", "u_m_s", "v_m_s"}
    missing = required.difference(data.columns)
    if missing:
        raise KeyError("TMY data are missing required columns: %s" % sorted(missing))

    raw = data.copy()
    raw["datetime"] = pd.to_datetime(raw["datetime"], utc=True, errors="coerce")
    raw = raw.dropna(subset=["datetime", "u_m_s", "v_m_s"])
    raw = add_calendar_columns(raw)

    # Keep the same original convention in the saved TMY table.
    raw["wind_speed_m_s"] = wind_speed(raw["u_m_s"], raw["v_m_s"])
    raw["wind_direction_deg"] = mathematical_direction(raw["u_m_s"], raw["v_m_s"])

    pieces = []
    for row in selected_months.itertuples(index=False):
        month = int(row.month)
        source_year = int(row.selected_year)

        selected = raw.loc[
            (raw["month"] == month) & (raw["year"] == source_year)
        ].copy()

        if selected.empty:
            raise ValueError(
                f"Selected TMY source month {month:02d}/{source_year} contains no records"
            )

        selected["source_year"] = source_year
        selected["sampling_method"] = "typical_meteorological_year"

        original = pd.to_datetime(selected["datetime"], utc=True)
        safe_day = np.minimum(original.dt.day, 28)
        selected["tmy_datetime"] = pd.to_datetime(
            {
                "year": np.full(len(selected), synthetic_year),
                "month": original.dt.month,
                "day": safe_day,
                "hour": original.dt.hour,
            },
            utc=True,
        )
        pieces.append(selected)

    if not pieces:
        raise ValueError("No TMY months could be built")

    result = pd.concat(pieces, ignore_index=True)
    sort_columns = ["tmy_datetime"]
    if "pressure_level_hpa" in result.columns:
        sort_columns.append("pressure_level_hpa")

    return result.sort_values(sort_columns).reset_index(drop=True)
