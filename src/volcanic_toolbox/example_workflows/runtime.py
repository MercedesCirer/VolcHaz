"""Load plain settings and keep construction inside the package."""
from pathlib import Path
import ast
import sys
import os
from contextlib import contextmanager
from contextvars import ContextVar
import difflib
from .settings_adapter import expression

# Compatibility imports are internal; examples only exposes data and entry points.
sys.path.insert(0, str(Path(__file__).parent / "compat"))

CONFIG_MODULES = ("scenario_config", "scenario_config_multiphase", "atlas_input_config",
                  "atlas_remote_config", "postprocessing_config", "mapping_config")
_EXAMPLES = ContextVar("toolbox_examples", default=None)
_EXECUTING = ContextVar("toolbox_execution_active", default=False)
_MISSING = object()

def resolve_examples(default):
    """Use the active application configuration rather than an imported example cache."""
    return _EXAMPLES.get() or Path(default)

@contextmanager
def bind_examples(examples):
    """Bind configuration location without starting a model or workflow step."""
    token = _EXAMPLES.set(Path(examples).resolve())
    try:
        yield
    finally:
        _EXAMPLES.reset(token)

@contextmanager
def _execution_configuration(examples, namespace):
    if _EXECUTING.get():
        yield
        return
    previous = {}
    for name in CONFIG_MODULES:
        module = sys.modules.get(name, _MISSING)
        # Preserve the module currently being imported; dependencies are refreshed.
        if module is not _MISSING and vars(module) is namespace:
            continue
        previous[name] = module
        sys.modules.pop(name, None)
    token = _EXECUTING.set(True)
    try:
        with bind_examples(examples):
            yield
    finally:
        _EXECUTING.reset(token)
        for name, module in previous.items():
            if module is _MISSING:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = module

CONFIG_PATHS = {'01_sample_eruption_candidates': 'preprocessing/configs/preprocessing_config.py',
 '02_download_era5': 'preprocessing/configs/preprocessing_config.py',
 '03_prepare_meteorology_general': 'preprocessing/configs/preprocessing_config.py',
 '04_sample_meteorology_general': 'preprocessing/configs/preprocessing_config.py',
 '05_plot_monthly_wind_roses': 'preprocessing/configs/preprocessing_config.py',
 '06_build_vei_scenarios': 'preprocessing/configs/preprocessing_config.py',
 '07_plot_scenario_pairplots': 'preprocessing/configs/preprocessing_config.py',
 '08_compare_meteorology_validated_wind_roses': 'preprocessing/configs/preprocessing_config.py',
 '09_compare_sampled_vs_validated_parameters': 'preprocessing/configs/preprocessing_config.py',
 'scenario_config': 'preprocessing/configs/preprocessing_config.py',
 'scenario_config_multiphase': 'preprocessing/configs/preprocessing_config.py',
 '11_download_atlas_era5': 'processing/configs/processing_config.py',
 'atlas_input_config': 'processing/configs/processing_config.py',
 'atlas_remote_config': 'processing/configs/processing_config.py',
 'postprocessing_config': 'postprocessing/configs/postprocessing_config.py',
 '16_summarize_point_hazard': 'postprocessing/configs/postprocessing_config.py',
 '17_plot_point_hazard_curves': 'postprocessing/configs/postprocessing_config.py',
 'mapping_config': 'postprocessing/configs/postprocessing_config.py'}

