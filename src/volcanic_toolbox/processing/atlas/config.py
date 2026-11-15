"""Configuration for GRIB-first ERA5 downloads required by ATLAS."""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Sequence

@dataclass(frozen=True)
class AtlasERA5DownloadConfig:
    """Control scenario parsing, GRIB retrieval and NetCDF conversion.

    ``keep_grib=False`` removes the smaller transport GRIB only after a valid
    NetCDF has been created. Failed conversions always retain the GRIB.
    """
    scenario_table: Path | str
    area: Sequence[float]
    output_directory: Path | str
    phase_names: Optional[Sequence[str]] = None
    days_after: int = 10
    max_workers: int = 1
    accepted_only: bool = True
    overwrite: bool = False
    dry_run: bool = True
    keep_grib: bool = False
    converter: str = "eccodes"
    grib_to_netcdf_executable: str = "grib_to_netcdf"
    netcdf_kind: int = 3
    netcdf_data_type: str = "NC_FLOAT"
    netcdf_compression_level: int = 4

    def __post_init__(self) -> None:
        object.__setattr__(self, "scenario_table", Path(self.scenario_table))
        object.__setattr__(self, "output_directory", Path(self.output_directory))
        object.__setattr__(self, "converter", self.converter.lower().strip())
        if len(tuple(self.area)) != 4:
            raise ValueError("area must contain NORTH, WEST, SOUTH and EAST")
        if self.days_after < 0: raise ValueError("days_after cannot be negative")
        if self.max_workers < 1: raise ValueError("max_workers must be at least 1")
        if self.converter != "eccodes":
            raise ValueError("converter currently supports only 'eccodes'")
        if self.netcdf_kind not in {1,2,3,4}:
            raise ValueError("netcdf_kind must be 1, 2, 3 or 4")
        if self.netcdf_data_type not in {"NC_BYTE","NC_SHORT","NC_INT","NC_FLOAT","NC_DOUBLE"}:
            raise ValueError("unsupported netcdf_data_type")
        if not 0 <= self.netcdf_compression_level <= 9:
            raise ValueError("netcdf_compression_level must be between 0 and 9")
        if self.netcdf_compression_level and self.netcdf_kind not in {3,4}:
            raise ValueError("compression requires netCDF-4 kind 3 or 4")
