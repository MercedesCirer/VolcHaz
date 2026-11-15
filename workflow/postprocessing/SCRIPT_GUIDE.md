# Postprocessing script guide

Convert ATLAS simulation outputs into probability fields, optional hazard indices, point results, curves, and maps. Edit [postprocessing_config.py](configs/postprocessing_config.py). These scripts do not rerun ATLAS.

Run commands from the toolbox root in your activated Python environment:

```bash
python workflow/run.py postprocessing all
python workflow/run.py postprocessing 04
```

Replace `04` with the required step number. Unless configured otherwise, output paths below are relative to `outputs/<SCENARIO_NAME>/postprocessing/`. `<phase>` identifies a phase and `<subset>` identifies a configured simulation subset.

| Script | Purpose and operation | Required inputs / previous steps | Main outputs | Included in `all` |
|---|---|---|---|---|
| `01_compute_probabilities.py` | Read ATLAS ensembles and compute configured concentration, ground-load, arrival-time, and persistence probability fields. Optionally classify hazard indices and extract/plot point results according to configuration. | Retrieved `*.part.nc` simulations; configured subsets, thresholds, altitude ranges, time settings, and optional points/index settings. | `atlas/<phase>/<subset>/probability_fields/atlas_probabilities_<phase>_<subset>.nc`, invalid-file reports, `atlas/atlas_postprocessing_manifest.csv`, and `atlas/atlas_postprocessing_configuration.json`; optional hazard-index NetCDFs, point CSVs, curve tables/figures, and combined multiphase indices. | Yes. |
| `02_inspect_outputs.py` | Inspect dimensions, variables, and reader compatibility of up to the first five discovered ATLAS output files. Report inspection errors for those files. | Existing `*.part.nc` files under the scenario's processing `atlas/runs/` directory. | Console inspection report only. This is a limited inspection, not an exhaustive ensemble validation. | No; run separately, preferably before step 01 when checking unfamiliar outputs. |
| `03_extract_points.py` | Re-extract probabilities for configured locations from existing probability grids, for example after changing points or nearest/IDW extraction settings. Does not recalculate gridded probabilities. | Probability NetCDFs from step 01; configured point table and/or inline points. | Regenerated `atlas/points/all_point_probabilities.csv`. | No; optional regeneration operation. |
| `04_summarize_points.py` | Summarize point hazard curves and identify consistency issues before choosing plots. | `atlas/points/all_point_probabilities.csv` from step 01 with point extraction enabled, or step 03. | `atlas/points/hazard_curves/point_curve_preplot_summary.csv` and `point_curve_consistency_issues.csv`; console summary. | No; run separately for point diagnostics. |
| `05_plot_hazard_curves.py` | Plot point curve groups whose maximum probability exceeds the configured plotting threshold. It derives the selection from the point table itself; step 04 is recommended for prior review but is not a file dependency. | Combined point-probability CSV; point-curve plotting threshold. | Selected curve PNGs in `atlas/points/hazard_curves/figures_selected/`; no figures if no groups qualify. | No; run separately for selected point curves. |
| `06_make_maps.py` | Generate configured probability and ordinal hazard-intensity maps from existing gridded products. | Probability NetCDFs from step 01; index NetCDFs when intensity maps are enabled; mapping settings and any configured background data. | Map files in the configured map output directory and `stage6_mapping_manifest.csv`, recording generated map paths. | Yes, after step 01. |
| `run_all.py` | Execute probability/index/optional point processing (01), followed by mapping (06). | Requirements of steps 01 and 06. | Their configured products. | Invoked by the `all` command. |

## Choosing a workflow

For the standard grid-and-map workflow, execute `all`. It currently runs only steps 01 and 06; it does not automatically run the inspection, point re-extraction, point-summary, or selected-curve scripts.

For a dedicated point review, configure points, run step 01, and then steps 04 and 05. If only locations or point-extraction settings change while probability grids remain valid, run 03, 04, and 05 instead of recomputing the ensemble. Step 01 can also generate its own point curves when enabled; step 05 is a separate selection-based plotting route.

If simulation subsets, probability thresholds, altitude ranges, or other probability definitions change, rerun step 01 before regenerating point results and maps. Consult the manifest and invalid-file reports to understand which simulations contributed to the products. A missing optional product can reflect a disabled setting rather than a failed computation.

## Metric-specific map framing

In section 06 of `workflow/postprocessing/configs/postprocessing_config.py`, each
map dictionary (`C3D`, `GL`, `AT`, `PT_CONDITIONAL`, `PT_UNCONDITIONAL`) accepts
`extent=(west, east, south, north)` in decimal degrees. It applies to both
isoprobability and fixed-probability intensity maps. Set `extent=None` to inherit
the general map extent, derived from the scenario's `MAP_EXTENT` or `ATLAS_AREA`.
At library level, if both metric and base extents are None, grid bounds plus
`padding_deg` are used. Metric framing changes only the displayed area; it does
not change numerical model domains, the probability grid, or interpolation.

The supplied Lascar defaults use (-73, -51, -39, -21) for concentration, arrival,
and persistence, and (-70.5, -65, -26, -21) for ground load. Change these values for
another study area. All five map metrics are enabled. Set their `enabled` values
to False to omit products. `BASE_CONFIG['interpolation_methods']` requests IDW,
linear, and nearest interpolation; select a smaller tuple to reduce output count.
Each method writes separate products. The probability NetCDFs must already
contain the requested metrics, thresholds, and time levels.
