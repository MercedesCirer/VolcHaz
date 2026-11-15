"""Read and normalize ATLAS Concentration_3D and Ground_load arrays.

The reader deliberately does NOT require a coordinate variable named ``time``.
Many ATLAS particle outputs expose time only as a NetCDF dimension. Stage 5
therefore infers the temporal axis from the dimensions of Concentration_3D.

Expected logical structures are:

    Concentration_3D(time, alt, lat, lon)
    Ground_load(time, lat, lon)

Dimension order may differ; axes are reordered internally from their names.
Ground_load may also be stored directly as (lat, lon).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
from netCDF4 import Dataset


class AtlasOutputError(RuntimeError):
    """Raised when an ATLAS .part.nc output cannot be interpreted."""


COORDINATE_VARIABLE_CANDIDATES = {
    "alt": ("alt", "altitude", "z", "height"),
    "lat": ("lat", "latitude", "y"),
    "lon": ("lon", "longitude", "x"),
}

DIMENSION_CANDIDATES = {
    "time": ("time", "Time", "t"),
    "alt": ("alt", "altitude", "z", "height"),
    "lat": ("lat", "latitude", "y"),
    "lon": ("lon", "longitude", "x"),
}

VARIABLE_CANDIDATES = {
    "c3d": ("Concentration_3D", "concentration_3d", "C3D"),
    "gl": ("Ground_load", "ground_load", "GL"),
}


def _first_existing(names, candidates, label):
    names = set(names)
    for candidate in candidates:
        if candidate in names:
            return candidate
    raise AtlasOutputError(
        f"Missing {label}. Tried {list(candidates)}. "
        f"Available: {sorted(names)}"
    )


def _find_dimension(variable_dimensions, candidates, label):
    """Find a logical axis from one variable's dimension names."""
    for candidate in candidates:
        if candidate in variable_dimensions:
            return candidate
    raise AtlasOutputError(
        f"Could not identify {label} dimension in {variable_dimensions}. "
        f"Tried {list(candidates)}."
    )


@dataclass(frozen=True)
class AtlasGrid:
    lat: np.ndarray
    lon: np.ndarray
    alt: np.ndarray


@dataclass(frozen=True)
class AtlasNames:
    """Variable names plus logical NetCDF dimension names."""

    alt_variable: str
    lat_variable: str
    lon_variable: str
    c3d: str
    gl: str

    time_dimension: str
    alt_dimension: str
    lat_dimension: str
    lon_dimension: str


def inspect(path: Path):
    """Inspect one ATLAS output without requiring a ``time`` coordinate variable."""
    with Dataset(path, "r") as dataset:
        variable_names = set(dataset.variables)

        c3d_name = _first_existing(
            variable_names,
            VARIABLE_CANDIDATES["c3d"],
            "C3D variable",
        )
        gl_name = _first_existing(
            variable_names,
            VARIABLE_CANDIDATES["gl"],
            "ground-load variable",
        )

        c3d_dimensions = tuple(dataset.variables[c3d_name].dimensions)

        time_dimension = _find_dimension(
            c3d_dimensions,
            DIMENSION_CANDIDATES["time"],
            "time",
        )
        alt_dimension = _find_dimension(
            c3d_dimensions,
            DIMENSION_CANDIDATES["alt"],
            "altitude",
        )
        lat_dimension = _find_dimension(
            c3d_dimensions,
            DIMENSION_CANDIDATES["lat"],
            "latitude",
        )
        lon_dimension = _find_dimension(
            c3d_dimensions,
            DIMENSION_CANDIDATES["lon"],
            "longitude",
        )

        alt_variable = _first_existing(
            variable_names,
            COORDINATE_VARIABLE_CANDIDATES["alt"],
            "altitude coordinate variable",
        )
        lat_variable = _first_existing(
            variable_names,
            COORDINATE_VARIABLE_CANDIDATES["lat"],
            "latitude coordinate variable",
        )
        lon_variable = _first_existing(
            variable_names,
            COORDINATE_VARIABLE_CANDIDATES["lon"],
            "longitude coordinate variable",
        )

        names = AtlasNames(
            alt_variable=alt_variable,
            lat_variable=lat_variable,
            lon_variable=lon_variable,
            c3d=c3d_name,
            gl=gl_name,
            time_dimension=time_dimension,
            alt_dimension=alt_dimension,
            lat_dimension=lat_dimension,
            lon_dimension=lon_dimension,
        )

        grid = AtlasGrid(
            lat=np.asarray(dataset.variables[lat_variable][:], dtype=float),
            lon=np.asarray(dataset.variables[lon_variable][:], dtype=float),
            alt=np.asarray(dataset.variables[alt_variable][:], dtype=float),
        )

    if grid.lat.ndim != 1:
        raise AtlasOutputError(
            f"Latitude coordinate must be 1D in {path}; shape={grid.lat.shape}"
        )
    if grid.lon.ndim != 1:
        raise AtlasOutputError(
            f"Longitude coordinate must be 1D in {path}; shape={grid.lon.shape}"
        )
    if grid.alt.ndim != 1:
        raise AtlasOutputError(
            f"Altitude coordinate must be 1D in {path}; shape={grid.alt.shape}"
        )

    return grid, names


