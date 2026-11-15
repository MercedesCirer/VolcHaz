"""Temporal and intensity hazard curves for configured points.

Figure filenames are intentionally compact to avoid Windows MAX_PATH problems
when the toolbox is stored inside deeply nested directories such as OneDrive.
"""

from __future__ import annotations

from pathlib import Path
import re

import matplotlib.pyplot as plt
import pandas as pd


def build_curve_tables(df):
    out = {}
    specs = {
        "arrival_time": (
            "arrival_probability",
            "time_threshold_h",
            1.0,
            "h",
        ),
        "persistence": (
            "post_arrival_persistence_probability",
            "time_threshold_h",
            1.0,
            "h",
        ),
        "c3d_intensity": (
            "c3d_probability_of_exceedance",
            "threshold",
            1e6,
            "mg m-3",
        ),
        "ground_load_intensity": (
            "ground_load_probability_of_exceedance",
            "threshold",
            1.0,
            "kg m-2",
        ),
    }

    for key, (metric, xcol, scale, units) in specs.items():
        frame = df[df.metric == metric].copy()
        if frame.empty:
            continue

        frame["curve_type"] = key
        frame["x"] = (
            pd.to_numeric(frame[xcol], errors="coerce")
            * scale
        )
        frame["x_units"] = units
        out[key] = frame

    return out


def _safe_token(value):
    """Return a short filesystem-safe token."""
    if pd.isna(value):
        return "NA"
    return re.sub(
        r"[^A-Za-z0-9_.-]+",
        "_",
        str(value),
    ).strip("_")


def _compact_filename(curve_key, descriptor):
    """Build short but traceable figure names.

    Examples
    --------
    AT_extreme_intensity_all_FL000_200_TH2e-07.png
    PTc_low_intensity_wet_FL000_200_TH2e-06.png
    C3D_high_intensity_all_FL200_350.png
    GL_low_intensity_all.png
    """
    prefix = {
        "arrival_time": "AT",
        "persistence": "PT",
        "c3d_intensity": "C3D",
        "ground_load_intensity": "GL",
    }[curve_key]

    if curve_key == "persistence":
        conditioning = str(
            descriptor.get("conditioning", "")
        ).lower()
        if conditioning == "conditional_on_arrival":
            prefix = "PTc"
        elif conditioning == "unconditional":
            prefix = "PTu"

    parts = [
        prefix,
        _safe_token(descriptor.get("phase", "")),
        _safe_token(descriptor.get("subset", "")),
    ]

    altitude_range = descriptor.get("altitude_range")
    if altitude_range is not None and not pd.isna(altitude_range):
        parts.append(_safe_token(altitude_range))

    threshold = descriptor.get("threshold")
    if threshold is not None and not pd.isna(threshold):
        parts.append(f"TH{_safe_token(threshold)}")

    parts = [part for part in parts if part]
    return "_".join(parts) + ".png"


def plot_curve_groups(tables, outdir, dpi=300):
    """Plot grouped point hazard curves.

    Filenames are deliberately compact because long project paths on Windows
    can otherwise exceed MAX_PATH and cause ``FileNotFoundError`` during
    ``fig.savefig``.
    """
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    saved = []

    for key, frame in tables.items():
        groups = ["phase", "subset"]

        if "altitude_range" in frame.columns:
            groups.append("altitude_range")

        if key in {"arrival_time", "persistence"}:
            groups.append("threshold")

        if key == "persistence":
            groups.append("conditioning")

        for values, group in frame.groupby(
            groups,
            dropna=False,
        ):
            if not isinstance(values, tuple):
                values = (values,)

            descriptor = dict(zip(groups, values))

            fig, ax = plt.subplots(figsize=(9, 5.5))

            for point_id, point_frame in group.groupby("point_id"):
                point_frame = point_frame.sort_values("x")
                ax.plot(
                    point_frame["x"],
                    point_frame["probability_percent"],
                    marker="o",
                    label=str(point_id),
                )

            ax.set_ylim(0, 100)
            ax.set_ylabel("Probability (%)")
            ax.grid(True, linestyle="--", alpha=0.35)

            if key == "arrival_time":
                ax.set_xlabel("Arrival-time threshold, t (h)")
                ax.set_title(r"$P(AT \leq t)$")

            elif key == "persistence":
                ax.set_xlabel("Persistence threshold, t (h)")
                conditioning = str(
                    descriptor.get("conditioning", "")
                )
                if conditioning == "conditional_on_arrival":
                    ax.set_title(
                        r"$P(PT \geq t \mid arrival)$"
                    )
                else:
                    ax.set_title(
                        r"$P(arrival\ and\ PT \geq t)$"
                    )

            elif key == "c3d_intensity":
                ax.set_xlabel(
                    r"C3D threshold (mg m$^{-3}$)"
                )
                ax.set_xscale("log")
                ax.set_title("C3D intensity hazard curve")

            else:
                ax.set_xlabel(
                    r"Ground-load threshold (kg m$^{-2}$)"
                )
                ax.set_xscale("log")
                ax.set_title("Ground-load intensity hazard curve")

            ax.legend(
                title="Point",
                bbox_to_anchor=(1.02, 1),
                loc="upper left",
                fontsize=8,
            )

            fig.tight_layout(rect=(0, 0, 0.8, 1))

            filename = _compact_filename(
                key,
                descriptor,
            )
            path = outdir / filename

            fig.savefig(
                path,
                dpi=dpi,
                bbox_inches="tight",
            )
            plt.close(fig)
            saved.append(path)

    return saved
