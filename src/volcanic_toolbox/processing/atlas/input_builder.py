"""Generate ATLAS 1.0 ERA5/Suzuki input files from accepted scenarios.

Supported scope
---------------
* One ERA5 meteorology per run.
* One eruptive phase per run.
* Suzuki vertical source distribution.
* Gaussian or bigaussian granulometric distribution.
* Percentage aggregation model.
* ``SIMULATION_END = number_of_meteorological_time_records - 1``.

Every configurable Phase1 parameter may be supplied either as:

* a constant; or
* the name of a column in the scenario table.

The builder does not create the external ATLAS installation tree. It writes
the paths that ATLAS will use after the generated inputs and meteorologies are
copied into that tree.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
import json
import math
from pathlib import Path, PurePosixPath
from typing import Any, Mapping

import pandas as pd
from netCDF4 import Dataset


class AtlasInputError(RuntimeError):
    """Raised when an ATLAS input cannot be generated safely."""


@dataclass(frozen=True)
class AtlasValue:
    """A value read from either a constant or a scenario-table column.

    Exactly one of ``constant`` or ``column`` must be supplied.

    Parameters
    ----------
    constant
        Fixed value used for every scenario of the phase.
    column
        Exact scenario-table column name.
    scale
        Multiplicative factor applied after reading the value. This is useful
        for converting an aggregation fraction (0--1) into percentage (0--100)
        by setting ``scale=100``.
    """

    constant: Any | None = None
    column: str | None = None
    scale: float = 1.0

    def __post_init__(self) -> None:
        selected = int(self.constant is not None) + int(self.column is not None)
        if selected != 1:
            raise ValueError(
                "AtlasValue requires exactly one of 'constant' or 'column'."
            )


@dataclass(frozen=True)
class AtlasPairValue:
    """Two ATLAS values, each independently constant or column based."""

    first: AtlasValue
    second: AtlasValue


@dataclass(frozen=True)
class AtlasMainInputConfig:
    """Configuration shared by all main ``.inp`` files.

    Parameters
    ----------
    time_step_seconds
        ATLAS numerical integration time step, in seconds.
    restart
        ``yes`` or ``no``.
    ztop_m
        Top of the computational domain, in metres.
    vertical_resolution_m
        Vertical grid spacing, in metres.
    longitude_resolution_deg, latitude_resolution_deg
        Horizontal computational-grid resolution, in degrees.
    output_frequency_h
        Output interval, in hours.
    vertical_layers
        ATLAS vertical-layer specification. It may be a spacing such as
        ``"1000"`` or an ATLAS-compatible explicit layer string.
    output_classes, output_phases, output_track_points
        ATLAS ``yes``/``no`` switches.
    terminal_velocity_model
        ATLAS terminal-velocity model code. For Ganser use ``2``.
    meteo_postprocess
        ERA5 postprocessing switch, normally ``no`` for prepared ERA5 files.
    """

    time_step_seconds: float = 15.0
    restart: str = "no"
    ztop_m: float = 55_000.0
    vertical_resolution_m: float = 1_000.0
    longitude_resolution_deg: float = 0.25
    latitude_resolution_deg: float = 0.25
    output_frequency_h: float = 1.0
    vertical_layers: str = "1000"
    output_classes: str = "no"
    output_phases: str = "no"
    output_track_points: str = "no"
    terminal_velocity_model: int = 2
    meteo_postprocess: str = "no"


@dataclass(frozen=True)
class AtlasPhaseConfig:
    """Complete independent configuration for one probabilistic phase.

    Required variable sources
    -------------------------
    datetime
        Date/time assigned to the phase.
    column_height
        Plume-top height. Interpretation is controlled globally by
        ``column_height_reference``.
    duration
        Eruption duration, in hours.

    Other parameters
    ----------------
    number_particles
        Number of computational particles.
    phase_name
        Text written as ``PHASE_NAME``.
    phase_type
        Fixed to ``eruption`` by validation.
    mass_flow_rate
        Numeric kg/s value or an ATLAS estimation string such as
        ``ESTIMATE-DEGRUYTER``.
    a_suzuki, l_suzuki
        Suzuki vertical-distribution parameters.
    d_top_hat_m
        Top-hat diameter written for ATLAS input completeness. It is not used
        when ``SOURCE_TYPE = suzuki``.
    volcano_name
        Volcano name or ``unknown``.
    source_longitude, source_latitude, source_elevation
        Source coordinates and elevation.
    phase_granulometry
        Path to an external granulometry file or ``NONE``.
    distribution
        ``GAUSSIAN`` or ``BIGAUSSIAN``.
    number_of_bins
        Number of granulometric bins.
    fi_mean_1, fi_disp_1
        Mean and dispersion of a Gaussian distribution, or the first
        component of a bigaussian distribution.
    fi_mean_2, fi_disp_2
        Required only for ``BIGAUSSIAN``.
    fi_range, density_range, sphericity_range
        Two-value ATLAS ranges.
    aggregate_size_microns
        Aggregate diameter in micrometres.
    aggregate_density_kg_m3
        Aggregate density in kg/m3.
    aggregation_percentage
        Percentage from 0 to 100. A table fraction can be converted with
        ``AtlasValue(column="...", scale=100)``.
    """

    datetime: AtlasValue
    column_height: AtlasValue
    duration: AtlasValue

    number_particles: AtlasValue = field(
        default_factory=lambda: AtlasValue(constant=5_000_000)
    )
    phase_name: AtlasValue = field(
        default_factory=lambda: AtlasValue(constant="phase")
    )
    phase_type: AtlasValue = field(
        default_factory=lambda: AtlasValue(constant="eruption")
    )
    mass_flow_rate: AtlasValue = field(
        default_factory=lambda: AtlasValue(
            constant="ESTIMATE-DEGRUYTER"
        )
    )
    a_suzuki: AtlasValue = field(
        default_factory=lambda: AtlasValue(constant=4.0)
    )
    l_suzuki: AtlasValue = field(
        default_factory=lambda: AtlasValue(constant=5.0)
    )
    d_top_hat_m: AtlasValue = field(
        default_factory=lambda: AtlasValue(constant=2_000.0)
    )

    volcano_name: AtlasValue = field(
        default_factory=lambda: AtlasValue(constant="unknown")
    )
    source_longitude: AtlasValue = field(
        default_factory=lambda: AtlasValue(constant=0.0)
    )
    source_latitude: AtlasValue = field(
        default_factory=lambda: AtlasValue(constant=0.0)
    )
    source_elevation: AtlasValue = field(
        default_factory=lambda: AtlasValue(constant=0.0)
    )

    phase_granulometry: AtlasValue = field(
        default_factory=lambda: AtlasValue(constant="NONE")
    )
    distribution: AtlasValue = field(
        default_factory=lambda: AtlasValue(constant="GAUSSIAN")
    )
    number_of_bins: AtlasValue = field(
        default_factory=lambda: AtlasValue(constant=14)
    )

    fi_mean_1: AtlasValue = field(
        default_factory=lambda: AtlasValue(constant=-0.413)
    )
    fi_disp_1: AtlasValue = field(
        default_factory=lambda: AtlasValue(constant=2.809)
    )
    fi_mean_2: AtlasValue | None = None
    fi_disp_2: AtlasValue | None = None

    fi_range: AtlasPairValue = field(
        default_factory=lambda: AtlasPairValue(
            AtlasValue(constant=-8.0),
            AtlasValue(constant=12.0),
        )
    )
    density_range: AtlasPairValue = field(
        default_factory=lambda: AtlasPairValue(
            AtlasValue(constant=440.0),
            AtlasValue(constant=2300.0),
        )
    )
    sphericity_range: AtlasPairValue = field(
        default_factory=lambda: AtlasPairValue(
            AtlasValue(constant=0.7),
            AtlasValue(constant=0.9),
        )
    )

    aggregate_size_microns: AtlasValue = field(
        default_factory=lambda: AtlasValue(constant=250.0)
    )
    aggregate_density_kg_m3: AtlasValue = field(
        default_factory=lambda: AtlasValue(constant=400.0)
    )
    aggregation_percentage: AtlasValue = field(
        default_factory=lambda: AtlasValue(constant=20.0)
    )


@dataclass(frozen=True)
class AtlasInputBuildConfig:
    """Top-level builder configuration.

    Parameters
    ----------
    scenario_table
        Accepted scenario CSV.
    local_inputs_root
        Local toolbox directory where generated input folders are written.
    local_meteorology_root
        Local root containing
        ``<phase>/date_YYYYMMDD/YYYYMMDD.era5.nc``.
    atlas_install_base
        Base path written inside ATLAS inputs, for example ``/users/your_username``.
    atlas_directory_name
        ATLAS installation folder, normally ``ATLAS-1.0``.
    meteorology_area
        ERA5 area as ``(north, west, south, east)``.
    domain_margin_deg
        Margin removed inward from every meteorological boundary.
    phases
        Independent phase configurations keyed by phase name.
    main
        Main ``.inp`` constants.
    accepted_column
        Acceptance column. Set to ``None`` when the table already contains
        accepted rows only.
    scenario_id_column
        Column used to distinguish scenarios. When absent, source-row numbers
        are used.
    run_folder_mode
        ``date_and_scenario`` is collision safe.
        ``date_only`` produces ``simulation_YYYYMMDD`` and is valid only when
        each phase/date occurs once.
    column_height_reference
        ``asl`` subtracts source elevation before writing COLUMN_HEIGHT.
        ``above_vent`` writes the value directly.
    overwrite
        Replace generated local inputs.
    require_local_meteorology
        Require each final ``.era5.nc`` to exist.
    fallback_meteorology_hours
        Used only while meteorologies are still being prepared. For six days
        of hourly data use 144. When the file exists, its actual time length
        always takes precedence.
    """

    scenario_table: Path
    local_inputs_root: Path
    local_meteorology_root: Path
    atlas_install_base: str

    meteorology_area: tuple[float, float, float, float]
    phases: Mapping[str, AtlasPhaseConfig]

    atlas_directory_name: str = "ATLAS-1.0"
    domain_margin_deg: float = 0.5
    main: AtlasMainInputConfig = field(
        default_factory=AtlasMainInputConfig
    )

    accepted_column: str | None = "accepted"
    scenario_id_column: str | None = "scenario_id"
    run_folder_mode: str = "date_and_scenario"
    column_height_reference: str = "asl"

    overwrite: bool = False
    require_local_meteorology: bool = False
    fallback_meteorology_hours: int | None = None


def _resolve(
    specification: AtlasValue,
    row: pd.Series,
    *,
    phase: str,
    parameter: str,
) -> Any:
    if specification.column is not None:
        if specification.column not in row.index:
            raise AtlasInputError(
                f"Phase {phase!r}: column {specification.column!r} "
                f"configured for {parameter!r} is missing."
            )
        value = row[specification.column]
        if pd.isna(value):
            raise AtlasInputError(
                f"Phase {phase!r}: missing value in column "
                f"{specification.column!r} for {parameter!r}."
            )
    else:
        value = specification.constant

    if specification.scale != 1.0:
        try:
            value = float(value) * float(specification.scale)
        except (TypeError, ValueError) as error:
            raise AtlasInputError(
                f"Phase {phase!r}: {parameter!r} cannot be scaled."
            ) from error

    return value


def _resolve_pair(
    specification: AtlasPairValue,
    row: pd.Series,
    *,
    phase: str,
    parameter: str,
) -> tuple[float, float]:
    first = float(
        _resolve(
            specification.first,
            row,
            phase=phase,
            parameter=f"{parameter}[0]",
        )
    )
    second = float(
        _resolve(
            specification.second,
            row,
            phase=phase,
            parameter=f"{parameter}[1]",
        )
    )
    return first, second


def _number(value: Any, phase: str, parameter: str) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError) as error:
        raise AtlasInputError(
            f"Phase {phase!r}: {parameter!r} must be numeric; "
            f"received {value!r}."
        ) from error

    if not math.isfinite(result):
        raise AtlasInputError(
            f"Phase {phase!r}: {parameter!r} must be finite."
        )
    return result


def _format_number(value: Any) -> str:
    numeric = float(value)
    if numeric.is_integer():
        return str(int(numeric))
    return f"{numeric:.10f}".rstrip("0").rstrip(".")


def _round_positive_integer(value: Any) -> int:
    """Round a non-negative ATLAS value to the nearest integer."""
    numeric = float(value)
    return int(math.floor(numeric + 0.5))


def _safe_identifier(value: Any) -> str:
    text = str(value).strip()
    cleaned = "".join(
        character if character.isalnum() or character in "-_" else "_"
        for character in text
    )
    return cleaned.strip("_") or "scenario"


def _parse_datetime(value: Any, phase: str) -> datetime:
    parsed = pd.to_datetime(value, errors="coerce")
    if pd.isna(parsed):
        raise AtlasInputError(
            f"Phase {phase!r}: invalid datetime {value!r}."
        )
    return parsed.to_pydatetime()


def _hour_from_midnight(moment: datetime) -> float:
    return (
        moment.hour
        + moment.minute / 60.0
        + moment.second / 3600.0
        + moment.microsecond / 3_600_000_000.0
    )


def _atlas_root(config: AtlasInputBuildConfig) -> PurePosixPath:
    base = PurePosixPath(config.atlas_install_base)
    if base.name == config.atlas_directory_name:
        return base
    return base / config.atlas_directory_name


def _domain(
    area: tuple[float, float, float, float],
    margin: float,
) -> tuple[float, float, float, float]:
    north, west, south, east = map(float, area)

    if north <= south or east <= west:
        raise AtlasInputError(
            f"Invalid meteorology area {area}; expected "
            "(north, west, south, east)."
        )
    if margin < 0:
        raise AtlasInputError("domain_margin_deg cannot be negative.")

    latmax = north - margin
    latmin = south + margin
    lonmax = east - margin
    lonmin = west + margin

    if latmax <= latmin or lonmax <= lonmin:
        raise AtlasInputError(
            "domain_margin_deg collapses the computational domain."
        )

    return latmax, latmin, lonmax, lonmin


def _meteorology_hours(
    path: Path,
    config: AtlasInputBuildConfig,
) -> tuple[int, str]:
    if path.is_file():
        with Dataset(path, "r") as dataset:
            if "time" not in dataset.dimensions:
                raise AtlasInputError(
                    f"Meteorology has no time dimension: {path}"
                )
            hours = len(dataset.dimensions["time"])

        if hours <= 0:
            raise AtlasInputError(
                f"Meteorology has no time records: {path}"
            )
        return int(hours), "actual_netcdf"

    if config.require_local_meteorology:
        raise AtlasInputError(
            f"Required meteorology does not exist: {path}"
        )

    fallback = config.fallback_meteorology_hours
    if fallback is None or fallback <= 0:
        raise AtlasInputError(
            f"Meteorology is absent at {path} and no positive "
            "fallback_meteorology_hours was configured."
        )

    return int(fallback), "fallback"


def _validate_fixed_scope(
    phase_name: str,
    phase: AtlasPhaseConfig,
) -> None:
    """Validate options intentionally fixed by Stage 4 v4.1."""
    if phase.phase_type.constant is not None:
        value = str(phase.phase_type.constant).strip().lower()
        if value != "eruption":
            raise AtlasInputError(
                f"Phase {phase_name!r}: only PHASE_TYPE=eruption is supported."
            )

    if phase.distribution.constant is not None:
        value = str(phase.distribution.constant).strip().upper()
        if value not in {"GAUSSIAN", "BIGAUSSIAN"}:
            raise AtlasInputError(
                f"Phase {phase_name!r}: DISTRIBUTION must be "
                "GAUSSIAN or BIGAUSSIAN."
            )

    # Requested physical validation only for constants. Values read from the
    # accepted table are assumed to have already passed preprocessing.
    if phase.column_height.constant is not None:
        height = _number(
            phase.column_height.constant,
            phase_name,
            "column_height constant",
        )
        if height <= 0:
            raise AtlasInputError(
                f"Phase {phase_name!r}: constant column_height "
                "must be positive."
            )

    if phase.duration.constant is not None:
        duration = _number(
            phase.duration.constant,
            phase_name,
            "duration constant",
        )
        if duration <= 0:
            raise AtlasInputError(
                f"Phase {phase_name!r}: constant duration must be positive."
            )


def _column_height_above_vent(
    raw_height: float,
    source_elevation: float,
    reference: str,
    *,
    phase: str,
) -> float:
    normalized = reference.strip().lower()
    if normalized == "asl":
        result = raw_height - source_elevation
    elif normalized == "above_vent":
        result = raw_height
    else:
        raise AtlasInputError(
            "column_height_reference must be 'asl' or 'above_vent'."
        )

    # This is a structural requirement for a usable ATLAS input, not a
    # resampling/acceptance validation of a table value.
    if result <= 0:
        raise AtlasInputError(
            f"Phase {phase!r}: COLUMN_HEIGHT above vent is {result} m."
        )
    return result


def _render_main(
    *,
    moment: datetime,
    simulation_end: float,
    domain: tuple[float, float, float, float],
    meteo_path: str,
    phase_path: str,
    main: AtlasMainInputConfig,
) -> str:
    latmax, latmin, lonmax, lonmin = domain
    start = _hour_from_midnight(moment)

    return f"""!*********************************************
