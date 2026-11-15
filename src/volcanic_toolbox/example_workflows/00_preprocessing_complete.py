"""=============================================================================
VOLCANIC TOOLBOX - COMPLETE PREPROCESSING EXAMPLE
=============================================================================

PURPOSE
-------

This example orchestrates the complete preprocessing workflow used before
model-specific input preparation.

It intentionally DOES NOT execute ATLAS or any other dispersal model.

The workflow is:

    A. Define/load the eruptive scenario configuration.
    B. Preview stochastic eruptive-parameter distributions.
    C. Download or reuse ERA5 u/v pressure-level meteorology.
    D. Extract wind at the eruptive source and phase-specific pressure level.
    E. Build a Typical Meteorological Year (TMY) for each eruptive phase.
    F. Draw random meteorological samples from:
           - the complete historical ERA5 record; and
           - the phase-specific TMY.
    G. Plot monthly wind roses for diagnostic inspection.
    H. Select the meteorological source used by each eruptive phase.
    I. Repeatedly sample eruptive parameters + meteorology.
    J. Calculate MER with the Degruyter-Bonadonna formulation.
    K. Calculate erupted mass for every phase.
    L. Validate the SUM of phase masses against the selected VEI range.
    M. Stop when the requested number of valid scenarios is reached OR when
       max_attempts is reached.
    N. Save valid/evaluated scenarios, diagnostics and pairplots.

The example is deliberately verbose and heavily documented so that it can be
used as the main user-facing preprocessing example in the GitHub repository.

=============================================================================
WHAT SHOULD THE USER EDIT?
=============================================================================

Most SCENARIO-SPECIFIC parameters remain in:

    workflow/preprocessing/configs/preprocessing_config.py

This avoids defining the same volcano, phases or meteorological settings twice.

The following objects are expected from scenario_config.py:

    SCENARIO_NAME
    LATITUDE
    LONGITUDE
    VENT_ELEVATION_M
    YEARS
    N_METEOROLOGY_SAMPLES
    PHASE_METEOROLOGY
    SEASONS
    phase_configs()

For example:

    PHASE_METEOROLOGY = {
        "extreme_intensity": {
            "pressure_level_hpa": 50,
            "source": "tmy",
        },
        "high_intensity": {
            "pressure_level_hpa": 100,
            "source": "tmy",
        },
        "low_intensity": {
            "pressure_level_hpa": 200,
            "source": "tmy",
        },
    }

``source`` must be:

    "tmy"
        Random meteorological timestamps are drawn from the Typical
        Meteorological Year constructed for that phase.

    "historical"
        Random meteorological timestamps are drawn from the full ERA5 record.

The phase names in PHASE_METEOROLOGY must exactly match the names returned by
phase_configs().

=============================================================================
OUTPUT STRUCTURE
=============================================================================

Everything is stored below:

    outputs/<SCENARIO_NAME>/preprocessing/

The ScenarioOutputManager creates:

    configuration/
    eruption/
    meteorology/
        <phase_name>/
    scenarios/
    figures/
        wind_roses/
        pairplots/

Raw phase-specific ERA5 files are additionally stored as:

    meteorology/<phase_name>/raw_era5/

=============================================================================
"""
from __future__ import annotations
from dataclasses import asdict
import json
from pathlib import Path
import pandas as pd
from scenario_config import LATITUDE, LONGITUDE, N_METEOROLOGY_SAMPLES, PHASE_METEOROLOGY, SCENARIO_NAME, SCENARIO_TYPE, SEASONS, VENT_ELEVATION_M, YEARS, phase_configs, phase_mass_fraction_constraints, validate_scenario_configuration
from volcanic_toolbox.preprocessing import MERConfig, ScenarioOutputManager
from volcanic_toolbox.preprocessing.eruption import VEIConfig, sample_candidate_eruption_parameters, summarize_samples
from volcanic_toolbox.preprocessing.meteorology import ERA5DownloadConfig, MeteorologySampleConfig, TMYConfig, bbox_around_point, build_phase_tmy, combine_yearly_files, download_era5_range, load_selected_phase_meteorology, sample_phase_meteorology, save_phase_meteorology_products
from volcanic_toolbox.preprocessing.plotting import plot_monthly_wind_rose_mosaic, plot_multiphase_pairplots, plot_parameter_histogram
from volcanic_toolbox.preprocessing.scenarios import MultiphaseVEIScenarioBuilder, VEIScenarioBuilder, PhaseMassFractionConstraint, ScenarioBuildConfig
RUN_ERUPTION_PREVIEW = True
RUN_METEOROLOGY_PREPROCESSING = True
DOWNLOAD_ERA5 = False
RUN_WIND_ROSES = True
RUN_SCENARIO_BUILD = True
RUN_PAIRPLOTS = True
ERUPTION_PREVIEW_SAMPLES = 5000
ERUPTION_PREVIEW_SEED = 42
ERUPTION_HISTOGRAM_BINS = 30
ERUPTION_HISTOGRAM_DENSITY = True
ERUPTION_HISTOGRAM_OVERLAY_PDF = True
YEAR_START, YEAR_END = YEARS
ERA5_HALF_BOX_DEGREES = 0.25
ERA5_TIMES_UTC = ('00:00', '06:00', '12:00', '18:00')
ERA5_OVERWRITE = False
TMY_CONFIG = TMYConfig(speed_weight=0.3, direction_weight=0.7, speed_bins=28, direction_bins=28, use_daily_means=False)
METEOROLOGY_SAMPLE_CONFIG = MeteorologySampleConfig(number_of_samples=N_METEOROLOGY_SAMPLES, seed=42, replace=True)
WIND_ROSE_DIRECTION_CONVENTION = 'from'
WIND_ROSE_USE_DAILY_MEANS = True
WIND_ROSE_SPEED_BINS = 5
WIND_ROSE_DIRECTION_BINS = 16
WIND_ROSE_PERCENTAGE = True
WIND_ROSE_DPI = 300
VEI_CONFIG = VEIConfig(vei=4, minimum_volume_km3=0.1, maximum_volume_km3=1.0, bulk_density_kg_m3=1000.0, volume_basis='bulk_tephra', source_reference='Replace with the bibliographic source adopted for the VEI-volume range and bulk density.')
MER_CONFIG = MERConfig(vent_elevation_m=VENT_ELEVATION_M, alpha=0.1, beta=0.5, source_temperature_k=1200.0, source_heat_capacity_j_kg_k=1250.0, z1=2.8)
SCENARIO_BUILD_CONFIG = ScenarioBuildConfig(target_valid_scenarios=1000, batch_size=1000, max_attempts=100000, seed=42, wind_column='wind_speed_m_s', datetime_column='datetime', sample_meteorology_with_replacement=True)
PHASE_MASS_FRACTION_CONSTRAINTS = ()

