"""Configuration for one phase of a multiphase eruptive event."""

from __future__ import annotations
from dataclasses import dataclass
from typing import Sequence

from .parameter import ParameterConfig


@dataclass(frozen=True)
class EruptionPhaseConfig:
    """Definition of one stochastic eruptive phase.

    Parameters are sampled independently within the phase and prefixed in the
    output table. The phase must include the configured height and duration keys.
    """

    name: str
    parameters: Sequence[ParameterConfig]
    height_key: str = "column_height"
    duration_key: str = "duration"

    def __post_init__(self) -> None:
        name = self.name.strip().lower().replace(" ", "_")
        if not name or not name.replace("_", "").isalnum():
            raise ValueError("phase name must contain letters, numbers or underscores")
        object.__setattr__(self, "name", name)
        params = tuple(self.parameters)
        if not params:
            raise ValueError("each phase requires at least one parameter")
        keys = [p.key for p in params]
        if len(keys) != len(set(keys)):
            raise ValueError("parameter keys must be unique inside a phase")
        if self.height_key not in keys:
            raise KeyError("phase is missing height parameter key '%s'" % self.height_key)
        if self.duration_key not in keys:
            raise KeyError("phase is missing duration parameter key '%s'" % self.duration_key)
        object.__setattr__(self, "parameters", params)

    def output_column(self, parameter_key: str) -> str:
        config = next(p for p in self.parameters if p.key == parameter_key)
        return "%s_%s" % (self.name, config.column_name)