STEP_CONFIG_KEYS = {'01_sample_eruption_candidates': {'NUMBER_OF_CANDIDATES': 'PREVIEW_NUMBER_OF_CANDIDATES',
                                   'RANDOM_SEED': 'PREVIEW_RANDOM_SEED',
                                   'HISTOGRAM_BINS': 'PREVIEW_HISTOGRAM_BINS',
                                   'HISTOGRAM_DENSITY': 'PREVIEW_HISTOGRAM_DENSITY',
                                   'OVERLAY_THEORETICAL_PDF': 'PREVIEW_OVERLAY_THEORETICAL_PDF',
                                   'SHOW_FIGURES': 'PREVIEW_SHOW_FIGURES'},
 '02_download_era5': {'ERA5_HALF_BOX_DEGREES': 'ERA5_HALF_BOX_DEGREES',
                      'ERA5_TIMES_UTC': 'ERA5_TIMES_UTC',
                      'ERA5_OVERWRITE': 'ERA5_OVERWRITE'},
 '03_prepare_meteorology_general': {'TMY_CONFIG': 'TMY_SETTINGS'},
 '04_sample_meteorology_general': {'SAMPLE_CONFIG': 'METEOROLOGY_SAMPLE_SETTINGS'},
 '05_plot_monthly_wind_roses': {'WIND_ROSE_DIRECTION_CONVENTION': 'WIND_ROSE_DIRECTION_CONVENTION',
                                'WIND_ROSE_USE_DAILY_VECTOR_MEANS': 'WIND_ROSE_USE_DAILY_VECTOR_MEANS',
                                'WIND_ROSE_PERCENTAGE': 'WIND_ROSE_PERCENTAGE'},
 '06_build_vei_scenarios': {'VEI_CONFIG': 'VEI_METADATA',
                            'BUILD_CONFIG': 'SCENARIO_BUILD_SETTINGS'},
 '07_plot_scenario_pairplots': {'MAX_POINTS': 'SCENARIO_PLOTS_MAX_POINTS',
                                'RANDOM_SEED': 'SCENARIO_PLOTS_RANDOM_SEED',
                                'DPI': 'SCENARIO_PLOTS_DPI',
                                'FILENAME_PREFIX': 'SCENARIO_PLOTS_FILENAME_PREFIX',
                                'PAIRPLOT_METRICS': 'SCENARIO_PLOTS_PAIRPLOT_METRICS'},
 '08_compare_meteorology_validated_wind_roses': {'DIRECTION_BINS': 'WIND_COMPARISON_DIRECTION_BINS',
                                                 'SPEED_BINS': 'WIND_COMPARISON_SPEED_BINS',
                                                 'DPI': 'WIND_COMPARISON_DPI'},
 '09_compare_sampled_vs_validated_parameters': {'HISTOGRAM_BINS': 'PARAMETER_COMPARISON_HISTOGRAM_BINS',
                                                'DENSITY': 'PARAMETER_COMPARISON_DENSITY',
                                                'DPI': 'PARAMETER_COMPARISON_DPI',
                                                'SHOW_FIGURES': 'PARAMETER_COMPARISON_SHOW_FIGURES'},
 '11_download_atlas_era5': {'ATLAS_AREA': 'ATLAS_AREA',
                            'ATLAS_DAYS_AFTER': 'ATLAS_DAYS_AFTER',
                            'ATLAS_MAX_WORKERS': 'ATLAS_MAX_WORKERS',
                            'ATLAS_OVERWRITE': 'ATLAS_OVERWRITE',
                            'ATLAS_KEEP_GRIB': 'ATLAS_KEEP_GRIB',
                            'ATLAS_GRIB_TO_NETCDF_EXECUTABLE': 'ATLAS_GRIB_TO_NETCDF_EXECUTABLE',
                            'ATLAS_NETCDF_KIND': 'ATLAS_NETCDF_KIND',
                            'ATLAS_NETCDF_DATA_TYPE': 'ATLAS_NETCDF_DATA_TYPE',
                            'ATLAS_NETCDF_COMPRESSION_LEVEL': 'ATLAS_NETCDF_COMPRESSION_LEVEL',
                            'ATLAS_DRY_RUN': 'ATLAS_DRY_RUN'},
 'atlas_input_config': {'ATLAS_INSTALL_BASE': 'ATLAS_INSTALL_BASE',
                        'ATLAS_DIRECTORY_NAME': 'ATLAS_DIRECTORY_NAME',
                        'ATLAS_RUN_FOLDER_MODE': 'ATLAS_RUN_FOLDER_MODE',
                        'ATLAS_REQUIRE_LOCAL_METEOROLOGY': 'ATLAS_REQUIRE_LOCAL_METEOROLOGY',
                        'ATLAS_FALLBACK_METEOROLOGY_HOURS': 'ATLAS_FALLBACK_METEOROLOGY_HOURS',
                        'ATLAS_INPUT_OVERWRITE': 'ATLAS_INPUT_OVERWRITE',
                        'ATLAS_MAIN_INPUT': 'ATLAS_MAIN_INPUT',
                        'ATLAS_VOLCANO_NAME': 'ATLAS_VOLCANO_NAME',
                        'ATLAS_NUMBER_PARTICLES': 'ATLAS_NUMBER_PARTICLES',
                        'ATLAS_MASS_FLOW_RATE': 'ATLAS_MASS_FLOW_RATE',
                        'ATLAS_SUZUKI_A': 'ATLAS_SUZUKI_A',
                        'ATLAS_SUZUKI_L': 'ATLAS_SUZUKI_L',
                        'ATLAS_TOP_HAT_DIAMETER_M': 'ATLAS_TOP_HAT_DIAMETER_M',
                        'ATLAS_PHASE_GRANULOMETRY': 'ATLAS_PHASE_GRANULOMETRY',
                        'ATLAS_DISTRIBUTION': 'ATLAS_DISTRIBUTION',
                        'ATLAS_NUMBER_OF_BINS': 'ATLAS_NUMBER_OF_BINS',
                        'ATLAS_DEFAULT_MEAN_PHI': 'ATLAS_DEFAULT_MEAN_PHI',
                        'ATLAS_DEFAULT_SORTING_PHI': 'ATLAS_DEFAULT_SORTING_PHI',
                        'ATLAS_PARTICLE_DENSITY_RANGE_KG_M3': 'ATLAS_PARTICLE_DENSITY_RANGE_KG_M3',
                        'ATLAS_SPHERICITY_RANGE': 'ATLAS_SPHERICITY_RANGE',
                        'ATLAS_AGGREGATE_SIZE_MICRONS': 'ATLAS_AGGREGATE_SIZE_MICRONS',
                        'ATLAS_DEFAULT_AGGREGATE_DENSITY_KG_M3': 'ATLAS_DEFAULT_AGGREGATE_DENSITY_KG_M3',
                        'ATLAS_DEFAULT_AGGREGATION_PERCENTAGE': 'ATLAS_DEFAULT_AGGREGATION_PERCENTAGE'},
 'atlas_remote_config': {'ATLAS_REMOTE_PHASES': 'ATLAS_REMOTE_PHASES',
                         'SSH_HOST': 'SSH_HOST',
                         'SSH_PORT': 'SSH_PORT',
                         'SSH_USER': 'SSH_USER',
                         'SSH_PASSWORD_ENV_VAR': 'SSH_PASSWORD_ENV_VAR',
                         'SSH_PRIVATE_KEY': 'SSH_PRIVATE_KEY',
                         'SSH_HOST_KEY_POLICY': 'SSH_HOST_KEY_POLICY',
                         'REMOTE_ATLAS_ROOT': 'REMOTE_ATLAS_ROOT',
                         'REMOTE_ATLAS_EXECUTABLE': 'REMOTE_ATLAS_EXECUTABLE',
                         'MPI_PROCESSES': 'MPI_PROCESSES',
                         'LAUNCH_COMMAND_TEMPLATE': 'LAUNCH_COMMAND_TEMPLATE',
                         'REMOTE_SHELL_PREAMBLE': 'REMOTE_SHELL_PREAMBLE',
                         'ATLAS_REMOTE_DRY_RUN': 'ATLAS_REMOTE_DRY_RUN',
                         'POLL_SECONDS': 'POLL_SECONDS',
                         'RECONNECT_SECONDS': 'RECONNECT_SECONDS',
                         'MAX_RECONNECT_ATTEMPTS': 'MAX_RECONNECT_ATTEMPTS',
                         'MIN_REMOTE_PART_BYTES': 'MIN_REMOTE_PART_BYTES',
                         'ACCEPT_NONEMPTY_PART_ON_FAILED_EXIT': 'ACCEPT_NONEMPTY_PART_ON_FAILED_EXIT',
                         'DONE_PART_RECHECK_SECONDS': 'DONE_PART_RECHECK_SECONDS',
                         'DONE_PART_MAX_RECHECKS': 'DONE_PART_MAX_RECHECKS',
                         'CLEANUP_REMOTE_SIMULATION': 'CLEANUP_REMOTE_SIMULATION',
                         'AUTO_DELETE_UNUSED_REMOTE_METEO': 'AUTO_DELETE_UNUSED_REMOTE_METEO',
                         'SKIP_MISSING_METEOROLOGY': 'SKIP_MISSING_METEOROLOGY',
                         'CONTINUE_ON_ERROR': 'CONTINUE_ON_ERROR'},
 'postprocessing_config': {'ATLAS_POSTPROCESS_CONFIG': 'ATLAS_POSTPROCESS_CONFIG',
                           'PROBABILITY_CUTOFF_PERCENT': 'PROBABILITY_CUTOFF_PERCENT',
                           'ATLAS_INDEX_CONFIG': 'ATLAS_INDEX_CONFIG',
                           'USE_SCENARIO_PHASES': 'USE_SCENARIO_PHASES'},
 '16_summarize_point_hazard': {'ZERO_TOLERANCE_PERCENT': 'ZERO_TOLERANCE_PERCENT'},
 '17_plot_point_hazard_curves': {'MIN_PROBABILITY_TO_PLOT_PERCENT': 'MIN_PROBABILITY_TO_PLOT_PERCENT'},
 'mapping_config': {'BASE_CONFIG': 'BASE_CONFIG',
                    'TEXT_CONFIG': 'TEXT_CONFIG',
                    'OUTPUT_CONFIG': 'OUTPUT_CONFIG',
                    'C3D': 'C3D',
                    'GL': 'GL',
                    'AT': 'AT',
                    'PT_CONDITIONAL': 'PT_CONDITIONAL',
                    'PT_UNCONDITIONAL': 'PT_UNCONDITIONAL',
                    'MAP_CONFIG': 'MAP_CONFIG',
                    'BASEMAP_SHP': 'BASEMAP_SHP'}}

