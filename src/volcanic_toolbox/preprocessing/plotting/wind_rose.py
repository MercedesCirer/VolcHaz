"""Monthly and annual wind-rose plots from u/v meteorological tables."""

from __future__ import annotations

from pathlib import Path
from typing import Optional, Sequence, Tuple, Union
import math

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


def prepare_daily_wind(
    data: pd.DataFrame,
    datetime_column: str = "datetime",
    u_column: str = "u_m_s",
    v_column: str = "v_m_s",
    direction_convention: str = "from",
) -> pd.DataFrame:
    """Average u/v by day, then calculate daily vector speed and direction."""
    missing = {datetime_column, u_column, v_column}.difference(data.columns)
    if missing:
        raise KeyError(f"Wind table is missing columns: {sorted(missing)}")
    frame = data[[datetime_column, u_column, v_column]].copy()
    frame[datetime_column] = pd.to_datetime(frame[datetime_column], errors="coerce")
    frame[u_column] = pd.to_numeric(frame[u_column], errors="coerce")
    frame[v_column] = pd.to_numeric(frame[v_column], errors="coerce")
    frame = frame.dropna()
    frame["date"] = frame[datetime_column].dt.normalize()
    daily = frame.groupby("date", as_index=False).agg(
        u_m_s=(u_column, "mean"), v_m_s=(v_column, "mean"), n_records=(u_column, "size")
    )
    daily["wind_speed_m_s"] = np.hypot(daily["u_m_s"], daily["v_m_s"])
    direction_to = (
        90.0 - np.degrees(np.arctan2(daily["v_m_s"], daily["u_m_s"]))
    ) % 360.0
    if direction_convention == "to":
        daily["wind_direction_deg"] = direction_to
    elif direction_convention == "from":
        daily["wind_direction_deg"] = (direction_to + 180.0) % 360.0
    else:
        raise ValueError("direction_convention must be 'from' or 'to'")
    daily["month"] = daily["date"].dt.month
    return daily


def plot_monthly_wind_rose_mosaic(
    data: pd.DataFrame,
    output_path: Optional[Union[str, Path]] = None,
    direction_convention: str = "from",
    use_daily_vector_means: bool = True,
    speed_bins: int = 5,
    direction_bins: int = 16,
    percentage: bool = True,
    figsize: Tuple[float, float] = (18, 14),
    dpi: int = 300,
) -> Tuple[plt.Figure, np.ndarray]:
    """Plot twelve monthly wind roses using one shared speed scale."""
    frame = (
        prepare_daily_wind(data, direction_convention=direction_convention)
        if use_daily_vector_means
        else _prepare_instantaneous(data, direction_convention)
    )
    speed_edges = _speed_edges(frame["wind_speed_m_s"].to_numpy(), speed_bins)
    direction_edges = np.linspace(0.0, 360.0, direction_bins + 1)
    groups = [frame.loc[frame["month"] == month] for month in range(1, 13)]
    maximum = max(
        (_rose_counts(group, direction_edges, speed_edges, percentage).sum(axis=1).max()
         if not group.empty else 0.0)
        for group in groups
    )
    fig, axes = plt.subplots(
        3, 4, figsize=figsize, subplot_kw={"projection": "polar"}, squeeze=False
    )
    month_names = [
        "January", "February", "March", "April", "May", "June",
        "July", "August", "September", "October", "November", "December",
    ]
    cmap = plt.get_cmap("viridis", speed_bins)
    for month, ax in enumerate(axes.ravel(), start=1):
        group = groups[month - 1]
        counts = _rose_counts(group, direction_edges, speed_edges, percentage)
        _draw_rose(ax, counts, direction_edges, cmap)
        _format_polar(ax, month_names[month - 1], maximum, percentage)

    scalar = plt.cm.ScalarMappable(
        norm=plt.Normalize(speed_edges[0], speed_edges[-1]), cmap=cmap
    )
    scalar.set_array([])
    
    # 1. MOSAIC SPACING
    # Reserve space on the right (right=0.85) for the colorbar
    fig.subplots_adjust(top=0.92, bottom=0.08, left=0.05, right=0.85, wspace=0.35, hspace=0.35)

    # 2. REPOSITIONED COLORBAR WITH LARGER FONT SIZES
    cbar = fig.colorbar(scalar, ax=axes.ravel().tolist(), shrink=0.75, pad=0.03)
    cbar.set_label("Wind speed (m/s)", fontsize=14, labelpad=12) # Colorbar label font size
    cbar.ax.tick_params(labelsize=12)                             # Colorbar tick-label font size

    _save(fig, output_path, dpi)
    return fig, axes


