# Configuration reference

The toolbox has exactly three user-editable configuration files:

| Stage | File, relative to workflow/ |
|---|---|
| Preprocessing | preprocessing/configs/preprocessing_config.py |
| Processing | processing/configs/processing_config.py |
| Postprocessing | postprocessing/configs/postprocessing_config.py |

Each file contains uppercase comment headings corresponding to the workflow steps. Edit values, lists, and dictionaries only; do not add imports, functions, or class instances.

## Preprocessing configuration

- SCENARIO_TYPE: select "monophase" or "multiphase".
- A. SINGLE-PHASE SCENARIO: edit MONOPHASE_SCENARIO for a single eruptive phase.
- B. MULTIPHASE SCENARIO: copy the `MULTIPHASE_SCENARIO` assignment from the adjacent `multiphase_example.txt` into section B, then edit it. The inactive section is ignored.
- C. COMPLETE-STAGE EXECUTION: enable downloads and diagnostics for preprocessing/run_all.py.
- 01. ERUPTIVE PARAMETER PREVIEW: candidate count, seed, and histogram settings (PREVIEW_*).
- 02. ERA5 DOWNLOAD: geographic half-width, UTC times, and overwrite behavior. Coordinates, inclusive years, and pressure levels come from the selected scenario.
- 03. METEOROLOGICAL PREPARATION: typical meteorological year settings (TMY_SETTINGS).
- 04. METEOROLOGICAL SAMPLING: seed and replacement options (METEOROLOGY_SAMPLE_SETTINGS).
- 05. WIND ROSES: direction convention, daily vector averaging, and percentage display.
- 06. PHYSICALLY ADMISSIBLE SCENARIO GENERATION: accepted count, batch size, maximum attempts, and seed (SCENARIO_BUILD_SETTINGS).
- 07-09. DIAGNOSTICS: scenario pairplots, wind comparisons, and sampled/accepted parameter comparisons.
- 10. PAIRING INSPECTION: uses generated tables and the selected scenario; no additional settings are required.

Both scenario sections retain their own volcano coordinates, event constraints, meteorological source settings, and phase definitions. Within the selected scenario, PHASES and PHASE_METEOROLOGY must use identical phase names.

The command `python workflow/run.py preprocessing all` includes steps 08 and 09 by
default. In section C, set `RUN_WIND_COMPARISON` or `RUN_PARAMETER_COMPARISON` to
`False` to skip the corresponding diagnostic. Step 08 compares historical/TMY winds
with accepted-scenario winds using common wind-rose scales. Step 09 compares the
independent step 01 reference sample with accepted eruptive parameters and saves
histograms and descriptive statistics. When `RUN_PARAMETER_COMPARISON=True`, step
01 runs even if `RUN_PREVIEW=False`, ensuring a current reference sample. These
diagnostics do not alter accepted scenarios. Standalone steps 08 and 09 ignore
these execution flags; standalone step 09 requires existing outputs from steps 01
and 06. Step 10 remains a separately executed pairing inspection.

## Processing configuration

- 01. COMPLETE ATLAS METEOROLOGY: domain, additional days, download controls, GRIB conversion, and NetCDF options.
- 02. RESUME CONCATENATION: reuses the step 01 settings.
- 03. MODEL INPUTS: installation paths and model-input settings.
- 04. REMOTE EXECUTION: SSH access, launch command, MPI processes, resumability, and cleanup.

ATLAS_DRY_RUN=True prepares requests without downloading data. ATLAS_REMOTE_DRY_RUN=True validates the remote environment without launching simulations. Use SSH keys or the configured password environment variable; do not store passwords here.

## Postprocessing configuration

- 01. PROBABILITIES, POINTS, AND INDICES: thresholds, altitudes, month groups, points, extraction settings, and index rules.
- 02. INSPECTION AND 03. REPEATED POINT EXTRACTION: reuse the step 01 settings.
- 04. POINT SUMMARY: numerical tolerance.
- 05. HAZARD CURVES: minimum probability displayed.
- 06. MAPS: basemap, cartographic settings, output controls, and product styling.

Phases follow the active preprocessing scenario. Multiphase weights are methodological assumptions requiring scientific justification.

## Scientific conventions

- COLUMN_HEIGHT_REFERENCE="above_vent" denotes height above the vent; "asl" denotes plume-top altitude above sea level.
- MER is in kg/s. Duration is specified in hours and converted to seconds for mass calculations.
- Fallout volume is in km³ and is converted to mass using bulk density in kg/m³.
- Concentration is in kg/m³, ground load in kg/m², postprocessing altitude in metres above sea level, and time in hours.
- Probabilities are percentages. Hazard indices are ordinal, not joint probabilities.
- parameters defines a candidate distribution and bounds defines its admissible sampling limits. Accepted distributions may differ after physical conditioning.


## Editing a scientific application safely

Every setting and nested field is documented directly in its configuration file. Each dictionary is shown as a named group with one field per line. Change the value on the right; keep the field name, quotes, commas, and brackets.

Changing SCENARIO_NAME, coordinates, phase names, or valid scientific parameters does not require editing internal code. The step runner refreshes imported configuration dependencies, including when several steps are executed within the same Python session. Result paths, source coordinates, source elevation, parameter columns, and inherited phases follow the active scenario.

Existing output files are not recalculated merely by editing a config. After changing the meteorological period, coordinates, pressure level, or source, rerun the affected meteorological preparation and sampling steps. After changing eruptive distributions or event constraints, rebuild the accepted scenarios and regenerate model inputs. A new scenario name identifies a new output directory, which must first be populated by the relevant steps.

Explicit scientific choices remain explicit. Renaming multiphase phases requires updating explicitly specified phase weights and filters. Processing output_frequency_h and postprocessing dt_hours must describe the same model-output interval. Index levels must exist among the computed probability thresholds. The configuration check reports these genuine inconsistencies; it does not reject a scenario because its name differs from the distributed example.


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
