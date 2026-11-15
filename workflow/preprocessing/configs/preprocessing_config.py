# HOW TO EDIT THIS FILE (NO PROGRAMMING REQUIRED)
# - The text after # explains a setting and is not executed.
# - Change only the value to the right of = or :; keep the name on the left.
# - A dictionary {...} is just a named group of settings, not a function.
# - Keep the quotes around text, commas between entries, and opening/closing brackets.
# - Write True or False exactly as shown. None means automatic/not specified.
# - (2010, 2020) is a pair; [ ... ] is a list of repeated entries.
# - Example: change 'SCENARIO_NAME': 'lascar_tmy' to 'SCENARIO_NAME': 'my_case'.
# - Do not change units without converting the corresponding numerical values.
# - After scientific changes, rerun the steps that generate the affected data.
# - Run workflow/run.py --check to validate the three configs and their consistency.
#
# =============================================================================
# PREPROCESSING CONFIGURATION
# =============================================================================
# Edit data only: do not add imports, functions, or class instances.
# SCENARIO_TYPE selects the corresponding scenario section below.
# Units: m, h, hPa, km³, and kg/m³; fractions are between 0 and 1.

# Active scenario type: "monophase" uses MONOPHASE_SCENARIO; "multiphase" uses
# MULTIPHASE_SCENARIO. Section B is in multiphase_example.txt; copy it into the
# location indicated below before selecting "multiphase".
SCENARIO_TYPE = 'monophase'

# =============================================================================
# A. SINGLE-PHASE SCENARIO
# =============================================================================
# Used when SCENARIO_TYPE = "monophase".
# PHASES and PHASE_METEOROLOGY must use identical phase names.

