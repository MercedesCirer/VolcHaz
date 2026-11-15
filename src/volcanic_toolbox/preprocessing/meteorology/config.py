"""Configuration objects for ERA5 retrieval and meteorological sampling."""

from __future__ import annotations
from dataclasses import dataclass
from typing import Sequence, Tuple


@dataclass(frozen=True)
class ERA5DownloadConfig:
    year_start: int
    year_end: int
    pressure_levels_hpa: Sequence[int]
    latitude: float
    longitude: float
    half_box_degrees: float = 0.25
    times_utc: Tuple[str, ...] = ("00:00", "06:00", "12:00", "18:00")
    dataset_id: str = "reanalysis-era5-pressure-levels"
    data_format: str = "netcdf"
    download_format: str = "unarchived"

    def __post_init__(self) -> None:
        if self.year_end < self.year_start:
            raise ValueError("year_end must be >= year_start")
        if not self.pressure_levels_hpa:
            raise ValueError("at least one pressure level is required")
        if not -90 <= self.latitude <= 90:
            raise ValueError("invalid latitude")
        if not -180 <= self.longitude <= 360:
            raise ValueError("invalid longitude")
        if self.half_box_degrees <= 0:
            raise ValueError("half_box_degrees must be > 0")


@dataclass(frozen=True)
class MeteorologySampleConfig:
    """Common configuration for random and TMY meteorological assignment."""

    number_of_samples: int
    seed: int = 42
    replace: bool = True

    def __post_init__(self) -> None:
        if self.number_of_samples <= 0:
            raise ValueError("number_of_samples must be > 0")
