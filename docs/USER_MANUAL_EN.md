# VolcHaz user manual

[Español](MANUAL_ES.md)

VolcHaz connects three stages. Preprocessing pairs possible eruptions with historical atmospheric conditions and retains scenarios that meet physical constraints. Processing uses those scenarios to drive ATLAS, a model of tephra transport and deposition. Postprocessing estimates hazard for the simulated ensemble and produces tables, curves and maps. The supplied Lascar settings are retained to demonstrate the workflow. They were not the settings used in the original study.

## 1. Install VolcHaz

On GitHub, use **Code → Download ZIP**, then extract it, or clone the repository. Open Anaconda Prompt on Windows or a terminal with Conda on macOS/Linux. Change to the extracted folder containing `pyproject.toml` (replace the example path). Use this folder whenever running the commands in this manual.

```text
cd "path/to/VolcHaz"
conda create -n volchaz python=3.13 pip
conda activate volchaz
python -m pip install -e ".[all]"
python -m pip check
python workflow/run.py --check
```

VolcHaz requires Python 3.10 or newer. On later visits, run `conda activate volchaz` again. The editable installation reads the source in this folder. `python -m pip install -r requirements.txt` installs the same complete set. The core packages are NumPy and SciPy for numerical work, pandas for tables and Matplotlib for graphics. The `era5` extra adds xarray, netCDF4 and cdsapi for atmospheric data. The `atlas` extra adds netCDF4 and Paramiko for model output and SSH. The `mapping` extra adds netCDF4, GeoPandas, Shapely, pyproj and Cartopy for maps. A preprocessing-only installation can use `python -m pip install -e ".[era5]"`. Package versions are declared in `pyproject.toml`.

### Connect to Copernicus CDS