# Scientific settings for a single eruptive phase. Edit the values below when SCENARIO_TYPE is
# "monophase".
MONOPHASE_SCENARIO = {
    # Application identifier and output folder name. For example, "lascar_tmy" creates
    # outputs/lascar_tmy/. Changing it automatically updates subsequent-stage paths; generate
    # the new scenario outputs before running ATLAS.
    'SCENARIO_NAME': 'lascar_historical',
    # Volcano latitude in decimal degrees, between -90 and 90; southern latitudes are
    # negative. Automatically passed to meteorological extraction and ATLAS.
    'LATITUDE': -23.37,
    # Volcano longitude in decimal degrees, between -180 and 180; western longitudes are
    # negative. Automatically passed to extraction and ATLAS.
    'LONGITUDE': -67.73,
    # Eruptive vent elevation in metres above sea level; nonnegative. Used by MER calculations
    # and ATLAS source coordinates.
    'VENT_ELEVATION_M': 5592.0,
    # Meaning of sampled column heights: "above_vent" means metres above the vent; "asl" means
    # metres above sea level. Processing inherits this reference.
    'COLUMN_HEIGHT_REFERENCE': 'above_vent',
    # Inclusive ERA5 period as (first_year, last_year). Example: (2010, 2020) includes both
    # 2010 and 2020. Rerun meteorological preparation after changing it.
    'YEARS': (2010, 2020),
    # Number of sampled meteorological records for each phase; positive integer. This is not
    # the number of final accepted eruption scenarios.
    'N_METEOROLOGY_SAMPLES': 5000,
    # Named month groups used in scenario summaries. Each value contains month numbers
    # (January=1, December=12). Postprocessing month_groups are configured independently.
    'SEASONS': {
        # Month numbers assigned to the "wet" preprocessing season; 1=January and 12=December.
        'wet': (10, 11, 12, 1, 2, 3, 4),
        # Month numbers assigned to the "dry" preprocessing season; 1=January and 12=December.
        'dry': (5, 6, 7, 8, 9),
    },
    # Volcanic Explosivity Index label for the event. The explicit minimum/maximum fallout-
    # volume values below determine the mass acceptance interval.
    'EVENT_VEI': 4,
    # Lower admissible fallout volume in km³. Converted to mass using BULK_DENSITY_KG_M3.
    # Specify the fallout component represented by the simulations.
    'MINIMUM_FALLOUT_VOLUME_KM3': 0.08,
    # Upper admissible fallout volume in km³; must exceed the lower value. Applies to the
    # total event volume for multiphase scenarios.
    'MAXIMUM_FALLOUT_VOLUME_KM3': 0.12,
    # Bulk deposit density in kg/m³; positive. Converts fallout volume to mass. It is distinct
    # from individual particle or aggregate density.
    'BULK_DENSITY_KG_M3': 1000.0,
    # Lower phi limit of the ATLAS total grain-size distribution. Smaller phi values denote
    # larger grains. This is a model limit, not a sampled mean.
    'TGSD_MIN_PHI': -8.0,
    # Upper phi limit of the ATLAS grain-size distribution; greater than TGSD_MIN_PHI. Larger
    # phi values denote smaller grains.
    'TGSD_MAX_PHI': 10.0,
    # Meteorological settings keyed by phase name. Every name must also occur in PHASES, with
    # exactly the same spelling.
    'PHASE_METEOROLOGY': {
        # Meteorological settings for phase "eruption"; the name must match an entry in
        # PHASES.
        'eruption': {
            # Representative ERA5 pressure level in hPa, such as 50 or 100. Used to
            # characterize wind and estimate MER; complete ATLAS forcing uses additional
            # atmospheric information.
            'pressure_level_hpa': 50,
            # Meteorological source: "historical" samples the complete prepared record; "tmy"
            # samples the constructed typical meteorological year.
            'source': 'historical',
        },
    },
    # List of eruptive phase definitions. A monophase event has one entry; a multiphase event
    # has at least two. Copy a complete phase entry to add another phase.
    'PHASES': [
        # Entry 1: edit the named values within this block.
        {
            # Unique phase name, using lowercase letters, numbers, and underscores. Use the
            # identical name in PHASE_METEOROLOGY and any explicit phase weights/filters.
            'name': 'eruption',
            # Eruptive parameters for this phase. Each entry describes one parameter, its
            # units, distribution, and admissible bounds.
            'parameters': [
                # Entry 1: edit the named values within this block.
                {
                    # Scientific parameter: plume/column height in metres.
                    # COLUMN_HEIGHT_REFERENCE determines whether it is above the vent or above
                    # sea level. Keep the machine key "column_height".
                    'key': 'column_height',
                    # Human-readable label for this eruptive parameter in summaries and plots.
                    # It is separate from the machine identifier in key.
                    'name': 'Column height',
                    # Units of this eruptive parameter, such as "m", "h", "phi", "fraction",
                    # or "kg m-3". Units also determine sampled-table column names; do not
                    # change them without compatible numerical conversion.
                    'units': 'm',
                    # Sampling distribution: "uniform" (low/high), "triangular"
                    # (left/mode/right), "normal" or "gaussian" (mean/std), "fixed" (value),
                    # or "lognormal" (mu/sigma by default).
                    'distribution': 'uniform',
                    # Numeric inputs required by the selected distribution. Example: uniform
                    # uses low/high; triangular uses left/mode/right; normal uses mean/std.
                    'parameters': {
                        # Lower limit of a uniform distribution, in this parameter’s units.
                        'low': 15000,
                        # Upper limit of a uniform distribution; strictly greater than low, in
                        # the same units.
                        'high': 25000,
                    },
                    # Optional inclusive admissible limits for this parameter. They are
                    # separate from the sampling distribution. Out-of-range values are
                    # resampled by default.
                    'bounds': {
                        # Lower inclusive admissible value, in this parameter’s units; None
                        # leaves it unbounded below.
                        'minimum': 15000,
                        # Upper inclusive admissible value, in this parameter’s units; None
                        # leaves it unbounded above.
                        'maximum': 25000,
                    },
                },
                # Entry 2: edit the named values within this block.
                {
                    # Scientific parameter: equivalent eruptive duration of this modeled phase
                    # in hours, not necessarily the chronological duration of the complete
                    # episode. Keep the machine key "duration".
                    'key': 'duration',
                    # Human-readable label for this eruptive parameter in summaries and plots.
                    # It is separate from the machine identifier in key.
                    'name': 'Equivalent eruptive duration',
                    # Units of this eruptive parameter, such as "m", "h", "phi", "fraction",
                    # or "kg m-3". Units also determine sampled-table column names; do not
                    # change them without compatible numerical conversion.
                    'units': 'h',
                    # Sampling distribution: "uniform" (low/high), "triangular"
                    # (left/mode/right), "normal" or "gaussian" (mean/std), "fixed" (value),
                    # or "lognormal" (mu/sigma by default).
                    'distribution': 'uniform',
                    # Numeric inputs required by the selected distribution. Example: uniform
                    # uses low/high; triangular uses left/mode/right; normal uses mean/std.
                    'parameters': {
                        # Lower limit of a uniform distribution, in this parameter’s units.
                        'low': 0.25,
                        # Upper limit of a uniform distribution; strictly greater than low, in
                        # the same units.
                        'high': 6.0,
                    },
                    # Optional inclusive admissible limits for this parameter. They are
                    # separate from the sampling distribution. Out-of-range values are
                    # resampled by default.
                    'bounds': {
                        # Lower inclusive admissible value, in this parameter’s units; None
                        # leaves it unbounded below.
                        'minimum': 0.25,
                        # Upper inclusive admissible value, in this parameter’s units; None
                        # leaves it unbounded above.
                        'maximum': 6.0,
                    },
                },
                # Entry 3: edit the named values within this block.
                {
                    # Scientific parameter: mean total grain-size distribution in phi units.
                    # Larger phi means finer particles. Keep the machine key "mean_phi".
                    'key': 'mean_phi',
                    # Human-readable label for this eruptive parameter in summaries and plots.
                    # It is separate from the machine identifier in key.
                    'name': 'Mean TGSD',
                    # Units of this eruptive parameter, such as "m", "h", "phi", "fraction",
                    # or "kg m-3". Units also determine sampled-table column names; do not
                    # change them without compatible numerical conversion.
                    'units': 'phi',
                    # Sampling distribution: "uniform" (low/high), "triangular"
                    # (left/mode/right), "normal" or "gaussian" (mean/std), "fixed" (value),
                    # or "lognormal" (mu/sigma by default).
                    'distribution': 'uniform',
                    # Numeric inputs required by the selected distribution. Example: uniform
                    # uses low/high; triangular uses left/mode/right; normal uses mean/std.
                    'parameters': {
                        # Lower limit of a uniform distribution, in this parameter’s units.
                        'low': -2.0,
                        # Upper limit of a uniform distribution; strictly greater than low, in
                        # the same units.
                        'high': 2.0,
                    },
                    # Optional inclusive admissible limits for this parameter. They are
                    # separate from the sampling distribution. Out-of-range values are
                    # resampled by default.
                    'bounds': {
                        # Lower inclusive admissible value, in this parameter’s units; None
                        # leaves it unbounded below.
                        'minimum': -2.0,
                        # Upper inclusive admissible value, in this parameter’s units; None
                        # leaves it unbounded above.
                        'maximum': 2.0,
                    },
                },
                # Entry 4: edit the named values within this block.
                {
                    # Scientific parameter: TGSD spread/sorting in phi units; use physically
                    # meaningful positive values. Keep the machine key "sorting_phi".
                    'key': 'sorting_phi',
                    # Human-readable label for this eruptive parameter in summaries and plots.
                    # It is separate from the machine identifier in key.
                    'name': 'TGSD sorting',
                    # Units of this eruptive parameter, such as "m", "h", "phi", "fraction",
                    # or "kg m-3". Units also determine sampled-table column names; do not
                    # change them without compatible numerical conversion.
                    'units': 'phi',
                    # Sampling distribution: "uniform" (low/high), "triangular"
                    # (left/mode/right), "normal" or "gaussian" (mean/std), "fixed" (value),
                    # or "lognormal" (mu/sigma by default).
                    'distribution': 'uniform',
                    # Numeric inputs required by the selected distribution. Example: uniform
                    # uses low/high; triangular uses left/mode/right; normal uses mean/std.
                    'parameters': {
                        # Lower limit of a uniform distribution, in this parameter’s units.
                        'low': 2.0,
                        # Upper limit of a uniform distribution; strictly greater than low, in
                        # the same units.
                        'high': 2.5,
                    },
                    # Optional inclusive admissible limits for this parameter. They are
                    # separate from the sampling distribution. Out-of-range values are
                    # resampled by default.
                    'bounds': {
                        # Lower inclusive admissible value, in this parameter’s units; None
                        # leaves it unbounded below.
                        'minimum': 2.0,
                        # Upper inclusive admissible value, in this parameter’s units; None
                        # leaves it unbounded above.
                        'maximum': 2.5,
                    },
                },
                # Entry 5: edit the named values within this block.
                {
                    # Scientific parameter: aggregation fraction passed to ATLAS, from 0 to 1.
                    # It is automatically converted to percentage during input generation.
                    # Keep the machine key "aggregation_fraction".
                    'key': 'aggregation_fraction',
                    # Human-readable label for this eruptive parameter in summaries and plots.
                    # It is separate from the machine identifier in key.
                    'name': 'Aggregation fraction',
                    # Units of this eruptive parameter, such as "m", "h", "phi", "fraction",
                    # or "kg m-3". Units also determine sampled-table column names; do not
                    # change them without compatible numerical conversion.
                    'units': 'fraction',
                    # Sampling distribution: "uniform" (low/high), "triangular"
                    # (left/mode/right), "normal" or "gaussian" (mean/std), "fixed" (value),
                    # or "lognormal" (mu/sigma by default).
                    'distribution': 'uniform',
                    # Numeric inputs required by the selected distribution. Example: uniform
                    # uses low/high; triangular uses left/mode/right; normal uses mean/std.
                    'parameters': {
                        # Lower limit of a uniform distribution, in this parameter’s units.
                        'low': 0.1,
                        # Upper limit of a uniform distribution; strictly greater than low, in
                        # the same units.
                        'high': 0.5,
                    },
                    # Optional inclusive admissible limits for this parameter. They are
                    # separate from the sampling distribution. Out-of-range values are
                    # resampled by default.
                    'bounds': {
                        # Lower inclusive admissible value, in this parameter’s units; None
                        # leaves it unbounded below.
                        'minimum': 0.1,
                        # Upper inclusive admissible value, in this parameter’s units; None
                        # leaves it unbounded above.
                        'maximum': 0.5,
                    },
                },
                # Entry 6: edit the named values within this block.
                {
                    # Scientific parameter: aggregate density in kg/m³, distinct from bulk
                    # deposit density. Keep the machine key "aggregate_density".
                    'key': 'aggregate_density',
                    # Human-readable label for this eruptive parameter in summaries and plots.
                    # It is separate from the machine identifier in key.
                    'name': 'Aggregate density',
                    # Units of this eruptive parameter, such as "m", "h", "phi", "fraction",
                    # or "kg m-3". Units also determine sampled-table column names; do not
                    # change them without compatible numerical conversion.
                    'units': 'kg m-3',
                    # Sampling distribution: "uniform" (low/high), "triangular"
                    # (left/mode/right), "normal" or "gaussian" (mean/std), "fixed" (value),
                    # or "lognormal" (mu/sigma by default).
                    'distribution': 'uniform',
                    # Numeric inputs required by the selected distribution. Example: uniform
                    # uses low/high; triangular uses left/mode/right; normal uses mean/std.
                    'parameters': {
                        # Lower limit of a uniform distribution, in this parameter’s units.
                        'low': 100.0,
                        # Upper limit of a uniform distribution; strictly greater than low, in
                        # the same units.
                        'high': 700.0,
                    },
                    # Optional inclusive admissible limits for this parameter. They are
                    # separate from the sampling distribution. Out-of-range values are
                    # resampled by default.
                    'bounds': {
                        # Lower inclusive admissible value, in this parameter’s units; None
                        # leaves it unbounded below.
                        'minimum': 100.0,
                        # Upper inclusive admissible value, in this parameter’s units; None
                        # leaves it unbounded above.
                        'maximum': 700.0,
                    },
                },
            ],
        },
    ],
}


