# Preprocessing script guide

Prepare meteorological data and physically admissible eruption scenarios before running ATLAS. Edit [preprocessing_config.py](configs/preprocessing_config.py); do not edit the scripts.

Run commands from the toolbox root in your activated Python environment:

```bash
python workflow/run.py preprocessing all
python workflow/run.py preprocessing 08
```

Replace `08` with the required step number. Paths below are relative to `outputs/<SCENARIO_NAME>/preprocessing/`, except raw ERA5 files. `<phase>` is a configured phase name; `<type>` is `monophase` or `multiphase`; `<vei>` is the configured VEI.

| Script | Purpose and operation | Required inputs / previous steps | Main outputs | Included in `all` |
|---|---|---|---|---|
| `01_preview_eruption.py` | Generate an independent sample of configured eruptive parameters and inspect their distributions before physical event validation. This sample is not the complete population of attempts evaluated in step 06. | Active scenario and `PREVIEW_*` settings. | `eruption/<phase>_candidates.csv`, `<phase>_summary.csv`; parameter-distribution PNGs in `figures/eruption_distributions/<phase>/`. | When `RUN_PREVIEW=True` or `RUN_PARAMETER_COMPARISON=True`. |
| `02_download_meteorology.py` | Download or reuse ERA5 wind data for the configured years, coordinates, and pressure levels. TMY selection happens later. | ERA5 settings; configured CDS access for downloads. | Raw NetCDF files in `data/era5/<SCENARIO_NAME>/<phase>/` relative to the toolbox root. | When `DOWNLOAD_METEOROLOGY=True`. Standalone execution performs download/reuse regardless of this flag. |
| `03_prepare_meteorology.py` | Extract and combine winds at the selected location/level. Retain the complete record for historical sampling or construct a typical meteorological year (TMY). | Compatible raw ERA5 NetCDF files from step 02 or supplied by the user. | `meteorology/<phase>/full_wind_data.csv`; for TMY, `tmy_wind_data.csv` and supporting month-selection products. | Always. |
| `04_sample_meteorology.py` | Draw meteorological samples from the selected historical or TMY source for scenario generation. | Step 03; meteorological sample count and sampling settings. | `meteorology/<phase>/random_historical_meteorology_samples.csv` or `random_tmy_meteorology_samples.csv`, plus `selected_meteorology_samples.csv`. | Always. |
| `05_wind_roses.py` | Visualize annual and monthly wind frequencies for the selected meteorological source. | Prepared meteorology from step 03; `WIND_ROSE_*` settings. | Annual/monthly wind-rose PNGs in `figures/wind_roses/`. | When `RUN_WIND_ROSES=True`. |
| `06_build_scenarios.py` | Sample eruptive parameters, associate meteorology, calculate wind-dependent mass eruption rate (MER), and retain scenarios satisfying the configured event mass/volume constraints. | Selected meteorology from step 04; scenario, MER, event constraints, and build settings. Step 01 is not required for this generation. | `scenarios/valid_<type>_vei<vei>.csv`, `all_evaluated_<type>_vei<vei>.csv`, `<type>_vei<vei>_summary.csv`; phase-diagnostic CSV for multiphase scenarios. | Always. |
| `07_check_scenarios.py` | Plot parameter relationships for evaluated scenarios. | Evaluated scenarios from step 06; pairplot settings. | Scenario pairplot PNGs in `figures/pairplots/`. | When `RUN_SCENARIO_PLOTS=True`. |
| `08_compare_winds.py` | Compare the complete historical or TMY wind population with winds assigned to accepted scenarios, using common speed/direction bins and radial scales. Directions are meteorological FROM, recalculated from wind components. | Steps 03 and 06; `WIND_COMPARISON_*` settings. | `figures/wind_roses/<phase>_<source>_vs_validated_same_convention.png`; console record counts. | When `RUN_WIND_COMPARISON=True`. |
| `09_compare_parameters.py` | Compare the independent step 01 parameter sample with accepted scenarios to visualize changes associated with physical conditioning. This is a descriptive comparison, not a formal statistical hypothesis test. | Steps 01 and 06; `PARAMETER_COMPARISON_*` settings. | `<parameter>_sampled_vs_validated.png` and `sampled_vs_validated_summary.csv` in `figures/eruption_distributions/<phase>/`. | When `RUN_PARAMETER_COMPARISON=True`; step 01 then runs automatically to refresh the reference. |
| `10_check_pairing.py` | Display meteorological associations for the first 20 accepted scenarios, including dates, winds, available pressure/season fields, and available event totals. Useful for visual inspection of phase associations; it does not automatically certify their consistency. | Accepted scenarios from step 06. | Console table only; no new result file. | No; execute separately. |
| `run_all.py` | Run the main preprocessing sequence using section C execution flags. | The same requirements as the enabled individual steps. | The outputs of enabled steps; no additional combined result file. | Invoked by the `all` command. |

## Execution and interpretation

Steps 03, 04, and 06 always run. Downloads and diagnostics are controlled in section C of the configuration. Steps 08 and 09 are enabled by default. Setting their flags to `False` skips them in `all`; standalone execution ignores these sequence-selection flags. Step 09 requires a current step 01 reference when executed separately.

The accepted table is the preprocessing product used by processing. Diagnostic figures do not modify it. Differences between source and accepted distributions can reflect both sampling variability and physical conditioning. Changing scientific settings requires rerunning the affected preparation/generation steps before interpreting downstream diagnostics.