def configuration_files(examples):
    """Return the three user-editable stage configuration files."""
    return [Path(examples)/stage/"configs"/(stage+"_config.py")
            for stage in ("preprocessing","processing","postprocessing")]

def load_settings(path):
    if not path.is_file():
        raise FileNotFoundError(f"Missing configuration file: {path}")
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except SyntaxError as error:
        raise ValueError(f"{path.name}:{error.lineno}: invalid configuration syntax. "
                         "Keep the quotes, commas, and brackets around the edited value.") from error
    values = {}
    for node in tree.body:
        if not isinstance(node, ast.Assign) or len(node.targets) != 1 or not isinstance(node.targets[0], ast.Name):
            raise ValueError(f"{path.name}: only variable assignments are allowed")
        key = node.targets[0].id
        if key in values:
            raise ValueError(f"{path.name}: duplicate setting {key}")
        try:
            values[key] = ast.literal_eval(node.value)
        except (ValueError, TypeError) as error:
            raise ValueError(f"{path.name}:{node.lineno}: {key} must contain plain data, "
                             "not a function call or expression.") from error
    return values

def get_step_settings(name, examples):
    """Select the variables required by one step from its consolidated stage file."""
    if name not in CONFIG_PATHS:
        return {}
    values = load_settings(Path(examples)/CONFIG_PATHS[name])
    known = {variable for step, mapping in STEP_CONFIG_KEYS.items()
             if CONFIG_PATHS[step] == CONFIG_PATHS[name] for variable in mapping.values()}
    if CONFIG_PATHS[name].startswith("preprocessing/"):
        known.update({"SCENARIO_TYPE", "MONOPHASE_SCENARIO", "MULTIPHASE_SCENARIO",
                      "RUN_PREVIEW", "DOWNLOAD_METEOROLOGY", "RUN_WIND_ROSES", "RUN_SCENARIO_PLOTS",
                      "RUN_WIND_COMPARISON", "RUN_PARAMETER_COMPARISON"})
    unknown = set(values)-known
    if unknown:
        key = sorted(unknown)[0]
        closest = difflib.get_close_matches(key, known, n=1)
        hint = f" Did you mean {closest[0]}?" if closest else ""
        raise ValueError(f"Unknown setting {key} in {CONFIG_PATHS[name]}.{hint}")
    if name in {"scenario_config","scenario_config_multiphase"}:
        kind = "multiphase" if name=="scenario_config_multiphase" else values["SCENARIO_TYPE"]
        if kind not in {"monophase","multiphase"}:
            raise ValueError("SCENARIO_TYPE must be monophase or multiphase")
        scenario = dict(values[kind.upper()+"_SCENARIO"])
        scenario["SCENARIO_TYPE"] = kind
        return scenario
    missing = set(STEP_CONFIG_KEYS[name].values())-set(values)
    if missing:
        raise ValueError(f"Missing setting {sorted(missing)[0]} in {CONFIG_PATHS[name]}")
    return {key: values[variable] for key, variable in STEP_CONFIG_KEYS[name].items()}

