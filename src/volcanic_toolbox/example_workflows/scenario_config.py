"""Scenario configuration for a monophase tephra-dispersal application."""
from volcanic_toolbox.preprocessing.eruption import BoundsConfig, EruptionPhaseConfig, ParameterConfig
SCENARIO_TYPE = 'monophase'
SCENARIO_NAME = 'lascar_1993_monophase_refined'
LATITUDE = -23.37
LONGITUDE = -67.73
VENT_ELEVATION_M = 5592.0
COLUMN_HEIGHT_REFERENCE = 'above_vent'
YEARS = (2010, 2020)
N_METEOROLOGY_SAMPLES = 5000
SEASONS = {'wet': (10, 11, 12, 1, 2, 3, 4), 'dry': (5, 6, 7, 8, 9)}
EVENT_VEI = 4
MINIMUM_FALLOUT_VOLUME_KM3 = 0.08
MAXIMUM_FALLOUT_VOLUME_KM3 = 0.12
BULK_DENSITY_KG_M3 = 1000.0
TGSD_MIN_PHI = -8.0
TGSD_MAX_PHI = 10.0
PHASE_METEOROLOGY = {'eruption': {'pressure_level_hpa': 50, 'source': 'tmy'}}

def monophase_config() -> EruptionPhaseConfig:
    """Return the single eruptive phase used by the monophase scenario."""
    return EruptionPhaseConfig(name='eruption', parameters=[ParameterConfig(key='column_height', name='Column height', units='m', distribution='uniform', parameters={'low': 15000, 'high': 25000}, bounds=BoundsConfig(minimum=15000, maximum=25000)), ParameterConfig(key='duration', name='Equivalent eruptive duration', units='h', distribution='uniform', parameters={'low': 0.25, 'high': 6.0}, bounds=BoundsConfig(minimum=0.25, maximum=6.0)), ParameterConfig(key='mean_phi', name='Mean TGSD', units='phi', distribution='uniform', parameters={'low': -2.0, 'high': 2.0}, bounds=BoundsConfig(minimum=-2.0, maximum=2.0)), ParameterConfig(key='sorting_phi', name='TGSD sorting', units='phi', distribution='uniform', parameters={'low': 2.0, 'high': 2.5}, bounds=BoundsConfig(minimum=2.0, maximum=2.5)), ParameterConfig(key='aggregation_fraction', name='Aggregation fraction', units='fraction', distribution='uniform', parameters={'low': 0.1, 'high': 0.5}, bounds=BoundsConfig(minimum=0.1, maximum=0.5)), ParameterConfig(key='aggregate_density', name='Aggregate density', units='kg m-3', distribution='uniform', parameters={'low': 100.0, 'high': 700.0}, bounds=BoundsConfig(minimum=100.0, maximum=700.0))])

def phase_configs() -> list[EruptionPhaseConfig]:
    """Return the active eruptive phases."""
    return [monophase_config()]

def phase_mass_fraction_constraints():
    """Return no phase-mass-fraction constraints for a monophase scenario."""
    return ()

def validate_scenario_configuration() -> None:
    """Validate the internal consistency of the monophase configuration."""
    if SCENARIO_TYPE.lower().strip() != 'monophase':
        raise ValueError("This configuration file defines a monophase scenario only. SCENARIO_TYPE must be 'monophase'.")
    phases = phase_configs()
    if len(phases) != 1:
        raise ValueError('A monophase scenario must contain exactly one eruptive phase.')
    phase_name = phases[0].name
    if set(PHASE_METEOROLOGY) != {phase_name}:
        raise ValueError(f'PHASE_METEOROLOGY must contain exactly the active phase name. phase={phase_name!r}, meteorology={list(PHASE_METEOROLOGY)!r}')
    settings = PHASE_METEOROLOGY[phase_name]
    if 'pressure_level_hpa' not in settings:
        raise KeyError(f'{phase_name}: pressure_level_hpa is required.')
    pressure_level = float(settings['pressure_level_hpa'])
    if pressure_level <= 0:
        raise ValueError(f'{phase_name}: pressure_level_hpa must be > 0.')
    source = str(settings.get('source', '')).lower().strip()
    if source not in {'tmy', 'historical'}:
        raise ValueError(f"{phase_name}: source must be 'tmy' or 'historical'.")
    height_reference = str(COLUMN_HEIGHT_REFERENCE).lower().strip()
    if height_reference not in {'asl', 'above_vent'}:
        raise ValueError("COLUMN_HEIGHT_REFERENCE must be 'asl' or 'above_vent'.")
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
ATLAS_DRY_RUN = True
