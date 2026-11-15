"""Distribution plots for sampled eruption parameters."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import matplotlib.pyplot as plt
import numpy as np

from ..eruption.distributions import physical_to_log_space
from ..eruption.parameter import ParameterConfig


def plot_parameter_histogram(
    values: np.ndarray,
    config: ParameterConfig,
    *,
    bins: int = 30,
    density: bool = True,
    overlay_pdf: bool = True,
    output_path: Optional[str | Path] = None,
    show: bool = False,
) -> tuple[plt.Figure, plt.Axes]:
    """Plot one sampled parameter and optionally overlay its theoretical PDF.

    The function does not create output directories unless ``output_path`` is
    explicitly supplied.
    """
    array = np.asarray(values, dtype=float)

    if array.ndim != 1:
        raise ValueError("values must be one-dimensional.")
    if array.size == 0:
        raise ValueError("values cannot be empty.")
    if not np.all(np.isfinite(array)):
        raise ValueError("values contain non-finite entries.")
    if bins <= 0:
        raise ValueError("bins must be greater than zero.")

    fig, ax = plt.subplots(figsize=(7.0, 4.5))
    counts, edges, _ = ax.hist(
        array,
        bins=bins,
        density=density,
        edgecolor="white",
        alpha=0.85,
        label="Samples",
    )

    xlabel = config.name
    if config.units:
        xlabel += f" [{config.units}]"

    ax.set_xlabel(xlabel)
    ax.set_ylabel("Probability density" if density else "Frequency")
    ax.set_title(f"{config.name}: {config.distribution}")
    ax.minorticks_on()
    ax.tick_params(which="major", length=6)
    ax.tick_params(which="minor", length=3)

    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    if overlay_pdf:
        x = _build_x_grid(array=array, config=config)
        pdf = _theoretical_pdf(x=x, config=config)

        if pdf is not None:
            if density:
                y = pdf
            else:
                mean_bin_width = float(np.mean(np.diff(edges)))
                y = pdf * array.size * mean_bin_width

            ax.plot(x, y, linewidth=2, label="Theoretical PDF")
            ax.legend(frameon=False)

        elif config.distribution == "fixed":
            ax.axvline(
                config.parameters["value"],
                linewidth=2,
                label="Fixed value",
            )
            ax.legend(frameon=False)

    fig.tight_layout()

    if output_path is not None:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(output_path, dpi=300, bbox_inches="tight")

    if show:
        plt.show()

    return fig, ax


def _build_x_grid(
    array: np.ndarray,
    config: ParameterConfig,
) -> np.ndarray:
    minimum = float(np.min(array))
    maximum = float(np.max(array))

    if config.bounds is not None:
        if config.bounds.minimum is not None:
            minimum = config.bounds.minimum
        if config.bounds.maximum is not None:
            maximum = config.bounds.maximum

    if minimum == maximum:
        padding = max(abs(minimum) * 0.05, 1.0)
        minimum -= padding
        maximum += padding

    return np.linspace(minimum, maximum, 500)


def _theoretical_pdf(
    x: np.ndarray,
    config: ParameterConfig,
) -> Optional[np.ndarray]:
    distribution = (
        "normal" if config.distribution == "gaussian" else config.distribution
    )
    p = config.parameters

    if distribution == "normal":
        mean = p["mean"]
        std = p["std"]
        return (
            np.exp(-0.5 * ((x - mean) / std) ** 2)
            / (std * np.sqrt(2.0 * np.pi))
        )

    if distribution == "uniform":
        pdf = np.zeros_like(x, dtype=float)
        inside = (x >= p["low"]) & (x <= p["high"])
        pdf[inside] = 1.0 / (p["high"] - p["low"])
        return pdf

    if distribution == "triangular":
        left = p["left"]
        mode = p["mode"]
        right = p["right"]

        pdf = np.zeros_like(x, dtype=float)

        # Rising branch:
        # f(x) = 2(x-left) / [(right-left)(mode-left)]
        # for left <= x <= mode.
        if mode > left:
            rising = (x >= left) & (x <= mode)
            pdf[rising] = (
                2.0 * (x[rising] - left)
                / ((right - left) * (mode - left))
            )

        # Falling branch:
        # f(x) = 2(right-x) / [(right-left)(right-mode)]
        # for mode <= x <= right.
        if right > mode:
            falling = (x >= mode) & (x <= right)
            pdf[falling] = (
                2.0 * (right - x[falling])
                / ((right - left) * (right - mode))
            )

        # Handle the limiting cases mode == left or mode == right.
        if mode == left:
            falling = (x >= left) & (x <= right)
            pdf[falling] = (
                2.0 * (right - x[falling])
                / ((right - left) ** 2)
            )

        if mode == right:
            rising = (x >= left) & (x <= right)
            pdf[rising] = (
                2.0 * (x[rising] - left)
                / ((right - left) ** 2)
            )

        return pdf

    if distribution == "lognormal":
        parameterization = str(
            config.metadata.get("parameterization", "log_space")
        ).lower()

        if parameterization == "physical_space":
            mu, sigma = physical_to_log_space(
                mean=p["mean"],
                std=p["std"],
            )
        else:
            mu = p["mu"]
            sigma = p["sigma"]

        pdf = np.zeros_like(x, dtype=float)
        positive = x > 0
        pdf[positive] = (
            np.exp(-((np.log(x[positive]) - mu) ** 2) / (2.0 * sigma**2))
            / (x[positive] * sigma * np.sqrt(2.0 * np.pi))
        )
        return pdf

    return None
