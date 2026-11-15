"""Prepare phase-specific meteorological datasets for stochastic sampling.

Supports both source strategies defined in scenario_config.py:

- source="historical":
    saves the complete historical ERA5 wind time series as full_wind_data.csv

- source="tmy":
    saves full_wind_data.csv and also builds/saves the TMY products

The script works for monophase and multiphase scenarios because it iterates
over every phase defined in PHASE_METEOROLOGY.
"""
from pathlib import Path
from volcanic_toolbox.preprocessing.meteorology import TMYConfig, build_phase_tmy, combine_yearly_files, save_phase_meteorology_products
from volcanic_toolbox.preprocessing.output import ScenarioOutputManager
from scenario_config import LATITUDE, LONGITUDE, PHASE_METEOROLOGY, SCENARIO_NAME
outputs = ScenarioOutputManager(scenario_name=SCENARIO_NAME).ensure(PHASE_METEOROLOGY)
TMY_CONFIG = TMYConfig(speed_weight=0.3, direction_weight=0.7, speed_bins=28, direction_bins=28)
for phase, settings in PHASE_METEOROLOGY.items():
    source = str(settings['source']).strip().lower()
    if source not in {'historical', 'tmy'}:
        raise ValueError(f"Phase {phase!r}: source must be 'historical' or 'tmy'; received {settings['source']!r}.")
    pressure_level_hpa = settings['pressure_level_hpa']
    raw_dir = Path('data') / 'era5' / SCENARIO_NAME / phase
    era5_files = sorted(raw_dir.glob('*.nc'))
    if not era5_files:
        raise FileNotFoundError(f'No ERA5 NetCDF files found for phase {phase!r} in:\n  {raw_dir}\n\nRun workflow/preprocessing/02_download_meteorology.py first.')
    phase_dir = outputs.phase_meteorology_dir(phase)
    full_data = combine_yearly_files(era5_files, LATITUDE, LONGITUDE, pressure_level_hpa)
    if source == 'tmy':
        products = build_phase_tmy(phase, full_data, TMY_CONFIG)
        save_phase_meteorology_products(products, phase_dir)
        print(f'{phase}: source=tmy | historical rows={len(products.full_data):,} | TMY rows={len(products.tmy_data):,}')
    else:
        phase_dir.mkdir(parents=True, exist_ok=True)
        full_path = phase_dir / 'full_wind_data.csv'
        full_data.to_csv(full_path, index=False)
        print(f'{phase}: source=historical | historical rows={len(full_data):,}')
    print(f'  output: {phase_dir}')
