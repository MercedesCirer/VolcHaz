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
# PROCESSING CONFIGURATION
# =============================================================================
# Edit data only: no imports, functions, or class instances.
# Scenario identity and phase names are inherited from preprocessing.



# =============================================================================
# 01. COMPLETE ATLAS METEOROLOGY
# =============================================================================
# ATLAS_AREA order: north, west, south, east (degrees).
# ATLAS_DRY_RUN=True prepares requests without downloading data.

# Complete ERA5 forcing domain as (north, west, south, east), in decimal degrees. Must cover
# the simulation region; this ordering differs from map extents.
ATLAS_AREA = (-20.63, -74.35, -41.18, -49.31)

# Number of additional calendar days after eruption onset included in the forcing; nonnegative
# integer. The eruption day is also included.
ATLAS_DAYS_AFTER = 5

# Maximum concurrent complete-forcing download workers; positive integer. Start with 1.
ATLAS_MAX_WORKERS = 1

# True replaces complete ATLAS meteorology files; False reuses compatible files that are
# already complete.
ATLAS_OVERWRITE = False

# True retains downloaded GRIB files after successful conversion; False removes intermediate
# GRIB files when the workflow allows it.
ATLAS_KEEP_GRIB = False

# Executable name or full path of the GRIB-to-NetCDF converter. "grib_to_netcdf" requires the
# program to be available on the executable search path.
ATLAS_GRIB_TO_NETCDF_EXECUTABLE = 'grib_to_netcdf'

# NetCDF format code accepted by the converter: 1, 2, 3, or 4. Compression is supported by
# this workflow only with kinds 3 or 4.
ATLAS_NETCDF_KIND = 3

# Numeric type requested from the converter, such as "NC_FLOAT". Keep compatible with the
# installed converter and ATLAS.
ATLAS_NETCDF_DATA_TYPE = 'NC_FLOAT'

# NetCDF compression level, integer 0-9; 0 disables compression. Higher levels can reduce disk
# size at greater processing cost.
ATLAS_NETCDF_COMPRESSION_LEVEL = 4

# True writes the complete-forcing request plan without downloading; False retrieves,
# converts, and concatenates the required meteorology.
ATLAS_DRY_RUN = True

# =============================================================================
# 02. RESUME METEOROLOGICAL CONCATENATION
# =============================================================================
# Uses the complete ATLAS meteorology settings above; no duplicate settings are required.



# =============================================================================
# 03. ATLAS MODEL INPUTS
# =============================================================================

# Remote parent directory containing the ATLAS installation, written into model inputs.
# Together with ATLAS_DIRECTORY_NAME it must identify the same installation as
# REMOTE_ATLAS_ROOT.
ATLAS_INSTALL_BASE = '/users/your_username'

# ATLAS installation folder name under ATLAS_INSTALL_BASE, for example "ATLAS-1.0".
ATLAS_DIRECTORY_NAME = 'ATLAS-1.0'

# Run naming: "date_and_scenario" keeps separate folders for each date/scenario combination;
# "date_only" requires dates to uniquely identify runs.
ATLAS_RUN_FOLDER_MODE = 'date_and_scenario'

# True requires actual local forcing files when generating inputs; False permits the
# configured fallback meteorological duration.
ATLAS_REQUIRE_LOCAL_METEOROLOGY = False

# Number of hourly forcing records assumed only when local forcing is not required and
# unavailable. 144 represents six days.
ATLAS_FALLBACK_METEOROLOGY_HOURS = 144

# True replaces generated ATLAS input files; False preserves existing inputs where supported.
ATLAS_INPUT_OVERWRITE = True