def execute(name, namespace, examples):
    """Run one step with fresh, consistently bound configuration dependencies."""
    with _execution_configuration(examples, namespace):
        return _execute(name, namespace, Path(examples))

def _execute(name, namespace, examples):
    if name in {"scenario_config", "scenario_config_multiphase"}:
        from .scenario_loader import configure_scenario
        namespace.update(configure_scenario(get_step_settings(name,examples)))
        def inherited_model_setting(key):
            if key not in STEP_CONFIG_KEYS["11_download_atlas_era5"]:
                raise AttributeError(key)
            return get_step_settings("11_download_atlas_era5",examples)[key]
        # Model-only controls are requested lazily; preprocessing needs no processing file.
        namespace["__getattr__"] = inherited_model_setting
        return
    path = Path(__file__).parent / (name + ".py")
    settings = get_step_settings(name,examples)
    if name=="postprocessing_config" and settings.pop("USE_SCENARIO_PHASES",True):
        from scenario_config import phase_configs
        phases=tuple(p.name for p in phase_configs())
        settings["ATLAS_POSTPROCESS_CONFIG"]["phases"]=phases
        settings["ATLAS_INDEX_CONFIG"]["phase_order"]=phases
        if len(phases)==1:
            settings["ATLAS_INDEX_CONFIG"]["calculate_weighted_index"]=False
    tree = ast.parse(path.read_text(encoding="utf-8-sig"))
    class Settings(ast.NodeTransformer):
        def visit_Assign(self, node):
            if len(node.targets)==1 and isinstance(node.targets[0],ast.Name) and node.targets[0].id in settings:
                node.value = expression(node.value, settings[node.targets[0].id])
            return node
        def visit_FunctionDef(self, node):
            if node.name.upper() in settings:
                for child in ast.walk(node):
                    if isinstance(child,ast.Return):
                        child.value = expression(child.value,settings[node.name.upper()])
            return node
    tree = ast.fix_missing_locations(Settings().visit(tree))
    namespace["__file__"] = str(Path(examples) / (name + ".py"))
    previous = Path.cwd()
    try:
        os.chdir(Path(examples).parent)
        exec(compile(tree,str(path),"exec"),namespace)
    finally:
        os.chdir(previous)


