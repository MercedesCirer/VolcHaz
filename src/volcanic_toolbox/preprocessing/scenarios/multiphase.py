"""Build multiphase VEI events with independent meteorology for each phase."""

from __future__ import annotations
from dataclasses import dataclass
from typing import Mapping, Optional, Sequence
import numpy as np
import pandas as pd

from ..eruption import EruptionPhaseConfig, VEIConfig
from ..eruption.sampler import sample_candidate_eruption_parameters
from ..physics import MERConfig, calculate_mer_degruyter_bonadonna, mass_from_mer_duration
from .builder import DEFAULT_SOUTHERN_SEASONS, ScenarioBuildConfig, ScenarioBuildResult


@dataclass(frozen=True)
class PhaseMassFractionConstraint:
    phase_name: str
    minimum: float = 0.0
    maximum: float = 1.0

    def __post_init__(self):
        if not 0 <= self.minimum <= self.maximum <= 1:
            raise ValueError("phase mass fractions must satisfy 0 <= min <= max <= 1")


class MultiphaseVEIScenarioBuilder:
    """Generate events composed of two or more independently forced phases.

    Preferred v3 API
    ----------------
    ``meteorology_by_phase`` maps every phase name to its own meteorological
    sample table. Each phase can therefore use a different pressure level,
    TMY, historical ensemble, date, wind speed and sampling method.

    Backward compatibility
    ----------------------
    Passing ``meteorology`` uses the same table for all phases, reproducing the
    Stage 3 v2 behavior.

    The VEI constraint is applied to the sum of all phase masses.
    """

    def __init__(
        self,
        phase_configs: Sequence[EruptionPhaseConfig],
        meteorology: Optional[pd.DataFrame] = None,
        vei_config: Optional[VEIConfig] = None,
        mer_config: Optional[MERConfig] = None,
        build_config: Optional[ScenarioBuildConfig] = None,
        *,
        meteorology_by_phase: Optional[Mapping[str, pd.DataFrame]] = None,
        phase_fraction_constraints: Optional[Sequence[PhaseMassFractionConstraint]] = None,
        seasons: Optional[Mapping[str, Sequence[int]]] = None,
    ):
        self.phase_configs = tuple(phase_configs)
        if vei_config is None or mer_config is None or build_config is None:
            raise ValueError("vei_config, mer_config and build_config are required")
        self.vei_config = vei_config
        self.mer_config = mer_config
        self.config = build_config
        self.fraction_constraints = {
            item.phase_name: item for item in (phase_fraction_constraints or ())
        }
        self.seasons = dict(seasons or DEFAULT_SOUTHERN_SEASONS)
        if meteorology_by_phase is not None and meteorology is not None:
            raise ValueError("pass meteorology_by_phase or meteorology, not both")
        if meteorology_by_phase is None:
            if meteorology is None:
                raise ValueError("meteorology_by_phase is required")
            meteorology_by_phase = {
                phase.name: meteorology.copy() for phase in self.phase_configs
            }
            self.shared_meteorology = True
        else:
            meteorology_by_phase = {
                name: table.copy() for name, table in meteorology_by_phase.items()
            }
            self.shared_meteorology = False
        self.meteorology_by_phase = meteorology_by_phase
        self._validate_inputs()

    def build(self) -> ScenarioBuildResult:
        rng = np.random.default_rng(self.config.seed)
        batches = []
        accepted_count = attempts = batch_number = 0

        while accepted_count < self.config.target_valid_scenarios and attempts < self.config.max_attempts:
            n = min(self.config.batch_size, self.config.max_attempts - attempts)
            batch_number += 1
            parts = []
            for phase in self.phase_configs:
                seed = int(rng.integers(0, np.iinfo(np.uint32).max))
                sampled = sample_candidate_eruption_parameters(
                    phase.parameters, n, seed=seed,
                    candidate_prefix=f"{phase.name}_b{batch_number:04d}",
                ).drop(columns=["candidate_status"])
                sampled = sampled.rename(columns={c: f"{phase.name}_{c}" for c in sampled.columns})
                parts.append(sampled.reset_index(drop=True))
                phase_meteo = self._sample_phase_meteorology(phase.name, n, rng)
                parts.append(phase_meteo.reset_index(drop=True))

            batch = pd.concat(parts, axis=1)
            batch = self._evaluate_batch(batch)
            batches.append(batch)
            attempts += len(batch)
            accepted_count += int(batch["accepted"].sum())

        evaluated = pd.concat(batches, ignore_index=True)
        valid = evaluated.loc[evaluated["accepted"]].copy()
        valid = valid.iloc[:self.config.target_valid_scenarios].reset_index(drop=True)
        valid.insert(0, "scenario_id", [f"multiphase_{i:06d}" for i in range(1, len(valid)+1)])

        summary = pd.DataFrame([{
            "scenario_type": "multiphase_independent_meteorology",
            "number_of_phases": len(self.phase_configs),
            "phase_names": ",".join(p.name for p in self.phase_configs),
            "requested_valid_scenarios": self.config.target_valid_scenarios,
            "obtained_valid_scenarios": len(valid),
            "total_attempts": len(evaluated),
            "accepted_attempts": int(evaluated["accepted"].sum()),
            "rejected_attempts": int((~evaluated["accepted"]).sum()),
            "acceptance_rate": float(evaluated["accepted"].mean()),
            "target_reached": len(valid) == self.config.target_valid_scenarios,
            "max_attempts": self.config.max_attempts,
            "vei": self.vei_config.vei,
            "minimum_event_mass_kg": self.vei_config.minimum_mass_kg,
            "maximum_event_mass_kg": self.vei_config.maximum_mass_kg,
            "shared_meteorology_across_phases": self.shared_meteorology,
        }])
        diagnostics = self._phase_diagnostics(evaluated)
        return ScenarioBuildResult(valid, evaluated, summary, diagnostics)

    def _sample_phase_meteorology(self, phase_name, n, rng):
        table = self.meteorology_by_phase[phase_name]
        replace = self.config.sample_meteorology_with_replacement
        if not replace and n > len(table):
            raise ValueError(f"batch exceeds meteorology length for phase {phase_name}")
        indices = rng.choice(len(table), size=n, replace=replace)
        sampled = table.iloc[indices].copy().reset_index(drop=True)
        if "meteo_source_row" not in sampled:
            sampled.insert(0, "meteo_source_row", indices)
        return sampled.rename(columns={c: f"{phase_name}_{c}" for c in sampled.columns})

    def _evaluate_batch(self, batch):
        out = batch.copy()
        mass_columns = []
        phase_error = np.zeros(len(out), dtype=bool)
        phase_seasons = []

        for phase in self.phase_configs:
            hcol = phase.output_column(phase.height_key)
            dcol = phase.output_column(phase.duration_key)
            wind_col = f"{phase.name}_{self.config.wind_column}"
            datetime_col = f"{phase.name}_{self.config.datetime_column}"
            mer_col = f"{phase.name}_mer_kg_s"
            mass_col = f"{phase.name}_mass_kg"
            volume_col = f"{phase.name}_volume_km3"
            mers, masses = [], []
            for h, d, wind in zip(out[hcol], out[dcol], out[wind_col]):
                try:
                    mer = calculate_mer_degruyter_bonadonna(
                        plume_height_m=float(h), wind_speed_m_s=float(wind),
                        vent_elevation_m=self.mer_config.vent_elevation_m,
                        config=self.mer_config,
                        height_reference=self.config.height_reference,
                    )
                    mass = mass_from_mer_duration(mer, float(d))
                except Exception:
                    mer = mass = np.nan
                mers.append(mer); masses.append(mass)
            out[mer_col] = mers
            out[mass_col] = masses
            out[volume_col] = out[mass_col] / self.vei_config.bulk_density_kg_m3 / 1e9
            out[f"{phase.name}_season"] = self._assign_seasons(out[datetime_col])
            phase_seasons.append(f"{phase.name}_season")
            mass_columns.append(mass_col)
            phase_error |= ~np.isfinite(out[mass_col].to_numpy())

        out["event_total_mass_kg"] = out[mass_columns].sum(axis=1)
        out["event_total_volume_km3"] = out["event_total_mass_kg"] / self.vei_config.bulk_density_kg_m3 / 1e9
        duration_cols = [p.output_column(p.duration_key) for p in self.phase_configs]
        out["event_total_duration_h"] = out[duration_cols].sum(axis=1)
        for phase, mass_col in zip(self.phase_configs, mass_columns):
            out[f"{phase.name}_mass_fraction"] = out[mass_col] / out["event_total_mass_kg"]

        season_values = out[phase_seasons]
        out["same_season_across_phases"] = season_values.nunique(axis=1) == 1
        out["event_season"] = np.where(
            out["same_season_across_phases"], season_values.iloc[:, 0], "mixed"
        )

        below = out["event_total_mass_kg"] < self.vei_config.minimum_mass_kg
        above = out["event_total_mass_kg"] > self.vei_config.maximum_mass_kg
        fraction_failure = np.zeros(len(out), dtype=bool)
        fraction_reason = np.full(len(out), "", dtype=object)
        for name, constraint in self.fraction_constraints.items():
            col = f"{name}_mass_fraction"
            if col not in out:
                raise KeyError(f"fraction constraint refers to unknown phase '{name}'")
            bad = (out[col] < constraint.minimum) | (out[col] > constraint.maximum)
            fraction_failure |= bad.to_numpy()
            fraction_reason = np.where(bad, f"phase_fraction_outside_bounds:{name}", fraction_reason)

        accepted = ~(phase_error | below.to_numpy() | above.to_numpy() | fraction_failure)
        reasons = np.where(
            phase_error, "physical_calculation_error",
            np.where(below, "event_mass_below_vei_minimum",
                np.where(above, "event_mass_above_vei_maximum",
                    np.where(fraction_failure, fraction_reason, "accepted")))
        )
        out["accepted"] = accepted
        out["validation_reason"] = reasons
        out["vei"] = self.vei_config.vei
        out["vei_min_mass_kg"] = self.vei_config.minimum_mass_kg
        out["vei_max_mass_kg"] = self.vei_config.maximum_mass_kg
        return out

    def _phase_diagnostics(self, evaluated):
        rows = []
        for phase in self.phase_configs:
            table = self.meteorology_by_phase[phase.name]
            method_col = f"{phase.name}_sampling_method"
            pressure_col = f"{phase.name}_pressure_level_hpa"
            rows.append({
                "phase": phase.name,
                "meteorology_rows_available": len(table),
                "sampling_methods": (
                    ",".join(sorted(map(str, evaluated[method_col].dropna().unique())))
                    if method_col in evaluated else "unspecified"
                ),
                "pressure_levels_hpa": (
                    ",".join(map(str, sorted(evaluated[pressure_col].dropna().unique())))
                    if pressure_col in evaluated else "unspecified"
                ),
                "accepted_phase_wind_mean_m_s": float(
                    evaluated.loc[evaluated["accepted"], f"{phase.name}_{self.config.wind_column}"].mean()
                ),
            })
        return pd.DataFrame(rows)

    def _assign_seasons(self, datetimes):
        month_to_season = {}
        for season, months in self.seasons.items():
            for month in months:
                if int(month) in month_to_season:
                    raise ValueError("month appears in multiple seasons")
                month_to_season[int(month)] = season
        parsed = pd.to_datetime(datetimes, errors="coerce")
        return parsed.dt.month.map(month_to_season).fillna("unassigned")

    def _validate_inputs(self):
        if len(self.phase_configs) < 2:
            raise ValueError("multiphase builder requires at least two phases")
        names = [p.name for p in self.phase_configs]
        if len(names) != len(set(names)):
            raise ValueError("phase names must be unique")
        missing_tables = set(names).difference(self.meteorology_by_phase)
        extra_tables = set(self.meteorology_by_phase).difference(names)
        if missing_tables:
            raise KeyError(f"meteorology missing for phases: {sorted(missing_tables)}")
        if extra_tables:
            raise KeyError(f"meteorology supplied for unknown phases: {sorted(extra_tables)}")
        required = {self.config.wind_column, self.config.datetime_column}
        for name, table in self.meteorology_by_phase.items():
            if table.empty:
                raise ValueError(f"meteorology for phase '{name}' cannot be empty")
            missing = required.difference(table.columns)
            if missing:
                raise KeyError(f"meteorology for phase '{name}' is missing: {sorted(missing)}")
