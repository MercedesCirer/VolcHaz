"""Generate ATLAS main and Phase1 input files for validated scenarios.

General for:
    - monophase
    - multiphase
    - TMY-based preprocessing
    - historical-random preprocessing

TMY vs historical requires no branch here: the validated scenario table already
contains the selected phase-specific datetimes, and ATLAS meteorology is resolved
from those dates in the model-specific ERA5 tree.
"""
from volcanic_toolbox.preprocessing.output import ScenarioOutputManager
from volcanic_toolbox.processing.atlas.input_builder import AtlasInputBuildConfig, build_atlas_inputs
from atlas_input_config import ATLAS_DIRECTORY_NAME, ATLAS_FALLBACK_METEOROLOGY_HOURS, ATLAS_INPUT_OVERWRITE, ATLAS_INSTALL_BASE, ATLAS_MAIN_INPUT, ATLAS_PHASES, ATLAS_REQUIRE_LOCAL_METEOROLOGY, ATLAS_RUN_FOLDER_MODE
from scenario_config import ATLAS_AREA, COLUMN_HEIGHT_REFERENCE, EVENT_VEI, SCENARIO_NAME, SCENARIO_TYPE, phase_configs, validate_scenario_configuration

def main():
    validate_scenario_configuration()
    outputs = ScenarioOutputManager(scenario_name=SCENARIO_NAME).ensure()
    scenario_type = str(SCENARIO_TYPE).strip().lower()
    if scenario_type not in {'monophase', 'multiphase'}:
        raise ValueError(f"SCENARIO_TYPE must be 'monophase' or 'multiphase'. Received: {SCENARIO_TYPE!r}")
    scenario_table = outputs.scenarios_dir / f'valid_{scenario_type}_vei{EVENT_VEI}.csv'
    if not scenario_table.exists():
        raise FileNotFoundError(f'Missing validated scenario table:\n  {scenario_table}\n\nRun workflow/preprocessing/06_build_scenarios.py first.')
    active_phase_names = [phase.name for phase in phase_configs()]
    missing_atlas_phases = [phase_name for phase_name in active_phase_names if phase_name not in ATLAS_PHASES]
    if missing_atlas_phases:
        raise KeyError(f'atlas_input_config.py does not define ATLAS settings for active phase(s): {missing_atlas_phases}. Active phases: {active_phase_names}. Available ATLAS_PHASES: {list(ATLAS_PHASES)}.')
    active_atlas_phases = {phase_name: ATLAS_PHASES[phase_name] for phase_name in active_phase_names}
    print('=' * 79)
    print('ATLAS INPUT GENERATION')
    print('=' * 79)
    print(f'Scenario:       {SCENARIO_NAME}')
    print(f'Scenario type:  {scenario_type}')
    print(f'VEI:            {EVENT_VEI}')
    print(f"Phases:         {', '.join(active_phase_names)}")
    print(f'Scenario table: {scenario_table}')
    print()
    config = AtlasInputBuildConfig(scenario_table=scenario_table, local_inputs_root=outputs.atlas_inputs_dir, local_meteorology_root=outputs.atlas_era5_dir, atlas_install_base=ATLAS_INSTALL_BASE, atlas_directory_name=ATLAS_DIRECTORY_NAME, meteorology_area=ATLAS_AREA, domain_margin_deg=0.5, phases=active_atlas_phases, main=ATLAS_MAIN_INPUT, accepted_column=None, scenario_id_column='scenario_id', run_folder_mode=ATLAS_RUN_FOLDER_MODE, column_height_reference=COLUMN_HEIGHT_REFERENCE, overwrite=ATLAS_INPUT_OVERWRITE, require_local_meteorology=ATLAS_REQUIRE_LOCAL_METEOROLOGY, fallback_meteorology_hours=ATLAS_FALLBACK_METEOROLOGY_HOURS)
    manifest = build_atlas_inputs(config)
    print(f'Generated input records: {len(manifest):,}')
    print('Phases:', ', '.join(sorted(manifest['phase'].unique())))
    print('Inputs root:', outputs.atlas_inputs_dir)
    print('Manifest:', outputs.atlas_inputs_dir / 'atlas_input_manifest.csv')
    print('\nCreation summary:')
    print(manifest.groupby(['phase', 'meteorology_time_source', 'main_status', 'phase_status'], dropna=False).size().rename('count').reset_index().to_string(index=False))
if __name__ == '__main__':
    main()
