"""Read Stage 5 probability NetCDF products."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import numpy as np
from netCDF4 import Dataset


@dataclass
class ProbabilityField:
    path: Path
    variable: str
    phase: str
    subset: str
    metric: str
    values: np.ndarray
    lat: np.ndarray
    lon: np.ndarray
    attrs: dict


def discover_probability_files(root: Path) -> list[Path]:
    return sorted(root.rglob("atlas_probabilities_*.nc"))


def load_probability_fields(path: Path) -> list[ProbabilityField]:
    result = []

    with Dataset(path) as ds:
        lat = np.asarray(ds.variables["lat"][:], dtype=float)
        lon = np.asarray(ds.variables["lon"][:], dtype=float)
        phase = str(getattr(ds, "phase", ""))
        subset = str(getattr(ds, "subset", ""))

        for name, variable in ds.variables.items():
            if variable.dimensions != ("lat", "lon"):
                continue

            attrs = {
                attr: variable.getncattr(attr)
                for attr in variable.ncattrs()
                if attr != "_FillValue"
            }

            metric = str(attrs.get("metric", ""))
            if not metric:
                continue

            values = np.asarray(
                np.ma.filled(variable[:], np.nan),
                dtype=float,
            )

            result.append(
                ProbabilityField(
                    path=path,
                    variable=name,
                    phase=phase,
                    subset=subset,
                    metric=metric,
                    values=values,
                    lat=lat,
                    lon=lon,
                    attrs=attrs,
                )
            )

    return result


def load_all_fields(root: Path) -> list[ProbabilityField]:
    fields = []
    for path in discover_probability_files(root):
        fields.extend(load_probability_fields(path))
    return fields