def _validate_phase_configuration(phases):
    """Check that phase meteorological configuration matches eruptive phases."""
    phase_names = [phase.name for phase in phases]
    configured = set(PHASE_METEOROLOGY)
    defined = set(phase_names)
    missing = defined - configured
    extra = configured - defined
    if missing:
        raise KeyError('PHASE_METEOROLOGY is missing phase(s): ' + ', '.join(sorted(missing)))
    if extra:
        raise KeyError('PHASE_METEOROLOGY contains unknown phase(s): ' + ', '.join(sorted(extra)))
    for phase_name in phase_names:
        settings = PHASE_METEOROLOGY[phase_name]
        if 'pressure_level_hpa' not in settings:
            raise KeyError(f'{phase_name}: pressure_level_hpa is required.')
        source = str(settings.get('source', '')).lower().strip()
        if source not in {'historical', 'tmy'}:
            raise ValueError(f"{phase_name}: source must be 'historical' or 'tmy'.")

def _save_configuration_snapshot(outputs, phases):
    """Save a machine-readable record of the preprocessing assumptions."""
    snapshot = {'scenario_name': SCENARIO_NAME, 'volcano': {'latitude': LATITUDE, 'longitude': LONGITUDE, 'vent_elevation_m': VENT_ELEVATION_M}, 'years': [YEAR_START, YEAR_END], 'phase_meteorology': PHASE_METEOROLOGY, 'seasons': {name: list(months) for name, months in SEASONS.items()}, 'eruption_phases': [{'name': phase.name, 'height_key': phase.height_key, 'duration_key': phase.duration_key, 'parameters': [parameter.to_dict() for parameter in phase.parameters]} for phase in phases], 'vei': VEI_CONFIG.to_dict(), 'mer': asdict(MER_CONFIG), 'tmy': asdict(TMY_CONFIG), 'meteorology_sampling': asdict(METEOROLOGY_SAMPLE_CONFIG), 'scenario_builder': asdict(SCENARIO_BUILD_CONFIG), 'phase_mass_fraction_constraints': [{'phase_name': phase_name, 'minimum': minimum, 'maximum': maximum} for phase_name, minimum, maximum in phase_mass_fraction_constraints()]}
    path = outputs.configuration_dir / 'preprocessing_configuration.json'
    path.write_text(json.dumps(snapshot, indent=2, default=str), encoding='utf-8')
    return path

