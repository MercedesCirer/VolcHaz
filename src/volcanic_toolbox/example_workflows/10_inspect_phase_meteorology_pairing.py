"""Inspect meteorological pairing in the physically validated scenario ensemble.

This is a diagnostic example only. It does not modify scenario files or outputs.
It works with both monophase and multiphase scenario configurations.
"""
from __future__ import annotations
import pandas as pd
from volcanic_toolbox.preprocessing.output import ScenarioOutputManager
from scenario_config import EVENT_VEI, SCENARIO_NAME, SCENARIO_TYPE, phase_configs

def main() -> None:
    outputs = ScenarioOutputManager(scenario_name=SCENARIO_NAME).ensure()
    scenario_type = SCENARIO_TYPE.lower().strip()
    if scenario_type not in {'monophase', 'multiphase'}:
        raise ValueError("SCENARIO_TYPE must be 'monophase' or 'multiphase'.")
    scenario_file = outputs.scenarios_dir / f'valid_{scenario_type}_vei{EVENT_VEI}.csv'
    if not scenario_file.exists():
        raise FileNotFoundError(f'Missing validated scenario table:\n  {scenario_file}\n\nRun the physically constrained scenario-building example first.')
    data = pd.read_csv(scenario_file)
    columns = ['scenario_id']
    for phase in phase_configs():
        phase_columns = [f'{phase.name}_datetime', f'{phase.name}_wind_speed_m_s', f'{phase.name}_wind_direction_deg', f'{phase.name}_pressure_level_hpa', f'{phase.name}_season']
        columns.extend((column for column in phase_columns if column in data.columns))
    for column in ('event_total_mass_kg', 'event_total_volume_km3', 'event_total_duration_h'):
        if column in data.columns:
            columns.append(column)
    print('=' * 79)
    print('VALIDATED SCENARIO — METEOROLOGICAL PAIRING INSPECTION')
    print('=' * 79)
    print(f'Scenario: {SCENARIO_NAME}')
    print(f'Type:     {scenario_type}')
    print(f'File:     {scenario_file}')
    print()
    print(data[columns].head(20).to_string(index=False))
if __name__ == '__main__':
    main()
