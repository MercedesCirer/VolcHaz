"""Compare the active meteorological source with validated-scenario wind roses.

The source for each phase is read from PHASE_METEOROLOGY in scenario_config.py.

- historical -> compare full_wind_data.csv against validated scenarios
- tmy        -> compare tmy_wind_data.csv against validated scenarios

The script supports both monophase and multiphase scenarios because it
iterates over every phase returned by phase_configs() and reads the common
validated scenario table for the active SCENARIO_TYPE.

Both datasets are plotted using:
- individual records
- meteorological FROM direction recalculated directly from u/v
- common direction bins
- common wind-speed bins
- common radial maximum
"""
from __future__ import annotations
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from volcanic_toolbox.preprocessing.output import ScenarioOutputManager
from scenario_config import EVENT_VEI, PHASE_METEOROLOGY, SCENARIO_NAME, SCENARIO_TYPE, phase_configs
DIRECTION_BINS = 16
SPEED_BINS = 5
DPI = 300

def meteorological_from_direction(u, v):
    """Meteorological FROM direction in degrees."""
    return (np.degrees(np.arctan2(-np.asarray(u), -np.asarray(v))) + 360.0) % 360.0

def prepare_from_uv(data, u_col, v_col):
    """Recalculate wind speed and meteorological FROM direction from u/v."""
    frame = data.copy()
    missing = {u_col, v_col}.difference(frame.columns)
    if missing:
        raise KeyError(f'Meteorological table is missing required columns: {sorted(missing)}')
    frame['wind_speed_m_s'] = np.hypot(frame[u_col], frame[v_col])
    frame['wind_direction_deg'] = meteorological_from_direction(frame[u_col], frame[v_col])
    return frame

def rose_counts(frame, direction_edges, speed_edges):
    """Return percentage counts for direction x wind-speed classes."""
    counts, _, _ = np.histogram2d(frame['wind_direction_deg'], frame['wind_speed_m_s'], bins=[direction_edges, speed_edges])
    if counts.sum() > 0:
        counts = counts / counts.sum() * 100.0
    return counts

def draw_rose(ax, counts, direction_edges, cmap, title, shared_maximum):
    """Draw one stacked wind rose."""
    width = 2.0 * np.pi / (len(direction_edges) - 1)
    for i in range(counts.shape[0]):
        bottom = 0.0
        for j in range(counts.shape[1]):
            value = counts[i, j]
            if value > 0:
                ax.bar(np.deg2rad(direction_edges[i]), value, width=width, bottom=bottom, align='edge', color=cmap(j), edgecolor='none', alpha=0.85)
                bottom += value
    ax.set_theta_zero_location('N')
    ax.set_theta_direction(-1)
    ax.set_xticks(np.deg2rad(np.arange(0, 360, 45)))
    ax.set_xticklabels(['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW'])
    ax.set_ylim(0, max(shared_maximum * 1.08, 1.0))
    ax.yaxis.set_major_formatter(lambda value, position: f'{value:g}%')
    ax.set_title(title, pad=12)

