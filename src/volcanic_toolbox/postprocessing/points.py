"""Point loading and extraction from probability NetCDF files.

Important semantic rule
-----------------------
For ``method="nearest"``, Stage 5 now selects the geometrically nearest grid
node FIRST and then reads the value at that exact node.

It does NOT search for the nearest finite/non-NaN value.

This matters especially for conditional persistence. A NaN conditional
persistence value means that no arrival occurred at that grid node, so
silently jumping to a more distant node with a finite value would create a
misleading point result.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from netCDF4 import Dataset


def load_points(config):
    frames = []

    if config.point_table is not None:
        if not config.point_table.is_file():
            raise FileNotFoundError(config.point_table)

        df = pd.read_csv(config.point_table)
        df.columns = df.columns.str.strip()

        required = {"point_id", "latitude", "longitude"}
        if not required.issubset(df.columns):
            raise ValueError(
                f"Point CSV needs columns {sorted(required)}"
            )

        frames.append(
            df[["point_id", "latitude", "longitude"]]
        )

    if config.inline_points:
        frames.append(
            pd.DataFrame(
                config.inline_points,
                columns=["point_id", "latitude", "longitude"],
            )
        )

    if not frames:
        return pd.DataFrame(
            columns=["point_id", "latitude", "longitude"]
        )

    points = pd.concat(frames, ignore_index=True)
    points["point_id"] = (
        points["point_id"].astype(str).str.strip()
    )
    points["latitude"] = pd.to_numeric(
        points["latitude"],
        errors="coerce",
    )
    points["longitude"] = pd.to_numeric(
        points["longitude"],
        errors="coerce",
    )

    points = (
        points
        .dropna()
        .drop_duplicates("point_id", keep="last")
        .reset_index(drop=True)
    )

    if not points["latitude"].between(-90, 90).all():
        raise ValueError("Invalid point latitude")

    return points


def _normalize_longitude(point_lon, grid_lon):
    if np.nanmax(grid_lon) > 180 and point_lon < 0:
        return point_lon % 360

    if np.nanmin(grid_lon) < 0 and point_lon > 180:
        return ((point_lon + 180) % 360) - 180

    return point_lon


def _extract_value(
    values,
    lat,
    lon,
    point_lat,
    point_lon,
    cfg,
):
    """Extract one gridded probability at a requested location."""

    point_lon = _normalize_longitude(point_lon, lon)

    lon_grid, lat_grid = np.meshgrid(lon, lat)
    distance = np.hypot(
        lat_grid - point_lat,
        lon_grid - point_lon,
    )

    # ------------------------------------------------------------------
    # NEAREST
    # ------------------------------------------------------------------
    # Choose the nearest geometrical node regardless of whether the
    # probability value is finite. If it is NaN, preserve NaN.
    #
    # For conditional persistence:
    #
    #     NaN = no arrival occurred at this node
    #
    # and must NOT be replaced with a value from a farther grid node.
    # ------------------------------------------------------------------
    if cfg.method == "nearest":
        flat_index = int(np.nanargmin(distance))
        row, col = np.unravel_index(
            flat_index,
            distance.shape,
        )

        value = values[row, col]

        return (
            float(value) if np.isfinite(value) else np.nan,
            float(distance[row, col]),
            "nearest",
            float(lat[row]),
            float(lon[col]),
        )

    # ------------------------------------------------------------------
    # IDW
    # ------------------------------------------------------------------
    # IDW uses only finite probability values. A radius is strongly
    # recommended for conditional probabilities to avoid extrapolating from
    # distant nodes.
    # ------------------------------------------------------------------
    flat_distance = distance.ravel()
    flat_values = values.ravel()

    valid = (
        np.isfinite(flat_distance)
        & np.isfinite(flat_values)
    )

    candidates = np.where(valid)[0]

    if cfg.idw_radius_deg is not None:
        candidates = candidates[
            flat_distance[candidates]
            <= cfg.idw_radius_deg
        ]

    if not len(candidates):
        return (
            np.nan,
            np.nan,
            "idw_no_valid_value",
            np.nan,
            np.nan,
        )

    candidates = candidates[
        np.argsort(flat_distance[candidates])
    ][:cfg.idw_k]

    zero = candidates[
        flat_distance[candidates] == 0
    ]

    if len(zero):
        chosen = int(zero[0])
        row, col = np.unravel_index(
            chosen,
            distance.shape,
        )
        return (
            float(flat_values[chosen]),
            0.0,
            "exact",
            float(lat[row]),
            float(lon[col]),
        )

    weights = (
        1.0
        / flat_distance[candidates] ** cfg.idw_power
    )

    value = float(
        np.sum(weights * flat_values[candidates])
        / np.sum(weights)
    )

    nearest = int(candidates[0])
    row, col = np.unravel_index(
        nearest,
        distance.shape,
    )

    return (
        value,
        float(flat_distance[nearest]),
        "idw",
        float(lat[row]),
        float(lon[col]),
    )


def extract_points(path, points, cfg):
    """Extract all probability fields for all requested points."""
    if points.empty:
        return pd.DataFrame()

    rows = []

    with Dataset(path) as dataset:
        lat = np.asarray(
            dataset.variables["lat"][:],
            dtype=float,
        )
        lon = np.asarray(
            dataset.variables["lon"][:],
            dtype=float,
        )

        variables = [
            (name, variable)
            for name, variable in dataset.variables.items()
            if variable.dimensions == ("lat", "lon")
        ]

        for name, variable in variables:
            values = np.asarray(
                np.ma.filled(
                    variable[:],
                    np.nan,
                ),
                dtype=float,
            )

            attrs = {
                attr: variable.getncattr(attr)
                for attr in variable.ncattrs()
                if attr != "_FillValue"
            }

            for point in points.itertuples(index=False):
                (
                    value,
                    distance,
                    method,
                    grid_latitude,
                    grid_longitude,
                ) = _extract_value(
                    values,
                    lat,
                    lon,
                    float(point.latitude),
                    float(point.longitude),
                    cfg,
                )

                row = {
                    "point_id": point.point_id,
                    "latitude": point.latitude,
                    "longitude": point.longitude,
                    "grid_latitude": grid_latitude,
                    "grid_longitude": grid_longitude,
                    "probability_percent": value,
                    "nearest_distance_degrees": distance,
                    "extraction_method": method,
                    "variable": name,
                    "phase": getattr(dataset, "phase", ""),
                    "subset": getattr(dataset, "subset", ""),
                    "source_probability_netcdf": str(path),
                }

                row.update(attrs)
                rows.append(row)

    return pd.DataFrame(rows)


# Compatibility alias for earlier Stage 5 workflow versions.
extract_points_from_probability_netcdf = extract_points
