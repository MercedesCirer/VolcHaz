"""Inspect one or more ATLAS .part.nc files before running Stage 5."""
from pathlib import Path
from netCDF4 import Dataset
from scenario_config import SCENARIO_NAME
from volcanic_toolbox.postprocessing.atlas_reader import inspect
runs_root = Path('outputs') / SCENARIO_NAME / 'processing' / 'atlas' / 'runs'
files = sorted(runs_root.rglob('*.part.nc'))
if not files:
    raise FileNotFoundError(f'No *.part.nc files were found below: {runs_root}')
print(f'Found {len(files)} .part.nc file(s).')
print()
for path in files[:5]:
    print('=' * 80)
    print(path)
    with Dataset(path, 'r') as dataset:
        print('Dimensions:')
        for name, dimension in dataset.dimensions.items():
            print(f'  {name}: {len(dimension)}')
        print('Variables:')
        for name, variable in dataset.variables.items():
            print(f'  {name}: dimensions={variable.dimensions}, shape={variable.shape}')
    try:
        grid, names = inspect(path)
        print('Stage 5 inspection: OK')
        print(f'  C3D variable: {names.c3d}')
        print(f'  GL variable:  {names.gl}')
        print(f'  time dimension: {names.time_dimension}')
        print(f'  altitude dimension: {names.alt_dimension}')
        print(f'  latitude dimension: {names.lat_dimension}')
        print(f'  longitude dimension: {names.lon_dimension}')
        print(f'  grid: alt={len(grid.alt)}, lat={len(grid.lat)}, lon={len(grid.lon)}')
    except Exception as error:
        print(f'Stage 5 inspection: ERROR -> {error}')
    print()