def plot_annual_wind_rose(
    data: pd.DataFrame,
    output_path: Optional[Union[str, Path]] = None,
    direction_convention: str = "from",
    speed_bins: int = 5,
    direction_bins: int = 16,
    percentage: bool = True,
    dpi: int = 300,
) -> Tuple[plt.Figure, plt.Axes]:
    """Plot an annual wind rose based on daily vector means."""
    frame = prepare_daily_wind(data, direction_convention=direction_convention)
    speed_edges = _speed_edges(frame["wind_speed_m_s"].to_numpy(), speed_bins)
    direction_edges = np.linspace(0.0, 360.0, direction_bins + 1)
    counts = _rose_counts(frame, direction_edges, speed_edges, percentage)
    fig, ax = plt.subplots(figsize=(8, 8), subplot_kw={"projection": "polar"})
    cmap = plt.get_cmap("viridis", speed_bins)
    _draw_rose(ax, counts, direction_edges, cmap)
    _format_polar(ax, "Annual", counts.sum(axis=1).max(), percentage)
    scalar = plt.cm.ScalarMappable(
        norm=plt.Normalize(speed_edges[0], speed_edges[-1]), cmap=cmap
    )
    scalar.set_array([])
    cbar = fig.colorbar(scalar, ax=ax, orientation="horizontal", pad=0.10)
    cbar.set_label("Wind speed (m/s)")
    _save(fig, output_path, dpi)
    return fig, ax


def _prepare_instantaneous(data: pd.DataFrame, convention: str) -> pd.DataFrame:
    frame = data.copy()
    frame["datetime"] = pd.to_datetime(frame["datetime"])
    frame["wind_speed_m_s"] = np.hypot(frame["u_m_s"], frame["v_m_s"])
    direction_to = (90.0 - np.degrees(np.arctan2(frame["v_m_s"], frame["u_m_s"]))) % 360
    frame["wind_direction_deg"] = direction_to if convention == "to" else (direction_to + 180) % 360
    frame["month"] = frame["datetime"].dt.month
    return frame


def _speed_edges(values: np.ndarray, number: int) -> np.ndarray:
    minimum, maximum = float(np.nanmin(values)), float(np.nanmax(values))
    if math.isclose(minimum, maximum):
        maximum = minimum + max(0.5, abs(minimum) * 0.05)
    return np.linspace(max(0.0, minimum), maximum, number + 1)


def _rose_counts(frame, direction_edges, speed_edges, percentage):
    if frame.empty:
        return np.zeros((len(direction_edges)-1, len(speed_edges)-1))
    counts, _, _ = np.histogram2d(
        frame["wind_direction_deg"], frame["wind_speed_m_s"],
        bins=[direction_edges, speed_edges],
    )
    if percentage and counts.sum() > 0:
        counts = counts / counts.sum() * 100.0
    return counts


def _draw_rose(ax, counts, direction_edges, cmap):
    width = 2 * np.pi / (len(direction_edges)-1)
    for i in range(counts.shape[0]):
        bottom = 0.0
        for j in range(counts.shape[1]):
            value = counts[i, j]
            if value > 0:
                ax.bar(np.deg2rad(direction_edges[i]), value, width=width,
                       bottom=bottom, align="edge", color=cmap(j), edgecolor="none", alpha=0.85)
                bottom += value


def _format_polar(ax, title, maximum, percentage):
    ax.set_theta_zero_location("N")
    ax.set_theta_direction(-1)
    ax.set_xticks(np.deg2rad(np.arange(0, 360, 45)))
    ax.set_xticklabels(["N", "NE", "E", "SE", "S", "SW", "W", "NW"])
    ax.set_title(title, pad=12)
    ax.set_ylim(0, max(maximum * 1.08, 1.0))
    if percentage:
        ax.yaxis.set_major_formatter(lambda value, position: f"{value:g}%")


def _save(fig, output_path, dpi):
    if output_path is not None:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(path, dpi=dpi, bbox_inches="tight")