# =============================================================================
# B. MULTIPHASE SCENARIO — EXTERNAL REFERENCE
# =============================================================================
# The complete section B is stored in multiphase_example.txt in this directory
# (workflow/preprocessing/configs/multiphase_example.txt).
# It is a reference note and is not loaded automatically.
# To use a multiphase event, copy its entire MULTIPHASE_SCENARIO = {...} block
# into this position, before section C, then set SCENARIO_TYPE = "multiphase".
# For a monophase event, leave this block in the note and keep
# SCENARIO_TYPE = "monophase"; no MULTIPHASE_SCENARIO definition is required.

# =============================================================================
# C. COMPLETE-STAGE EXECUTION
# =============================================================================
# These flags apply to preprocessing/run_all.py.

# True runs the candidate-parameter preview in the complete preprocessing sequence; False
# skips that diagnostic unless RUN_PARAMETER_COMPARISON is True. In that case,
# step 01 runs automatically to provide a fresh reference sample for step 09.
RUN_PREVIEW = True

# True includes the ERA5 download in preprocessing/run_all.py. False reuses files already
# present; the standalone step 02 always performs the download/reuse operation.
# Existing raw ERA5 files belong in data/era5/<SCENARIO_NAME>/<phase_name>/.
# For the current monophase example: data/era5/lascar_historical/eruption/*.nc.
# This flag applies equally to historical and TMY scenarios.
# source="tmy" constructs a TMY in step 03; it does not enable downloading.
DOWNLOAD_METEOROLOGY = False

