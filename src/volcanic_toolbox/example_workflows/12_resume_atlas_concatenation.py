"""Concatenate existing pressure/single NetCDF chunks without downloading.

This is useful when example 11 already downloaded and converted the data but
was interrupted before the final ``YYYYMMDD.era5.nc`` files were completed.
"""
from pathlib import Path
from volcanic_toolbox.preprocessing.output import ScenarioOutputManager
from volcanic_toolbox.processing.atlas.workflow import _group_jobs, _process_phase_date
from volcanic_toolbox.processing.atlas import AtlasERA5DownloadConfig, prepare_atlas_era5_downloads
from scenario_config import ATLAS_AREA, ATLAS_DAYS_AFTER, ATLAS_GRIB_TO_NETCDF_EXECUTABLE, ATLAS_KEEP_GRIB, ATLAS_NETCDF_COMPRESSION_LEVEL, ATLAS_NETCDF_DATA_TYPE, ATLAS_NETCDF_KIND, SCENARIO_NAME
outputs = ScenarioOutputManager(scenario_name=SCENARIO_NAME).ensure()
scenario_table = outputs.scenarios_dir / 'valid_multiphase_vei4.csv'
config = AtlasERA5DownloadConfig(scenario_table=scenario_table, area=ATLAS_AREA, output_directory=outputs.atlas_dir, days_after=ATLAS_DAYS_AFTER, max_workers=1, overwrite=False, dry_run=False, keep_grib=ATLAS_KEEP_GRIB, grib_to_netcdf_executable=ATLAS_GRIB_TO_NETCDF_EXECUTABLE, netcdf_kind=ATLAS_NETCDF_KIND, netcdf_data_type=ATLAS_NETCDF_DATA_TYPE, netcdf_compression_level=ATLAS_NETCDF_COMPRESSION_LEVEL)
preparation = prepare_atlas_era5_downloads(config)
for key, jobs in _group_jobs(preparation.jobs).items():
    phase, initial_date = key
    print(f'Processing {phase} / {initial_date}')
    for message in _process_phase_date(jobs, config):
        print(' ', message)