# Shared ATLAS numerical and output settings. These are model controls, not candidate eruption
# parameters.
ATLAS_MAIN_INPUT = {
    # ATLAS integration time step in seconds; positive.
    'time_step_seconds': 15,
    # ATLAS restart keyword, normally "no" for a new simulation; use syntax accepted by the
    # installed model.
    'restart': 'no',
    # Model-domain top altitude in metres.
    'ztop_m': 55000,
    # Model vertical grid spacing in metres; positive.
    'vertical_resolution_m': 1000,
    # Model longitude grid spacing in degrees; positive.
    'longitude_resolution_deg': 0.25,
    # Model latitude grid spacing in degrees; positive.
    'latitude_resolution_deg': 0.25,
    # Hours between ATLAS output records. Keep postprocessing dt_hours consistent with the
    # actual saved interval.
    'output_frequency_h': 1,
    # ATLAS vertical-output layer specification as a string; retain model-compatible syntax.
    'vertical_layers': '1000',
    # ATLAS option controlling separate class output, usually "yes" or "no" according to model
    # syntax.
    'output_classes': 'no',
    # ATLAS option controlling separate phase output, according to model syntax.
    'output_phases': 'no',
    # ATLAS option controlling tracked-point output, according to model syntax.
    'output_track_points': 'no',
    # ATLAS terminal-velocity model code. Keep a value supported by the installed ATLAS
    # version.
    'terminal_velocity_model': 1,
    # ATLAS meteorological postprocessing option, normally "no" in the current workflow.
    'meteo_postprocess': 'no',
}

# Human-readable volcano label written into ATLAS inputs. Update when changing volcano; source
# coordinates and elevation are inherited from preprocessing.
ATLAS_VOLCANO_NAME = 'Lascar'

# Number of numerical particles released by ATLAS; positive integer. More particles increase
# computational cost and can reduce particle-sampling noise.
ATLAS_NUMBER_PARTICLES = 5000000

# ATLAS mass-flow specification or model keyword, such as "ESTIMATE-DEGRUYTER". Must be
# supported by the installed ATLAS version.
ATLAS_MASS_FLOW_RATE = 'ESTIMATE-DEGRUYTER'

# Suzuki vertical-source distribution parameter A; dimensionless. Interpret and select with
# the installed ATLAS formulation.
ATLAS_SUZUKI_A = 4.0

# Suzuki vertical-source distribution parameter L; dimensionless. Model control for the
# vertical release distribution.
ATLAS_SUZUKI_L = 5.0

# Top-hat source diameter in metres, used by the applicable ATLAS source formulation.
ATLAS_TOP_HAT_DIAMETER_M = 2000.0

# ATLAS granulometry specification or keyword; "NONE" retains the current model-input
# convention. Use a value supported by ATLAS.
ATLAS_PHASE_GRANULOMETRY = 'NONE'

# ATLAS grain-size distribution keyword, for example "GAUSSIAN"; must match the model syntax.
ATLAS_DISTRIBUTION = 'GAUSSIAN'

# Number of ATLAS grain-size classes/bins; positive integer.
ATLAS_NUMBER_OF_BINS = 14

# Fallback TGSD mean in phi units, used only if the phase lacks a sampled mean_phi parameter.
ATLAS_DEFAULT_MEAN_PHI = -0.413

# Fallback TGSD sorting in phi units, used only if the phase lacks a sampled sorting_phi
# parameter.
ATLAS_DEFAULT_SORTING_PHI = 2.809

# ATLAS particle density endpoints as (first, second), in kg/m³. Distinct from the bulk
# deposit density used for event mass constraints.
ATLAS_PARTICLE_DENSITY_RANGE_KG_M3 = (1000.0, 2500.0)

# Particle sphericity endpoints, dimensionless, typically within 0-1; follow the model
# convention.
ATLAS_SPHERICITY_RANGE = (0.5, 0.8)

# Aggregate particle size in micrometres; not metres.
ATLAS_AGGREGATE_SIZE_MICRONS = 250.0

# Fallback aggregate density in kg/m³ when no sampled aggregate_density is defined.
ATLAS_DEFAULT_AGGREGATE_DENSITY_KG_M3 = 400.0

