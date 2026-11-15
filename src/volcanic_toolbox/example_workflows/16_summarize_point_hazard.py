"""Stage 5.1 - Summarize point hazard results before creating figures.

Run this AFTER ``workflow/postprocessing/01_compute_probabilities.py`` with:

    create_point_curves=False

The script reads the already-generated:

    outputs/<scenario>/postprocessing/atlas/points/
        all_point_probabilities.csv

It does NOT rerun ATLAS and does NOT recalculate gridded probabilities.
"""
from pathlib import Path
import pandas as pd
from scenario_config import SCENARIO_NAME
from volcanic_toolbox.postprocessing.point_diagnostics import print_point_hazard_summary
SCENARIO_ROOT = Path('outputs') / SCENARIO_NAME
POINT_RESULTS = SCENARIO_ROOT / 'postprocessing' / 'atlas' / 'points' / 'all_point_probabilities.csv'
SUMMARY_OUTPUT = SCENARIO_ROOT / 'postprocessing' / 'atlas' / 'points' / 'hazard_curves' / 'point_curve_preplot_summary.csv'
CONSISTENCY_OUTPUT = SCENARIO_ROOT / 'postprocessing' / 'atlas' / 'points' / 'hazard_curves' / 'point_curve_consistency_issues.csv'
ZERO_TOLERANCE_PERCENT = 0.0
if not POINT_RESULTS.is_file():
    raise FileNotFoundError(f'Point-probability table not found:\n{POINT_RESULTS}\n\nConfigure points and run python workflow/run.py postprocessing 01 or 03.')
data = pd.read_csv(POINT_RESULTS)
summary, issues = print_point_hazard_summary(data, zero_tolerance=ZERO_TOLERANCE_PERCENT)
SUMMARY_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
summary.to_csv(SUMMARY_OUTPUT, index=False)
issues.to_csv(CONSISTENCY_OUTPUT, index=False)
print()
print(f'Summary table written to:\n  {SUMMARY_OUTPUT}')
if not issues.empty:
    print(f'Consistency issues written to:\n  {CONSISTENCY_OUTPUT}')
