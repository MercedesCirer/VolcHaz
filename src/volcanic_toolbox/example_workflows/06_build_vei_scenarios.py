"""Build a physically validated monophase or multiphase VEI scenario ensemble.

All scientific scenario choices are read from scenario_config.py.

The script is intentionally independent of the meteorological sampling
strategy. Whether meteorology came from a TMY or the full historical ERA5
record is resolved in step 04; this stage reads only
``selected_meteorology_samples.csv`` for each active phase.

Supported combinations:
    - monophase + historical
    - monophase + TMY
    - multiphase + historical
    - multiphase + TMY
    - mixed source by phase, if configured intentionally
"""
from __future__ import annotations
import pandas as pd
from volcanic_toolbox.preprocessing.eruption import VEIConfig
from volcanic_toolbox.preprocessing.physics import MERConfig
from volcanic_toolbox.preprocessing.scenarios import MultiphaseVEIScenarioBuilder, PhaseMassFractionConstraint, ScenarioBuildConfig, VEIScenarioBuilder
from volcanic_toolbox.preprocessing.output import ScenarioOutputManager
from scenario_config import BULK_DENSITY_KG_M3, COLUMN_HEIGHT_REFERENCE, EVENT_VEI, MAXIMUM_FALLOUT_VOLUME_KM3, MINIMUM_FALLOUT_VOLUME_KM3, SCENARIO_NAME, SCENARIO_TYPE, SEASONS, VENT_ELEVATION_M, phase_configs, phase_mass_fraction_constraints, validate_scenario_configuration
VEI_CONFIG = VEIConfig(vei=EVENT_VEI, minimum_volume_km3=MINIMUM_FALLOUT_VOLUME_KM3, maximum_volume_km3=MAXIMUM_FALLOUT_VOLUME_KM3, bulk_density_kg_m3=BULK_DENSITY_KG_M3, source_reference='scenario_config.py')
MER_CONFIG = MERConfig(vent_elevation_m=VENT_ELEVATION_M)
BUILD_CONFIG = ScenarioBuildConfig(target_valid_scenarios=1000, batch_size=1000, max_attempts=200000, seed=42, height_reference=COLUMN_HEIGHT_REFERENCE, wind_column='wind_speed_m_s', datetime_column='datetime', sample_meteorology_with_replacement=True)

def _load_meteorology(outputs, phases):
    """Load the selected meteorological sample for every active phase."""
    tables = {}
    for phase in phases:
        path = outputs.phase_meteorology_dir(phase.name) / 'selected_meteorology_samples.csv'
        if not path.exists():
            raise FileNotFoundError(f'Missing selected meteorology for phase {phase.name!r}:\n  {path}\n\nRun 04_sample_meteorology.py first.')
        tables[phase.name] = pd.read_csv(path, parse_dates=['datetime'])
    return tables

def _normalize_monophase_table(table, phase):
    """Convert monophase output to the phase-aware schema used downstream."""
    frame = table.copy()
    phase_name = phase.name
    rename = {parameter.column_name: f'{phase_name}_{parameter.column_name}' for parameter in phase.parameters if parameter.column_name in frame.columns}
    rename.update({'mer_kg_s': f'{phase_name}_mer_kg_s', 'calculated_mass_kg': f'{phase_name}_mass_kg', 'calculated_volume_km3': f'{phase_name}_volume_km3', 'datetime': f'{phase_name}_datetime', 'season': f'{phase_name}_season'})
    meteorological_columns = {'wind_speed_m_s', 'wind_direction_deg', 'u_m_s', 'v_m_s', 'pressure_level_hpa', 'latitude', 'longitude', 'sampling_method', 'meteo_id', 'meteo_source_row', 'tmy_datetime', 'source_year', 'year', 'month', 'day', 'hour'}
    for column in frame.columns:
        if column in meteorological_columns:
            rename[column] = f'{phase_name}_{column}'
    frame = frame.rename(columns=rename)
    mass = f'{phase_name}_mass_kg'
    volume = f'{phase_name}_volume_km3'
    duration = f'{phase_name}_duration_h'
    season = f'{phase_name}_season'
    if mass in frame:
        frame['event_total_mass_kg'] = frame[mass]
        frame[f'{phase_name}_mass_fraction'] = 1.0
    if volume in frame:
        frame['event_total_volume_km3'] = frame[volume]
    if duration in frame:
        frame['event_total_duration_h'] = frame[duration]
    if season in frame:
        frame['same_season_across_phases'] = True
        frame['event_season'] = frame[season]
    frame['column_height_reference'] = COLUMN_HEIGHT_REFERENCE
    return frame

