"""Download ERA5 pressure-level u and v wind components through CDS API."""

from __future__ import annotations
import calendar
import logging
import time
from pathlib import Path
from typing import List, Optional, Sequence, Union

logger = logging.getLogger(__name__)

DEFAULT_VARIABLES = ("u_component_of_wind", "v_component_of_wind")
DEFAULT_TIMES = ("00:00", "06:00", "12:00", "18:00")
DATASET_ID = "reanalysis-era5-pressure-levels"


def ensure_directory(path: Union[str, Path]) -> Path:
    path = Path(path)
    path.mkdir(parents=True, exist_ok=True)
    return path


def normalize_longitude(lon: float) -> float:
    return ((float(lon) + 180.0) % 360.0) - 180.0


def bbox_around_point(
    latitude: float,
    longitude: float,
    half_latitude: float = 0.25,
    half_longitude: float = 0.25,
) -> List[float]:
    """Return CDS area [north, west, south, east]."""
    if not -90 <= latitude <= 90:
        raise ValueError("invalid latitude")
    lon = normalize_longitude(longitude)
    north = min(90.0, latitude + half_latitude)
    south = max(-90.0, latitude - half_latitude)
    west = normalize_longitude(lon - half_longitude)
    east = normalize_longitude(lon + half_longitude)
    if west > east:
        raise ValueError(
            "Bounding boxes crossing the antimeridian are not supported "
            "by this helper; split the request into two areas."
        )
    return [round(north, 4), round(west, 4), round(south, 4), round(east, 4)]


def build_filename(year: int, pressure_level_hpa: int) -> str:
    return "era5_%d_%dhPa.nc" % (year, pressure_level_hpa)


def is_readable_netcdf(path: Union[str, Path]) -> bool:
    path = Path(path)
    if not path.exists() or path.stat().st_size < 1024:
        return False
    try:
        import xarray as xr
        with xr.open_dataset(path) as ds:
            names = set(ds.variables)
            return bool({"u", "v"} & names)
    except Exception:
        return False


def build_request(
    year: int,
    pressure_level_hpa: int,
    area: Sequence[float],
    variables: Sequence[str] = DEFAULT_VARIABLES,
    times: Sequence[str] = DEFAULT_TIMES,
    data_format: str = "netcdf",
    download_format: str = "unarchived",
) -> dict:
    """Build a current CDS request dictionary without making a network call."""
    months = ["%02d" % month for month in range(1, 13)]
    days = ["%02d" % day for day in range(1, 32)]
    return {
        "product_type": ["reanalysis"],
        "variable": list(variables),
        "pressure_level": [str(int(pressure_level_hpa))],
        "year": [str(int(year))],
        "month": months,
        "day": days,
        "time": list(times),
        "area": list(area),
        "data_format": data_format,
        "download_format": download_format,
    }


def download_era5_pressure_level(
    year: int,
    pressure_level_hpa: int,
    area: Sequence[float],
    output_directory: Union[str, Path],
    variables: Sequence[str] = DEFAULT_VARIABLES,
    times: Sequence[str] = DEFAULT_TIMES,
    dataset_id: str = DATASET_ID,
    overwrite: bool = False,
    max_retries: int = 3,
    retry_wait_seconds: float = 10.0,
    filename: Optional[str] = None,
) -> Path:
    """Download one year and one pressure level.

    Requires ``cdsapi`` and valid CDS credentials. The request is kept separate
    from scientific processing so existing NetCDF files can be reused.
    """
    try:
        import cdsapi
    except ImportError as exc:
        raise ImportError(
            "cdsapi is required for downloading ERA5. Install with "
            "'python -m pip install cdsapi'."
        ) from exc

    output_directory = ensure_directory(output_directory)
    target = output_directory / (
        filename or build_filename(year, pressure_level_hpa)
    )

    if target.exists() and not overwrite and is_readable_netcdf(target):
        logger.info("Using cached file: %s", target)
        return target

    request = build_request(
        year=year,
        pressure_level_hpa=pressure_level_hpa,
        area=area,
        variables=variables,
        times=times,
    )
    client = cdsapi.Client()

    for attempt in range(1, max_retries + 1):
        try:
            logger.info(
                "Downloading ERA5 year=%s level=%s hPa attempt=%s",
                year, pressure_level_hpa, attempt
            )
            client.retrieve(dataset_id, request, str(target))
            if not is_readable_netcdf(target):
                raise IOError("downloaded file is not a readable u/v NetCDF")
            return target
        except Exception:
            if attempt == max_retries:
                raise
            time.sleep(retry_wait_seconds)
    raise RuntimeError("unreachable download state")


def download_era5_range(
    year_start: int,
    year_end: int,
    pressure_levels_hpa: Sequence[int],
    area: Sequence[float],
    output_directory: Union[str, Path],
    overwrite: bool = False,
    **kwargs
) -> List[Path]:
    """Download inclusive years and all requested pressure levels."""
    if year_end < year_start:
        raise ValueError("year_end must be >= year_start")
    paths = []
    for year in range(year_start, year_end + 1):
        for level in pressure_levels_hpa:
            paths.append(
                download_era5_pressure_level(
                    year, int(level), area, output_directory,
                    overwrite=overwrite, **kwargs
                )
            )
    return paths
