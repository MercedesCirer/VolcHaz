"""Plot accepted/rejected scenario pairplots for monophase or multiphase cases.

The eruptive structure is selected in ``scenario_config.py`` through:

    SCENARIO_TYPE = "monophase"

or:

    SCENARIO_TYPE = "multiphase"

No plotting-script change is required when switching scenario type.

The scenario-building workflow stores both monophase and multiphase results
using the same phase-aware column convention:

    <phase>_column_height_m
    <phase>_duration_h
    <phase>_mer_kg_s
    <phase>_mass_kg
    <phase>_volume_km3
    <phase>_mass_fraction
    <phase>_wind_speed_m_s

Consequently, the same phase-aware plotting function can be used for either
scenario structure. A monophase scenario simply produces one pairplot, whereas
a multiphase scenario produces one pairplot for each configured phase.
"""
from __future__ import annotations
from pathlib import Path
import pandas as pd
from volcanic_toolbox.preprocessing.output import ScenarioOutputManager
from volcanic_toolbox.preprocessing.plotting import plot_multiphase_pairplots
from scenario_config import SCENARIO_NAME, SCENARIO_TYPE, phase_configs, validate_scenario_configuration
MAX_POINTS = 5000
RANDOM_SEED = 42
DPI = 300
FILENAME_PREFIX = 'scenario_pairplot'
PAIRPLOT_METRICS = None

def _find_evaluated_table(scenarios_directory: Path, scenario_type: str) -> Path:
    """Find the evaluated scenario table for the active scenario structure."""
    pattern = f'all_evaluated_{scenario_type}_vei*.csv'
    matches = sorted(scenarios_directory.glob(pattern))
    if not matches:
        raise FileNotFoundError(f"No evaluated scenario table was found for SCENARIO_TYPE='{scenario_type}'.\nExpected a file matching:\n  {scenarios_directory / pattern}\nRun workflow/preprocessing/06_build_scenarios.py first.")
    if len(matches) > 1:
        raise RuntimeError(f'More than one evaluated scenario table matches the active scenario type:\n' + '\n'.join((f'  - {path}' for path in matches)) + '\nRemove/rename obsolete tables or select a different SCENARIO_NAME so that the scenario output directory contains one active VEI ensemble.')
    return matches[0]

def main() -> None:
    validate_scenario_configuration()
    scenario_type = SCENARIO_TYPE.lower().strip()
    phases = tuple(phase_configs())
    outputs = ScenarioOutputManager(scenario_name=SCENARIO_NAME).ensure([phase.name for phase in phases])
    evaluated_path = _find_evaluated_table(outputs.scenarios_dir, scenario_type)
    scenarios = pd.read_csv(evaluated_path)
    phase_names = [phase.name for phase in phases]
    phase_labels = {phase.name: 'Eruption' if scenario_type == 'monophase' else phase.name.replace('_', ' ').title() for phase in phases}
    paths = plot_multiphase_pairplots(scenarios=scenarios, phase_names=phase_names, phase_labels=phase_labels, metrics=PAIRPLOT_METRICS, output_directory=outputs.pairplots_dir, filename_prefix=FILENAME_PREFIX, max_points=MAX_POINTS, seed=RANDOM_SEED, dpi=DPI)
    print('=' * 79)
    print('SCENARIO PAIRPLOTS')
    print('=' * 79)
    print(f'Scenario:      {SCENARIO_NAME}')
    print(f'Scenario type: {scenario_type}')
    print(f'Input table:   {evaluated_path}')
    print()
    for phase_name, path in paths.items():
        print(f'{phase_name:24s}: {path}')
if __name__ == '__main__':
    main()
