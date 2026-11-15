"""Diagnostics for deciding whether point hazard curves are informative."""

from __future__ import annotations

import numpy as np
import pandas as pd


C3D_METRICS = {
    "c3d_probability_of_exceedance",
    "arrival_probability",
    "post_arrival_persistence_probability",
}


def _threshold_label(row):
    threshold = row.get("threshold", np.nan)
    units = row.get("threshold_units", "")

    if pd.isna(threshold):
        return ""

    threshold = float(threshold)

    if units == "kg m-3":
        return f"{threshold * 1e6:g} mg m-3"

    return f"{threshold:g} {units}".strip()


def _safe_max(series):
    values = pd.to_numeric(
        series,
        errors="coerce",
    )

    if not values.notna().any():
        return np.nan

    return float(values.max())


def point_hazard_summary(
    dataframe: pd.DataFrame,
    zero_tolerance: float = 0.0,
):
    """Return group-level diagnostics for point probability results.

    The summary is designed to answer:

      * Are all selected points exactly 0%?
      * Which phase/subset/altitude-range/threshold combinations have signal?
      * What is the maximum probability among the selected points?
      * Are conditional persistence values present where C3D PoE is 0%?

    ``zero_tolerance`` is in percentage points.
    """
    if dataframe.empty:
        return pd.DataFrame(), pd.DataFrame()

    df = dataframe.copy()
    df["probability_percent"] = pd.to_numeric(
        df["probability_percent"],
        errors="coerce",
    )

    summary_rows = []

    # C3D intensity: one potential curve per phase/subset/altitude range.
    c3d = df[
        df["metric"] == "c3d_probability_of_exceedance"
    ]

    if not c3d.empty:
        groups = [
            "phase",
            "subset",
            "altitude_range",
        ]

        for keys, group in c3d.groupby(
            groups,
            dropna=False,
        ):
            maximum = _safe_max(
                group["probability_percent"]
            )
            summary_rows.append({
                "curve_type": "C3D",
                **dict(zip(groups, keys)),
                "threshold": np.nan,
                "conditioning": "",
                "max_probability_percent": maximum,
                "number_points": group["point_id"].nunique(),
                "number_positive_rows": int(
                    (
                        group["probability_percent"]
                        > zero_tolerance
                    ).sum()
                ),
                "recommended_to_plot": bool(
                    np.isfinite(maximum)
                    and maximum > zero_tolerance
                ),
            })

    # GL intensity: one potential curve per phase/subset.
    gl = df[
        df["metric"]
        == "ground_load_probability_of_exceedance"
    ]

    if not gl.empty:
        groups = ["phase", "subset"]

        for keys, group in gl.groupby(
            groups,
            dropna=False,
        ):
            maximum = _safe_max(
                group["probability_percent"]
            )
            summary_rows.append({
                "curve_type": "GL",
                **dict(zip(groups, keys)),
                "altitude_range": "",
                "threshold": np.nan,
                "conditioning": "",
                "max_probability_percent": maximum,
                "number_points": group["point_id"].nunique(),
                "number_positive_rows": int(
                    (
                        group["probability_percent"]
                        > zero_tolerance
                    ).sum()
                ),
                "recommended_to_plot": bool(
                    np.isfinite(maximum)
                    and maximum > zero_tolerance
                ),
            })

    # AT: one potential curve per phase/subset/range/concentration threshold.
    at = df[
        df["metric"] == "arrival_probability"
    ]

    if not at.empty:
        groups = [
            "phase",
            "subset",
            "altitude_range",
            "threshold",
        ]

        for keys, group in at.groupby(
            groups,
            dropna=False,
        ):
            maximum = _safe_max(
                group["probability_percent"]
            )
            summary_rows.append({
                "curve_type": "AT",
                **dict(zip(groups, keys)),
                "conditioning": "",
                "max_probability_percent": maximum,
                "number_points": group["point_id"].nunique(),
                "number_positive_rows": int(
                    (
                        group["probability_percent"]
                        > zero_tolerance
                    ).sum()
                ),
                "recommended_to_plot": bool(
                    np.isfinite(maximum)
                    and maximum > zero_tolerance
                ),
            })

    # PT: one potential curve per phase/subset/range/concentration threshold/
    # conditioning definition.
    pt = df[
        df["metric"]
        == "post_arrival_persistence_probability"
    ]

    if not pt.empty:
        groups = [
            "phase",
            "subset",
            "altitude_range",
            "threshold",
            "conditioning",
        ]

        for keys, group in pt.groupby(
            groups,
            dropna=False,
        ):
            maximum = _safe_max(
                group["probability_percent"]
            )
            summary_rows.append({
                "curve_type": "PT",
                **dict(zip(groups, keys)),
                "max_probability_percent": maximum,
                "number_points": group["point_id"].nunique(),
                "number_positive_rows": int(
                    (
                        group["probability_percent"]
                        > zero_tolerance
                    ).sum()
                ),
                "recommended_to_plot": bool(
                    np.isfinite(maximum)
                    and maximum > zero_tolerance
                ),
            })

    summary = pd.DataFrame(summary_rows)

    # ------------------------------------------------------------------
    # Consistency diagnostic.
    #
    # For the same phase/subset/range/threshold/point:
    #
    # temporal mean exceedance -> maximum exceedance must also occur.
    #
    # Therefore positive AT/PT cannot coexist with exactly-zero C3D PoE
    # at the SAME grid node and threshold.
    # ------------------------------------------------------------------
    issues = []

    if not c3d.empty and (not at.empty or not pt.empty):
        c3d_key = [
            "point_id",
            "phase",
            "subset",
            "altitude_range",
            "threshold",
        ]

        c3d_lookup = (
            c3d[c3d_key + ["probability_percent"]]
            .rename(columns={
                "probability_percent":
                    "c3d_probability_percent"
            })
        )

        temporal = pd.concat(
            [at, pt],
            ignore_index=True,
        )

        temporal = temporal.merge(
            c3d_lookup,
            on=c3d_key,
            how="left",
        )

        bad = temporal[
            (
                temporal["c3d_probability_percent"]
                <= zero_tolerance
            )
            & (
                temporal["probability_percent"]
                > zero_tolerance
            )
        ]

        for _, row in bad.iterrows():
            issues.append({
                "point_id": row["point_id"],
                "phase": row["phase"],
                "subset": row["subset"],
                "altitude_range": row["altitude_range"],
                "threshold": row["threshold"],
                "temporal_metric": row["metric"],
                "conditioning": row.get(
                    "conditioning",
                    "",
                ),
                "temporal_probability_percent":
                    row["probability_percent"],
                "c3d_probability_percent":
                    row["c3d_probability_percent"],
                "message": (
                    "Temporal probability is positive while "
                    "C3D PoE is zero for the same point, "
                    "altitude range and concentration threshold."
                ),
            })

    return summary, pd.DataFrame(issues)