def main():
    validate_scenario_configuration()
    scenario_type = str(SCENARIO_TYPE).strip().lower()
    if scenario_type not in {'monophase', 'multiphase'}:
        raise ValueError("SCENARIO_TYPE must be 'monophase' or 'multiphase'.")
    phases = tuple(phase_configs())
    if scenario_type == 'monophase' and len(phases) != 1:
        raise ValueError('A monophase scenario must contain exactly one eruptive phase.')
    if scenario_type == 'multiphase' and len(phases) < 2:
        raise ValueError('A multiphase scenario must contain at least two eruptive phases.')
    outputs = ScenarioOutputManager(scenario_name=SCENARIO_NAME).ensure([phase.name for phase in phases])
    meteorology = _load_meteorology(outputs, phases)
    if scenario_type == 'monophase':
        phase = phases[0]
        result = VEIScenarioBuilder(parameter_configs=phase.parameters, meteorology=meteorology[phase.name], vei_config=VEI_CONFIG, mer_config=MER_CONFIG, build_config=BUILD_CONFIG, seasons=SEASONS).build()
        result.valid_scenarios = _normalize_monophase_table(result.valid_scenarios, phase)
        result.evaluated_scenarios = _normalize_monophase_table(result.evaluated_scenarios, phase)
    else:
        constraints = tuple((PhaseMassFractionConstraint(phase_name=phase_name, minimum=minimum, maximum=maximum) for phase_name, minimum, maximum in phase_mass_fraction_constraints()))
        result = MultiphaseVEIScenarioBuilder(phase_configs=phases, meteorology_by_phase=meteorology, vei_config=VEI_CONFIG, mer_config=MER_CONFIG, build_config=BUILD_CONFIG, phase_fraction_constraints=constraints, seasons=SEASONS).build()
    valid_name = f'valid_{scenario_type}_vei{VEI_CONFIG.vei}.csv'
    evaluated_name = f'all_evaluated_{scenario_type}_vei{VEI_CONFIG.vei}.csv'
    summary_name = f'{scenario_type}_vei{VEI_CONFIG.vei}_summary.csv'
    valid_path = outputs.scenarios_dir / valid_name
    evaluated_path = outputs.scenarios_dir / evaluated_name
    summary_path = outputs.scenarios_dir / summary_name
    result.valid_scenarios.to_csv(valid_path, index=False)
    result.evaluated_scenarios.to_csv(evaluated_path, index=False)
    result.summary.to_csv(summary_path, index=False)
    if scenario_type == 'multiphase' and result.phase_diagnostics is not None:
        diagnostics_path = outputs.scenarios_dir / f'multiphase_vei{VEI_CONFIG.vei}_phase_diagnostics.csv'
        result.phase_diagnostics.to_csv(diagnostics_path, index=False)
    else:
        diagnostics_path = None
    print('=' * 79)
    print('PHYSICALLY VALIDATED ERUPTION-SCENARIO ENSEMBLE')
    print('=' * 79)
    print(f'Scenario:                {SCENARIO_NAME}')
    print(f'Scenario type:           {scenario_type}')
    print('Phases:                  ' + ', '.join((phase.name for phase in phases)))
    print(f'Column-height reference: {COLUMN_HEIGHT_REFERENCE}')
    print(f'Fallout-volume bounds:   {MINIMUM_FALLOUT_VOLUME_KM3:g}-{MAXIMUM_FALLOUT_VOLUME_KM3:g} km3')
    print(f'Bulk density:            {BULK_DENSITY_KG_M3:g} kg m-3')
    print(f'Acceptance rate:         {result.acceptance_rate * 100:.3f}%')
    print(f'Valid scenarios:         {valid_path}')
    print(f'All attempts:            {evaluated_path}')
    print(f'Summary:                 {summary_path}')
    if diagnostics_path is not None:
        print(f'Phase diagnostics:       {diagnostics_path}')
if __name__ == '__main__':
    main()
