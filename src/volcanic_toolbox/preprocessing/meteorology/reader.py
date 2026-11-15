"""Read ERA5 NetCDF files and extract the nearest grid point."""

from __future__ import annotations
from pathlib import Path
from typing import Iterable, Optional, Sequence, Union
import numpy as np
import pandas as pd
import xarray as xr


def _first_existing(names, candidates):
    for candidate in candidates:
        if candidate in names:
            return candidate
    raise KeyError("None of these names were found: %s" % list(candidates))


def normalize_requested_longitude(lon: float, dataset_longitudes) -> float:
    lon = float(lon)
    values = np.asarray(dataset_longitudes)
    if np.nanmax(values) > 180 and lon < 0:
        return lon % 360
    if np.nanmin(values) < 0 and lon > 180:
        return ((lon + 180) % 360) - 180
    return lon


def extract_point_from_netcdf(
    file_path: Union[str, Path],
    latitude: float,
    longitude: float,
    pressure_level_hpa: Optional[int] = None,
) -> pd.DataFrame:
    """Extract nearest-point u/v observations from one ERA5 NetCDF.

    Handles common coordinate names such as time/valid_time, latitude/lat,
    longitude/lon and pressure_level/level.
    """
    with xr.open_dataset(file_path) as ds:
        lat_name = _first_existing(ds.coords, ("latitude", "lat"))
        lon_name = _first_existing(ds.coords, ("longitude", "lon"))
        time_name = _first_existing(ds.coords, ("valid_time", "time"))
        u_name = _first_existing(ds.data_vars, ("u", "u_component_of_wind"))
        v_name = _first_existing(ds.data_vars, ("v", "v_component_of_wind"))

        requested_lon = normalize_requested_longitude(
            longitude, ds[lon_name].values
        )
        selected = ds.sel(
            {lat_name: latitude, lon_name: requested_lon},
            method="nearest"
        )

        level_name = next(
            (name for name in ("pressure_level", "level", "isobaricInhPa")
             if name in selected.coords),
            None
        )
        if pressure_level_hpa is not None and level_name is not None:
            selected = selected.sel(
                {level_name: pressure_level_hpa}, method="nearest"
            )

        # Remove singleton dimensions such as number/expver if present.
        selected = selected.squeeze(drop=True)
        frame = selected[[u_name, v_name]].to_dataframe().reset_index()
        frame = frame.rename(
            columns={
                time_name: "datetime",
                u_name: "u_m_s",
                v_name: "v_m_s",
            }
        )
        if "datetime" not in frame:
            raise KeyError("No time coordinate survived extraction")

        frame["datetime"] = pd.to_datetime(frame["datetime"], utc=True)
        frame["latitude"] = float(selected[lat_name].values)
        frame["longitude"] = float(selected[lon_name].values)
        if level_name is not None:
            level_value = np.asarray(selected[level_name].values).reshape(-1)[0]
            frame["pressure_level_hpa"] = float(level_value)
        elif pressure_level_hpa is not None:
            frame["pressure_level_hpa"] = float(pressure_level_hpa)
        else:
            frame["pressure_level_hpa"] = np.nan

        keep = [
            "datetime", "u_m_s", "v_m_s", "latitude", "longitude",
            "pressure_level_hpa"
        ]
        frame = frame[keep].drop_duplicates().sort_values("datetime")
        return frame.reset_index(drop=True)


def combine_yearly_files(
    file_paths: Iterable[Union[str, Path]],
    latitude: float,
    longitude: float,
    pressure_level_hpa: Optional[int] = None,
) -> pd.DataFrame:
    frames = [
        extract_point_from_netcdf(
            path, latitude, longitude, pressure_level_hpa
        )
        for path in file_paths
    ]
    if not frames:
        raise ValueError("No files were supplied")
    data = pd.concat(frames, ignore_index=True)
    return data.drop_duplicates(
        subset=["datetime", "pressure_level_hpa"]
    ).sort_values(["datetime", "pressure_level_hpa"]).reset_index(drop=True)