# Fallback aggregation percentage, 0-100. Sampled aggregation_fraction values are fractions
# 0-1 and are automatically converted to percent.
ATLAS_DEFAULT_AGGREGATION_PERCENTAGE = 20.0

# =============================================================================
# 04. REMOTE ATLAS EXECUTION
# =============================================================================
# ATLAS_REMOTE_DRY_RUN=True validates the remote environment without launching simulations.
# Use environment variables or SSH keys for authentication; do not store passwords here.

# None runs all manifest phases; otherwise provide phase names as a tuple. Explicit names must
# match the active preprocessing scenario.
ATLAS_REMOTE_PHASES = None

# SSH server hostname or IP address. Replace "your.remote.host" with the actual server.
SSH_HOST = 'your.remote.host'

# SSH port number, normally 22; integer from 1 to 65535.
SSH_PORT = 22

# SSH username on the remote server.
SSH_USER = 'your_username'

# Name of the local environment variable holding the SSH password, not the password itself.
# Key authentication is preferable where available.
SSH_PASSWORD_ENV_VAR = 'ATLAS_SSH_PASSWORD'

# Private-key file path, or None to use available SSH-agent/default key mechanisms. Do not
# insert the key contents.
SSH_PRIVATE_KEY = None

# "reject" requires a previously trusted host key; "auto_add" automatically trusts an unknown
# host. Configure according to the computing environment.
SSH_HOST_KEY_POLICY = 'reject'

# Absolute ATLAS installation directory on the server. Must be consistent with
# ATLAS_INSTALL_BASE and ATLAS_DIRECTORY_NAME.
REMOTE_ATLAS_ROOT = '/users/your_username/ATLAS-1.0'

# Executable path relative to REMOTE_ATLAS_ROOT, such as "Runs/P_ATLAS.1.0.x".
REMOTE_ATLAS_EXECUTABLE = 'Runs/P_ATLAS.1.0.x'

# Number of MPI processes used by the launch command; positive integer compatible with
# allocated resources.
MPI_PROCESSES = 32

# Remote launch command. Supported placeholders: {mpi_processes}, {executable}, {date}, and
# {run_dir}. Adapt to the cluster environment.
LAUNCH_COMMAND_TEMPLATE = 'mpirun -np {mpi_processes} {executable} {date}'

# Optional shell setup commands, such as loading MPI modules; an empty string performs no
# extra setup.
REMOTE_SHELL_PREAMBLE = ''

# True validates SSH, installation, and simulation setup without launching the batch; False
# uploads and runs the simulations.
ATLAS_REMOTE_DRY_RUN = True

# Seconds between remote-status checks; positive.
POLL_SECONDS = 30

# Seconds between SSH reconnection attempts; positive.
RECONNECT_SECONDS = 15

# Maximum SSH reconnection attempts before stopping.
MAX_RECONNECT_ATTEMPTS = 100

# Minimum output-file byte count used in remote completion checks. This size criterion alone
# does not establish scientific validity.
MIN_REMOTE_PART_BYTES = 1

# True permits a nonempty particle output after a failed process exit; False requires the
# stricter completion path. Inspect results from failed exits.
ACCEPT_NONEMPTY_PART_ON_FAILED_EXIT = True

# Seconds between output-availability rechecks after a remote completion marker.
DONE_PART_RECHECK_SECONDS = 10

# Maximum number of output rechecks after completion.
DONE_PART_MAX_RECHECKS = 12

# True cleans up the remote simulation after a verified local result has been obtained.
CLEANUP_REMOTE_SIMULATION = True

# True allows cleanup of remote forcing files once no remaining simulation needs them.
AUTO_DELETE_UNUSED_REMOTE_METEO = True

# True skips runs with missing forcing and continues the batch; False treats missing forcing
# as an error.
SKIP_MISSING_METEOROLOGY = True

# True continues after individual simulation errors; False stops on unexpected errors.
CONTINUE_ON_ERROR = False


