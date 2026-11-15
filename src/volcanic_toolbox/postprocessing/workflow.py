"""High-level Stage 5 ATLAS postprocessing workflow."""

from __future__ import annotations

from pathlib import Path
import json
import logging

import pandas as pd

from .config import AtlasPostprocessConfig
from .curves import build_curve_tables, plot_curve_groups
from .discovery import discover_simulations, temporal_subsets
from .indices import (
    HazardIndexError,
    MultiphaseIndexConfig,
    combine_phase_index_files,
    write_phase_index_netcdf,
)
from .points import (
    extract_points,
    load_points,
)
from .probabilities import (
    calculate_probabilities,
    write_probability_netcdf,
)

logger = logging.getLogger(__name__)


def run_atlas_postprocessing(
    config: AtlasPostprocessConfig,
    index_config: MultiphaseIndexConfig | None = None,
) -> pd.DataFrame:
    """Run probability, point, curve and optional hazard-index products."""
    config.output_root.mkdir(parents=True, exist_ok=True)
    grouped = discover_simulations(config)
    points = load_points(config)

    manifest_rows = []
    all_point_tables = []
    probability_by_phase_subset: dict[tuple[str, str], Path] = {}
    index_by_phase_subset: dict[tuple[str, str], Path] = {}

    for phase, simulations in grouped.items():
        if not simulations:
            logger.warning('No outputs found for phase %s', phase)
            continue

        for subset_name, subset_simulations in temporal_subsets(
            simulations,
            config.month_groups,
        ).items():
            if not subset_simulations:
                logger.warning('No simulations for %s/%s', phase, subset_name)
                continue

            result = calculate_probabilities(
                subset_simulations,
                phase=phase,
                subset=subset_name,
                config=config,
            )

            fields_dir = (
                config.output_root / 'atlas' / phase / subset_name
                / 'probability_fields'
            )
            probability_path = (
                fields_dir / f'atlas_probabilities_{phase}_{subset_name}.nc'
            )
            write_probability_netcdf(result, probability_path)
            probability_by_phase_subset[(phase, subset_name)] = probability_path

            invalid_path = (
                fields_dir / f'invalid_files_{phase}_{subset_name}.csv'
            )
            pd.DataFrame(
                result.invalid_files,
                columns=['path', 'error'],
            ).to_csv(invalid_path, index=False)

            row = {
                'phase': phase,
                'subset': subset_name,
                'number_discovered': len(subset_simulations),
                'number_structurally_valid': len(result.valid_files),
                'number_reported_invalid_entries': len(result.invalid_files),
                'number_probability_fields': len(result.fields),
                'probability_netcdf': str(probability_path),
                'invalid_files_csv': str(invalid_path),
                'phase_index_netcdf': '',
                'multiphase_index_netcdf': '',
            }

            if index_config is not None and index_config.enabled:
                index_path = (
                    config.output_root / 'atlas' / phase / subset_name
                    / 'hazard_indices'
                    / f'atlas_hazard_indices_{phase}_{subset_name}.nc'
                )
                write_phase_index_netcdf(
                    probability_path,
                    index_path,
                    index_config,
                )
                index_by_phase_subset[(phase, subset_name)] = index_path
                row['phase_index_netcdf'] = str(index_path)

            manifest_rows.append(row)

            if not points.empty:
                point_table = (
                    config.output_root / 'atlas' / phase / subset_name
                    / 'points'
                    / f'point_probabilities_{phase}_{subset_name}.csv'
                )
                point_table.parent.mkdir(parents=True, exist_ok=True)
                extracted = extract_points(
                    probability_path,
                    points,
                    config.point_extraction,
                )
                extracted.to_csv(point_table, index=False)
                all_point_tables.append(extracted)

    # Combine classified grids only after all phase products exist.
    if index_config is not None and index_config.enabled:
        subsets = sorted({subset for _, subset in index_by_phase_subset})
        for subset in subsets:
            phase_files = {
                phase: index_by_phase_subset[(phase, subset)]
                for phase in index_config.phase_order
                if (phase, subset) in index_by_phase_subset
            }
            if not phase_files:
                continue
            combined_path = (
                config.output_root / 'atlas' / 'multiphase' / subset
                / 'hazard_indices'
                / f'atlas_multiphase_hazard_indices_{subset}.nc'
            )
            try:
                combine_phase_index_files(
                    phase_files,
                    combined_path,
                    subset,
                    index_config,
                )
            except HazardIndexError as error:
                logger.warning(
                    'Multiphase index skipped for subset %s: %s',
                    subset,
                    error,
                )
                continue

            # Record the combined product on every matching manifest row.
            for row in manifest_rows:
                if row['subset'] == subset:
                    row['multiphase_index_netcdf'] = str(combined_path)

    manifest = pd.DataFrame(manifest_rows)
    manifest_path = (
        config.output_root / 'atlas' / 'atlas_postprocessing_manifest.csv'
    )
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest.to_csv(manifest_path, index=False)

    if all_point_tables:
        point_probabilities = pd.concat(all_point_tables, ignore_index=True)
        combined_path = (
            config.output_root / 'atlas' / 'points'
            / 'all_point_probabilities.csv'
        )
        combined_path.parent.mkdir(parents=True, exist_ok=True)
        point_probabilities.to_csv(combined_path, index=False)

        curve_tables = build_curve_tables(point_probabilities)
        curve_table_dir = (
            config.output_root / 'atlas' / 'points' / 'hazard_curves'
            / 'tables'
        )
        curve_table_dir.mkdir(parents=True, exist_ok=True)
        for name, table in curve_tables.items():
            table.to_csv(curve_table_dir / f'{name}.csv', index=False)

        if config.create_point_curves:
            plot_curve_groups(
                curve_tables,
                config.output_root / 'atlas' / 'points'
                / 'hazard_curves' / 'figures',
            )

    snapshot = {
        'runs_root': str(config.runs_root),
        'output_root': str(config.output_root),
        'phases': config.phases,
        'c3d_thresholds_kg_m3': config.c3d_thresholds_kg_m3,
        'gl_thresholds_kg_m2': config.gl_thresholds_kg_m2,
        'c3d_exceedance_vertical_operator': (
            config.c3d_exceedance_vertical_operator
        ),
        'temporal_vertical_operator': config.temporal_vertical_operator,
        'arrival_hours': config.arrival_hours,
        'persistence_hours': config.persistence_hours,
        'dt_hours': config.dt_hours,
        'probability_comparison': config.probability_comparison,
        'month_groups': [
            {'name': group.name, 'months': group.months}
            for group in config.month_groups
        ],
        'hazard_indices_enabled': bool(
            index_config is not None and index_config.enabled
        ),
    }
    if index_config is not None and index_config.enabled:
        snapshot['hazard_index_config'] = {
            'phase_order': index_config.phase_order,
            'rules': [
                {
                    'metric': rule.metric,
                    'levels': rule.levels,
                    'probability_cutoff_percent': (
                        rule.probability_cutoff_percent
                    ),
                    'index_values': rule.index_values,
                    'enabled': rule.enabled,
                }
                for rule in index_config.rules
            ],
            'calculate_phase_sum': index_config.calculate_phase_sum,
            'calculate_weighted_index': (
                index_config.calculate_weighted_index
            ),
            'weights_by_metric': index_config.weights_by_metric,
            'require_all_phases': index_config.require_all_phases,
        }

    (
        config.output_root / 'atlas'
        / 'atlas_postprocessing_configuration.json'
    ).write_text(json.dumps(snapshot, indent=2), encoding='utf-8')

    return manifest
