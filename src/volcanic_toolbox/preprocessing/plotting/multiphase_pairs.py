"""Create one pairplot per phase using the original accepted/rejected style."""

from __future__ import annotations
from pathlib import Path
from typing import Dict, Mapping, Optional, Sequence
import re
import matplotlib.pyplot as plt
import pandas as pd
from .scenario_pairs import plot_scenario_pairplot

DEFAULT_PHASE_METRICS = (
    "column_height_m", "duration_h", "mer_kg_s", "mass_kg",
    "volume_km3", "mass_fraction", "wind_speed_m_s",
)


def detect_phase_names(scenarios: pd.DataFrame, required_suffix="column_height_m") -> list[str]:
    suffix = "_" + required_suffix
    phases = sorted({c[:-len(suffix)] for c in scenarios.columns if c.endswith(suffix)})
    if not phases:
        raise ValueError(f"No phases detected from suffix '{suffix}'")
    return phases


def build_phase_pairplot_table(scenarios, phase_name, metrics=None, status_column="accepted"):
    metrics = list(metrics or DEFAULT_PHASE_METRICS)
    table = pd.DataFrame(index=scenarios.index)
    selected = []
    for metric in metrics:
        source = f"{phase_name}_{metric}"
        if source in scenarios:
            table[metric] = scenarios[source]
            selected.append(metric)
    table[status_column] = scenarios[status_column]
    if len(selected) < 2:
        raise ValueError(f"Not enough columns for phase '{phase_name}'")
    return table, selected


def plot_multiphase_pairplots(
    scenarios: pd.DataFrame,
    phase_names: Optional[Sequence[str]] = None,
    phase_labels: Optional[Mapping[str, str]] = None,
    metrics: Optional[Sequence[str]] = None,
    output_directory: str | Path = "outputs",
    filename_prefix: str = "scenario_pairplot",
    max_points: int = 5000,
    seed: int = 42,
    dpi: int = 300,
) -> Dict[str, Path]:
    phases = list(phase_names or detect_phase_names(scenarios))
    output = Path(output_directory); output.mkdir(parents=True, exist_ok=True)
    paths = {}
    for phase in phases:
        table, columns = build_phase_pairplot_table(scenarios, phase, metrics)
        safe = re.sub(r"[^A-Za-z0-9_-]+", "_", phase).strip("_")
        path = output / f"{filename_prefix}_{safe}.png"
        fig, _ = plot_scenario_pairplot(table, columns=columns, output_path=None,
                                         max_points=max_points, seed=seed, dpi=dpi)
        label = phase_labels.get(phase, phase) if phase_labels else phase
        fig.suptitle(f"{label.replace('_', ' ')} — accepted and rejected scenarios",
                     fontsize=14, y=1.025)
        fig.savefig(path, dpi=dpi, bbox_inches="tight")
        plt.close(fig)
        paths[phase] = path
    return paths