def _preview_eruptive_parameters(phases, outputs):
    """Sample and plot the unvalidated eruptive distributions."""
    print('\n[1/5] ERUPTIVE-PARAMETER PREVIEW')
    for phase_index, phase in enumerate(phases):
        phase_dir = outputs.eruption_dir / phase.name
        phase_dir.mkdir(parents=True, exist_ok=True)
        candidates = sample_candidate_eruption_parameters(phase.parameters, number_of_candidates=ERUPTION_PREVIEW_SAMPLES, seed=ERUPTION_PREVIEW_SEED + phase_index, candidate_prefix=f'{phase.name}_preview')
        candidates.to_csv(phase_dir / 'eruption_parameter_preview.csv', index=False)
        summarize_samples(candidates).to_csv(phase_dir / 'eruption_parameter_summary.csv')
        for parameter in phase.parameters:
            plot_parameter_histogram(values=candidates[parameter.column_name].to_numpy(), config=parameter, bins=ERUPTION_HISTOGRAM_BINS, density=ERUPTION_HISTOGRAM_DENSITY, overlay_pdf=ERUPTION_HISTOGRAM_OVERLAY_PDF, output_path=phase_dir / f'{parameter.key}_distribution.png', show=False)
        print(f'  {phase.name}: {len(candidates):,} preview candidates')

