# User settings: edit values, lists, and dictionaries only.
# None selects the default behavior; True/False enables or disables an option.
# Derived fields, including output paths and phase names, are resolved internally.

RUN_ERUPTION_PREVIEW = True

RUN_METEOROLOGY_PREPROCESSING = True

DOWNLOAD_ERA5 = False

RUN_WIND_ROSES = True

RUN_SCENARIO_BUILD = True

RUN_PAIRPLOTS = True

ERUPTION_PREVIEW_SAMPLES = 5000

ERUPTION_PREVIEW_SEED = 42

ERUPTION_HISTOGRAM_BINS = 30

ERUPTION_HISTOGRAM_DENSITY = True

ERUPTION_HISTOGRAM_OVERLAY_PDF = True

ERA5_HALF_BOX_DEGREES = 0.25

ERA5_TIMES_UTC = ('00:00', '06:00', '12:00', '18:00')

ERA5_OVERWRITE = False

TMY_CONFIG = {'speed_weight': 0.3,
 'direction_weight': 0.7,
 'speed_bins': 28,
 'direction_bins': 28,
 'use_daily_means': False}

METEOROLOGY_SAMPLE_CONFIG = {'seed': 42, 'replace': True}

WIND_ROSE_DIRECTION_CONVENTION = 'from'

WIND_ROSE_USE_DAILY_MEANS = True

WIND_ROSE_SPEED_BINS = 5

WIND_ROSE_DIRECTION_BINS = 16

WIND_ROSE_PERCENTAGE = True

WIND_ROSE_DPI = 300

VEI_CONFIG = {'vei': 4,
 'minimum_volume_km3': 0.1,
 'maximum_volume_km3': 1.0,
 'bulk_density_kg_m3': 1000.0,
 'volume_basis': 'bulk_tephra',
 'source_reference': 'Replace with the bibliographic source adopted for the VEI-volume '
                     'range and bulk density.'}

MER_CONFIG = {'alpha': 0.1,
 'beta': 0.5,
 'source_temperature_k': 1200.0,
 'source_heat_capacity_j_kg_k': 1250.0,
 'z1': 2.8}

SCENARIO_BUILD_CONFIG = {'target_valid_scenarios': 1000,
 'batch_size': 1000,
 'max_attempts': 100000,
 'seed': 42,
 'wind_column': 'wind_speed_m_s',
 'datetime_column': 'datetime',
 'sample_meteorology_with_replacement': True}

PHASE_MASS_FRACTION_CONSTRAINTS = ()
