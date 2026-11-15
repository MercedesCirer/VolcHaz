"""General user configuration for ATLAS input generation.

This file is independent of:
    - monophase vs multiphase scenario structure
    - TMY vs historical preprocessing meteorology

Active phases and stochastic parameter column names are derived automatically
from scenario_config.py. ATLAS-specific numerical/model settings remain here.

Required stochastic phase parameters:
    column_height
    duration

Optional stochastic parameters are used when present:
    mean_phi
    sorting_phi
    aggregation_fraction
    aggregate_density

If an optional parameter is absent from a phase, the ATLAS defaults defined
below are used for that phase.
"""
from volcanic_toolbox.processing.atlas.input_builder import AtlasMainInputConfig, AtlasPairValue, AtlasPhaseConfig, AtlasValue
from scenario_config import LATITUDE, LONGITUDE, TGSD_MAX_PHI, TGSD_MIN_PHI, VENT_ELEVATION_M, phase_configs
ATLAS_INSTALL_BASE = '/users/your_username'
ATLAS_DIRECTORY_NAME = 'ATLAS-1.0'
ATLAS_RUN_FOLDER_MODE = 'date_and_scenario'
ATLAS_REQUIRE_LOCAL_METEOROLOGY = False
ATLAS_FALLBACK_METEOROLOGY_HOURS = 144
ATLAS_INPUT_OVERWRITE = True
ATLAS_MAIN_INPUT = AtlasMainInputConfig(time_step_seconds=15, restart='no', ztop_m=55000, vertical_resolution_m=1000, longitude_resolution_deg=0.25, latitude_resolution_deg=0.25, output_frequency_h=1, vertical_layers='1000', output_classes='no', output_phases='no', output_track_points='no', terminal_velocity_model=1, meteo_postprocess='no')
ATLAS_VOLCANO_NAME = 'Lascar'
ATLAS_NUMBER_PARTICLES = 5000000
ATLAS_MASS_FLOW_RATE = 'ESTIMATE-DEGRUYTER'
ATLAS_SUZUKI_A = 4.0
ATLAS_SUZUKI_L = 5.0
ATLAS_TOP_HAT_DIAMETER_M = 2000.0
ATLAS_PHASE_GRANULOMETRY = 'NONE'
ATLAS_DISTRIBUTION = 'GAUSSIAN'
ATLAS_NUMBER_OF_BINS = 14
ATLAS_DEFAULT_MEAN_PHI = -0.413
ATLAS_DEFAULT_SORTING_PHI = 2.809
ATLAS_PARTICLE_DENSITY_RANGE_KG_M3 = (1000.0, 2500.0)
ATLAS_SPHERICITY_RANGE = (0.5, 0.8)
ATLAS_AGGREGATE_SIZE_MICRONS = 250.0
ATLAS_DEFAULT_AGGREGATE_DENSITY_KG_M3 = 400.0
ATLAS_DEFAULT_AGGREGATION_PERCENTAGE = 20.0

def _parameter_map(phase):
    """Map ParameterConfig.key -> ParameterConfig for one phase."""
    return {parameter.key: parameter for parameter in phase.parameters}

def _phase_column(phase_name, parameter):
    """Return the phase-prefixed validated-table column name."""
    return f'{phase_name}_{parameter.column_name}'

def _required_parameter(parameters, phase_name, key):
    if key not in parameters:
        raise KeyError(f'Phase {phase_name!r} must define stochastic parameter {key!r} in scenario_config.py for ATLAS input generation.')
    return parameters[key]

def _optional_column_or_constant(*, parameters, phase_name, key, default, scale=1.0):
    """Read a sampled parameter when configured; otherwise use an ATLAS default."""
    parameter = parameters.get(key)
    if parameter is None:
        return AtlasValue(constant=default)
    return AtlasValue(column=_phase_column(phase_name, parameter), scale=scale)

def _build_atlas_phase(phase):
    """Build one AtlasPhaseConfig directly from one active scenario phase."""
    phase_name = phase.name
    parameters = _parameter_map(phase)
    column_height = _required_parameter(parameters, phase_name, 'column_height')
    duration = _required_parameter(parameters, phase_name, 'duration')
    return AtlasPhaseConfig(datetime=AtlasValue(column=f'{phase_name}_datetime'), column_height=AtlasValue(column=_phase_column(phase_name, column_height)), duration=AtlasValue(column=_phase_column(phase_name, duration)), number_particles=AtlasValue(constant=ATLAS_NUMBER_PARTICLES), phase_name=AtlasValue(constant=phase_name), phase_type=AtlasValue(constant='eruption'), mass_flow_rate=AtlasValue(constant=ATLAS_MASS_FLOW_RATE), a_suzuki=AtlasValue(constant=ATLAS_SUZUKI_A), l_suzuki=AtlasValue(constant=ATLAS_SUZUKI_L), d_top_hat_m=AtlasValue(constant=ATLAS_TOP_HAT_DIAMETER_M), volcano_name=AtlasValue(constant=ATLAS_VOLCANO_NAME), source_longitude=AtlasValue(constant=LONGITUDE), source_latitude=AtlasValue(constant=LATITUDE), source_elevation=AtlasValue(constant=VENT_ELEVATION_M), phase_granulometry=AtlasValue(constant=ATLAS_PHASE_GRANULOMETRY), distribution=AtlasValue(constant=ATLAS_DISTRIBUTION), number_of_bins=AtlasValue(constant=ATLAS_NUMBER_OF_BINS), fi_mean_1=_optional_column_or_constant(parameters=parameters, phase_name=phase_name, key='mean_phi', default=ATLAS_DEFAULT_MEAN_PHI), fi_disp_1=_optional_column_or_constant(parameters=parameters, phase_name=phase_name, key='sorting_phi', default=ATLAS_DEFAULT_SORTING_PHI), fi_mean_2=None, fi_disp_2=None, fi_range=AtlasPairValue(first=AtlasValue(constant=TGSD_MIN_PHI), second=AtlasValue(constant=TGSD_MAX_PHI)), density_range=AtlasPairValue(first=AtlasValue(constant=ATLAS_PARTICLE_DENSITY_RANGE_KG_M3[0]), second=AtlasValue(constant=ATLAS_PARTICLE_DENSITY_RANGE_KG_M3[1])), sphericity_range=AtlasPairValue(first=AtlasValue(constant=ATLAS_SPHERICITY_RANGE[0]), second=AtlasValue(constant=ATLAS_SPHERICITY_RANGE[1])), aggregate_size_microns=AtlasValue(constant=ATLAS_AGGREGATE_SIZE_MICRONS), aggregate_density_kg_m3=_optional_column_or_constant(parameters=parameters, phase_name=phase_name, key='aggregate_density', default=ATLAS_DEFAULT_AGGREGATE_DENSITY_KG_M3), aggregation_percentage=_optional_column_or_constant(parameters=parameters, phase_name=phase_name, key='aggregation_fraction', default=ATLAS_DEFAULT_AGGREGATION_PERCENTAGE, scale=100.0))
ATLAS_PHASES = {phase.name: _build_atlas_phase(phase) for phase in phase_configs()}
