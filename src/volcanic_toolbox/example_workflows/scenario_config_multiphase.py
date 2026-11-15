"""Shared configuration used by the Stage 4 examples."""
from volcanic_toolbox.preprocessing.eruption import BoundsConfig, EruptionPhaseConfig, ParameterConfig
SCENARIO_TYPE = 'multiphase'
SCENARIO_NAME = 'lascar_vei4_multi_phase'
LATITUDE = -23.37
LONGITUDE = -67.73
VENT_ELEVATION_M = 5592.0
YEARS = (2010, 2020)
N_METEOROLOGY_SAMPLES = 5000
MONOPHASE_METEOROLOGY = {'eruption': {'pressure_level_hpa': 100, 'source': 'tmy'}}
MULTIPHASE_METEOROLOGY = {'extreme_intensity': {'pressure_level_hpa': 50, 'source': 'tmy'}, 'high_intensity': {'pressure_level_hpa': 100, 'source': 'tmy'}, 'low_intensity': {'pressure_level_hpa': 200, 'source': 'tmy'}}
MULTIPHASE_MASS_FRACTION_CONSTRAINTS = (('high_intensity', 0.15, 0.5), ('low_intensity', 0.5, 0.85))

def phase_mass_fraction_constraints():
    """Return active phase-mass-fraction constraints."""
    scenario_type = SCENARIO_TYPE.lower().strip()
    if scenario_type == 'monophase':
        return ()
    if scenario_type == 'multiphase':
        return MULTIPHASE_MASS_FRACTION_CONSTRAINTS
    raise ValueError("SCENARIO_TYPE must be 'monophase' or 'multiphase'.")
PHASE_METEOROLOGY = MONOPHASE_METEOROLOGY if SCENARIO_TYPE.lower().strip() == 'monophase' else MULTIPHASE_METEOROLOGY
SEASONS = {'wet': (10, 11, 12, 1, 2, 3, 4), 'dry': (5, 6, 7, 8, 9)}

def multiphase_configs() -> list[EruptionPhaseConfig]:
    """Return the eruptive phases included in the multiphase scenario."""
    extreme = EruptionPhaseConfig(name='extreme_intensity', parameters=[ParameterConfig(key='column_height', name='Extreme-intensity plume top', units='m', distribution='uniform', parameters={'low': 18592, 'high': 23592}, bounds=BoundsConfig(minimum=18592, maximum=23592)), ParameterConfig(key='duration', name='Extreme-intensity duration', units='h', distribution='triangular', parameters={'left': 0.25, 'mode': 0.5, 'right': 1.0}, bounds=BoundsConfig(minimum=0.25, maximum=1.0)), ParameterConfig(key='aggregation_fraction', name='Extreme-intensity aggregation fraction', units='fraction', distribution='uniform', parameters={'low': 0.1, 'high': 0.5}, bounds=BoundsConfig(minimum=0.1, maximum=0.5))])
    high = EruptionPhaseConfig(name='high_intensity', parameters=[ParameterConfig(key='column_height', name='High-intensity plume top', units='m', distribution='triangular', parameters={'left': 13592, 'mode': 16092, 'right': 18592}, bounds=BoundsConfig(minimum=13592, maximum=18592)), ParameterConfig(key='duration', name='High-intensity duration', units='h', distribution='triangular', parameters={'left': 1.0, 'mode': 2.5, 'right': 5.0}, bounds=BoundsConfig(minimum=1.0, maximum=5.0)), ParameterConfig(key='aggregation_fraction', name='High-intensity aggregation fraction', units='fraction', distribution='uniform', parameters={'low': 0.1, 'high': 0.5}, bounds=BoundsConfig(minimum=0.1, maximum=0.5))])
    low = EruptionPhaseConfig(name='low_intensity', parameters=[ParameterConfig(key='column_height', name='Low-intensity plume top', units='m', distribution='triangular', parameters={'left': 9592, 'mode': 11592, 'right': 13592}, bounds=BoundsConfig(minimum=9592, maximum=13592)), ParameterConfig(key='duration', name='Low-intensity duration', units='h', distribution='triangular', parameters={'left': 5.0, 'mode': 12.0, 'right': 24.0}, bounds=BoundsConfig(minimum=5.0, maximum=24.0)), ParameterConfig(key='aggregation_fraction', name='Low-intensity aggregation fraction', units='fraction', distribution='uniform', parameters={'low': 0.1, 'high': 0.5}, bounds=BoundsConfig(minimum=0.1, maximum=0.5))])
    return [extreme, high, low]