def print_point_hazard_summary(
    dataframe: pd.DataFrame,
    zero_tolerance: float = 0.0,
):
    """Print a concise human-readable pre-plot report."""
    summary, issues = point_hazard_summary(
        dataframe,
        zero_tolerance=zero_tolerance,
    )

    print("=" * 79)
    print("ATLAS POINT-HAZARD PRE-PLOT SUMMARY")
    print("=" * 79)

    if dataframe.empty:
        print("No point probability records were found.")
        return summary, issues

    point_ids = sorted(
        dataframe["point_id"].astype(str).unique()
    )

    print(
        f"Selected points ({len(point_ids)}): "
        + ", ".join(point_ids)
    )
    print()

    if summary.empty:
        print("No supported hazard metrics were found.")
        return summary, issues

    informative = summary[
        summary["recommended_to_plot"]
    ]
    zero_groups = summary[
        ~summary["recommended_to_plot"]
    ]

    if informative.empty:
        print(
            "RESULT: probabilities are 0% (or undefined) "
            "for all selected points in every curve group."
        )
        print(
            "Recommendation: do not create point hazard "
            "curve figures for this selection."
        )
    else:
        print(
            f"Informative curve groups: {len(informative)} / "
            f"{len(summary)}"
        )
        print(
            f"Zero/undefined curve groups: {len(zero_groups)} / "
            f"{len(summary)}"
        )
        print()

        for curve_type in ("C3D", "GL", "AT", "PT"):
            table = summary[
                summary["curve_type"] == curve_type
            ]

            if table.empty:
                continue

            max_probability = _safe_max(
                table["max_probability_percent"]
            )

            n_useful = int(
                table["recommended_to_plot"].sum()
            )

            if (
                not np.isfinite(max_probability)
                or max_probability <= zero_tolerance
            ):
                print(
                    f"{curve_type}: 0% for all selected "
                    "points/groups -> figures not recommended."
                )
            else:
                print(
                    f"{curve_type}: maximum probability among "
                    f"selected points = {max_probability:.3g}% | "
                    f"useful groups = {n_useful}/{len(table)}"
                )

    print()
    print("C3D / AT / PT concentration thresholds:")
    thresholds = (
        dataframe[
            dataframe["metric"].isin(C3D_METRICS)
        ]["threshold"]
        .dropna()
        .astype(float)
        .unique()
    )

    if len(thresholds):
        print(
            "  "
            + ", ".join(
                f"{value * 1e6:g} mg m-3"
                for value in sorted(thresholds)
            )
        )

    print()
    print(
        "C3D uses the configured C3D vertical operator; "
        "AT/PT use the temporal vertical operator."
    )
    print(
        "Conditional PT is conditional on arrival, so it can "
        "be numerically high even when arrival is rare."
    )

    if issues.empty:
        print()
        print(
            "Consistency check: OK. No positive AT/PT values "
            "were found where the corresponding C3D PoE is 0%."
        )
    else:
        print()
        print(
            f"WARNING: {len(issues)} C3D-versus-temporal "
            "inconsistency record(s) were detected."
        )
        print(
            "With nearest-node extraction this should not occur. "
            "Re-run point extraction with the corrected points.py."
        )

    return summary, issues
