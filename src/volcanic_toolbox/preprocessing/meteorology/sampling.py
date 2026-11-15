"""Common meteorological samplers for random ERA5 and TMY methods."""

from __future__ import annotations
from dataclasses import dataclass
from typing import Optional
import numpy as np
import pandas as pd

from .config import MeteorologySampleConfig
from .wind import add_calendar_columns, add_wind_components


REQUIRED_COLUMNS = {
    "datetime", "u_m_s", "v_m_s", "pressure_level_hpa"
}


def _prepare(data: pd.DataFrame) -> pd.DataFrame:
    missing = REQUIRED_COLUMNS.difference(data.columns)
    if missing:
        raise KeyError("Meteorological data are missing: %s" % sorted(missing))
    result = data.copy()
    if "wind_speed_m_s" not in result:
        result = add_wind_components(result)
    return add_calendar_columns(result)


@dataclass
class RandomMeteorologySampler:
    """Sample random timestamps from the full ERA5 record."""

    data: pd.DataFrame
    config: MeteorologySampleConfig

    def sample(self) -> pd.DataFrame:
        prepared = _prepare(self.data)
        if not self.config.replace and self.config.number_of_samples > len(prepared):
            raise ValueError("Cannot sample without replacement beyond data length")
        rng = np.random.default_rng(self.config.seed)
        indices = rng.choice(
            len(prepared),
            size=self.config.number_of_samples,
            replace=self.config.replace,
        )
        sampled = prepared.iloc[indices].copy().reset_index(drop=True)
        sampled.insert(
            0, "meteo_id",
            ["random_%06d" % i for i in range(1, len(sampled) + 1)]
        )
        sampled["sampling_method"] = "random_era5"
        return sampled


@dataclass
class TypicalYearMeteorologySampler:
    """Sample timestamps from a previously constructed TMY table."""

    tmy_data: pd.DataFrame
    config: MeteorologySampleConfig

    def sample(self) -> pd.DataFrame:
        prepared = _prepare(self.tmy_data)
        if not self.config.replace and self.config.number_of_samples > len(prepared):
            raise ValueError("Cannot sample without replacement beyond TMY length")
        rng = np.random.default_rng(self.config.seed)
        indices = rng.choice(
            len(prepared),
            size=self.config.number_of_samples,
            replace=self.config.replace,
        )
        sampled = prepared.iloc[indices].copy().reset_index(drop=True)
        sampled.insert(
            0, "meteo_id",
            ["tmy_%06d" % i for i in range(1, len(sampled) + 1)]
        )
        sampled["sampling_method"] = "typical_meteorological_year"
        return sampled