!*
!*   ATLAS INPUT FILE
!*   VERSION: 1.0
!*
!*********************************************
!
!***********************************************
   SIMULATION_TIME
!***********************************************
   YEAR                = {moment.year}
   MONTH               = {moment.month}
   DAY                 = {moment.day}
   SIMULATION_START    = {_format_number(start)}
   SIMULATION_END      = {_format_number(simulation_end)}
   TIME_STEP           = {_format_number(main.time_step_seconds)}
   RESTART             = {main.restart}
!
!************************************************
   COMPUTATIONAL_DOMAIN
!************************************************
   LATMAX = {_format_number(latmax)}
   LATMIN = {_format_number(latmin)}
   LONMAX = {_format_number(lonmax)}
   LONMIN = {_format_number(lonmin)}
   ZTOP   = {_format_number(main.ztop_m)}
   VERTICAL_RESOLUTION  = {_format_number(main.vertical_resolution_m)}
   LONGITUDE_RESOLUTION = {_format_number(main.longitude_resolution_deg)}
   LATITUDE_RESOLUTION  = {_format_number(main.latitude_resolution_deg)}
!
!***********************************************
   OUTPUT_GRID
!***********************************************
   OUTPUT_LATMAX = {_format_number(latmax)}
   OUTPUT_LATMIN = {_format_number(latmin)}
   OUTPUT_LONMAX = {_format_number(lonmax)}
   OUTPUT_LONMIN = {_format_number(lonmin)}
   OUTPUT_FREQUENCY = {_format_number(main.output_frequency_h)}
   VERTICAL_LAYERS  = {main.vertical_layers}
   LONGITUDE_RESOLUTION = {_format_number(main.longitude_resolution_deg)}
   LATITUDE_RESOLUTION  = {_format_number(main.latitude_resolution_deg)}
   OUTPUT_CLASSES       = {main.output_classes}
   OUTPUT_PHASES        = {main.output_phases}
   OUTPUT_TRACK_POINTS  = {main.output_track_points}
