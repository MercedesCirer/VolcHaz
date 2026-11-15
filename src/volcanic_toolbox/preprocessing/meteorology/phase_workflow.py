"""Phase-specific TMY construction, stochastic sampling and export."""

from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import pandas as pd

from .config import MeteorologySampleConfig
from .sampling import RandomMeteorologySampler, TypicalYearMeteorologySampler
from .tmy import (
    TMYConfig, calculate_fs_table, select_typical_months,
    build_typical_meteorological_year,
)
from .wind import add_wind_components


@dataclass
class PhaseMeteorologyProducts:
    phase_name: str
    full_data: pd.DataFrame
    fs_scores: pd.DataFrame
    selected_months: pd.DataFrame
    tmy_data: pd.DataFrame
    historical_samples: pd.DataFrame | None = None
    tmy_samples: pd.DataFrame | None = None


def build_phase_tmy(
    phase_name: str,
    full_data: pd.DataFrame,
    config: TMYConfig,
) -> PhaseMeteorologyProducts:
    """Build one TMY from the wind series selected for one eruptive phase."""
    prepared = add_wind_components(full_data)
    fs = calculate_fs_table(prepared, config=config)
    selected = select_typical_months(fs)
    tmy = build_typical_meteorological_year(prepared, selected)
    return PhaseMeteorologyProducts(phase_name, prepared, fs, selected, tmy)


def sample_phase_meteorology(
    products: PhaseMeteorologyProducts,
    sample_config: MeteorologySampleConfig,
) -> PhaseMeteorologyProducts:
    """Create historical-random and TMY-random samples for one phase."""
    products.historical_samples = RandomMeteorologySampler(
        products.full_data, sample_config
    ).sample()
    products.tmy_samples = TypicalYearMeteorologySampler(
        products.tmy_data, sample_config
    ).sample()
    return products


def save_phase_meteorology_products(
    products: PhaseMeteorologyProducts,
    output_directory: str | Path,
) -> dict[str, Path]:
    """Save all available products for one phase."""
    output = Path(output_directory)
    output.mkdir(parents=True, exist_ok=True)
    tables = {
        "full": (products.full_data, output / "full_wind_data.csv"),
        "fs": (products.fs_scores, output / "tmy_fs_scores.csv"),
        "selected": (products.selected_months, output / "tmy_selected_months.csv"),
        "tmy": (products.tmy_data, output / "tmy_wind_data.csv"),
    }
    if products.historical_samples is not None:
        tables["historical_samples"] = (
            products.historical_samples,
            output / "random_historical_meteorology_samples.csv",
        )
    if products.tmy_samples is not None:
        tables["tmy_samples"] = (
            products.tmy_samples,
            output / "random_tmy_meteorology_samples.csv",
        )
    paths = {}
    for key, (table, path) in tables.items():
        table.to_csv(path, index=False)
        paths[key] = path
    return paths


def load_selected_phase_meteorology(
    phase_directory: str | Path,
    source: str,
) -> pd.DataFrame:
    """Load the chosen meteorological ensemble for one phase.

    source must be ``historical`` or ``tmy``.
    """
    source = source.lower().strip()
    filenames = {
        "historical": "random_historical_meteorology_samples.csv",
        "tmy": "random_tmy_meteorology_samples.csv",
    }
    if source not in filenames:
        raise ValueError("source must be 'historical' or 'tmy'")
    path = Path(phase_directory) / filenames[source]
    if not path.exists():
        raise FileNotFoundError(path)
    return pd.read_csv(path, parse_dates=["datetime"])
