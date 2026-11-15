"""Download ERA5, convert GRIB and create final ATLAS meteorology files.

The workflow is resumable for every phase/date folder:

1. If ``YYYYMMDD.era5.nc`` is complete, skip the folder.
2. Otherwise, download only missing GRIB/NetCDF products.
3. Convert GRIB to the intermediate pressure/single NetCDF files.
4. Create or append the final ``YYYYMMDD.era5.nc`` file.
5. Continue with the next phase/date folder.
"""
from volcanic_toolbox.preprocessing.output import ScenarioOutputManager
from volcanic_toolbox.processing.atlas import AtlasERA5DownloadConfig, execute_atlas_era5_downloads, prepare_atlas_era5_downloads
from scenario_config import ATLAS_AREA, ATLAS_DAYS_AFTER, ATLAS_DRY_RUN, ATLAS_GRIB_TO_NETCDF_EXECUTABLE, ATLAS_KEEP_GRIB, ATLAS_MAX_WORKERS, ATLAS_NETCDF_COMPRESSION_LEVEL, ATLAS_NETCDF_DATA_TYPE, ATLAS_NETCDF_KIND, ATLAS_OVERWRITE, EVENT_VEI, SCENARIO_NAME, SCENARIO_TYPE
outputs = ScenarioOutputManager(scenario_name=SCENARIO_NAME).ensure()
scenario_type = SCENARIO_TYPE.strip().lower()
if scenario_type not in {'monophase', 'multiphase'}:
    raise ValueError(f"SCENARIO_TYPE must be 'monophase' or 'multiphase'. Received: {SCENARIO_TYPE!r}")
scenario_table = outputs.scenarios_dir / f'valid_{scenario_type}_vei{EVENT_VEI}.csv'
if not scenario_table.exists():
    raise FileNotFoundError(f'Missing {scenario_table}. Run the physically constrained scenario-building example first.')
print('=' * 79)
print('ATLAS ERA5 PREPARATION')
print('=' * 79)
print(f'Scenario:      {SCENARIO_NAME}')
print(f'Scenario type: {scenario_type}')
print(f'VEI:           {EVENT_VEI}')
print(f'Scenario table: {scenario_table}')
print()
config = AtlasERA5DownloadConfig(scenario_table=scenario_table, area=ATLAS_AREA, output_directory=outputs.atlas_dir, days_after=ATLAS_DAYS_AFTER, max_workers=ATLAS_MAX_WORKERS, overwrite=ATLAS_OVERWRITE, dry_run=ATLAS_DRY_RUN, keep_grib=ATLAS_KEEP_GRIB, grib_to_netcdf_executable=ATLAS_GRIB_TO_NETCDF_EXECUTABLE, netcdf_kind=ATLAS_NETCDF_KIND, netcdf_data_type=ATLAS_NETCDF_DATA_TYPE, netcdf_compression_level=ATLAS_NETCDF_COMPRESSION_LEVEL)
preparation = prepare_atlas_era5_downloads(config)
print('Detected phases:', ', '.join(preparation.phase_names))
print('Scenario-phase rows:', f'{len(preparation.manifest):,}')
print('Unique calendar dates:', f'{preparation.unique_initial_dates:,}')
print('Unique phase-date combinations:', f'{preparation.unique_phase_dates:,}')
print('Monthly date groups:', f'{len(preparation.jobs):,}')
print('Total file requests (pressure + single):', f'{preparation.total_file_requests:,}')
print('\nCoverage by phase:')
print(preparation.coverage_summary.to_string(index=False))
print('\nManifest:', preparation.manifest_path)
print('Exhaustive download plan:', preparation.download_plan_path)
print('Coverage summary:', preparation.coverage_summary_path)
print('Detailed JSON preview:', preparation.request_preview_path)
execute_atlas_era5_downloads(preparation, config)
if config.dry_run:
    print('Dry run completed; no downloads submitted.')
else:
    print('Download, GRIB conversion and ATLAS concatenation completed.')
