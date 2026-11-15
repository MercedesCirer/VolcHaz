"""User-editable configuration for optional remote ATLAS execution.

Never commit passwords or private-key contents. Password authentication reads
the password from an environment variable; SSH-key authentication is preferred.
"""
from pathlib import Path
from volcanic_toolbox.preprocessing.output import ScenarioOutputManager
from volcanic_toolbox.processing.atlas.remote import AtlasRemoteConfig
from scenario_config import SCENARIO_NAME
outputs = ScenarioOutputManager(scenario_name=SCENARIO_NAME).ensure()
LOCAL_INPUTS_ROOT = outputs.atlas_inputs_dir
LOCAL_METEOROLOGY_ROOT = outputs.atlas_era5_dir
LOCAL_RUNS_ROOT = outputs.atlas_runs_dir
ATLAS_REMOTE_PHASES = None
SSH_HOST = 'your.remote.host'
SSH_PORT = 22
SSH_USER = 'your_username'
SSH_PASSWORD_ENV_VAR = 'ATLAS_SSH_PASSWORD'
SSH_PRIVATE_KEY = None
SSH_HOST_KEY_POLICY = 'reject'
REMOTE_ATLAS_ROOT = '/users/your_username/ATLAS-1.0'
REMOTE_ATLAS_EXECUTABLE = 'Runs/P_ATLAS.1.0.x'
MPI_PROCESSES = 32
LAUNCH_COMMAND_TEMPLATE = 'mpirun -np {mpi_processes} {executable} {date}'
REMOTE_SHELL_PREAMBLE = ''
ATLAS_REMOTE_DRY_RUN = True
POLL_SECONDS = 30
RECONNECT_SECONDS = 15
MAX_RECONNECT_ATTEMPTS = 100
MIN_REMOTE_PART_BYTES = 1
ACCEPT_NONEMPTY_PART_ON_FAILED_EXIT = True
DONE_PART_RECHECK_SECONDS = 10
DONE_PART_MAX_RECHECKS = 12
CLEANUP_REMOTE_SIMULATION = True
AUTO_DELETE_UNUSED_REMOTE_METEO = True
SKIP_MISSING_METEOROLOGY = True
CONTINUE_ON_ERROR = False
ATLAS_REMOTE_CONFIG = AtlasRemoteConfig(scenario_name=SCENARIO_NAME, local_inputs_root=LOCAL_INPUTS_ROOT, local_meteorology_root=LOCAL_METEOROLOGY_ROOT, local_runs_root=LOCAL_RUNS_ROOT, phases=ATLAS_REMOTE_PHASES, ssh_host=SSH_HOST, ssh_port=SSH_PORT, ssh_user=SSH_USER, password_env_var=SSH_PASSWORD_ENV_VAR, private_key_path=SSH_PRIVATE_KEY, host_key_policy=SSH_HOST_KEY_POLICY, remote_atlas_root=REMOTE_ATLAS_ROOT, remote_executable=REMOTE_ATLAS_EXECUTABLE, mpi_processes=MPI_PROCESSES, launch_command_template=LAUNCH_COMMAND_TEMPLATE, remote_shell_preamble=REMOTE_SHELL_PREAMBLE, dry_run=ATLAS_REMOTE_DRY_RUN, poll_seconds=POLL_SECONDS, reconnect_seconds=RECONNECT_SECONDS, max_reconnect_attempts=MAX_RECONNECT_ATTEMPTS, cleanup_remote_simulation=CLEANUP_REMOTE_SIMULATION, auto_delete_unused_remote_meteo=AUTO_DELETE_UNUSED_REMOTE_METEO, accept_nonempty_part_on_failed_exit=ACCEPT_NONEMPTY_PART_ON_FAILED_EXIT, min_remote_part_bytes=MIN_REMOTE_PART_BYTES, done_part_recheck_seconds=DONE_PART_RECHECK_SECONDS, done_part_max_rechecks=DONE_PART_MAX_RECHECKS, skip_missing_meteorology=SKIP_MISSING_METEOROLOGY, continue_on_error=CONTINUE_ON_ERROR)
