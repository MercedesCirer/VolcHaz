"""Sample phase-specific meteorology from historical ERA5 or a TMY.

The source for each phase is read from PHASE_METEOROLOGY in scenario_config.py.

- historical -> random sampling from full_wind_data.csv
- tmy        -> random sampling from tmy_wind_data.csv

The selected sample is always written to selected_meteorology_samples.csv.

This script supports both monophase and multiphase scenarios because it
iterates over every phase defined in PHASE_METEOROLOGY.
"""
import pandas as pd
from volcanic_toolbox.preprocessing.meteorology import MeteorologySampleConfig, RandomMeteorologySampler, TypicalYearMeteorologySampler
from volcanic_toolbox.preprocessing.output import ScenarioOutputManager
from scenario_config import N_METEOROLOGY_SAMPLES, PHASE_METEOROLOGY, SCENARIO_NAME
outputs = ScenarioOutputManager(scenario_name=SCENARIO_NAME).ensure(PHASE_METEOROLOGY)
SAMPLE_CONFIG = MeteorologySampleConfig(number_of_samples=N_METEOROLOGY_SAMPLES, seed=42, replace=True)
for phase, settings in PHASE_METEOROLOGY.items():
    source = str(settings['source']).strip().lower()
    if source not in {'historical', 'tmy'}:
        raise ValueError(f"Phase {phase!r}: source must be 'historical' or 'tmy'; received {settings['source']!r}.")
    folder = outputs.phase_meteorology_dir(phase)
    if source == 'historical':
        input_path = folder / 'full_wind_data.csv'
        if not input_path.exists():
            raise FileNotFoundError(f'Missing historical meteorology for phase {phase!r}:\n  {input_path}\n\nRun 03_prepare_meteorology.py first.')
        data = pd.read_csv(input_path, parse_dates=['datetime'])
        chosen = RandomMeteorologySampler(data=data, config=SAMPLE_CONFIG).sample()
        source_output_path = folder / 'random_historical_meteorology_samples.csv'
    else:
        input_path = folder / 'tmy_wind_data.csv'
        if not input_path.exists():
            raise FileNotFoundError(f"Missing TMY meteorology for phase {phase!r}:\n  {input_path}\n\nRun 03_prepare_meteorology.py with source='tmy' first.")
        data = pd.read_csv(input_path, parse_dates=['datetime'])
        chosen = TypicalYearMeteorologySampler(tmy_data=data, config=SAMPLE_CONFIG).sample()
        source_output_path = folder / 'random_tmy_meteorology_samples.csv'
    chosen.to_csv(source_output_path, index=False)
    selected_path = folder / 'selected_meteorology_samples.csv'
    chosen.to_csv(selected_path, index=False)
    print(f'{phase}: source={source} | population={len(data):,} | selected={len(chosen):,}')
    print(f'  source sample: {source_output_path}')
    print(f'  selected:      {selected_path}')