def monophase_config() -> EruptionPhaseConfig:
    """Return one independently defined phase representing the complete event.

    Edit this block when SCENARIO_TYPE = "monophase". Its ESP distributions are
    independent of the multiphase definitions above.
    """
    return EruptionPhaseConfig(name='eruption', parameters=[ParameterConfig(key='column_height', name='Plume top', units='m', distribution='triangular', parameters={'left': 13592, 'mode': 16092, 'right': 18592}, bounds=BoundsConfig(minimum=13592, maximum=18592)), ParameterConfig(key='duration', name='Eruption duration', units='h', distribution='triangular', parameters={'left': 1.0, 'mode': 5.0, 'right': 12.0}, bounds=BoundsConfig(minimum=1.0, maximum=12.0)), ParameterConfig(key='aggregation_fraction', name='Aggregation fraction', units='fraction', distribution='uniform', parameters={'low': 0.1, 'high': 0.5}, bounds=BoundsConfig(minimum=0.1, maximum=0.5))])

def phase_configs() -> list[EruptionPhaseConfig]:
    """Return the active phase set according to SCENARIO_TYPE."""
    scenario_type = SCENARIO_TYPE.lower().strip()
    if scenario_type == 'monophase':
        return [monophase_config()]
    if scenario_type == 'multiphase':
        phases = multiphase_configs()
        if len(phases) < 2:
            raise ValueError("SCENARIO_TYPE='multiphase' requires at least two phases.")
        return phases
    raise ValueError("SCENARIO_TYPE must be 'monophase' or 'multiphase'.")

def validate_scenario_configuration() -> None:
    """Validate consistency between active phases and meteorological settings."""
    phases = phase_configs()
    names = [phase.name for phase in phases]
    if SCENARIO_TYPE.lower().strip() == 'monophase' and len(phases) != 1:
        raise ValueError('A monophase scenario must contain exactly one phase.')
    if SCENARIO_TYPE.lower().strip() == 'multiphase' and len(phases) < 2:
        raise ValueError('A multiphase scenario must contain at least two phases.')
    if set(names) != set(PHASE_METEOROLOGY):
        raise ValueError(f'PHASE_METEOROLOGY keys must exactly match the active phase names. phases={names}, meteorology={list(PHASE_METEOROLOGY)}')
    for name, settings in PHASE_METEOROLOGY.items():
        if 'pressure_level_hpa' not in settings:
            raise KeyError(f'{name}: pressure_level_hpa is required.')
        source = str(settings.get('source', '')).lower().strip()
        if source not in {'tmy', 'historical'}:
            raise ValueError(f"{name}: source must be 'tmy' or 'historical'.")
    if SCENARIO_TYPE.lower().strip() == 'multiphase':
        for phase_name, minimum, maximum in MULTIPHASE_MASS_FRACTION_CONSTRAINTS:
            if phase_name not in names:
                raise ValueError(f"Mass-fraction constraint refers to undefined phase '{phase_name}'.")
            if not 0.0 <= float(minimum) <= float(maximum) <= 1.0:
                raise ValueError('Phase mass-fraction constraints must satisfy 0 <= minimum <= maximum <= 1.')
validate_scenario_configuration()
ATLAS_AREA = (-20.63, -74.35, -41.18, -49.31)
ATLAS_DAYS_AFTER = 5
ATLAS_MAX_WORKERS = 1
ATLAS_OVERWRITE = False
ATLAS_KEEP_GRIB = False
ATLAS_GRIB_TO_NETCDF_EXECUTABLE = 'grib_to_netcdf'
ATLAS_NETCDF_KIND = 3
ATLAS_NETCDF_DATA_TYPE = 'NC_FLOAT'
ATLAS_NETCDF_COMPRESSION_LEVEL = 4
ATLAS_DRY_RUN = False
