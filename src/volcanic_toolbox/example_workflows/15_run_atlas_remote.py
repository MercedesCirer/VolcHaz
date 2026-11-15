"""Optional ATLAS application example: execute prepared runs through SSH/MPI."""
from volcanic_toolbox.processing.atlas.remote import run_atlas_remote
from atlas_remote_config import ATLAS_REMOTE_CONFIG
summary = run_atlas_remote(ATLAS_REMOTE_CONFIG)
print('\nRemote ATLAS summary:')
if summary.empty:
    print('No runs.')
else:
    print(summary.groupby(['phase', 'status'], dropna=False).size().rename('count').reset_index().to_string(index=False))
