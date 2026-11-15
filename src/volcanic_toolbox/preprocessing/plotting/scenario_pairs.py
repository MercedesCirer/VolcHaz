"""Pairwise scenario diagnostics colored by physical acceptance."""

from __future__ import annotations

from pathlib import Path
from typing import Optional, Sequence, Tuple, Union

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


def plot_scenario_pairplot(
    scenarios: pd.DataFrame,
    columns: Optional[Sequence[str]] = None,
    status_column: str = "accepted",
    output_path: Optional[Union[str, Path]] = None,
    max_points: int = 5000,
    seed: int = 42,
    dpi: int = 300,
) -> Tuple[plt.Figure, np.ndarray]:
    """Create a scatter-matrix with accepted and rejected attempts separated."""
    default = [
        "column_height_m", "duration_h", "wind_speed_m_s",
        "mer_kg_s", "calculated_mass_kg", "calculated_volume_km3",
    ]
    selected = list(columns or [c for c in default if c in scenarios.columns])
    if len(selected) < 2:
        raise ValueError("At least two numeric columns are required")
    missing = set(selected + [status_column]).difference(scenarios.columns)
    if missing:
        raise KeyError(f"Scenario table is missing columns: {sorted(missing)}")
    frame = scenarios[selected + [status_column]].copy().dropna()
    if len(frame) > max_points:
        frame = frame.sample(max_points, random_state=seed)
    n = len(selected)
    fig, axes = plt.subplots(n, n, figsize=(3.0*n, 3.0*n), squeeze=False)
    statuses = [(False, "Rejected", "tab:orange"), (True, "Accepted", "tab:blue")]
    
    for row, ycol in enumerate(selected):
        for col, xcol in enumerate(selected):
            ax = axes[row, col]
            if row == col:
                for status, label, color in statuses:
                    values = frame.loc[frame[status_column].astype(bool) == status, xcol]
                    if not values.empty:
                        ax.hist(values, bins=25, alpha=0.5, density=True,
                                label=label, color=color)
            else:
                for status, label, color in statuses:
                    subset = frame.loc[frame[status_column].astype(bool) == status]
                    ax.scatter(subset[xcol], subset[ycol], s=9, alpha=0.35,
                               label=label, color=color, edgecolors="none")
            
            # --- MODIFICACIONES DE FUENTE AQUÍ ---
            
            # 1. X- and Y-axis label font size (e.g., fontsize=12)
            if row == n - 1:
                ax.set_xlabel(xcol, fontsize=12, labelpad=8)
            else:
                ax.set_xticklabels([])
                
            if col == 0:
                ax.set_ylabel(ycol, fontsize=12, labelpad=8)
            else:
                ax.set_yticklabels([])
            
            # 2. Axis tick-label font size (e.g., labelsize=10)
            ax.tick_params(axis='both', which='major', labelsize=10)

            ax.spines["top"].set_visible(False)
            ax.spines["right"].set_visible(False)

    # 3. Font size of the upper legend (e.g., fontsize=12)
    handles, labels = axes[0, 0].get_legend_handles_labels()
    if handles:
        fig.legend(
            handles, 
            labels, 
            loc="upper center", 
            ncol=2, 
            frameon=False, 
            fontsize=12, 
            bbox_to_anchor=(0.5, 1.02)  # Raise the legend slightly to avoid overlap
        )

    # Adjust rect to reserve space above the axes for the larger legend
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    
    if output_path is not None:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(path, dpi=dpi, bbox_inches="tight")
    return fig, axes