# True includes the annual/monthly wind-rose diagnostic in the complete preprocessing
# sequence.
RUN_WIND_ROSES = True

# True includes scenario pairplots after physical scenario generation in the complete
# preprocessing sequence.
RUN_SCENARIO_PLOTS = True

# True includes step 08 after scenario generation: compare the full historical or TMY
# wind distribution with winds associated with accepted scenarios. Saves a side-by-side
# wind-rose figure per phase using common direction/speed bins and scales.
# False skips this comparison in "all"; standalone step 08 remains available.
RUN_WIND_COMPARISON = True

# True includes step 09: compare each candidate eruptive-parameter distribution from
# step 01 with the accepted scenarios from step 06. Saves comparative histograms and
# a CSV of descriptive statistics per phase. The step 01 sample is an independent
# reference sample, not the complete set of attempts evaluated in step 06.
# Step 01 runs automatically when this flag is True, even if RUN_PREVIEW is False,
# so the reference reflects the current configuration rather than an older run.
# False skips this comparison in "all"; standalone step 09 remains available.
# These diagnostic flags do not change the accepted scenarios or run the model.
RUN_PARAMETER_COMPARISON = True

# =============================================================================
# 01. ERUPTIVE PARAMETER PREVIEW
# =============================================================================

# Number of unvalidated candidate parameter samples per phase; positive integer. Independent
# of the final accepted-scenario target.
PREVIEW_NUMBER_OF_CANDIDATES = 1000