def _prepare_phase_meteorology(phases, outputs):
    """Download/reuse ERA5, construct TMYs and sample meteorology."""
    print('\n[2/5] PHASE-SPECIFIC METEOROLOGY')
    products_by_phase = {}
    for phase_index, phase in enumerate(phases):
        settings = PHASE_METEOROLOGY[phase.name]
        pressure_level = int(settings['pressure_level_hpa'])
        phase_dir = outputs.phase_meteorology_dir(phase.name)
        raw_dir = phase_dir / 'raw_era5'
        raw_dir.mkdir(parents=True, exist_ok=True)
        era5_config = ERA5DownloadConfig(year_start=YEAR_START, year_end=YEAR_END, pressure_levels_hpa=(pressure_level,), latitude=LATITUDE, longitude=LONGITUDE, half_box_degrees=ERA5_HALF_BOX_DEGREES, times_utc=ERA5_TIMES_UTC)
        area = bbox_around_point(latitude=era5_config.latitude, longitude=era5_config.longitude, half_latitude=era5_config.half_box_degrees, half_longitude=era5_config.half_box_degrees)
        if DOWNLOAD_ERA5:
            print(f'  {phase.name}: downloading/reusing ERA5 {YEAR_START}-{YEAR_END}, {pressure_level} hPa')
            file_paths = download_era5_range(year_start=era5_config.year_start, year_end=era5_config.year_end, pressure_levels_hpa=era5_config.pressure_levels_hpa, area=area, output_directory=raw_dir, overwrite=ERA5_OVERWRITE, times=era5_config.times_utc, dataset_id=era5_config.dataset_id)
        else:
            file_paths = sorted(raw_dir.glob('*.nc'))
            if not file_paths:
                raise FileNotFoundError(f"No ERA5 NetCDF files were found for phase '{phase.name}' in:\n  {raw_dir}\n\nEither set DOWNLOAD_ERA5=True or copy the existing yearly ERA5 files into that directory.")
        full_data = combine_yearly_files(file_paths=file_paths, latitude=LATITUDE, longitude=LONGITUDE, pressure_level_hpa=pressure_level)
        products = build_phase_tmy(phase_name=phase.name, full_data=full_data, config=TMY_CONFIG)
        phase_sample_config = MeteorologySampleConfig(number_of_samples=METEOROLOGY_SAMPLE_CONFIG.number_of_samples, seed=METEOROLOGY_SAMPLE_CONFIG.seed + phase_index, replace=METEOROLOGY_SAMPLE_CONFIG.replace)
        products = sample_phase_meteorology(products, sample_config=phase_sample_config)
        paths = save_phase_meteorology_products(products, output_directory=phase_dir)
        products_by_phase[phase.name] = products
        print(f"  {phase.name}: {len(products.full_data):,} historical rows | {len(products.tmy_data):,} TMY rows | selected source = {settings['source']}")
        print('    saved: ' + ', '.join((f'{key}={path.name}' for key, path in paths.items())))
    return products_by_phase

def _plot_wind_roses(phases, outputs, products_by_phase=None):
    """Plot one monthly historical wind-rose mosaic per phase."""
    print('\n[3/5] WIND-ROSE DIAGNOSTICS')
    for phase in phases:
        if products_by_phase is not None and phase.name in products_by_phase:
            data = products_by_phase[phase.name].full_data
        else:
            path = outputs.phase_meteorology_dir(phase.name) / 'full_wind_data.csv'
            if not path.exists():
                raise FileNotFoundError(f'Missing {path}. Run meteorological preprocessing first.')
            data = pd.read_csv(path, parse_dates=['datetime'])
        output_path = outputs.wind_rose_dir / f'{phase.name}_monthly_wind_rose.png'
        plot_monthly_wind_rose_mosaic(data=data, output_path=output_path, direction_convention=WIND_ROSE_DIRECTION_CONVENTION, use_daily_vector_means=WIND_ROSE_USE_DAILY_MEANS, speed_bins=WIND_ROSE_SPEED_BINS, direction_bins=WIND_ROSE_DIRECTION_BINS, percentage=WIND_ROSE_PERCENTAGE, dpi=WIND_ROSE_DPI)
        print(f'  {phase.name}: {output_path}')

def _load_selected_meteorology(phases, outputs):
    """Load the historical or TMY sample selected independently for each phase."""
    meteorology_by_phase = {}
    for phase in phases:
        source = str(PHASE_METEOROLOGY[phase.name]['source']).lower().strip()
        meteorology_by_phase[phase.name] = load_selected_phase_meteorology(phase_directory=outputs.phase_meteorology_dir(phase.name), source=source)
    return meteorology_by_phase

