"""Create and incrementally append ATLAS meteorology files.

This module reproduces the logical NetCDF structure written by Florencia
Reckziegel's ``era5nc.f90`` and the supplied ``era5nc_atlas.py`` conversion
script.

One final file is created for every phase-date folder:

    YYYYMMDD.era5.nc

The date in the filename is the initial date assigned to that phase. Monthly
pressure/single NetCDF pairs are appended chronologically. Existing complete
outputs are skipped, while incomplete outputs are resumed only when their
current length exactly matches the next expected time offset.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Iterable, Sequence

import numpy as np
from netCDF4 import Dataset


PRESSURE_VARIABLES = {
    "T": "t",
    "U": "u",
    "V": "v",
    "W": "w",
    "R": "r",
    "Z": "z",
}

SURFACE_VARIABLES = {
    "Z:sfc": "z",
    "U10:sfc": "u10",
    "V10:sfc": "v10",
    "T2:sfc": "t2m",
    "LSM:sfc": "lsm",
    "BLH:sfc": "blh",
}

VARIABLE_ATTRIBUTES = {
    "Z:sfc": ("gpm", "Geopotential height at surface"),
    "U10:sfc": ("m/s", "u-component of wind at 10m"),
    "V10:sfc": ("m/s", "v-component (meridional) of wind at 10m"),
    "T2:sfc": ("K", "temperature at 2m"),
    "LSM:sfc": ("-", "Land mask"),
    "BLH:sfc": ("m", "Planetary Boundary Layer Height"),
    "T": ("K", "temperature"),
    "U": ("m/s", "u velocity"),
    "V": ("m/s", "v velocity"),
    "W": ("Pa/s", "Vertical omega velocity"),
    "R": ("%", "Relative humidity"),
    "Z": ("gpm", "Geopotential height"),
}


class AtlasConversionError(RuntimeError):
    """Raised when source files cannot reproduce the ATLAS structure."""


@dataclass(frozen=True)
class AtlasChunk:
    """One chronological pressure/single NetCDF pair."""

    pressure_path: Path
    single_path: Path
    start: date
    end_exclusive: date

    @property
    def number_of_hours(self) -> int:
        return (self.end_exclusive - self.start).days * 24


@dataclass(frozen=True)
class AtlasFileStatus:
    path: Path
    exists: bool
    valid_structure: bool
    current_hours: int
    expected_hours: int

    @property
    def complete(self) -> bool:
        return (
            self.exists
            and self.valid_structure
            and self.current_hours == self.expected_hours
        )


def _find_name(container, candidates: Iterable[str], kind: str) -> str:
    for name in candidates:
        if name in container:
            return name
    raise AtlasConversionError(
        f"Missing {kind}. Expected one of {list(candidates)}; "
        f"available names are {list(container)}."
    )


def _read_real4(variable, selection=Ellipsis) -> np.ndarray:
    """Reproduce the REAL(4) unpacking used by the original converter."""
    variable.set_auto_maskandscale(False)
    raw = variable[selection]
    if np.ma.isMaskedArray(raw):
        raw = raw.filled(np.nan)

    values = np.asarray(raw, dtype=np.float32)

    if "scale_factor" in variable.ncattrs():
        values = values * np.float32(variable.getncattr("scale_factor"))
    if "add_offset" in variable.ncattrs():
        values = values + np.float32(variable.getncattr("add_offset"))

    return np.asarray(values, dtype=np.float32)


def _read_coordinate(variable) -> np.ndarray:
    variable.set_auto_maskandscale(False)
    return np.asarray(variable[:], dtype=np.float32)


def _axis_map(variable, expected: Iterable[str]) -> tuple[int, ...]:
    aliases = {
        "time": {"time", "valid_time"},
        "level": {"level", "pressure_level", "isobaricInhPa"},
        "latitude": {"latitude", "lat"},
        "longitude": {"longitude", "lon"},
    }

    source = list(variable.dimensions)
    result = []

    for target in expected:
        matches = [
            index
            for index, dimension in enumerate(source)
            if dimension in aliases[target]
        ]
        if len(matches) != 1:
            raise AtlasConversionError(
                f"Variable {variable.name!r} has dimensions {source}; cannot "
                f"identify exactly one {target!r} axis."
            )
        result.append(matches[0])

    return tuple(result)


def _read_field(variable, expected_axes: tuple[str, ...]) -> np.ndarray:
    values = _read_real4(variable)
    axes = _axis_map(variable, expected_axes)

    if axes != tuple(range(values.ndim)):
        values = np.transpose(values, axes)

    return np.asarray(values, dtype=np.float32)


def _check_required_variables(
    dataset: Dataset,
    names: Iterable[str],
    label: str,
) -> None:
    missing = [name for name in names if name not in dataset.variables]
    if missing:
        raise AtlasConversionError(
            f"{label} file is missing variables {missing}; "
            f"available variables are {list(dataset.variables)}."
        )


def _normalize_longitude(lon: np.ndarray) -> np.ndarray:
    # Exact behavior used by the supplied converter.
    if len(lon) and lon[0] > 180.0 and lon[-1] > 180.0:
        return np.asarray(lon - np.float32(360.0), dtype=np.float32)
    return np.asarray(lon, dtype=np.float32)


def _read_chunk(chunk: AtlasChunk) -> dict:
    expected_hours = chunk.number_of_hours
    if expected_hours <= 0:
        raise AtlasConversionError(
            f"Invalid chunk interval: {chunk.start} to {chunk.end_exclusive}."
        )

    if not chunk.pressure_path.is_file():
        raise FileNotFoundError(chunk.pressure_path)
    if not chunk.single_path.is_file():
        raise FileNotFoundError(chunk.single_path)

    with Dataset(chunk.pressure_path, "r") as pressure, Dataset(
        chunk.single_path,
        "r",
    ) as single:
        _check_required_variables(
            pressure,
            PRESSURE_VARIABLES.values(),
            "Pressure-level",
        )
        _check_required_variables(
            single,
            SURFACE_VARIABLES.values(),
            "Single-level",
        )

        lon_name_p = _find_name(
            pressure.variables,
            ("longitude", "lon"),
            "pressure longitude",
        )
        lat_name_p = _find_name(
            pressure.variables,
            ("latitude", "lat"),
            "pressure latitude",
        )
        level_name = _find_name(
            pressure.variables,
            ("level", "pressure_level", "isobaricInhPa"),
            "pressure level",
        )
        lon_name_s = _find_name(
            single.variables,
            ("longitude", "lon"),
            "single longitude",
        )
        lat_name_s = _find_name(
            single.variables,
            ("latitude", "lat"),
            "single latitude",
        )

        lon = _read_coordinate(pressure.variables[lon_name_p])
        lat = _read_coordinate(pressure.variables[lat_name_p])
        lon_single = _read_coordinate(single.variables[lon_name_s])
        lat_single = _read_coordinate(single.variables[lat_name_s])

        if lon.shape != lon_single.shape or not np.array_equal(
            lon,
            lon_single,
        ):
            raise AtlasConversionError(
                "Pressure and single files have different longitudes."
            )
        if lat.shape != lat_single.shape or not np.array_equal(
            lat,
            lat_single,
        ):
            raise AtlasConversionError(
                "Pressure and single files have different latitudes."
            )

        lon = _normalize_longitude(lon)
        pres = _read_coordinate(pressure.variables[level_name])

        pressure_data = {
            output_name: _read_field(
                pressure.variables[source_name],
                ("time", "level", "latitude", "longitude"),
            )
            for output_name, source_name in PRESSURE_VARIABLES.items()
        }
        surface_data = {
            output_name: _read_field(
                single.variables[source_name],
                ("time", "latitude", "longitude"),
            )
            for output_name, source_name in SURFACE_VARIABLES.items()
        }

        pressure_hours = min(
            field.shape[0] for field in pressure_data.values()
        )
        surface_hours = min(
            field.shape[0] for field in surface_data.values()
        )

        if expected_hours > pressure_hours or expected_hours > surface_hours:
            raise AtlasConversionError(
                f"Requested {expected_hours} hours for {chunk.start}, but "
                f"pressure has {pressure_hours} and single has {surface_hours}."
            )

        expected_pressure_shape = (
            pressure_hours,
            len(pres),
            len(lat),
            len(lon),
        )
        expected_surface_shape = (
            surface_hours,
            len(lat),
            len(lon),
        )

        for name, field in pressure_data.items():
            if field.shape != expected_pressure_shape:
                raise AtlasConversionError(
                    f"{name} has shape {field.shape}; expected "
                    f"{expected_pressure_shape}."
                )

        for name, field in surface_data.items():
            if field.shape != expected_surface_shape:
                raise AtlasConversionError(
                    f"{name} has shape {field.shape}; expected "
                    f"{expected_surface_shape}."
                )

        # Match era5nc.f90: repeat the first surface geopotential and land mask.
        for invariant in ("Z:sfc", "LSM:sfc"):
            first = surface_data[invariant][0:1, :, :]
            surface_data[invariant] = np.repeat(
                first,
                expected_hours,
                axis=0,
            )

        return {
            "lon": lon,
            "lat": lat,
            "pres": pres,
            "pressure": {
                name: field[:expected_hours]
                for name, field in pressure_data.items()
            },
            "surface": {
                name: field[:expected_hours]
                for name, field in surface_data.items()
            },
            "hours": expected_hours,
        }


def final_atlas_filename(initial_date: date) -> str:
    """Return the required final name: YYYYMMDD.era5.nc."""
    return f"{initial_date:%Y%m%d}.era5.nc"


def inspect_atlas_file(
    path: Path,
    *,
    expected_hours: int,
    initial_date: date,
) -> AtlasFileStatus:
    path = Path(path)

    if not path.is_file():
        return AtlasFileStatus(
            path=path,
            exists=False,
            valid_structure=False,
            current_hours=0,
            expected_hours=expected_hours,
        )

    try:
        with Dataset(path, "r") as dataset:
            required_dimensions = {"lon", "lat", "pres", "time"}
            required_variables = {
                "lon",
                "lat",
                "pres",
                "time",
                *SURFACE_VARIABLES.keys(),
                *PRESSURE_VARIABLES.keys(),
            }

            structure_ok = (
                dataset.file_format == "NETCDF3_CLASSIC"
                and required_dimensions.issubset(dataset.dimensions)
                and required_variables.issubset(dataset.variables)
                and dataset.dimensions["time"].isunlimited()
                and int(dataset.getncattr("YEAR")) == initial_date.year
                and int(dataset.getncattr("MONTH")) == initial_date.month
                and int(dataset.getncattr("DAY")) == initial_date.day
            )
            current_hours = len(dataset.dimensions["time"])

        return AtlasFileStatus(
            path=path,
            exists=True,
            valid_structure=structure_ok,
            current_hours=current_hours,
            expected_hours=expected_hours,
        )
    except Exception:
        return AtlasFileStatus(
            path=path,
            exists=True,
            valid_structure=False,
            current_hours=0,
            expected_hours=expected_hours,
        )


def _create_output(
    output_path: Path,
    *,
    initial_date: date,
    expected_total_hours: int,
    chunk_data: dict,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = output_path.with_suffix(output_path.suffix + ".part")
    temporary.unlink(missing_ok=True)

    lon = chunk_data["lon"]
    lat = chunk_data["lat"]
    pres = chunk_data["pres"]

    try:
        with Dataset(temporary, "w", format="NETCDF3_CLASSIC") as output:
            output.createDimension("lon", len(lon))
            output.createDimension("lat", len(lat))
            output.createDimension("pres", len(pres))
            output.createDimension("time", None)

            lon_var = output.createVariable("lon", "f4", ("lon",))
            lat_var = output.createVariable("lat", "f4", ("lat",))
            pres_var = output.createVariable("pres", "f4", ("pres",))
            time_var = output.createVariable("time", "f4", ("time",))

            for name in SURFACE_VARIABLES:
                variable = output.createVariable(
                    name,
                    "f4",
                    ("time", "lat", "lon"),
                )
                units, description = VARIABLE_ATTRIBUTES[name]
                variable.setncattr("units", units.ljust(50))
                variable.setncattr(
                    "description",
                    description.ljust(50),
                )

            for name in PRESSURE_VARIABLES:
                variable = output.createVariable(
                    name,
                    "f4",
                    ("time", "pres", "lat", "lon"),
                )
                units, description = VARIABLE_ATTRIBUTES[name]
                variable.setncattr("units", units.ljust(50))
                variable.setncattr(
                    "description",
                    description.ljust(50),
                )

            output.setncattr("TITLE", "erainNC-1".ljust(10))
            output.setncattr("LONMIN", np.float32(-180.0))
            output.setncattr("LONMAX", np.float32(180.0))
            output.setncattr("LATMIN", np.float32(-90.0))
            output.setncattr("LATMAX", np.float32(90.0))
            output.setncattr("NX", np.int32(len(lon)))
            output.setncattr("NY", np.int32(len(lat)))
            output.setncattr("NP", np.int32(len(pres)))
            output.setncattr("NT", np.int32(expected_total_hours))
            output.setncattr("YEAR", np.int32(initial_date.year))
            output.setncattr("MONTH", np.int32(initial_date.month))
            output.setncattr("DAY", np.int32(initial_date.day))
            output.setncattr("HOUR", np.int32(0))
            output.setncattr("TIME_INCR", np.int32(3600))
            output.setncattr("CEN_LON", np.int32(0))
            output.setncattr("CEN_LAT", np.int32(0))

            lon_var[:] = lon
            lat_var[:] = lat
            pres_var[:] = pres
            time_var[:] = np.empty(0, dtype=np.float32)

        temporary.replace(output_path)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


def _validate_output_grid(
    output: Dataset,
    chunk_data: dict,
) -> None:
    comparisons = (
        ("lon", chunk_data["lon"]),
        ("lat", chunk_data["lat"]),
        ("pres", chunk_data["pres"]),
    )

    for name, expected in comparisons:
        actual = np.asarray(output.variables[name][:], dtype=np.float32)
        if actual.shape != expected.shape or not np.array_equal(
            actual,
            expected,
        ):
            raise AtlasConversionError(
                f"Cannot append: output {name} grid differs from source."
            )


def append_chunk(
    output_path: Path,
    chunk: AtlasChunk,
    *,
    event_initial_date: date,
    expected_total_hours: int,
) -> str:
    """Append one chunk at its exact chronological offset."""
    chunk_data = _read_chunk(chunk)
    expected_offset = (
        chunk.start - event_initial_date
    ).days * 24

    if expected_offset < 0:
        raise AtlasConversionError(
            f"Chunk {chunk.start} precedes event start {event_initial_date}."
        )

    if not output_path.exists():
        if expected_offset != 0:
            raise AtlasConversionError(
                "The first available chunk does not begin on the event date."
            )
        _create_output(
            output_path,
            initial_date=event_initial_date,
            expected_total_hours=expected_total_hours,
            chunk_data=chunk_data,
        )

    with Dataset(output_path, "a") as output:
        current_hours = len(output.dimensions["time"])

        if current_hours > expected_offset:
            # This chunk was already appended.
            chunk_end = expected_offset + chunk_data["hours"]
            if current_hours >= chunk_end:
                return (
                    f"SKIP APPENDED {chunk.start} to "
                    f"{chunk.end_exclusive - timedelta(days=1)}"
                )
            raise AtlasConversionError(
                f"Output has {current_hours} hours, which overlaps partially "
                f"with chunk offset {expected_offset}."
            )

        if current_hours < expected_offset:
            raise AtlasConversionError(
                f"Output has {current_hours} hours but the next chunk begins "
                f"at offset {expected_offset}. A preceding chunk is missing."
            )

        _validate_output_grid(output, chunk_data)

        start_index = current_hours
        end_index = start_index + chunk_data["hours"]

        output.variables["time"][start_index:end_index] = (
            np.arange(
                start_index,
                end_index,
                dtype=np.float32,
            )
            * np.float32(3600.0)
        )

        for name, field in chunk_data["surface"].items():
            output.variables[name][start_index:end_index, :, :] = field

        for name, field in chunk_data["pressure"].items():
            output.variables[name][
                start_index:end_index,
                :,
                :,
                :,
            ] = field

    return (
        f"APPENDED {chunk.start} to "
        f"{chunk.end_exclusive - timedelta(days=1)} -> {output_path}"
    )


def concatenate_chunks(
    chunks: Sequence[AtlasChunk],
    *,
    output_path: Path,
    event_initial_date: date,
    expected_total_hours: int,
    overwrite_invalid: bool = False,
) -> list[str]:
    """Create or resume one final ``YYYYMMDD.era5.nc`` file."""
    ordered = sorted(chunks, key=lambda item: item.start)

    if not ordered:
        raise AtlasConversionError("No NetCDF chunks were supplied.")

    status = inspect_atlas_file(
        output_path,
        expected_hours=expected_total_hours,
        initial_date=event_initial_date,
    )

    if status.complete:
        return [f"SKIP COMPLETE ATLAS {output_path}"]

    if status.exists and not status.valid_structure:
        if not overwrite_invalid:
            raise AtlasConversionError(
                f"Existing ATLAS file is invalid: {output_path}. "
                "Enable overwrite or remove it before retrying."
            )
        output_path.unlink()

    if status.current_hours > expected_total_hours:
        raise AtlasConversionError(
            f"{output_path} has {status.current_hours} hours, more than "
            f"the expected {expected_total_hours}."
        )

    messages = []

    for chunk in ordered:
        messages.append(
            append_chunk(
                output_path,
                chunk,
                event_initial_date=event_initial_date,
                expected_total_hours=expected_total_hours,
            )
        )

    final_status = inspect_atlas_file(
        output_path,
        expected_hours=expected_total_hours,
        initial_date=event_initial_date,
    )

    if not final_status.complete:
        raise AtlasConversionError(
            f"Final ATLAS file remains incomplete: {output_path} contains "
            f"{final_status.current_hours}/{expected_total_hours} hours."
        )

    messages.append(f"COMPLETE ATLAS {output_path}")
    return messages
