"""Distribution sampling and bound enforcement."""

from __future__ import annotations

from typing import Mapping, Optional, Tuple
import math
import numpy as np

from .parameter import ParameterConfig


def sample_normal(rng, size: int, mean: float, std: float) -> np.ndarray:
    _validate_size(size)
    if std <= 0:
        raise ValueError("std must be > 0")
    return rng.normal(mean, std, size)


def physical_to_log_space(mean: float, std: float) -> Tuple[float, float]:
    if mean <= 0 or std <= 0:
        raise ValueError("mean and std must be > 0")
    sigma = math.sqrt(math.log1p((std ** 2) / (mean ** 2)))
    mu = math.log(mean) - 0.5 * sigma ** 2
    return mu, sigma


def sample_lognormal(
    rng,
    size: int,
    mu: Optional[float] = None,
    sigma: Optional[float] = None,
    mean: Optional[float] = None,
    std: Optional[float] = None,
    parameterization: str = "log_space",
) -> np.ndarray:
    _validate_size(size)
    if parameterization == "physical_space":
        if mean is None or std is None:
            raise ValueError("physical_space requires mean and std")
        mu, sigma = physical_to_log_space(float(mean), float(std))
    elif mu is None or sigma is None:
        raise ValueError("log_space requires mu and sigma")
    if float(sigma) <= 0:
        raise ValueError("sigma must be > 0")
    return rng.lognormal(float(mu), float(sigma), size)


def sample_uniform(rng, size: int, low: float, high: float) -> np.ndarray:
    _validate_size(size)
    if high <= low:
        raise ValueError("high must exceed low")
    return rng.uniform(low, high, size)


def sample_triangular(
    rng, size: int, left: float, mode: float, right: float
) -> np.ndarray:
    _validate_size(size)
    if right <= left:
        raise ValueError("right must exceed left")
    if not left <= mode <= right:
        raise ValueError("left <= mode <= right is required")
    return rng.triangular(left, mode, right, size)


def sample_fixed(size: int, value: float) -> np.ndarray:
    _validate_size(size)
    return np.full(size, float(value))


def sample_distribution(config: ParameterConfig, size: int, rng) -> np.ndarray:
    values = _draw(config, size, rng)
    if config.bounds is None:
        return _validate(values, size, config.key)

    low = -np.inf if config.bounds.minimum is None else config.bounds.minimum
    high = np.inf if config.bounds.maximum is None else config.bounds.maximum

    if config.bounds.method == "clip":
        return _validate(np.clip(values, low, high), size, config.key)

    result = values.copy()
    bad = (~np.isfinite(result)) | (result < low) | (result > high)
    iterations = 0
    while bad.any() and iterations < config.bounds.max_iterations:
        result[bad] = _draw(config, int(bad.sum()), rng)
        bad = (~np.isfinite(result)) | (result < low) | (result > high)
        iterations += 1
    if bad.any():
        raise RuntimeError(
            "Could not sample %s within bounds after %d iterations"
            % (config.key, config.bounds.max_iterations)
        )
    return _validate(result, size, config.key)


def _draw(config: ParameterConfig, size: int, rng) -> np.ndarray:
    dist = "normal" if config.distribution == "gaussian" else config.distribution
    p = config.parameters
    if dist == "normal":
        return sample_normal(rng, size, p["mean"], p["std"])
    if dist == "uniform":
        return sample_uniform(rng, size, p["low"], p["high"])
    if dist == "triangular":
        return sample_triangular(
            rng, size, p["left"], p["mode"], p["right"]
        )
    if dist == "fixed":
        return sample_fixed(size, p["value"])
    if dist == "lognormal":
        mode = str(config.metadata.get("parameterization", "log_space")).lower()
        if mode == "physical_space":
            return sample_lognormal(
                rng, size, mean=p["mean"], std=p["std"],
                parameterization=mode
            )
        return sample_lognormal(
            rng, size, mu=p["mu"], sigma=p["sigma"],
            parameterization=mode
        )
    raise ValueError("unsupported distribution")


def _validate_size(size: int) -> None:
    if isinstance(size, bool) or not isinstance(size, (int, np.integer)):
        raise TypeError("size must be an integer")
    if size <= 0:
        raise ValueError("size must be > 0")


def _validate(values, size: int, key: str) -> np.ndarray:
    values = np.asarray(values, dtype=float)
    if values.shape != (size,):
        raise RuntimeError("%s returned unexpected shape" % key)
    if not np.isfinite(values).all():
        raise RuntimeError("%s returned non-finite values" % key)
    return values
