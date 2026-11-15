"""Compare sampled eruptive-parameter distributions with validated scenarios.

This diagnostic compares, phase by phase:

    sampled input population
        outputs/<SCENARIO_NAME>/preprocessing/eruption/<phase>_candidates.csv

against:

    physically validated ensemble
        outputs/<SCENARIO_NAME>/preprocessing/scenarios/
        valid_<SCENARIO_TYPE>_vei<EVENT_VEI>.csv

The script is general for:
    - monophase
    - multiphase
    - TMY meteorology
    - historical meteorology

Meteorological source does not need special handling here because physical
validation has already been completed in step 06.

For every configured eruptive parameter, one comparative histogram is saved in:

    outputs/<SCENARIO_NAME>/preprocessing/figures/
        eruption_distributions/<phase>/

For a monophase phase named "eruption", for example:

    outputs/lascar_1993_monophase_historical_refined/preprocessing/figures/
        eruption_distributions/eruption/

A CSV containing comparative descriptive statistics is also saved for each
phase in the same directory.
"""
from __future__ import annotations
from pathlib import Path
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from volcanic_toolbox.preprocessing.output import ScenarioOutputManager
from scenario_config import EVENT_VEI, SCENARIO_NAME, SCENARIO_TYPE, phase_configs
HISTOGRAM_BINS = 30
DENSITY = True
DPI = 300
SHOW_FIGURES = False

def _safe_numeric(series: pd.Series) -> np.ndarray:
    """Return finite numeric values from a pandas Series."""
    values = pd.to_numeric(series, errors='coerce').to_numpy(dtype=float)
    return values[np.isfinite(values)]

def _parameter_label(parameter) -> str:
    """Build a readable axis label from ParameterConfig metadata."""
    name = getattr(parameter, 'name', parameter.key)
    units = getattr(parameter, 'units', '')
    if units:
        return f'{name} ({units})'
    return str(name)

def _validated_column(phase_name: str, parameter, columns) -> str:
    """Resolve the phase-prefixed validated column for one parameter."""
    base = parameter.column_name
    preferred = f'{phase_name}_{base}'
    if preferred in columns:
        return preferred
    if base in columns:
        return base
    raise KeyError(f'Validated scenario table has no column for parameter {parameter.key!r} in phase {phase_name!r}.\nExpected either:\n  {preferred}\nor:\n  {base}')

def _common_edges(sampled: np.ndarray, validated: np.ndarray) -> np.ndarray:
    """Create common histogram edges for a fair visual comparison."""
    combined = np.concatenate([sampled, validated])
    value_min = float(np.nanmin(combined))
    value_max = float(np.nanmax(combined))
    if np.isclose(value_min, value_max):
        padding = abs(value_min) * 0.05 if value_min != 0 else 0.5
        value_min -= padding
        value_max += padding
    return np.linspace(value_min, value_max, HISTOGRAM_BINS + 1)

def _describe(values: np.ndarray) -> dict[str, float]:
    """Descriptive statistics used in the comparison table."""
    if len(values) == 0:
        return {'n': 0, 'mean': np.nan, 'std': np.nan, 'min': np.nan, 'p05': np.nan, 'p25': np.nan, 'median': np.nan, 'p75': np.nan, 'p95': np.nan, 'max': np.nan}
    return {'n': len(values), 'mean': float(np.mean(values)), 'std': float(np.std(values, ddof=1)) if len(values) > 1 else 0.0, 'min': float(np.min(values)), 'p05': float(np.percentile(values, 5)), 'p25': float(np.percentile(values, 25)), 'median': float(np.median(values)), 'p75': float(np.percentile(values, 75)), 'p95': float(np.percentile(values, 95)), 'max': float(np.max(values))}