# Integer random seed for reproducible sampling/subsampling; None permits a nondeterministic
# sequence.
PREVIEW_RANDOM_SEED = 42

# Number of histogram bins; positive integer. Changes plot detail, not the scientific sample.
PREVIEW_HISTOGRAM_BINS = 30

# True scales histograms to probability density; False shows counts.
PREVIEW_HISTOGRAM_DENSITY = True

# True overlays the candidate distribution’s theoretical probability-density curve.
PREVIEW_OVERLAY_THEORETICAL_PDF = True

# True displays figures interactively; False saves and closes them.
PREVIEW_SHOW_FIGURES = False

# =============================================================================
# 02. ERA5 DOWNLOAD
# =============================================================================
# Coordinates, inclusive years, and phase pressure levels come from the selected scenario.
# ERA5_HALF_BOX_DEGREES is the half-width in latitude and longitude.
# Times are expressed in UTC.

# Half-width of the small preprocessing ERA5 extraction box in geographic degrees. 0.25 gives
# a box extending 0.25 degrees from the volcano in each direction. Separate from the complete
# ATLAS domain.
ERA5_HALF_BOX_DEGREES = 0.25

# ERA5 observation times, in UTC, as quoted "HH:MM" values. Example: ("00:00", "06:00",
# "12:00", "18:00").
ERA5_TIMES_UTC = ('00:00', '06:00', '12:00', '18:00')

# True replaces existing preprocessing ERA5 files; False reuses readable files that are
# already available.
ERA5_OVERWRITE = False

# =============================================================================
# 03. METEOROLOGICAL PREPARATION
# =============================================================================

# Settings controlling typical meteorological year (TMY) selection; relevant to phases whose
# source is "tmy".
TMY_SETTINGS = {
    # Relative weight of wind-speed agreement in TMY month selection; nonnegative. Used
    # together with direction_weight.
    'speed_weight': 0.3,
    # Relative weight of wind-direction agreement in TMY selection; nonnegative. At least one
    # of the two weights must be positive.
    'direction_weight': 0.7,
    # Number of wind-speed histogram bins used in TMY comparison; positive integer.
    'speed_bins': 28,
    # Number of directional histogram bins used in TMY comparison; positive integer.
    'direction_bins': 28,
}

# =============================================================================
# 04. METEOROLOGICAL SAMPLING
# =============================================================================

# Random meteorological sampling settings. The sample count comes from N_METEOROLOGY_SAMPLES
# in the selected scenario.
METEOROLOGY_SAMPLE_SETTINGS = {
    # Random seed: use an integer for reproducible draws or None for a nondeterministic
    # sequence.
    'seed': 42,
    # True samples meteorological records with replacement, allowing repeated records; False
    # samples without replacement.
    'replace': True,
}