!
!***********************************************
   PHYSICS
!***********************************************
   TERMINAL_VELOCITY_MODEL = {main.terminal_velocity_model}
!
!***********************************************
   METEO_DATA
!***********************************************
   METEO_MODEL_DEFINITION
      ACTIVATE    = yes
      MODEL_TYPE  = ERA5
      FILE        = {meteo_path}
      POSTPROCESS = {main.meteo_postprocess}
   END_METEO_MODEL_DEFINITON
!
!*********************************************
   SOURCE_TERM
!*********************************************
   PHASE_DEFINITION
       ACTIVATE = yes
       INCLUDE  = {phase_path}
   END_PHASE_DEFINITION
!
"""


def _render_phase(
    *,
    initial_time: float,
    end_time: float,
    column_height: float,
    values: Mapping[str, Any],
) -> str:
    distribution = str(values["distribution"]).strip().upper()

    if distribution == "GAUSSIAN":
        fi_mean = _format_number(values["fi_mean_1"])
        fi_disp = _format_number(values["fi_disp_1"])
    elif distribution == "BIGAUSSIAN":
        if values["fi_mean_2"] is None or values["fi_disp_2"] is None:
            raise AtlasInputError(
                "BIGAUSSIAN requires fi_mean_2 and fi_disp_2."
            )
        fi_mean = (
            f"{_format_number(values['fi_mean_1'])} "
            f"{_format_number(values['fi_mean_2'])}"
        )
        fi_disp = (
            f"{_format_number(values['fi_disp_1'])} "
            f"{_format_number(values['fi_disp_2'])}"
        )
    else:
        raise AtlasInputError(
            "DISTRIBUTION must be GAUSSIAN or BIGAUSSIAN."
        )

    fi_range = values["fi_range"]
    density_range = values["density_range"]
    sphericity_range = values["sphericity_range"]

    return f"""!*********************************************
 SOURCE_TERM