def validate_configuration(examples):
    """Check all three files and genuine cross-stage inconsistencies; do not run workflows."""
    import math
    from volcanic_toolbox.preprocessing.meteorology import TMYConfig, MeteorologySampleConfig
    from volcanic_toolbox.preprocessing.scenarios import ScenarioBuildConfig
    from volcanic_toolbox.preprocessing.eruption import VEIConfig
    for path in configuration_files(examples):
        load_settings(path)
    scene = {}
    execute("scenario_config", scene, examples)
    TMYConfig(**get_step_settings("03_prepare_meteorology_general",examples)["TMY_CONFIG"])
    MeteorologySampleConfig(number_of_samples=scene["N_METEOROLOGY_SAMPLES"],
                            **get_step_settings("04_sample_meteorology_general",examples)["SAMPLE_CONFIG"])
    ScenarioBuildConfig(height_reference=scene["COLUMN_HEIGHT_REFERENCE"],
                        **get_step_settings("06_build_vei_scenarios",examples)["BUILD_CONFIG"])
    VEIConfig(vei=scene["EVENT_VEI"],minimum_volume_km3=scene["MINIMUM_FALLOUT_VOLUME_KM3"],
              maximum_volume_km3=scene["MAXIMUM_FALLOUT_VOLUME_KM3"],bulk_density_kg_m3=scene["BULK_DENSITY_KG_M3"])
    active = {phase.name for phase in scene["phase_configs"]()}
    model = {}
    execute("atlas_input_config",model,examples)
    products = {}
    execute("postprocessing_config",products,examples)
    maps = {}
    execute("mapping_config",maps,examples)
    remote = get_step_settings("atlas_remote_config",examples)
    if not 1<=remote["SSH_PORT"]<=65535 or remote["MPI_PROCESSES"]<1:
        raise ValueError("SSH_PORT must be 1-65535 and MPI_PROCESSES must be positive")
    if remote["ATLAS_REMOTE_PHASES"] is not None and set(remote["ATLAS_REMOTE_PHASES"])-active:
        raise ValueError("ATLAS_REMOTE_PHASES contains names absent from the active preprocessing PHASES")
    probability = products["ATLAS_POSTPROCESS_CONFIG"]
    index = products["ATLAS_INDEX_CONFIG"]
    if probability.phases is not None and set(probability.phases)-active:
        raise ValueError("Postprocessing phases contain names absent from the active preprocessing PHASES")
    if index.enabled and set(index.phase_order)-active:
        raise ValueError("Hazard-index phase_order contains names absent from the active preprocessing PHASES")
    if not math.isclose(float(probability.dt_hours),float(model["ATLAS_MAIN_INPUT"].output_frequency_h)):
        raise ValueError("Postprocessing dt_hours must match processing ATLAS_MAIN_INPUT.output_frequency_h "
                         "for the model outputs being analyzed")
    available = {"c3d":probability.c3d_thresholds_kg_m3,"gl":probability.gl_thresholds_kg_m2,
                 "arrival":probability.arrival_hours,"persistence_conditional":probability.persistence_hours,
                 "persistence_unconditional":probability.persistence_hours}
    if index.enabled:
        for rule in index.rules:
            if rule.enabled and any(not any(math.isclose(float(level),float(v)) for v in available[rule.metric]) for level in rule.levels):
                raise ValueError(f"Hazard-index {rule.metric} levels must exist in the corresponding probability thresholds")
    for name in ("C3D","GL","AT","PT_CONDITIONAL","PT_UNCONDITIONAL"):
        settings=get_step_settings("mapping_config",examples)[name]
        if settings.get("enabled") and settings.get("phases") is not None and set(settings["phases"])-active:
            raise ValueError(f"Map {name}.phases contains names absent from the active preprocessing PHASES")
    return {"scenario_name":scene["SCENARIO_NAME"],"phase_count":len(active)}
