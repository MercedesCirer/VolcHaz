# Processing script guide

Prepare complete atmospheric forcing and ATLAS input files, then execute the model. Edit [processing_config.py](configs/processing_config.py). Scenario identity, phases, and validated meteorological dates originate from preprocessing.

Run commands from the toolbox root in your activated Python environment:

```bash
python workflow/run.py processing all
python workflow/run.py processing 02
```

Replace `02` with the required step number. Output paths below are relative to `outputs/<SCENARIO_NAME>/processing/`. The representative winds used in preprocessing are not a substitute for the complete atmospheric fields required by ATLAS.

| Script | Purpose and operation | Required inputs / previous steps | Main outputs | Included in `all` |
|---|---|---|---|---|
| `01_prepare_model_meteorology.py` | Plan ERA5 requests for validated scenario dates; download missing atmospheric products, convert GRIB, and assemble ATLAS meteorology. Reuse complete files where supported by the configured overwrite/resume behavior. | Accepted preprocessing scenario table; domain/date settings; CDS access and `grib_to_netcdf` for actual downloads/conversion. | Request plans, manifests, coverage summaries, and request preview under `atlas/manifests/`; complete forcing files `atlas/era5/<phase>/<date>/YYYYMMDD.era5.nc` and intermediate products as applicable. | Yes. |
| `02_resume_meteorology.py` | Resume assembly of final forcing files from existing pressure-level and single-level NetCDF chunks without requesting new downloads. | Previously downloaded/converted chunks from step 01; the same forcing settings. | Completed/appended `YYYYMMDD.era5.nc` files in the ATLAS meteorology tree; refreshed preparation records. | No; recovery operation executed separately. |
| `03_build_model_inputs.py` | Translate validated scenarios and phase settings into ATLAS main and phase input files and record their meteorological associations. | Accepted preprocessing table; configured ATLAS installation and phase settings; local forcing from step 01 when required by configuration. | Per-run main/phase input files under `atlas/inputs/`; `atlas/inputs/atlas_input_manifest.csv`. | Yes, after step 01. |
| `04_run_model.py` | Execute prepared ATLAS runs through SSH/MPI, transfer required files, retrieve model results, and apply configured resume behavior. | Step 03 input manifest; forcing; SSH access; remote ATLAS installation and launch settings. | Retrieved simulation outputs, including `*.part.nc`, under `atlas/runs/`; configured execution logs and console status summary. | Yes, after step 03. |
| `run_all.py` | Execute steps 01, 03, and 04 in order. Step 02 is a recovery alternative, not an additional required preparation step. | All requirements of steps 01, 03, and 04. | Outputs of those individual steps. | Invoked by the `all` command. |

## Execution modes

`ATLAS_DRY_RUN=True` in the processing configuration prepares meteorological requests without submitting downloads. `ATLAS_REMOTE_DRY_RUN=True` validates the remote execution environment without launching simulations. These modes do not produce a complete new set of model results. Before a real model run, confirm the intended dry-run settings and the input/forcing paths.

Postprocessing requires actual retrieved ATLAS outputs. Exact run-folder names and retained intermediate files depend on the configured run-folder, overwrite, and cleanup settings. The generated manifests record the paths used for each run.
