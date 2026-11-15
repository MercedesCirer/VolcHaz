"""=============================================================================
ATLAS STAGE 5 - COMPLETE POSTPROCESSING CONFIGURATION
=============================================================================

This file is the main user-editable configuration for Stage 5.

Stage 5 DOES NOT execute ATLAS. It assumes that ATLAS simulations have already
been run and that each simulation folder contains a file ending in ``.part.nc``.

The workflow performs, in this order:

    1. Discover ATLAS ``*.part.nc`` outputs recursively.
    2. Group simulations by eruptive phase.
    3. Optionally subdivide every phase into user-defined month groups.
    4. Calculate probability fields for:
           - airborne concentration (C3D),
           - ground load (GL),
           - arrival time (AT),
           - post-arrival persistence time (PT).
    5. Optionally extract probability values at user-defined ground locations.
    6. Generate temporal and intensity hazard curves for those points.
    7. Convert probability fields into ordinal hazard indices.
    8. Combine phase-specific indices pixel by pixel using:
           - an unweighted phase sum;
           - an optional metric-specific weighted index;
           - contributing-phase count;
           - maximum phase-specific index.

IMPORTANT CONCEPTUAL DISTINCTION
--------------------------------

The multiphase products are HAZARD INDICES, not joint probabilities.

For example:

    extreme_intensity index = 3
    high_intensity index    = 2
    low_intensity index     = 1

The unweighted phase-sum index is:

    3 + 2 + 1 = 6

This does NOT mean a 6% probability or a physically summed concentration.
It is an ordinal summary of the phase-specific probabilistic hazard classes.

=============================================================================
VALUE CONVENTIONS
=============================================================================

C3D thresholds:
    kg m-3

Useful conversions:
    0.2 mg m-3 = 0.2e-6 kg m-3
    2.0 mg m-3 = 2.0e-6 kg m-3
    4.0 mg m-3 = 4.0e-6 kg m-3

Ground load:
    kg m-2

Altitude:
    metres above sea level, because ATLAS ``alt`` is treated as an absolute
    altitude coordinate in this Stage 5 implementation.

Probability:
    percent, from 0 to 100.

Time:
    hours.

=============================================================================
EXPECTED DIRECTORY STRUCTURE
=============================================================================

outputs/<scenario>/
    processing/
        atlas/
            runs/
                extreme_intensity/
                    simulation_YYYYMMDD_scenario_XXXXXX/
                        ...part.nc
                high_intensity/
                    simulation_YYYYMMDD_scenario_XXXXXX/
                        ...part.nc
                low_intensity/
                    simulation_YYYYMMDD_scenario_XXXXXX/
                        ...part.nc

The exact ``.part.nc`` filename does not matter. Stage 5 searches recursively
for every filename ending in ``.part.nc``.

=============================================================================
"""
from pathlib import Path
from volcanic_toolbox.postprocessing import AtlasPostprocessConfig, AltitudeRange, MetricIndexRule, MonthGroup, MultiphaseIndexConfig, PointExtractionConfig
from scenario_config import SCENARIO_NAME
SCENARIO_ROOT = Path('outputs') / SCENARIO_NAME
ATLAS_POSTPROCESS_CONFIG = AtlasPostprocessConfig(runs_root=SCENARIO_ROOT / 'processing' / 'atlas' / 'runs', output_root=SCENARIO_ROOT / 'postprocessing', phases=('extreme_intensity', 'high_intensity', 'low_intensity'), c3d_thresholds_kg_m3=(2e-07, 2e-06, 4e-06), gl_thresholds_kg_m2=(0.1, 1.0, 10.0, 100.0), altitude_ranges=(AltitudeRange(name='FL000_200', minimum_m=0.0, maximum_m=6096.0), AltitudeRange(name='FL200_350', minimum_m=6096.0, maximum_m=10668.0), AltitudeRange(name='FL350_500', minimum_m=10668.0, maximum_m=15240.0)), c3d_exceedance_vertical_operator='maximum', temporal_vertical_operator='mean', arrival_hours=(2, 4, 6, 12, 18, 24, 48, 72), persistence_hours=(1, 2, 4, 6, 12, 24, 48, 72), dt_hours=1.0, persistence_outputs=('conditional', 'unconditional'), month_groups=(MonthGroup(name='dry', months=(4, 5, 6, 7, 8, 9, 10)), MonthGroup(name='wet', months=(11, 12, 1, 2, 3))), point_table=Path('workflow') / 'atlas_points.csv', inline_points=(), point_extraction=PointExtractionConfig(method='nearest', idw_k=4, idw_power=1.0, idw_radius_deg=None), create_point_curves=False, probability_comparison='>', skip_invalid_files=True)
PROBABILITY_CUTOFF_PERCENT = 25.0
ATLAS_INDEX_CONFIG = MultiphaseIndexConfig(enabled=True, phase_order=('extreme_intensity', 'high_intensity', 'low_intensity'), rules=(MetricIndexRule(metric='c3d', levels=(2e-07, 2e-06, 4e-06), probability_cutoff_percent=PROBABILITY_CUTOFF_PERCENT, enabled=True), MetricIndexRule(metric='gl', levels=(0.1, 1.0, 10.0, 100.0), probability_cutoff_percent=PROBABILITY_CUTOFF_PERCENT, enabled=True), MetricIndexRule(metric='arrival', levels=(72, 48, 24, 18, 12, 6, 4, 2), probability_cutoff_percent=PROBABILITY_CUTOFF_PERCENT, enabled=True), MetricIndexRule(metric='persistence_conditional', levels=(1, 2, 4, 6, 12, 24, 48, 72), probability_cutoff_percent=PROBABILITY_CUTOFF_PERCENT, enabled=True), MetricIndexRule(metric='persistence_unconditional', levels=(1, 2, 4, 6, 12, 24, 48, 72), probability_cutoff_percent=PROBABILITY_CUTOFF_PERCENT, enabled=True)), calculate_phase_sum=True, calculate_weighted_index=True, weights_by_metric={'c3d': {'extreme_intensity': 0.35, 'high_intensity': 0.45, 'low_intensity': 0.2}, 'gl': {'extreme_intensity': 0.15, 'high_intensity': 0.3, 'low_intensity': 0.55}, 'arrival': {'extreme_intensity': 0.45, 'high_intensity': 0.4, 'low_intensity': 0.15}, 'persistence_conditional': {'extreme_intensity': 0.1, 'high_intensity': 0.25, 'low_intensity': 0.65}, 'persistence_unconditional': {'extreme_intensity': 0.1, 'high_intensity': 0.25, 'low_intensity': 0.65}}, calculate_contributing_phase_count=True, calculate_maximum_phase_index=True, require_all_phases=True)