def main():
    outputs = ScenarioOutputManager(scenario_name=SCENARIO_NAME).ensure(PHASE_METEOROLOGY)
    scenario_type = str(SCENARIO_TYPE).strip().lower()
    if scenario_type not in {'monophase', 'multiphase'}:
        raise ValueError("SCENARIO_TYPE must be 'monophase' or 'multiphase'.")
    scenario_file = outputs.scenarios_dir / f'valid_{scenario_type}_vei{EVENT_VEI}.csv'
    if not scenario_file.exists():
        raise FileNotFoundError(f'Missing validated scenario table:\n  {scenario_file}\n\nRun workflow/preprocessing/06_build_scenarios.py first.')
    scenarios = pd.read_csv(scenario_file)
    phases = tuple(phase_configs())
    for phase in phases:
        phase_name = phase.name
        if phase_name not in PHASE_METEOROLOGY:
            raise KeyError(f'Phase {phase_name!r} is present in phase_configs() but missing from PHASE_METEOROLOGY.')
        source = str(PHASE_METEOROLOGY[phase_name]['source']).strip().lower()
        if source not in {'historical', 'tmy'}:
            raise ValueError(f"Phase {phase_name!r}: source must be 'historical' or 'tmy'; received {source!r}.")
        phase_dir = outputs.phase_meteorology_dir(phase_name)
        if source == 'historical':
            source_file = phase_dir / 'full_wind_data.csv'
            source_label = 'Historical ERA5'
        else:
            source_file = phase_dir / 'tmy_wind_data.csv'
            source_label = 'TMY'
        if not source_file.exists():
            raise FileNotFoundError(f'Missing meteorological source table for phase {phase_name!r}:\n  {source_file}\n\nRun 03_prepare_meteorology.py first.')
        source_data = prepare_from_uv(pd.read_csv(source_file, parse_dates=['datetime']), 'u_m_s', 'v_m_s')
        u_col = f'{phase_name}_u_m_s'
        v_col = f'{phase_name}_v_m_s'
        missing = {u_col, v_col}.difference(scenarios.columns)
        if missing:
            raise KeyError(f'Validated scenario table is missing phase-specific wind columns for {phase_name!r}: {sorted(missing)}')
        validated = prepare_from_uv(scenarios, u_col, v_col)
        all_speeds = np.concatenate([source_data['wind_speed_m_s'].to_numpy(), validated['wind_speed_m_s'].to_numpy()])
        finite_speeds = all_speeds[np.isfinite(all_speeds)]
        if finite_speeds.size == 0:
            raise ValueError(f'No finite wind-speed values available for phase {phase_name!r}.')
        speed_min = max(0.0, float(np.nanmin(finite_speeds)))
        speed_max = float(np.nanmax(finite_speeds))
        if np.isclose(speed_min, speed_max):
            speed_max = speed_min + 0.5
        speed_edges = np.linspace(speed_min, speed_max, SPEED_BINS + 1)
        direction_edges = np.linspace(0.0, 360.0, DIRECTION_BINS + 1)
        source_counts = rose_counts(source_data, direction_edges, speed_edges)
        valid_counts = rose_counts(validated, direction_edges, speed_edges)
        shared_maximum = max(source_counts.sum(axis=1).max(), valid_counts.sum(axis=1).max())
        cmap = plt.get_cmap('viridis', SPEED_BINS)
        fig, axes = plt.subplots(1, 2, figsize=(16, 8), subplot_kw={'projection': 'polar'})
        draw_rose(axes[0], source_counts, direction_edges, cmap, f'{source_label} — individual records', shared_maximum)
        draw_rose(axes[1], valid_counts, direction_edges, cmap, 'Validated scenarios', shared_maximum)
        scalar = plt.cm.ScalarMappable(norm=plt.Normalize(speed_edges[0], speed_edges[-1]), cmap=cmap)
        scalar.set_array([])
        fig.subplots_adjust(top=0.95, bottom=0.16, wspace=0.28)
        cbar = fig.colorbar(scalar, ax=axes.tolist(), orientation='horizontal', pad=0.12, shrink=0.75)
        cbar.set_label('Wind speed (m/s)')
        output_path = outputs.wind_rose_dir / f'{phase_name}_{source}_vs_validated_same_convention.png'
        output_path.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(output_path, dpi=DPI, bbox_inches='tight')
        plt.close(fig)
        print('=' * 79)
        print(f'Scenario:         {SCENARIO_NAME}')
        print(f'Scenario type:    {scenario_type}')
        print(f'Phase:            {phase_name}')
        print(f'Source:           {source}')
        print(f'Source records:   {len(source_data):,}')
        print(f'Validated records:{len(validated):,}')
        print('Convention:       meteorological FROM, recalculated from u/v')
        print('Aggregation:      individual records in both datasets')
        print(f'Saved:            {output_path}')
if __name__ == '__main__':
    main()
