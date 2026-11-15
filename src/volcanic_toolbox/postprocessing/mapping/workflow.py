"""Stage 6 mapping workflow."""

from __future__ import annotations

import csv

from .base import read_basemap
from .products import (
    fields_for_metric,
    group_fields_for_intensity,
    make_intensity_map,
    make_isoprobability_map,
)
from .reader import load_all_fields


def run_probability_mapping(config):
    """Create maps for every requested interpolation method."""
    fields = load_all_fields(
        config.probability_root
    )

    if not fields:
        raise FileNotFoundError(
            "No atlas_probabilities_*.nc files were found under:\n"
            f"  {config.probability_root}"
        )

    basemap = read_basemap(
        config.base.basemap_shapefile
    )

    config.output.output_root.mkdir(
        parents=True,
        exist_ok=True,
    )

    manifest_rows = []

    for interpolation_method in config.base.interpolation_methods:

        print()
        print(
            f"[Stage 6] Interpolation method: "
            f"{interpolation_method.upper()}"
        )

        for metric_cfg in config.metrics:
            if not metric_cfg.enabled:
                continue

            metric_fields = fields_for_metric(
                fields,
                metric_cfg,
            )

            if not metric_fields:
                print(
                    f"[Stage 6] No fields found for "
                    f"{metric_cfg.metric}; skipping."
                )
                continue

            # ---------------------------------------------------------
            # A. Threshold-specific isoprobability maps
            # ---------------------------------------------------------
            for field in metric_fields:
                outputs = make_isoprobability_map(
                    field=field,
                    metric_cfg=metric_cfg,
                    global_basemap=basemap,
                    base_cfg=config.base,
                    text_cfg=config.text,
                    output_cfg=config.output,
                    min_probability=(
                        config.minimum_probability_to_draw_percent
                    ),
                    interpolation_method=interpolation_method,
                )

                for path in outputs:
                    manifest_rows.append(
                        (
                            interpolation_method,
                            metric_cfg.metric,
                            "isoprobability",
                            str(path),
                        )
                    )

            # ---------------------------------------------------------
            # B. Ordinal hazard-intensity maps
            # ---------------------------------------------------------
            groups = group_fields_for_intensity(
                metric_fields,
                metric_cfg.metric,
            )

            for fixed_probability in (
                metric_cfg.intensity_probability_levels_percent
            ):
                for group in groups.values():
                    outputs = make_intensity_map(
                        grouped_fields=group,
                        metric_cfg=metric_cfg,
                        fixed_probability=fixed_probability,
                        global_basemap=basemap,
                        base_cfg=config.base,
                        text_cfg=config.text,
                        output_cfg=config.output,
                        interpolation_method=interpolation_method,
                    )

                    for path in outputs:
                        manifest_rows.append(
                            (
                                interpolation_method,
                                metric_cfg.metric,
                                "hazard_intensity",
                                str(path),
                            )
                        )

    manifest = (
        config.output.output_root
        / "stage6_mapping_manifest.csv"
    )

    with manifest.open(
        "w",
        newline="",
        encoding="utf-8",
    ) as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "interpolation_method",
                "metric",
                "map_family",
                "output_file",
            ]
        )
        writer.writerows(manifest_rows)

    print()
    print(
        f"[Stage 6] Created {len(manifest_rows)} map file(s)."
    )
    print(
        f"[Stage 6] Manifest:\n  {manifest}"
    )

    return manifest_rows