!*********************************************
       NUMBER_PARTICLES = {int(values["number_particles"])}
!
       PHASE_NAME       = {values["phase_name"]}
       PHASE_TYPE       = eruption
       INITIAL_TIME     = {_format_number(initial_time)}
       END_TIME         = {_format_number(end_time)}
!
       SOURCE_TYPE      = suzuki
       COLUMN_HEIGHT    = {_round_positive_integer(column_height)}
       MASS_FLOW_RATE   = {values["mass_flow_rate"]}
       A_SUZUKI         = {_format_number(values["a_suzuki"])}
       L_SUZUKI         = {_format_number(values["l_suzuki"])}
       D_TOP_HAT        = {_format_number(values["d_top_hat_m"])}
!
       VOLCANO_NAME     = {values["volcano_name"]}
       SOURCE_LONGITUDE = {_format_number(values["source_longitude"])}
       SOURCE_LATITUDE  = {_format_number(values["source_latitude"])}
       SOURCE_ELEVATION = {_format_number(values["source_elevation"])}
!
       PHASE_GRANULOMETRY = {values["phase_granulometry"]}
       DISTRIBUTION       = {distribution}
       NUMBER_OF_BINS     = {int(values["number_of_bins"])}
       FI_MEAN            = {fi_mean}
       FI_DISP            = {fi_disp}
       FI_RANGE           = {_format_number(fi_range[0])} {_format_number(fi_range[1])}
       DENSITY_RANGE      = {_format_number(density_range[0])} {_format_number(density_range[1])}
       SPHERICITY_RANGE   = {_format_number(sphericity_range[0])} {_format_number(sphericity_range[1])}
