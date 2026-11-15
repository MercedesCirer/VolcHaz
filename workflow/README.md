# Workflow guide

The toolbox is controlled by exactly three configuration files, one alongside the scripts of each stage:

~~~text
workflow/
  preprocessing/
    configs/
      preprocessing_config.py
    01_preview_eruption.py
    02_download_meteorology.py
    ...
    10_check_pairing.py
    run_all.py
  processing/
    configs/
      processing_config.py
    01_prepare_model_meteorology.py
    ...
    04_run_model.py
    run_all.py
  postprocessing/
    configs/
      postprocessing_config.py
    01_compute_probabilities.py
    ...
    06_make_maps.py
    run_all.py
  run.py
~~~

## Configure the application

Open preprocessing/configs/preprocessing_config.py. Set SCENARIO_TYPE to "monophase" or "multiphase" and edit its corresponding scenario section. Configure the volcano, event constraints, meteorological period and source, phases, and candidate distributions. The inactive scenario section is ignored.

Continue through the numbered headings in the same file to configure sampling, meteorology downloads and preparation, wind roses, physical validation, and diagnostics. For multiphase cases, copy the assignment from the adjacent `multiphase_example.txt` into the configuration as indicated there.

For execution and output analysis, use processing/configs/processing_config.py and postprocessing/configs/postprocessing_config.py. The [configuration reference](CONFIGURATION.md) explains their sections and scientific conventions. Settings contain data only; functions and object construction remain internal.

## Preprocessing

Steps 01-04 prepare candidate parameters and meteorology; step 06 builds physically admissible scenarios. Step 05 and steps 07-10 provide optional diagnostics. The complete-stage runner invokes the same scripts and settings as individual execution, using the flags in section C.

Accepted scenarios satisfy the specified fallout mass/volume constraints using wind-dependent MER. They are a physically conditioned subset of the candidate parameter space. Equivalent eruptive duration differs from the full chronological duration of an episode.

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

## Processing

Run steps 01, 03, and 04 in order. Step 02 resumes meteorological concatenation. Preprocessing winds characterize representative conditions; complete ATLAS forcing supplies the meteorological fields required by the model.

ERA5 requires configured CDS access. Complete forcing preparation requires grib_to_netcdf. Remote execution requires SSH access, ATLAS, and a suitable launch command. Inspect requests with ATLAS_DRY_RUN=True and validate the server with ATLAS_REMOTE_DRY_RUN=True before actual execution.

## Postprocessing

Step 01 calculates selected probability and index products and can extract point results. Other steps inspect outputs, repeat extraction, summarize points, plot curves, and generate maps. The complete-stage runner executes steps 01 and 06; additional analyses can be run separately.

Phases follow the active scenario. Weighted combination is omitted for a single phase. Multiphase weights require scientific justification; combined indices are ordinal summaries, not joint probabilities.

## Execute and validate

From the toolbox root:

~~~powershell
python workflow/run.py
python workflow/run.py preprocessing 01
python workflow/run.py preprocessing all
python workflow/run.py --check
~~~

Commands and step numbers are unchanged. The configuration check validates all three files and the active scenario without downloading data or running ATLAS. It does not verify external services or credentials.

## Script reference tables

Each stage has an English guide describing every script, its purpose, prerequisites, outputs, and inclusion in the `all` sequence:

- [Preprocessing scripts](preprocessing/SCRIPT_GUIDE.md)
- [Processing scripts](processing/SCRIPT_GUIDE.md)
- [Postprocessing scripts](postprocessing/SCRIPT_GUIDE.md)