def validate_grid(reference: AtlasGrid, candidate: AtlasGrid, path: Path):
    """Require all simulations in one probabilistic ensemble to share a grid."""
    for key in ("lat", "lon", "alt"):
        first = getattr(reference, key)
        second = getattr(candidate, key)
        if (
            first.shape != second.shape
            or not np.allclose(first, second, equal_nan=True)
        ):
            raise AtlasOutputError(
                f"Grid mismatch for {key!r} in {path}. "
                f"Reference shape={first.shape}, candidate shape={second.shape}."
            )


def read_c3d(dataset: Dataset, names: AtlasNames) -> np.ndarray:
    """Return C3D reordered to (time, alt, lat, lon)."""
    variable = dataset.variables[names.c3d]
    dimensions = tuple(variable.dimensions)

    expected = (
        names.time_dimension,
        names.alt_dimension,
        names.lat_dimension,
        names.lon_dimension,
    )

    try:
        order = tuple(dimensions.index(name) for name in expected)
    except ValueError as error:
        raise AtlasOutputError(
            f"C3D dimensions are incompatible. "
            f"Found {dimensions}; expected logical dimensions {expected}."
        ) from error

    data = np.ma.filled(variable[:], np.nan)
    array = np.transpose(np.asarray(data, dtype=float), order)

    return np.nan_to_num(
        array,
        nan=0.0,
        posinf=0.0,
        neginf=0.0,
    )


def read_gl_final(dataset: Dataset, names: AtlasNames) -> np.ndarray:
    """Return final Ground_load field reordered to (lat, lon)."""
    variable = dataset.variables[names.gl]
    dimensions = list(variable.dimensions)
    slicer = [slice(None)] * variable.ndim

    if names.time_dimension in dimensions:
        time_axis = dimensions.index(names.time_dimension)
        slicer[time_axis] = -1
        dimensions.pop(time_axis)

    data = np.ma.filled(variable[tuple(slicer)], np.nan)
    data = np.asarray(data, dtype=float)

    try:
        order = (
            dimensions.index(names.lat_dimension),
            dimensions.index(names.lon_dimension),
        )
    except ValueError as error:
        raise AtlasOutputError(
            f"Ground_load dimensions are incompatible. "
            f"Found {variable.dimensions}; expected latitude/longitude "
            f"dimensions {names.lat_dimension!r}/{names.lon_dimension!r}."
        ) from error

    array = np.transpose(data, order)

    return np.nan_to_num(
        array,
        nan=0.0,
        posinf=0.0,
        neginf=0.0,
    )