def _plot_comparison(sampled: np.ndarray, validated: np.ndarray, parameter, phase_name: str, output_path: Path):
    """Plot sampled and validated distributions using common bins."""
    edges = _common_edges(sampled, validated)
    fig, ax = plt.subplots(figsize=(8, 5.5))
    ax.hist(sampled, bins=edges, density=DENSITY, histtype='step', linewidth=2.0, label=f'Sampled (n={len(sampled):,})')
    ax.hist(validated, bins=edges, density=DENSITY, histtype='step', linewidth=2.0, label=f'Validated (n={len(validated):,})')
    ax.axvline(np.median(sampled), linestyle='--', linewidth=1.2)
    ax.axvline(np.median(validated), linestyle=':', linewidth=1.5)
    ax.set_xlabel(_parameter_label(parameter))
    ax.set_ylabel('Probability density' if DENSITY else 'Count')
    ax.set_title(f'{phase_name}: sampled vs validated')
    ax.legend(frameon=False)
    fig.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=DPI, bbox_inches='tight')
    if SHOW_FIGURES:
        plt.show()
    plt.close(fig)

def main():
    scenario_type = str(SCENARIO_TYPE).strip().lower()
    if scenario_type not in {'monophase', 'multiphase'}:
        raise ValueError("SCENARIO_TYPE must be 'monophase' or 'multiphase'.")
    phases = tuple(phase_configs())
    if not phases:
        raise ValueError('scenario_config.phase_configs() returned no eruptive phases.')
    outputs = ScenarioOutputManager(scenario_name=SCENARIO_NAME).ensure([phase.name for phase in phases])
    validated_path = outputs.scenarios_dir / f'valid_{scenario_type}_vei{EVENT_VEI}.csv'
    if not validated_path.exists():
        raise FileNotFoundError(f'Missing validated scenario table:\n  {validated_path}\n\nRun workflow/preprocessing/06_build_scenarios.py first.')
    validated_table = pd.read_csv(validated_path)
    distribution_root = outputs.figures_dir / 'eruption_distributions'
    print('=' * 79)
    print('SAMPLED VS VALIDATED ERUPTIVE-PARAMETER DISTRIBUTIONS')
    print('=' * 79)
    print(f'Scenario:      {SCENARIO_NAME}')
    print(f'Scenario type: {scenario_type}')
    print(f'Validated:     {validated_path}')
    for phase in phases:
        phase_name = phase.name
        sampled_path = outputs.eruption_dir / f'{phase_name}_candidates.csv'
        if not sampled_path.exists():
            raise FileNotFoundError(f'Missing sampled eruptive-parameter table for phase {phase_name!r}:\n  {sampled_path}\n\nRun workflow/preprocessing/01_preview_eruption.py first.')
        sampled_table = pd.read_csv(sampled_path)
        phase_output_dir = distribution_root / phase_name
        phase_output_dir.mkdir(parents=True, exist_ok=True)
        summary_rows = []
        for parameter in phase.parameters:
            sampled_column = parameter.column_name
            if sampled_column not in sampled_table.columns:
                raise KeyError(f'Sampled table for phase {phase_name!r} is missing column {sampled_column!r}.')
            validated_column = _validated_column(phase_name, parameter, validated_table.columns)
            sampled_values = _safe_numeric(sampled_table[sampled_column])
            validated_values = _safe_numeric(validated_table[validated_column])
            if len(sampled_values) == 0:
                raise ValueError(f'No finite sampled values found for {phase_name}.{parameter.key}.')
            if len(validated_values) == 0:
                raise ValueError(f'No finite validated values found for {phase_name}.{parameter.key}.')
            filename = f'{parameter.key}_sampled_vs_validated.png'
            output_path = phase_output_dir / filename
            _plot_comparison(sampled=sampled_values, validated=validated_values, parameter=parameter, phase_name=phase_name, output_path=output_path)
            sampled_stats = _describe(sampled_values)
            validated_stats = _describe(validated_values)
            row = {'phase': phase_name, 'parameter': parameter.key, 'sampled_column': sampled_column, 'validated_column': validated_column}
            for key, value in sampled_stats.items():
                row[f'sampled_{key}'] = value
            for key, value in validated_stats.items():
                row[f'validated_{key}'] = value
            summary_rows.append(row)
            print(f'{phase_name}: {parameter.key} -> {output_path}')
        summary = pd.DataFrame(summary_rows)
        summary_path = phase_output_dir / 'sampled_vs_validated_summary.csv'
        summary.to_csv(summary_path, index=False)
        print(f'{phase_name}: summary -> {summary_path}')
if __name__ == '__main__':
    main()
