"""Plot annual and monthly wind roses for the active meteorological source.

The source for each phase is read from PHASE_METEOROLOGY in scenario_config.py.

- historical -> plots full_wind_data.csv
- tmy        -> plots tmy_wind_data.csv

Works for monophase and multiphase scenarios because it iterates over every
phase defined in PHASE_METEOROLOGY.
"""
import pandas as pd
from volcanic_toolbox.preprocessing.output import ScenarioOutputManager
from volcanic_toolbox.preprocessing.plotting import plot_annual_wind_rose, plot_monthly_wind_rose_mosaic
from scenario_config import PHASE_METEOROLOGY, SCENARIO_NAME
WIND_ROSE_DIRECTION_CONVENTION = "from"
WIND_ROSE_USE_DAILY_VECTOR_MEANS = True
WIND_ROSE_PERCENTAGE = True

outputs = ScenarioOutputManager(scenario_name=SCENARIO_NAME).ensure(PHASE_METEOROLOGY)
for phase, settings in PHASE_METEOROLOGY.items():
    source = str(settings['source']).strip().lower()
    if source not in {'historical', 'tmy'}:
        raise ValueError(f"Phase {phase!r}: source must be 'historical' or 'tmy'; received {settings['source']!r}.")
    phase_dir = outputs.phase_meteorology_dir(phase)
    if source == 'tmy':
        input_path = phase_dir / 'tmy_wind_data.csv'
    else:
        input_path = phase_dir / 'full_wind_data.csv'
    if not input_path.exists():
        raise FileNotFoundError(f'Missing meteorological dataset for phase {phase!r}:\n  {input_path}\n\nRun 03_prepare_meteorology.py first.')
    data = pd.read_csv(input_path, parse_dates=['datetime'])
    plot_monthly_wind_rose_mosaic(data, output_path=outputs.wind_rose_dir / f'{phase}_{source}_monthly.png', direction_convention=WIND_ROSE_DIRECTION_CONVENTION, use_daily_vector_means=WIND_ROSE_USE_DAILY_VECTOR_MEANS, percentage=WIND_ROSE_PERCENTAGE)
    plot_annual_wind_rose(data, output_path=outputs.wind_rose_dir / f'{phase}_{source}_annual.png', direction_convention=WIND_ROSE_DIRECTION_CONVENTION, percentage=WIND_ROSE_PERCENTAGE)
    print(f'{phase}: source={source} | rows={len(data):,} | input={input_path}')