def _normalize_monophase_table(table, phase_name):
    """Normalize single-phase output to the common phase-aware schema."""
    frame = table.copy()
    rename = {'column_height_m': f'{phase_name}_column_height_m', 'duration_h': f'{phase_name}_duration_h', 'aggregation_fraction_fraction': f'{phase_name}_aggregation_fraction_fraction', 'mer_kg_s': f'{phase_name}_mer_kg_s', 'calculated_mass_kg': f'{phase_name}_mass_kg', 'calculated_volume_km3': f'{phase_name}_volume_km3', 'datetime': f'{phase_name}_datetime', 'season': f'{phase_name}_season'}
    meteo_columns = {'wind_speed_m_s', 'wind_direction_deg', 'u_m_s', 'v_m_s', 'pressure_level_hpa', 'latitude', 'longitude', 'sampling_method', 'meteo_id', 'meteo_source_row', 'tmy_datetime', 'source_year', 'year', 'month', 'day', 'hour'}
    for column in frame.columns:
        if column in meteo_columns:
            rename[column] = f'{phase_name}_{column}'
    frame = frame.rename(columns=rename)
    mass = f'{phase_name}_mass_kg'
    volume = f'{phase_name}_volume_km3'
    duration = f'{phase_name}_duration_h'
    season = f'{phase_name}_season'
    if mass in frame:
        frame['event_total_mass_kg'] = frame[mass]
        frame[f'{phase_name}_mass_fraction'] = 1.0
    if volume in frame:
        frame['event_total_volume_km3'] = frame[volume]
    if duration in frame:
        frame['event_total_duration_h'] = frame[duration]
    if season in frame:
        frame['same_season_across_phases'] = True
        frame['event_season'] = frame[season]
    return frame

def _build_scenarios(phases, outputs):
    """Build monophase or multiphase scenarios according to SCENARIO_TYPE."""
    scenario_type = SCENARIO_TYPE.lower().strip()
    print(f'\n[4/5] {scenario_type.upper()} VEI SCENARIO BUILD')
    meteorology_by_phase = _load_selected_meteorology(phases, outputs)
    vei = VEI_CONFIG.vei
    if scenario_type == 'monophase':
        if len(phases) != 1:
            raise ValueError("SCENARIO_TYPE='monophase' requires exactly one phase.")
        phase = phases[0]
        result = VEIScenarioBuilder(parameter_configs=phase.parameters, meteorology=meteorology_by_phase[phase.name], vei_config=VEI_CONFIG, mer_config=MER_CONFIG, build_config=SCENARIO_BUILD_CONFIG, seasons=SEASONS).build()
        result.valid_scenarios = _normalize_monophase_table(result.valid_scenarios, phase.name)
        result.evaluated_scenarios = _normalize_monophase_table(result.evaluated_scenarios, phase.name)
        valid_path = outputs.scenarios_dir / f'valid_monophase_vei{vei}.csv'
        evaluated_path = outputs.scenarios_dir / f'all_evaluated_monophase_vei{vei}.csv'
        summary_path = outputs.scenarios_dir / f'monophase_vei{vei}_build_summary.csv'
        diagnostics_path = None
    elif scenario_type == 'multiphase':
        if len(phases) < 2:
            raise ValueError("SCENARIO_TYPE='multiphase' requires at least two phases.")
        result = MultiphaseVEIScenarioBuilder(phase_configs=phases, meteorology_by_phase=meteorology_by_phase, vei_config=VEI_CONFIG, mer_config=MER_CONFIG, build_config=SCENARIO_BUILD_CONFIG, phase_fraction_constraints=tuple((PhaseMassFractionConstraint(phase_name=phase_name, minimum=minimum, maximum=maximum) for phase_name, minimum, maximum in phase_mass_fraction_constraints())), seasons=SEASONS).build()
        valid_path = outputs.scenarios_dir / f'valid_multiphase_vei{vei}.csv'
        evaluated_path = outputs.scenarios_dir / f'all_evaluated_{SCENARIO_TYPE.lower().strip()}_vei{vei}.csv'
        summary_path = outputs.scenarios_dir / f'multiphase_vei{vei}_build_summary.csv'
        diagnostics_path = outputs.scenarios_dir / f'multiphase_vei{vei}_phase_diagnostics.csv'
    else:
        raise ValueError("SCENARIO_TYPE must be 'monophase' or 'multiphase'.")
    result.valid_scenarios.to_csv(valid_path, index=False)
    result.evaluated_scenarios.to_csv(evaluated_path, index=False)
    result.summary.to_csv(summary_path, index=False)
    if diagnostics_path is not None and result.phase_diagnostics is not None:
        result.phase_diagnostics.to_csv(diagnostics_path, index=False)
    print(result.summary.to_string(index=False))
    print(f'\n  Acceptance rate: {result.acceptance_rate * 100:.3f}%')
    print(f'\n  Valid scenarios: {valid_path}')
    print(f'  All attempts:    {evaluated_path}')
    print(f'  Summary:         {summary_path}')
    return result

