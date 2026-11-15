"""Configuration objects for stochastic eruption parameters."""

from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Mapping, Optional
import math

SUPPORTED_DISTRIBUTIONS = {"normal", "gaussian", "lognormal", "uniform", "triangular", "fixed"}


@dataclass(frozen=True)
class BoundsConfig:
    """Inclusive bounds and enforcement method for a sampled parameter."""

    minimum: Optional[float] = None
    maximum: Optional[float] = None
    method: str = "resample"
    max_iterations: int = 10000

    def __post_init__(self) -> None:
        method = self.method.lower().strip()
        object.__setattr__(self, "method", method)
        if self.minimum is not None and not math.isfinite(self.minimum):
            raise ValueError("minimum must be finite or None")
        if self.maximum is not None and not math.isfinite(self.maximum):
            raise ValueError("maximum must be finite or None")
        if self.minimum is not None and self.maximum is not None:
            if self.minimum > self.maximum:
                raise ValueError("minimum cannot exceed maximum")
        if method not in {"resample", "clip"}:
            raise ValueError("method must be 'resample' or 'clip'")
        if self.max_iterations <= 0:
            raise ValueError("max_iterations must be > 0")


@dataclass(frozen=True)
class ParameterConfig:
    """Immutable configuration for one candidate eruption parameter.

    Lognormal distributions support:
    - metadata={"parameterization": "log_space"} with mu and sigma.
    - metadata={"parameterization": "physical_space"} with mean and std.
    """

    key: str
    name: str
    units: Optional[str]
    distribution: str
    parameters: Mapping[str, float]
    bounds: Optional[BoundsConfig] = None
    description: Optional[str] = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        key = self.key.strip()
        name = self.name.strip()
        distribution = self.distribution.lower().strip()
        if not key or not key.replace("_", "").isalnum():
            raise ValueError("key must contain letters, numbers or underscores")
        if not name:
            raise ValueError("name cannot be empty")
        if distribution not in SUPPORTED_DISTRIBUTIONS:
            raise ValueError("unsupported distribution: %s" % distribution)

        numeric = {}
        for pname, value in dict(self.parameters).items():
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise TypeError("%s must be numeric" % pname)
            value = float(value)
            if not math.isfinite(value):
                raise ValueError("%s must be finite" % pname)
            numeric[pname] = value

        object.__setattr__(self, "key", key)
        object.__setattr__(self, "name", name)
        object.__setattr__(self, "distribution", distribution)
        object.__setattr__(self, "parameters", MappingProxyType(numeric))
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))
        self._validate()

    def _require(self, *names: str) -> None:
        missing = [name for name in names if name not in self.parameters]
        if missing:
            raise ValueError("%s is missing %s" % (self.key, missing))

    def _validate(self) -> None:
        dist = "normal" if self.distribution == "gaussian" else self.distribution
        p = self.parameters
        if dist == "normal":
            self._require("mean", "std")
            if p["std"] <= 0:
                raise ValueError("normal std must be > 0")
        elif dist == "uniform":
            self._require("low", "high")
            if p["high"] <= p["low"]:
                raise ValueError("uniform high must exceed low")
        elif dist == "triangular":
            self._require("left", "mode", "right")
            if not p["left"] <= p["mode"] <= p["right"]:
                raise ValueError("triangular requires left <= mode <= right")
            if p["right"] <= p["left"]:
                raise ValueError("triangular right must exceed left")
        elif dist == "fixed":
            self._require("value")
        elif dist == "lognormal":
            mode = str(self.metadata.get("parameterization", "log_space")).lower()
            if mode == "log_space":
                self._require("mu", "sigma")
                if p["sigma"] <= 0:
                    raise ValueError("lognormal sigma must be > 0")
            elif mode == "physical_space":
                self._require("mean", "std")
                if p["mean"] <= 0 or p["std"] <= 0:
                    raise ValueError("physical-space mean and std must be > 0")
            else:
                raise ValueError("invalid lognormal parameterization")

    @property
    def column_name(self) -> str:
        return "%s_%s" % (self.key, self.units) if self.units else self.key

    def to_dict(self) -> dict:
        return {
            "key": self.key,
            "name": self.name,
            "units": self.units,
            "distribution": self.distribution,
            "parameters": dict(self.parameters),
            "bounds": None if self.bounds is None else {
                "minimum": self.bounds.minimum,
                "maximum": self.bounds.maximum,
                "method": self.bounds.method,
                "max_iterations": self.bounds.max_iterations,
            },
            "description": self.description,
            "metadata": dict(self.metadata),
        }