1. Register or sign in to the Climate Data Store. Visit the CDS API setup page and copy the URL and personal access token from your account. Install `cdsapi` with `python -m pip install "cdsapi>=0.7"` if you did not install the `era5` or `all` extra. [CDS API setup](https://cds.climate.copernicus.eu/how-to-api)
2. Create a plain-text file named `.cdsapirc` in your home directory. On Windows use `%USERPROFILE%\.cdsapirc` and check that the editor did not append `.txt`. On macOS/Linux use `~/.cdsapirc`. Replace the placeholder with the token from your account. Keep this file outside VolcHaz.

   ```yaml
   url: https://cds.climate.copernicus.eu/api
   key: YOUR_PERSONAL_ACCESS_TOKEN
   ```
3. Sign in and accept the terms on the download page for ERA5 pressure levels. Also accept the single-level terms for ATLAS forcing. A valid token alone does not grant access to datasets whose terms you have yet to accept. [ERA5 pressure levels](https://cds.climate.copernicus.eu/datasets/reanalysis-era5-pressure-levels?tab=download) · [ERA5 single levels](https://cds.climate.copernicus.eu/datasets/reanalysis-era5-single-levels?tab=download)
4. Run preprocessing step 02 to submit the requests. Check **Your requests** in CDS for a queued job. For an authorization error, review the token, URL and dataset terms. If a transfer fails, rerun step 02 to reuse readable cached files when `ERA5_OVERWRITE=False`.

### Install the converter and prepare ATLAS

Install ecCodes on the computer that downloads complete ATLAS meteorology. In the active environment, run `conda install -c conda-forge eccodes` and check `grib_to_netcdf -V`. If the converter is installed in a different location, set its executable path in `ATLAS_GRIB_TO_NETCDF_EXECUTABLE`. Use a distribution with the NetCDF-enabled converter. [ecCodes package](https://github.com/conda-forge/eccodes-feedstock) · [Converter documentation](https://confluence.ecmwf.int/spaces/ECC/pages/45747871/grib_to_netcdf)

ATLAS is installed separately on the server that will run the simulations. Ask the server administrator for SSH access, an appropriate allocation, and the path to a build compatible with the generated ERA5 inputs. To build ATLAS-1.0, follow its repository and manual. Its requirements include MPI (for example Open MPI or MPICH), an MPI-compatible Fortran compiler, NCO, NetCDF-Fortran, Python 3 and make. Configure its Makefile for the server, run `make` at the ATLAS root, and locate `Runs/P_ATLAS.1.0.x`. Run the ATLAS-provided demonstration on the server to verify the model and its libraries before connecting VolcHaz. [ATLAS-1.0 source and installation](https://github.com/ATLASFlor/ATLAS-1.0)

## 2. Find and edit your files

```text
VolcHaz/
├── README.md, LICENSE, pyproject.toml, requirements.txt
├── docs/                        Bilingual manuals
├── workflow/
│   ├── run.py                   Menu and numbered step launcher
│   ├── atlas_points.csv          Locations for point analysis
│   ├── preprocessing/
│   │   ├── configs/preprocessing_config.py
│   │   ├── configs/multiphase_example.txt
│   │   └── 01–10 scripts and run_all.py
│   ├── processing/
│   │   ├── configs/processing_config.py
│   │   └── 01–04 scripts and run_all.py
│   └── postprocessing/
│       ├── configs/postprocessing_config.py
│       └── 01–06 scripts and run_all.py
├── src/volcanic_toolbox/         Python implementation
├── data/                       Local ERA5 and basemaps, added as needed
└── outputs/<SCENARIO_NAME>/      Generated results by stage
```

Open the three `*_config.py` files in a text editor. Change values to the right of `=` or `:`. Keep variable names, commas, brackets and quotes around text. Write decimals with a period and use `True`, `False` and `None` exactly as shown. Lines starting with `#` explain each field. Edit `workflow/atlas_points.csv` if using a point table. After each edit run `python workflow/run.py --check`. This checks the configuration and consistency across stages without connecting to external services. Run `python workflow/run.py` to use the interactive menu, or supply a stage and step number directly.

## 3. Preprocessing — prepare accepted scenarios

Edit [preprocessing_config.py](../workflow/preprocessing/configs/preprocessing_config.py). With `SCENARIO_TYPE='monophase'`, change `MONOPHASE_SCENARIO`. For multiple phases, copy the whole `MULTIPHASE_SCENARIO = {...}` assignment from [multiphase_example.txt](../workflow/preprocessing/configs/multiphase_example.txt) into section B of the same Python file and set `SCENARIO_TYPE='multiphase'`. Use the same phase names in `PHASES` and `PHASE_METEOROLOGY`.

- `SCENARIO_NAME` names the data and output directories. `LATITUDE` and `LONGITUDE` are decimal degrees (south and west are negative). `VENT_ELEVATION_M` is metres above sea level. `COLUMN_HEIGHT_REFERENCE` sets the height datum, `above_vent` or `asl`.
- `YEARS` includes both endpoints. For each phase, choose `pressure_level_hpa` and `source`. The `historical` source uses the full record. The `tmy` source uses representative months selected from the historical record with `TMY_SETTINGS`, based on agreement in wind speed and direction. The selected records retain historical timestamps for subsequent ATLAS forcing. `ERA5_HALF_BOX_DEGREES` sets the extraction half-width and `ERA5_TIMES_UTC` the observation times. `N_METEOROLOGY_SAMPLES` and `METEOROLOGY_SAMPLE_SETTINGS` control the size, seed and replacement of the wind sample.
- `PHASES` defines candidate column heights, equivalent durations, grain-size and aggregation parameters. Keep the machine names such as `column_height` and `duration`. Select `distribution`, its `parameters` and admissible `bounds` together. Equivalent duration is the time over which the modeled phase releases material. Use `TGSD_MIN_PHI` and `TGSD_MAX_PHI` for the grain-size limits. Lower phi means coarser grains.
- Give the event an `EVENT_VEI` label and specify `MINIMUM_FALLOUT_VOLUME_KM3`, `MAXIMUM_FALLOUT_VOLUME_KM3` and `BULK_DENSITY_KG_M3`. VolcHaz converts volume to mass, estimates wind-dependent mass eruption rate (kg/s), and multiplies by duration in seconds. For multiphase cases the event constraint applies to the sum of phase masses. `SCENARIO_BUILD_SETTINGS` controls the accepted target, batch size, maximum attempts, seed and pairing with replacement. `SEASONS` labels subsets for preprocessing summaries.

For example, Lascar uses `pressure_level_hpa=50` for phase `eruption`, `YEARS=(2010, 2020)`, and a target of 1,000 accepted scenarios with fallout volumes between 0.08 and 0.12 km³. A uniform distribution takes `low` and `high`. A triangular one takes `left`, `mode` and `right`. A normal one takes `mean` and `std`, and a fixed input takes `value`. By default a lognormal uses `mu` and `sigma` in log space. Distinguish the distribution's parameters from the optional `minimum` and `maximum` in `bounds`. These limits control sampling before the physical check.

Run these commands on a fresh checkout. Step 02 downloads one NetCDF per year and phase to `data/era5/<SCENARIO_NAME>/<phase>/`. With complete compatible files already there, start at step 03. Keep only the files matching the intended period, level, area and UTC times in that phase folder. Use a new `SCENARIO_NAME` when changing the meteorological inputs, or replace stale files before rerunning.

```text
python workflow/run.py preprocessing 02
python workflow/run.py preprocessing 03
python workflow/run.py preprocessing 04
python workflow/run.py preprocessing 06
python workflow/run.py preprocessing 10
```

Step 03 extracts the wind series near the volcano and writes `full_wind_data.csv`, plus TMY diagnostics where applicable. Step 04 saves `selected_meteorology_samples.csv`. Step 06 writes accepted scenarios, all evaluated combinations and a summary in `outputs/<SCENARIO_NAME>/preprocessing/scenarios/`. Confirm the accepted count and volume range. If the attempt limit is reached, review the physical assumptions and sampling bounds before deciding whether to increase `max_attempts`. Step 10 prints the accepted phase-date-wind pairings.

Optional steps are 01 (candidate histograms), 05 (annual and monthly wind roses), 07 (pairplots), 08 (winds before/after physical selection), and 09 (candidate versus accepted parameter histograms, requiring 01 and 06). `python workflow/run.py preprocessing all` runs 03, 04 and 06 plus download and diagnostics selected by `DOWNLOAD_METEOROLOGY` and the `RUN_*` flags. If `RUN_PARAMETER_COMPARISON=True`, it also runs 01. Step 10 is separate. See the [preprocessing script reference](../workflow/preprocessing/SCRIPT_GUIDE.md).

## 4. Processing — prepare meteorology, build inputs and run ATLAS

Edit [processing_config.py](../workflow/processing/configs/processing_config.py). The scenario identity and phase dates come from preprocessing.

1. Set `ATLAS_AREA` as (north, west, south, east) and `ATLAS_DAYS_AFTER` to cover transport after onset. An onset day plus five additional days requests six calendar days. The meteorology for this stage uses complete pressure-level and single-level ERA5 fields. The wind series sampled in preprocessing serves to select scenarios.
2. Run `python workflow/run.py processing 01` with `ATLAS_DRY_RUN=True` to inspect the request plan in `outputs/<SCENARIO_NAME>/processing/atlas/manifests/`. Then set it to `False` and run 01 again to download, convert and assemble `YYYYMMDD.era5.nc` forcing files in `atlas/era5/`. Start with `ATLAS_MAX_WORKERS=1`. If converted chunks exist and only assembly was interrupted, run `python workflow/run.py processing 02` to resume assembly.
3. Set `ATLAS_INSTALL_BASE` to the remote parent directory, `ATLAS_DIRECTORY_NAME` to the installation folder and `REMOTE_ATLAS_ROOT` to their combined absolute path. Confirm `ATLAS_VOLCANO_NAME` and review `ATLAS_MAIN_INPUT` (domain top, grid resolution, integration step and output frequency), `ATLAS_NUMBER_PARTICLES`, `ATLAS_MASS_FLOW_RATE`, source settings and grain properties against your ATLAS build. Set `ATLAS_REQUIRE_LOCAL_METEOROLOGY=True` when generating inputs for actual runs. Run `python workflow/run.py processing 03`. Inspect `atlas/inputs/atlas_input_manifest.csv` and the main/phase `.inp` files before proceeding.
4. Set `SSH_HOST`, `SSH_PORT`, `SSH_USER` and `REMOTE_ATLAS_EXECUTABLE`. Confirm the server fingerprint with the administrator and connect once using `ssh -p PORT USER@HOST` so the verified key is recorded in your local SSH known-hosts file. Keep `SSH_HOST_KEY_POLICY='reject'`. Use your SSH agent or set `SSH_PRIVATE_KEY` to the path to your key. If password authentication is required, place the password in the local environment variable named by `SSH_PASSWORD_ENV_VAR` (default `ATLAS_SSH_PASSWORD`), keeping it out of the configuration and repository.
5. Configure `MPI_PROCESSES`, `REMOTE_SHELL_PREAMBLE` and `LAUNCH_COMMAND_TEMPLATE` for the server allocation. The launcher fills `{mpi_processes}`, `{executable}`, `{date}` and `{run_dir}`; it expects the command to reflect completion of ATLAS. On a scheduler-managed cluster, use an administrator-approved launch procedure that waits for model completion. Review `SKIP_MISSING_METEOROLOGY`, `ACCEPT_NONEMPTY_PART_ON_FAILED_EXIT`, `CLEANUP_REMOTE_SIMULATION` and `AUTO_DELETE_UNUSED_REMOTE_METEO` before running. The two cleanup flags control deletion of remote runs and unused forcing.
6. Run `python workflow/run.py processing 04` with `ATLAS_REMOTE_DRY_RUN=True` first to verify the connection and paths. After successful validation, set it to `False` and run 04 again to upload inputs and forcing, execute ATLAS and retrieve results. Confirm the local `*.part.nc` files in `outputs/<SCENARIO_NAME>/processing/atlas/runs/<phase>/<run_folder>/`. The runner can reuse local completed outputs. For a changed model or ensemble use a new scenario directory so old results do not mix with new ones.

`python workflow/run.py processing all` runs 01, 03 and 04 in sequence. See the [processing script reference](../workflow/processing/SCRIPT_GUIDE.md).

If you use password authentication, this prompts for the password without embedding it in the command. Run it in the same activated terminal you will use for step 04. Delete the temporary variable with `Remove-Item Env:ATLAS_SSH_PASSWORD` in PowerShell or `unset ATLAS_SSH_PASSWORD` in Bash afterward.

**PowerShell 7**

```powershell
$env:ATLAS_SSH_PASSWORD = Read-Host -MaskInput "ATLAS SSH password"
```

**Bash**

```bash
read -r -s -p "ATLAS SSH password: " ATLAS_SSH_PASSWORD
export ATLAS_SSH_PASSWORD
```

## 5. Postprocessing — estimate and map hazard

Edit [postprocessing_config.py](../workflow/postprocessing/configs/postprocessing_config.py). First run `python workflow/run.py postprocessing 02` to inspect up to five retrieved files. In `ATLAS_POSTPROCESS_CONFIG`, set the airborne concentration thresholds `c3d_thresholds_kg_m3`, final ground-load thresholds `gl_thresholds_kg_m2`, named `altitude_ranges` in metres above sea level and the vertical operators. Set `arrival_hours`, `persistence_hours` and `dt_hours`, which must match the saved interval `output_frequency_h`. Each `month_groups` entry names a subset of simulation onset months. To use the same seasons throughout, synchronize these groups with preprocessing `SEASONS`.

`probability_comparison` selects strict or inclusive exceedance. Concentration and ground-load probabilities describe the fraction of contributing simulations meeting the configured criteria. Arrival gives the probability that the first exceedance occurs by the requested hour. Persistence describes the contiguous exceedance after first arrival. Conditional persistence uses simulations with an exceedance as its denominator, and unconditional persistence uses all contributing simulations. Review sample counts and invalid-file reports, especially when `skip_invalid_files=True`. VolcHaz reports percentages for the selected ensemble. Interpreting them as annual probabilities requires a separate eruption-frequency model.

Set `ATLAS_INDEX_CONFIG` and `PROBABILITY_CUTOFF_PERCENT` for hazard classes. Every threshold and time used by an index or a map must exist among the calculated outputs. Multiphase indices combine ordinal classes with configured rules and weights. They do not represent joint probabilities or summed physical concentrations. For locations, edit [atlas_points.csv](../workflow/atlas_points.csv) with the header `point_id,latitude,longitude`, or set `inline_points`. Choose the nearest cell or inverse-distance weighting in `point_extraction`. Set `point_table=None` and `inline_points=()` to omit locations.

```text
python workflow/run.py postprocessing 01
python workflow/run.py postprocessing 04
python workflow/run.py postprocessing 05
python workflow/run.py postprocessing 06
```

Step 01 produces probability NetCDFs under `outputs/<SCENARIO_NAME>/postprocessing/atlas/<phase>/<subset>/probability_fields/` and writes configuration and manifest records in `postprocessing/atlas/`. When enabled it also produces hazard indices and point results. Step 03 re-extracts point results from existing grids if only the locations or point interpolation changed. Step 04 summarizes the point CSV and checks curve consistency. Step 05 plots selected groups using `MIN_PROBABILITY_TO_PLOT_PERCENT`. Run those point-specific steps when you have point outputs.

For step 06, download Natural Earth's **Admin 0 – Countries** 1:10m shapefile and extract its components together under `data/basemaps/global/`. The default `BASEMAP_SHP` expects `ne_10m_admin_0_countries.shp` there, alongside its `.dbf`, `.shx` and `.prj` files. Configure metrics in `C3D`, `GL`, `AT`, `PT_CONDITIONAL` and `PT_UNCONDITIONAL`. Each metric can set `extent` as (west, east, south, north) or inherit the overall display extent with `None`. Map extent controls framing. Use `BASE_CONFIG` for interpolation, `OUTPUT_CONFIG` for files and `MAP_CONFIG` for the visibility cutoff. Check `stage6_mapping_manifest.csv` for the generated maps. [Natural Earth download](https://www.naturalearthdata.com/downloads/10m-cultural-vectors/10m-admin-0-countries/)

`python workflow/run.py postprocessing all` runs 01 and 06. Recalculate 01 after changing thresholds, altitude intervals or simulation subsets. For appearance changes alone, rerun 06. Keep your configuration files, seeds, model and Python package versions, forcing records and manifests with any results used in a scientific study. See the [postprocessing script reference](../workflow/postprocessing/SCRIPT_GUIDE.md) and the [configuration reference](../workflow/CONFIGURATION.md).
