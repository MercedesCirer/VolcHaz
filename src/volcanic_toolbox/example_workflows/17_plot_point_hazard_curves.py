"""Stage 5.2 - Plot only informative point hazard curves.

Run this AFTER:
    workflow/postprocessing/01_compute_probabilities.py
    16_summarize_point_hazard.py

Only curve groups whose maximum point probability is greater than
MIN_PROBABILITY_TO_PLOT_PERCENT are sent to the plotting function.
"""
from pathlib import Path
import pandas as pd
from scenario_config import SCENARIO_NAME
from volcanic_toolbox.postprocessing.curves import build_curve_tables, plot_curve_groups
from volcanic_toolbox.postprocessing.point_diagnostics import point_hazard_summary
SCENARIO_ROOT = Path('outputs') / SCENARIO_NAME
POINT_RESULTS = SCENARIO_ROOT / 'postprocessing' / 'atlas' / 'points' / 'all_point_probabilities.csv'
FIGURE_DIR = SCENARIO_ROOT / 'postprocessing' / 'atlas' / 'points' / 'hazard_curves' / 'figures_selected'
MIN_PROBABILITY_TO_PLOT_PERCENT = 0.0
if not POINT_RESULTS.is_file():
    raise FileNotFoundError(POINT_RESULTS)
data = pd.read_csv(POINT_RESULTS)
curve_tables = build_curve_tables(data)
summary, _ = point_hazard_summary(data, zero_tolerance=MIN_PROBABILITY_TO_PLOT_PERCENT)
filtered = {}
for curve_key, table in curve_tables.items():
    if curve_key == 'c3d_intensity':
        summary_type = 'C3D'
        group_cols = ['phase', 'subset', 'altitude_range']
    elif curve_key == 'ground_load_intensity':
        summary_type = 'GL'
        group_cols = ['phase', 'subset']
    elif curve_key == 'arrival_time':
        summary_type = 'AT'
        group_cols = ['phase', 'subset', 'altitude_range', 'threshold']
    elif curve_key == 'persistence':
        summary_type = 'PT'
        group_cols = ['phase', 'subset', 'altitude_range', 'threshold', 'conditioning']
    else:
        continue
    useful = summary[(summary['curve_type'] == summary_type) & summary['recommended_to_plot']]
    if useful.empty:
        print(f'{summary_type}: no informative groups; no figures will be created.')
        continue
    keep = table.merge(useful[group_cols].drop_duplicates(), on=group_cols, how='inner')
    if not keep.empty:
        filtered[curve_key] = keep
if not filtered:
    print('No curve group exceeds the configured probability criterion. No figures were created.')
else:
    saved = plot_curve_groups(filtered, FIGURE_DIR)
    print(f'Created {len(saved)} informative hazard-curve figure(s) in:\n  {FIGURE_DIR}')
