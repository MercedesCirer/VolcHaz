"""Stage 5.0b - Re-extract selected points from existing probability NetCDFs.

Use this script when the gridded Stage 5 probability products already exist
and you only need to regenerate point results.

It does NOT read ATLAS .part.nc simulations and does NOT recalculate
probabilities.

This is especially useful after changing:
    - the point table,
    - nearest/IDW extraction settings,
    - point-extraction logic.
"""
from pathlib import Path
import pandas as pd
from scenario_config import SCENARIO_NAME
from postprocessing_config import ATLAS_POSTPROCESS_CONFIG
from volcanic_toolbox.postprocessing.points import extract_points, load_points
SCENARIO_ROOT = Path('outputs') / SCENARIO_NAME
ATLAS_POSTPROCESSING_ROOT = SCENARIO_ROOT / 'postprocessing' / 'atlas'
OUTPUT = ATLAS_POSTPROCESSING_ROOT / 'points' / 'all_point_probabilities.csv'
points = load_points(ATLAS_POSTPROCESS_CONFIG)
if points.empty:
    raise ValueError('No points are configured. Set point_table and/or inline_points in workflow/postprocessing/configs/postprocessing_config.py.')
probability_files = sorted(ATLAS_POSTPROCESSING_ROOT.glob('*/**/probability_fields/atlas_probabilities_*.nc'))
if not probability_files:
    raise FileNotFoundError(f'No Stage 5 probability NetCDF files were found under:\n  {ATLAS_POSTPROCESSING_ROOT}\n\nRun workflow/postprocessing/01_compute_probabilities.py first.')
tables = []
print(f'Re-extracting {len(points)} point(s) from {len(probability_files)} probability NetCDF file(s)...')
for path in probability_files:
    extracted = extract_points(path, points, ATLAS_POSTPROCESS_CONFIG.point_extraction)
    if not extracted.empty:
        tables.append(extracted)
if not tables:
    raise RuntimeError('Probability files were found but no point values could be extracted.')
result = pd.concat(tables, ignore_index=True)
OUTPUT.parent.mkdir(parents=True, exist_ok=True)
result.to_csv(OUTPUT, index=False)
print()
print(f'Point probabilities regenerated successfully:\n  {OUTPUT}')
print(f'Rows written: {len(result)}')
print()
print('Next run:\n  python workflow/run.py postprocessing 04')