def _plot_pairplots(result, phases, outputs):
    """Plot accepted/rejected parameter relationships independently for each phase."""
    print('\n[5/5] ACCEPTED / REJECTED PAIRPLOTS')
    phase_labels = {phase.name: phase.name.replace('_', ' ').title() for phase in phases}
    paths = plot_multiphase_pairplots(scenarios=result.evaluated_scenarios, phase_names=[phase.name for phase in phases], phase_labels=phase_labels, output_directory=outputs.pairplots_dir, filename_prefix='scenario_pairplot', max_points=5000, seed=42, dpi=300)
    for phase, path in paths.items():
        print(f'  {phase}: {path}')

def main():
    validate_scenario_configuration()
    phases = tuple(phase_configs())
    _validate_phase_configuration(phases)
    outputs = ScenarioOutputManager(scenario_name=SCENARIO_NAME).ensure(phase_names=[phase.name for phase in phases])
    config_path = _save_configuration_snapshot(outputs, phases)
    print('=' * 79)
    print('VOLCANIC TOOLBOX - PREPROCESSING')
    print('=' * 79)
    print(f'Scenario: {SCENARIO_NAME}')
    print('Phases:   ' + ', '.join((phase.name for phase in phases)))
    print(f'ERA5:     {YEAR_START}-{YEAR_END}')
    print(f'Target:   {SCENARIO_BUILD_CONFIG.target_valid_scenarios:,} valid scenarios')
    print(f'Outputs:  {outputs.preprocessing_dir}')
    print(f'Config:   {config_path}')
    if RUN_ERUPTION_PREVIEW:
        _preview_eruptive_parameters(phases, outputs)
    products_by_phase = None
    if RUN_METEOROLOGY_PREPROCESSING:
        products_by_phase = _prepare_phase_meteorology(phases, outputs)
    if RUN_WIND_ROSES:
        _plot_wind_roses(phases, outputs, products_by_phase=products_by_phase)
    result = None
    if RUN_SCENARIO_BUILD:
        result = _build_scenarios(phases, outputs)
    if RUN_PAIRPLOTS:
        if result is None:
            vei = VEI_CONFIG.vei
            evaluated_path = outputs.scenarios_dir / f'all_evaluated_multiphase_vei{vei}.csv'
            if not evaluated_path.exists():
                raise FileNotFoundError(f'Cannot create pairplots because {evaluated_path} does not exist. Run the scenario builder first.')
            evaluated = pd.read_csv(evaluated_path)

            class ExistingResult:
                evaluated_scenarios = evaluated
            result = ExistingResult()
        _plot_pairplots(result, phases, outputs)
    print('\n' + '=' * 79)
    print('PREPROCESSING COMPLETED')
    print('=' * 79)
    print('\nMain scenario table expected by the processing stage:')
    print('  ' + str(outputs.scenarios_dir / f'valid_{SCENARIO_TYPE.lower().strip()}_vei{VEI_CONFIG.vei}.csv'))
if __name__ == '__main__':
    main()
