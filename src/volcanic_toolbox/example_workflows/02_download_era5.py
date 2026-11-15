from pathlib import Path
from volcanic_toolbox.preprocessing.meteorology import bbox_around_point, download_era5_range
from scenario_config import SCENARIO_NAME, LATITUDE, LONGITUDE, YEARS, PHASE_METEOROLOGY
ERA5_HALF_BOX_DEGREES = 0.25
ERA5_TIMES_UTC = ("00:00", "06:00", "12:00", "18:00")
ERA5_OVERWRITE = False

for phase, cfg in PHASE_METEOROLOGY.items():
    output = Path('data') / 'era5' / SCENARIO_NAME / phase
    area = bbox_around_point(LATITUDE, LONGITUDE, ERA5_HALF_BOX_DEGREES, ERA5_HALF_BOX_DEGREES)
    download_era5_range(year_start=YEARS[0], year_end=YEARS[1], pressure_levels_hpa=[cfg['pressure_level_hpa']], area=area, output_directory=output, times=ERA5_TIMES_UTC, overwrite=ERA5_OVERWRITE)
    print(phase, output)