# =============================================================================
# 05. ANNUAL AND MONTHLY WIND ROSES
# =============================================================================
# The meteorological source is taken from PHASE_METEOROLOGY.

# Wind direction convention: "from" is the meteorological direction from which wind
# originates; "to" shows where it travels.
WIND_ROSE_DIRECTION_CONVENTION = 'from'

# True uses daily vector-mean winds for monthly roses; False uses individual records. The
# annual rose uses the input records.
WIND_ROSE_USE_DAILY_VECTOR_MEANS = True

# True displays frequencies as percentages; False displays counts. Applies to both annual and
# monthly wind roses.
WIND_ROSE_PERCENTAGE = True

# =============================================================================
# 06. PHYSICALLY ADMISSIBLE SCENARIO GENERATION
# =============================================================================

# Descriptive provenance for event constraints; this does not replace the scientific volume
# and density settings in the selected scenario.
VEI_METADATA = {
    # Bibliographic reference or provenance text explaining the chosen event constraints. Does
    # not affect numerical calculations.
    'source_reference': 'scenario_config.py',
}

# Controls final physically accepted scenarios, stopping limits, and reproducibility. Rejected
# candidates do not count toward the target.
SCENARIO_BUILD_SETTINGS = {
    # Requested number of physically accepted scenarios; positive integer. Increase for the
    # final scientific ensemble after a small operational test.
    'target_valid_scenarios': 1000,
    # Number of candidate combinations evaluated per batch; positive integer. Larger batches
    # can improve throughput but consume more memory.
    'batch_size': 1000,
    # Maximum total candidate combinations evaluated before stopping. Must be at least
    # target_valid_scenarios. Reaching this limit may produce fewer accepted scenarios than
    # requested.
    'max_attempts': 200000,
    # Random seed: use an integer for reproducible draws or None for a nondeterministic
    # sequence.
    'seed': 42,
    # Name of the prepared wind-speed column; normally "wind_speed_m_s". Advanced setting:
    # keep unchanged unless the input tables use another compatible name.
    'wind_column': 'wind_speed_m_s',
    # Name of the meteorological timestamp column; normally "datetime". Keep unchanged for
    # toolbox-generated tables.
    'datetime_column': 'datetime',
    # True allows a meteorological record to be paired with multiple eruption candidates.
    # False restricts repeated records within sampling.
    'sample_meteorology_with_replacement': True,
}

# =============================================================================
# 07. SCENARIO PAIRPLOTS
# =============================================================================

# Maximum plotted/subsampled points for pairplots; limits drawing cost without changing the
# stored scenario ensemble.
SCENARIO_PLOTS_MAX_POINTS = 5000

# Integer random seed for reproducible sampling/subsampling; None permits a nondeterministic
# sequence.
SCENARIO_PLOTS_RANDOM_SEED = 42

# Saved figure resolution in dots per inch.
SCENARIO_PLOTS_DPI = 300

# Prefix for diagnostic plot filenames; does not change scenario identity.
SCENARIO_PLOTS_FILENAME_PREFIX = 'scenario_pairplot'

# Scenario-table metrics included in pairplots. Keep valid generated column/metric
# identifiers.
SCENARIO_PLOTS_PAIRPLOT_METRICS = None

# =============================================================================
# 08. WIND COMPARISON
# =============================================================================

# Number of directional sectors in wind comparisons; positive integer.
WIND_COMPARISON_DIRECTION_BINS = 16

# Number of speed classes in wind comparisons; positive integer.
WIND_COMPARISON_SPEED_BINS = 5

# Saved figure resolution in dots per inch.
WIND_COMPARISON_DPI = 300

# =============================================================================
# 09. ERUPTIVE PARAMETER COMPARISON
# =============================================================================

# Number of histogram bins; positive integer. Changes plot detail, not the scientific sample.
PARAMETER_COMPARISON_HISTOGRAM_BINS = 30

# True displays probability-density histograms; False displays counts.
PARAMETER_COMPARISON_DENSITY = True

# Saved figure resolution in dots per inch.
PARAMETER_COMPARISON_DPI = 300

# True displays figures interactively; False saves and closes them.
PARAMETER_COMPARISON_SHOW_FIGURES = True

# =============================================================================
# 10. PHASE-METEOROLOGY PAIRING INSPECTION
# =============================================================================
# This diagnostic uses the selected scenario and generated tables; no additional settings are required.



