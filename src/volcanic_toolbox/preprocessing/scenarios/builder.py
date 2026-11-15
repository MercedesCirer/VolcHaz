"""Build physically validated VEI-constrained scenario ensembles."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Optional, Sequence

import numpy as np
import pandas as pd

from ..eruption import ParameterConfig, VEIConfig
from ..eruption.sampler import sample_candidate_eruption_parameters
from ..physics import (
    MERConfig,
    calculate_mer_degruyter_bonadonna,
    mass_from_mer_duration,
)


DEFAULT_SOUTHERN_SEASONS = {
    "summer": (12, 1, 2),
    "autumn": (3, 4, 5),
    "winter": (6, 7, 8),
    "spring": (9, 10, 11),
}


@dataclass(frozen=True)
class ScenarioBuildConfig:
    """Controls target size, stopping rules and reproducibility."""

    target_valid_scenarios: int = 1000
    batch_size: int = 1000
    max_attempts: int = 100_000
    seed: Optional[int] = None
    height_column: str = "column_height_m"
    duration_column: str = "duration_h"
    wind_column: str = "wind_speed_m_s"
    datetime_column: str = "datetime"
    height_reference: str = "asl"
    sample_meteorology_with_replacement: bool = True

    def __post_init__(self) -> None:
        if self.target_valid_scenarios <= 0:
            raise ValueError("target_valid_scenarios must be > 0")
        if self.batch_size <= 0:
            raise ValueError("batch_size must be > 0")
        if self.max_attempts < self.target_valid_scenarios:
            raise ValueError("max_attempts must be >= target_valid_scenarios")

        reference = str(self.height_reference).lower().strip()
        if reference not in {"asl", "above_vent"}:
            raise ValueError(
                "height_reference must be 'asl' or 'above_vent'"
            )


@dataclass
class ScenarioBuildResult:
    """Validated scenarios, all attempts, and run-level diagnostics."""

    valid_scenarios: pd.DataFrame
    evaluated_scenarios: pd.DataFrame
    summary: pd.DataFrame
    phase_diagnostics: pd.DataFrame | None = None

    @property
    def acceptance_rate(self) -> float:
        if self.evaluated_scenarios.empty:
            return 0.0
        return float(self.evaluated_scenarios["accepted"].mean())


class VEIScenarioBuilder:
    """Repeatedly sample candidate parameters and meteorology until target or stop."""

    def __init__(
        self,
        parameter_configs: Sequence[ParameterConfig],
        meteorology: pd.DataFrame,
        vei_config: VEIConfig,
        mer_config: MERConfig,
        build_config: ScenarioBuildConfig,
        seasons: Optional[Mapping[str, Sequence[int]]] = None,
    ) -> None:
        self.parameter_configs = tuple(parameter_configs)
        self.meteorology = meteorology.copy()
        self.vei_config = vei_config
        self.mer_config = mer_config
        self.config = build_config
        self.seasons = dict(seasons or DEFAULT_SOUTHERN_SEASONS)
        self._validate_inputs()

    def build(self) -> ScenarioBuildResult:
        rng = np.random.default_rng(self.config.seed)
        evaluated_batches = []
        accepted_count = 0
        attempts = 0
        batch_number = 0

        while (
            accepted_count < self.config.target_valid_scenarios
            and attempts < self.config.max_attempts
        ):
            remaining_attempts = self.config.max_attempts - attempts
            batch_n = min(self.config.batch_size, remaining_attempts)
            batch_number += 1
            eruption_seed = int(rng.integers(0, np.iinfo(np.uint32).max))
            candidates = sample_candidate_eruption_parameters(
                self.parameter_configs,
                number_of_candidates=batch_n,
                seed=eruption_seed,
                candidate_prefix=f"batch{batch_number:04d}",
            )
            meteo = self._sample_meteorology(batch_n, rng)
            batch = pd.concat(
                [candidates.reset_index(drop=True), meteo.reset_index(drop=True)],
                axis=1,
            )
            batch = self._evaluate_batch(batch)
            evaluated_batches.append(batch)
            attempts += len(batch)
            accepted_count += int(batch["accepted"].sum())

        evaluated = pd.concat(evaluated_batches, ignore_index=True)
        valid = evaluated.loc[evaluated["accepted"]].copy()
        valid = valid.iloc[: self.config.target_valid_scenarios].reset_index(drop=True)
        valid.insert(
            0,
            "scenario_id",
            [f"scenario_{index:06d}" for index in range(1, len(valid) + 1)],
        )

        reached_target = len(valid) == self.config.target_valid_scenarios
        summary = pd.DataFrame(
            [
                {
                    "requested_valid_scenarios": self.config.target_valid_scenarios,
                    "obtained_valid_scenarios": len(valid),
                    "total_attempts": len(evaluated),
                    "accepted_attempts": int(evaluated["accepted"].sum()),
                    "rejected_attempts": int((~evaluated["accepted"]).sum()),
                    "acceptance_rate": float(evaluated["accepted"].mean()),
                    "target_reached": reached_target,
                    "max_attempts": self.config.max_attempts,
                    "meteorology_rows_available": len(self.meteorology),
                    "vei": self.vei_config.vei,
                    "minimum_mass_kg": self.vei_config.minimum_mass_kg,
                    "maximum_mass_kg": self.vei_config.maximum_mass_kg,
                }
            ]
        )
        return ScenarioBuildResult(valid, evaluated, summary)

    def _sample_meteorology(
        self, number: int, rng: np.random.Generator
    ) -> pd.DataFrame:
        replace = self.config.sample_meteorology_with_replacement
        if not replace and number > len(self.meteorology):
            raise ValueError("Batch exceeds meteorology length without replacement")
        indices = rng.choice(len(self.meteorology), size=number, replace=replace)
        sampled = self.meteorology.iloc[indices].copy().reset_index(drop=True)
        if "meteo_source_row" not in sampled:
            sampled.insert(0, "meteo_source_row", indices)
        return sampled

    def _evaluate_batch(self, batch: pd.DataFrame) -> pd.DataFrame:
        result = batch.copy()
        mers = []
        masses = []
        reasons = []
        accepted = []

        for row in result.itertuples(index=False):
            row_dict = row._asdict()
            try:
                mer = calculate_mer_degruyter_bonadonna(
                    plume_height_m=float(row_dict[self.config.height_column]),
                    wind_speed_m_s=float(row_dict[self.config.wind_column]),
                    vent_elevation_m=self.mer_config.vent_elevation_m,
                    height_reference=self.config.height_reference,
                    config=self.mer_config,
                )
                mass = mass_from_mer_duration(
                    mer, float(row_dict[self.config.duration_column])
                )
                if mass < self.vei_config.minimum_mass_kg:
                    ok = False
                    reason = "mass_below_vei_minimum"
                elif mass > self.vei_config.maximum_mass_kg:
                    ok = False
                    reason = "mass_above_vei_maximum"
                else:
                    ok = True
                    reason = "accepted"
            except Exception as exc:
                mer = np.nan
                mass = np.nan
                ok = False
                reason = "physical_calculation_error:" + type(exc).__name__
            mers.append(mer)
            masses.append(mass)
            accepted.append(ok)
            reasons.append(reason)

        result["mer_kg_s"] = mers
        result["calculated_mass_kg"] = masses
        result["calculated_volume_km3"] = (
            result["calculated_mass_kg"]
            / self.vei_config.bulk_density_kg_m3
            / 1.0e9
        )
        result["accepted"] = accepted
        result["validation_reason"] = reasons
        result["vei"] = self.vei_config.vei
        result["vei_min_mass_kg"] = self.vei_config.minimum_mass_kg
        result["vei_max_mass_kg"] = self.vei_config.maximum_mass_kg
        result["season"] = self._assign_seasons(result[self.config.datetime_column])
        return result

    def _assign_seasons(self, datetimes: pd.Series) -> pd.Series:
        month_to_season = {}
        for season, months in self.seasons.items():
            for month in months:
                if month in month_to_season:
                    raise ValueError(f"Month {month} appears in multiple seasons")
                month_to_season[int(month)] = season
        parsed = pd.to_datetime(datetimes, errors="coerce")
        return parsed.dt.month.map(month_to_season).fillna("unassigned")

    def _validate_inputs(self) -> None:
        required = {
            self.config.wind_column,
            self.config.datetime_column,
        }
        missing = required.difference(self.meteorology.columns)
        if missing:
            raise KeyError(f"Meteorology is missing columns: {sorted(missing)}")
        parameter_columns = {config.column_name for config in self.parameter_configs}
        for required_parameter in (
            self.config.height_column,
            self.config.duration_column,
        ):
            if required_parameter not in parameter_columns:
                raise KeyError(
                    f"No ParameterConfig produces '{required_parameter}'"
                )
        if self.meteorology.empty:
            raise ValueError("meteorology cannot be empty")