!
       AGGREGATION
          AGGREGATION_MODEL = PERCENTAGE
          AGGREGATE_SIZE    = {_format_number(values["aggregate_size_microns"])}
          AGGREGATE_DENSITY = {_format_number(values["aggregate_density_kg_m3"])}
          PERCENTAGE_(%)    = {_round_positive_integer(values["aggregation_percentage"])}
       END_AGGREGATION
!
"""


def _write(path: Path, text: str, overwrite: bool) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)

    if path.exists() and not overwrite:
        return "skipped_existing"

    existed = path.exists()
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(text, encoding="utf-8", newline="\n")
    temporary.replace(path)
    return "replaced" if existed else "created"


def _run_folder(
    mode: str,
    date_key: str,
    scenario_id: str,
) -> str:
    if mode == "date_only":
        return f"simulation_{date_key}"
    if mode == "date_and_scenario":
        return (
            f"simulation_{date_key}_scenario_"
            f"{_safe_identifier(scenario_id)}"
        )
    raise AtlasInputError(
        "run_folder_mode must be 'date_only' or 'date_and_scenario'."
    )


def _selected_rows(
    table: pd.DataFrame,
    accepted_column: str | None,
) -> pd.DataFrame:
    if accepted_column is None or accepted_column not in table.columns:
        return table.copy()

    normalized = table[accepted_column].astype(str).str.strip().str.lower()
    mask = normalized.isin(
        {"true", "1", "yes", "accepted"}
    )
    return table.loc[mask].copy()


def build_atlas_inputs(config: AtlasInputBuildConfig) -> pd.DataFrame:
    """Generate one main and one Phase1 input per row and configured phase."""
    scenario_table = Path(config.scenario_table)
    if not scenario_table.is_file():
        raise FileNotFoundError(scenario_table)
    if not config.phases:
        raise AtlasInputError("At least one phase must be configured.")

    for phase_name, phase in config.phases.items():
        _validate_fixed_scope(phase_name, phase)

    table = pd.read_csv(scenario_table)
    rows = _selected_rows(table, config.accepted_column)
    domain = _domain(
        config.meteorology_area,
        config.domain_margin_deg,
    )
    atlas_root = _atlas_root(config)

    manifest_rows: list[dict[str, Any]] = []
    seen_folders: set[tuple[str, str]] = set()

    for source_row, row in rows.iterrows():
        if (
            config.scenario_id_column
            and config.scenario_id_column in row.index
            and not pd.isna(row[config.scenario_id_column])
        ):
            scenario_id = str(row[config.scenario_id_column])
        else:
            scenario_id = f"{int(source_row) + 1:06d}"

        for phase_name, phase in config.phases.items():
            moment = _parse_datetime(
                _resolve(
                    phase.datetime,
                    row,
                    phase=phase_name,
                    parameter="datetime",
                ),
                phase_name,
            )
            date_key = moment.strftime("%Y%m%d")
            folder_name = _run_folder(
                config.run_folder_mode,
                date_key,
                scenario_id,
            )

            folder_key = (phase_name, folder_name)
            if folder_key in seen_folders:
                raise AtlasInputError(
                    f"Duplicate output folder {phase_name}/{folder_name}. "
                    "Use run_folder_mode='date_and_scenario' or unique "
                    "scenario identifiers."
                )
            seen_folders.add(folder_key)

            local_meteo = (
                Path(config.local_meteorology_root)
                / phase_name
                / f"date_{date_key}"
                / f"{date_key}.era5.nc"
            )
            meteo_hours, meteo_time_source = _meteorology_hours(
                local_meteo,
                config,
            )

            simulation_start = _hour_from_midnight(moment)
            simulation_end = float(meteo_hours - 1)

            duration = _number(
                _resolve(
                    phase.duration,
                    row,
                    phase=phase_name,
                    parameter="duration",
                ),
                phase_name,
                "duration",
            )
            eruption_end = simulation_start + duration

            # Operational checks are always required to avoid an invalid file.
            if duration <= 0:
                raise AtlasInputError(
                    f"Phase {phase_name!r}: duration is not positive."
                )
            if simulation_start > simulation_end:
                raise AtlasInputError(
                    f"Phase {phase_name!r}: simulation starts at "
                    f"{simulation_start}, after meteorology end "
                    f"{simulation_end}."
                )
            if eruption_end > simulation_end:
                raise AtlasInputError(
                    f"Phase {phase_name!r}: eruption ends at {eruption_end}, "
                    f"after meteorology end {simulation_end}."
                )

            source_elevation = _number(
                _resolve(
                    phase.source_elevation,
                    row,
                    phase=phase_name,
                    parameter="source_elevation",
                ),
                phase_name,
                "source_elevation",
            )
            raw_height = _number(
                _resolve(
                    phase.column_height,
                    row,
                    phase=phase_name,
                    parameter="column_height",
                ),
                phase_name,
                "column_height",
            )
            column_height = _column_height_above_vent(
                raw_height,
                source_elevation,
                config.column_height_reference,
                phase=phase_name,
            )

            distribution = str(
                _resolve(
                    phase.distribution,
                    row,
                    phase=phase_name,
                    parameter="distribution",
                )
            ).strip().upper()
            if distribution not in {"GAUSSIAN", "BIGAUSSIAN"}:
                raise AtlasInputError(
                    f"Phase {phase_name!r}: distribution must be "
                    "GAUSSIAN or BIGAUSSIAN."
                )

            phase_type = str(
                _resolve(
                    phase.phase_type,
                    row,
                    phase=phase_name,
                    parameter="phase_type",
                )
            ).strip().lower()
            if phase_type != "eruption":
                raise AtlasInputError(
                    f"Phase {phase_name!r}: only phase_type='eruption' "
                    "is supported."
                )

            fi_mean_2 = (
                None
                if phase.fi_mean_2 is None
                else _number(
                    _resolve(
                        phase.fi_mean_2,
                        row,
                        phase=phase_name,
                        parameter="fi_mean_2",
                    ),
                    phase_name,
                    "fi_mean_2",
                )
            )
            fi_disp_2 = (
                None
                if phase.fi_disp_2 is None
                else _number(
                    _resolve(
                        phase.fi_disp_2,
                        row,
                        phase=phase_name,
                        parameter="fi_disp_2",
                    ),
                    phase_name,
                    "fi_disp_2",
                )
            )

            values = {
                "number_particles": int(
                    _number(
                        _resolve(
                            phase.number_particles,
                            row,
                            phase=phase_name,
                            parameter="number_particles",
                        ),
                        phase_name,
                        "number_particles",
                    )
                ),
                "phase_name": _resolve(
                    phase.phase_name,
                    row,
                    phase=phase_name,
                    parameter="phase_name",
                ),
                "mass_flow_rate": _resolve(
                    phase.mass_flow_rate,
                    row,
                    phase=phase_name,
                    parameter="mass_flow_rate",
                ),
                "a_suzuki": _number(
                    _resolve(
                        phase.a_suzuki,
                        row,
                        phase=phase_name,
                        parameter="a_suzuki",
                    ),
                    phase_name,
                    "a_suzuki",
                ),
                "l_suzuki": _number(
                    _resolve(
                        phase.l_suzuki,
                        row,
                        phase=phase_name,
                        parameter="l_suzuki",
                    ),
                    phase_name,
                    "l_suzuki",
                ),
                "d_top_hat_m": _number(
                    _resolve(
                        phase.d_top_hat_m,
                        row,
                        phase=phase_name,
                        parameter="d_top_hat_m",
                    ),
                    phase_name,
                    "d_top_hat_m",
                ),
                "volcano_name": _resolve(
                    phase.volcano_name,
                    row,
                    phase=phase_name,
                    parameter="volcano_name",
                ),
                "source_longitude": _number(
                    _resolve(
                        phase.source_longitude,
                        row,
                        phase=phase_name,
                        parameter="source_longitude",
                    ),
                    phase_name,
                    "source_longitude",
                ),
                "source_latitude": _number(
                    _resolve(
                        phase.source_latitude,
                        row,
                        phase=phase_name,
                        parameter="source_latitude",
                    ),
                    phase_name,
                    "source_latitude",
                ),
                "source_elevation": source_elevation,
                "phase_granulometry": _resolve(
                    phase.phase_granulometry,
                    row,
                    phase=phase_name,
                    parameter="phase_granulometry",
                ),
                "distribution": distribution,
                "number_of_bins": int(
                    _number(
                        _resolve(
                            phase.number_of_bins,
                            row,
                            phase=phase_name,
                            parameter="number_of_bins",
                        ),
                        phase_name,
                        "number_of_bins",
                    )
                ),
                "fi_mean_1": _number(
                    _resolve(
                        phase.fi_mean_1,
                        row,
                        phase=phase_name,
                        parameter="fi_mean_1",
                    ),
                    phase_name,
                    "fi_mean_1",
                ),
                "fi_disp_1": _number(
                    _resolve(
                        phase.fi_disp_1,
                        row,
                        phase=phase_name,
                        parameter="fi_disp_1",
                    ),
                    phase_name,
                    "fi_disp_1",
                ),
                "fi_mean_2": fi_mean_2,
                "fi_disp_2": fi_disp_2,
                "fi_range": _resolve_pair(
                    phase.fi_range,
                    row,
                    phase=phase_name,
                    parameter="fi_range",
                ),
                "density_range": _resolve_pair(
                    phase.density_range,
                    row,
                    phase=phase_name,
                    parameter="density_range",
                ),
                "sphericity_range": _resolve_pair(
                    phase.sphericity_range,
                    row,
                    phase=phase_name,
                    parameter="sphericity_range",
                ),
                "aggregate_size_microns": _number(
                    _resolve(
                        phase.aggregate_size_microns,
                        row,
                        phase=phase_name,
                        parameter="aggregate_size_microns",
                    ),
                    phase_name,
                    "aggregate_size_microns",
                ),
                "aggregate_density_kg_m3": _number(
                    _resolve(
                        phase.aggregate_density_kg_m3,
                        row,
                        phase=phase_name,
                        parameter="aggregate_density_kg_m3",
                    ),
                    phase_name,
                    "aggregate_density_kg_m3",
                ),
                "aggregation_percentage": _number(
                    _resolve(
                        phase.aggregation_percentage,
                        row,
                        phase=phase_name,
                        parameter="aggregation_percentage",
                    ),
                    phase_name,
                    "aggregation_percentage",
                ),
            }

            allowed_mer_estimators = {
                "ESTIMATE-MASTIN",
                "ESTIMATE-DEGRUYTER",
                "ESTIMATE-WOODHOUSE",
            }
            mass_flow_rate = str(values["mass_flow_rate"]).strip().upper()
            if mass_flow_rate not in allowed_mer_estimators:
                raise AtlasInputError(
                    f"Phase {phase_name!r}: MASS_FLOW_RATE must be one of "
                    f"{sorted(allowed_mer_estimators)}; received "
                    f"{values['mass_flow_rate']!r}."
                )
            values["mass_flow_rate"] = mass_flow_rate

            if not 0 <= values["aggregation_percentage"] <= 100:
                raise AtlasInputError(
                    f"Phase {phase_name!r}: aggregation percentage must "
                    "be between 0 and 100."
                )
            if values["number_particles"] <= 0:
                raise AtlasInputError(
                    f"Phase {phase_name!r}: number_particles must be positive."
                )
            if values["number_of_bins"] <= 0:
                raise AtlasInputError(
                    f"Phase {phase_name!r}: number_of_bins must be positive."
                )

            local_run = (
                Path(config.local_inputs_root)
                / phase_name
                / folder_name
            )
            main_path = local_run / f"{date_key}.inp"
            phase_path = local_run / f"{date_key}.Phase1.inp"

            atlas_meteo = (
                atlas_root
                / "Data"
                / "era5"
                / phase_name
                / f"{date_key}.era5.nc"
            )
            atlas_phase = (
                atlas_root
                / "Runs"
                / phase_name
                / folder_name
                / f"{date_key}.Phase1.inp"
            )

            main_text = _render_main(
                moment=moment,
                simulation_end=simulation_end,
                domain=domain,
                meteo_path=atlas_meteo.as_posix(),
                phase_path=atlas_phase.as_posix(),
                main=config.main,
            )
            phase_text = _render_phase(
                initial_time=simulation_start,
                end_time=eruption_end,
                column_height=column_height,
                values=values,
            )

            main_status = _write(
                main_path,
                main_text,
                config.overwrite,
            )
            phase_status = _write(
                phase_path,
                phase_text,
                config.overwrite,
            )

            manifest_rows.append(
                {
                    "scenario_id": scenario_id,
                    "source_row": int(source_row),
                    "phase": phase_name,
                    "date_key": date_key,
                    "initial_datetime": moment.isoformat(),
                    "run_folder": folder_name,
                    "main_input_path": str(main_path),
                    "phase_input_path": str(phase_path),
                    "local_meteorology_path": str(local_meteo),
                    "local_meteorology_exists": local_meteo.is_file(),
                    "meteorology_time_source": meteo_time_source,
                    "meteorology_hours": meteo_hours,
                    "simulation_start_h": simulation_start,
                    "simulation_end_h": simulation_end,
                    "eruption_end_h": eruption_end,
                    "column_height_above_vent_m": column_height,
                    "distribution": distribution,
                    "atlas_meteorology_path": atlas_meteo.as_posix(),
                    "atlas_phase_input_path": atlas_phase.as_posix(),
                    "main_status": main_status,
                    "phase_status": phase_status,
                }
            )

    manifest = pd.DataFrame(manifest_rows)
    output_root = Path(config.local_inputs_root)
    output_root.mkdir(parents=True, exist_ok=True)

    manifest.to_csv(
        output_root / "atlas_input_manifest.csv",
        index=False,
    )

    snapshot = {
        "scenario_table": str(config.scenario_table),
        "local_inputs_root": str(config.local_inputs_root),
        "local_meteorology_root": str(config.local_meteorology_root),
        "atlas_install_base": config.atlas_install_base,
        "atlas_directory_name": config.atlas_directory_name,
        "meteorology_area": list(config.meteorology_area),
        "domain_margin_deg": config.domain_margin_deg,
        "run_folder_mode": config.run_folder_mode,
        "column_height_reference": config.column_height_reference,
        "phases": list(config.phases),
    }
    (
        output_root / "atlas_input_configuration.json"
    ).write_text(
        json.dumps(snapshot, indent=2),
        encoding="utf-8",
    )

    return manifest
