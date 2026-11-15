"""Classify phase probabilities and combine multiphase hazard indices.

The index stage is intentionally applied *after* probability calculation.
It does not pair individual simulations across phases. Each phase ensemble is
first reduced to probability fields; those fields are then classified and
combined pixel by pixel.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import json
import math
import re
from typing import Any, Mapping, Sequence

import numpy as np
from netCDF4 import Dataset


class HazardIndexError(RuntimeError):
    """Raised when probability fields cannot be classified or combined."""


@dataclass(frozen=True)
class MetricIndexRule:
    """Classification rule for one probability metric.

    Parameters
    ----------
    metric
        One of ``c3d``, ``gl``, ``arrival``, ``persistence_conditional`` or
        ``persistence_unconditional``.
    levels
        Severity levels ordered from least to most severe. Units depend on the
        metric:

        * c3d: kg/m3 concentration thresholds;
        * gl: kg/m2 ground-load thresholds;
        * arrival: hours, ordered from longest to shortest;
        * persistence: hours, ordered from shortest to longest.

    probability_cutoff_percent
        Minimum probability required for a level to be assigned.
    index_values
        Optional ordinal values paired with ``levels``. When omitted, values
        are 1, 2, ..., N. Index 0 always means that no configured level reached
        the probability cutoff.
    enabled
        Disable a metric without deleting its configuration.
    """

    metric: str
    levels: tuple[float, ...]
    probability_cutoff_percent: float = 25.0
    index_values: tuple[int, ...] | None = None
    enabled: bool = True

    def __post_init__(self) -> None:
        metric = self.metric.strip().lower()
        object.__setattr__(self, 'metric', metric)
        allowed = {
            'c3d',
            'gl',
            'arrival',
            'persistence_conditional',
            'persistence_unconditional',
        }
        if metric not in allowed:
            raise ValueError(f'Unsupported index metric: {metric!r}')
        if not self.levels:
            raise ValueError(f'{metric}: at least one level is required.')
        if any(not math.isfinite(float(v)) for v in self.levels):
            raise ValueError(f'{metric}: levels must be finite.')
        if not 0 <= self.probability_cutoff_percent <= 100:
            raise ValueError('probability_cutoff_percent must be 0--100.')
        values = self.index_values
        if values is None:
            values = tuple(range(1, len(self.levels) + 1))
            object.__setattr__(self, 'index_values', values)
        if len(values) != len(self.levels):
            raise ValueError('index_values and levels must have equal length.')
        if any(int(v) <= 0 for v in values):
            raise ValueError('All non-zero index values must be positive.')
        if any(b <= a for a, b in zip(values, values[1:])):
            raise ValueError('index_values must increase with severity.')


@dataclass(frozen=True)
class MultiphaseIndexConfig:
    """Controls phase-level classification and multiphase combination.

    Parameters
    ----------
    enabled
        Run the hazard-index stage.
    phase_order
        Phases expected in every multiphase product.
    rules
        Metric classification rules.
    calculate_phase_sum
        Save the unweighted sum of phase indices.
    calculate_weighted_index
        Save the weighted average of phase indices. Because weights sum to 1,
        this output remains on the same ordinal scale as the phase indices.
    weights_by_metric
        Mapping ``metric -> phase -> weight``. Every enabled metric must have
        non-negative weights for all phases and the weights must sum to 1.
    calculate_contributing_phase_count
        Save the number of phases with a non-zero index in each pixel.
    calculate_maximum_phase_index
        Save the maximum phase-specific index in each pixel.
    require_all_phases
        If true, a combined subset is skipped unless all configured phases are
        available. This prevents silently combining incomplete events.
    """

    enabled: bool = True
    phase_order: tuple[str, ...] = (
        'extreme_intensity',
        'high_intensity',
        'low_intensity',
    )
    rules: tuple[MetricIndexRule, ...] = ()
    calculate_phase_sum: bool = True
    calculate_weighted_index: bool = True
    weights_by_metric: Mapping[str, Mapping[str, float]] = field(
        default_factory=dict
    )
    calculate_contributing_phase_count: bool = True
    calculate_maximum_phase_index: bool = True
    require_all_phases: bool = True

    def __post_init__(self) -> None:
        if not self.phase_order:
            raise ValueError('phase_order cannot be empty.')
        if len(set(self.phase_order)) != len(self.phase_order):
            raise ValueError('phase_order contains duplicate names.')
        enabled_metrics = {rule.metric for rule in self.rules if rule.enabled}
        if len(enabled_metrics) != len([r for r in self.rules if r.enabled]):
            raise ValueError('Only one enabled rule is allowed per metric.')
        if self.calculate_weighted_index:
            missing = enabled_metrics.difference(self.weights_by_metric)
            if missing:
                raise ValueError(
                    f'Missing phase weights for metrics: {sorted(missing)}'
                )
            for metric in enabled_metrics:
                weights = self.weights_by_metric[metric]
                absent = set(self.phase_order).difference(weights)
                if absent:
                    raise ValueError(
                        f'{metric}: missing weights for phases {sorted(absent)}'
                    )
                selected = [float(weights[p]) for p in self.phase_order]
                if any(value < 0 for value in selected):
                    raise ValueError(f'{metric}: weights cannot be negative.')
                if not math.isclose(sum(selected), 1.0, abs_tol=1e-8):
                    raise ValueError(
                        f'{metric}: phase weights must sum to 1; '
                        f'got {sum(selected):.12g}.'
                    )


@dataclass(frozen=True)
class IndexField:
    name: str
    values: np.ndarray
    attributes: dict[str, Any]
    metric: str
    stratum_key: tuple[tuple[str, Any], ...]


def _safe(value: object) -> str:
    return re.sub(r'[^A-Za-z0-9_]+', '_', str(value)).strip('_')


def _token(value: float) -> str:
    return f'{float(value):.12g}'.replace('-', 'm').replace('.', 'p')


def _close(a: Any, b: float) -> bool:
    try:
        return math.isclose(float(a), float(b), rel_tol=1e-9, abs_tol=1e-12)
    except (TypeError, ValueError):
        return False


def _variable_metric(variable: Any) -> str | None:
    metric = getattr(variable, 'metric', '')
    conditioning = getattr(variable, 'conditioning', '')
    if metric == 'c3d_probability_of_exceedance':
        return 'c3d'
    if metric == 'ground_load_probability_of_exceedance':
        return 'gl'
    if metric == 'arrival_probability':
        return 'arrival'
    if metric == 'post_arrival_persistence_probability':
        if conditioning == 'conditional_on_arrival':
            return 'persistence_conditional'
        if conditioning == 'unconditional':
            return 'persistence_unconditional'
    return None


def _stratum(variable: Any, metric: str) -> tuple[tuple[str, Any], ...]:
    attributes: list[tuple[str, Any]] = []
    if metric in {
        'c3d', 'arrival', 'persistence_conditional',
        'persistence_unconditional'
    }:
        attributes.append(('altitude_range', getattr(variable, 'altitude_range')))
    if metric in {
        'arrival', 'persistence_conditional',
        'persistence_unconditional'
    }:
        attributes.append(('threshold', float(getattr(variable, 'threshold'))))
        attributes.append(
            ('threshold_units', getattr(variable, 'threshold_units'))
        )
    return tuple(attributes)


def _level_value(variable: Any, metric: str) -> float:
    if metric in {'c3d', 'gl'}:
        return float(getattr(variable, 'threshold'))
    return float(getattr(variable, 'time_threshold_h'))


def _index_name(metric: str, stratum: tuple[tuple[str, Any], ...]) -> str:
    parts = [f'{metric}_hazard_index']
    for key, value in stratum:
        if isinstance(value, float):
            value = _token(value)
        parts.append(f'{_safe(key)}_{_safe(value)}')
    return '__'.join(parts)


def classify_probability_file(
    probability_path: Path,
    rule: MetricIndexRule,
) -> tuple[np.ndarray, np.ndarray, list[IndexField], str, str]:
    """Classify one phase/subset probability NetCDF for one metric."""
    with Dataset(probability_path, 'r') as dataset:
        lat = np.asarray(dataset.variables['lat'][:], dtype=np.float64)
        lon = np.asarray(dataset.variables['lon'][:], dtype=np.float64)
        phase = str(getattr(dataset, 'phase', ''))
        subset = str(getattr(dataset, 'subset', ''))

        groups: dict[
            tuple[tuple[str, Any], ...], dict[float, tuple[str, np.ndarray]]
        ] = {}
        for name, variable in dataset.variables.items():
            if variable.dimensions != ('lat', 'lon'):
                continue
            metric = _variable_metric(variable)
            if metric != rule.metric:
                continue
            stratum = _stratum(variable, metric)
            level = _level_value(variable, metric)
            values = np.asarray(np.ma.filled(variable[:], np.nan), dtype=float)
            groups.setdefault(stratum, {})[level] = (name, values)

    fields: list[IndexField] = []
    for stratum, available in groups.items():
        index = np.zeros((len(lat), len(lon)), dtype=np.int16)
        source_variables: list[str] = []
        missing_levels: list[float] = []

        for level, index_value in zip(rule.levels, rule.index_values or ()):
            match = next(
                (key for key in available if _close(key, float(level))),
                None,
            )
            if match is None:
                missing_levels.append(float(level))
                continue
            variable_name, probability = available[match]
            source_variables.append(variable_name)
            qualifies = np.isfinite(probability) & (
                probability >= rule.probability_cutoff_percent
            )
            index = np.where(
                qualifies,
                np.maximum(index, int(index_value)),
                index,
            ).astype(np.int16)

        if missing_levels:
            raise HazardIndexError(
                f'{probability_path}: metric {rule.metric!r}, stratum '
                f'{dict(stratum)} is missing configured levels '
                f'{missing_levels}. Available levels: {sorted(available)}'
            )

        name = _index_name(rule.metric, stratum)
        attributes = {
            'metric': rule.metric,
            'index_definition': (
                'highest configured severity level whose probability is '
                'greater than or equal to the probability cutoff'
            ),
            'probability_cutoff_percent': float(
                rule.probability_cutoff_percent
            ),
            'severity_levels': json.dumps([float(v) for v in rule.levels]),
            'index_values': json.dumps([int(v) for v in rule.index_values or ()]),
            'source_probability_variables': json.dumps(source_variables),
            'minimum_index': 0,
            'maximum_index': max(rule.index_values or (0,)),
        }
        for key, value in stratum:
            attributes[key] = value

        fields.append(
            IndexField(
                name=name,
                values=index,
                attributes=attributes,
                metric=rule.metric,
                stratum_key=stratum,
            )
        )

    if not fields:
        raise HazardIndexError(
            f'No probability variables matched metric {rule.metric!r} in '
            f'{probability_path}.'
        )
    return lat, lon, fields, phase, subset


def write_phase_index_netcdf(
    probability_path: Path,
    output_path: Path,
    config: MultiphaseIndexConfig,
) -> Path:
    """Write every enabled phase-specific hazard index."""
    all_fields: list[IndexField] = []
    reference_lat = reference_lon = None
    phase = subset = ''

    for rule in config.rules:
        if not rule.enabled:
            continue
        lat, lon, fields, current_phase, current_subset = (
            classify_probability_file(probability_path, rule)
        )
        if reference_lat is None:
            reference_lat, reference_lon = lat, lon
            phase, subset = current_phase, current_subset
        elif (
            reference_lat.shape != lat.shape
            or reference_lon.shape != lon.shape
            or not np.allclose(reference_lat, lat)
            or not np.allclose(reference_lon, lon)
        ):
            raise HazardIndexError('Grid changed during index classification.')
        all_fields.extend(fields)

    if reference_lat is None or not all_fields:
        raise HazardIndexError('No enabled hazard-index fields were created.')

    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = output_path.with_suffix(output_path.suffix + '.tmp')
    with Dataset(temporary, 'w', format='NETCDF4') as dataset:
        dataset.createDimension('lat', len(reference_lat))
        dataset.createDimension('lon', len(reference_lon))
        lat_var = dataset.createVariable('lat', 'f8', ('lat',))
        lon_var = dataset.createVariable('lon', 'f8', ('lon',))
        lat_var[:] = reference_lat
        lon_var[:] = reference_lon
        lat_var.units = 'degrees_north'
        lon_var.units = 'degrees_east'
        dataset.phase = phase
        dataset.subset = subset
        dataset.product = 'phase_hazard_indices'
        dataset.source_probability_netcdf = str(probability_path)

        for field in all_fields:
            variable = dataset.createVariable(
                field.name, 'i2', ('lat', 'lon'), zlib=True, complevel=4
            )
            variable[:] = field.values
            for key, value in field.attributes.items():
                setattr(variable, key, value)

    temporary.replace(output_path)
    return output_path


def _read_phase_index_file(path: Path) -> tuple[np.ndarray, np.ndarray, dict[str, tuple[np.ndarray, dict[str, Any]]]]:
    with Dataset(path, 'r') as dataset:
        lat = np.asarray(dataset.variables['lat'][:], dtype=float)
        lon = np.asarray(dataset.variables['lon'][:], dtype=float)
        fields = {}
        for name, variable in dataset.variables.items():
            if variable.dimensions != ('lat', 'lon'):
                continue
            values = np.asarray(np.ma.filled(variable[:], 0), dtype=float)
            attrs = {
                attr: variable.getncattr(attr)
                for attr in variable.ncattrs()
                if attr != '_FillValue'
            }
            fields[name] = (values, attrs)
    return lat, lon, fields


def combine_phase_index_files(
    phase_files: Mapping[str, Path],
    output_path: Path,
    subset: str,
    config: MultiphaseIndexConfig,
) -> Path:
    """Combine matching phase-specific indices pixel by pixel."""
    missing = set(config.phase_order).difference(phase_files)
    if missing and config.require_all_phases:
        raise HazardIndexError(
            f'Subset {subset!r} is missing phase index files: {sorted(missing)}'
        )
    phases = [p for p in config.phase_order if p in phase_files]
    if not phases:
        raise HazardIndexError(f'No phase index files for subset {subset!r}.')

    reference_lat = reference_lon = None
    by_phase: dict[str, dict[str, tuple[np.ndarray, dict[str, Any]]]] = {}
    for phase in phases:
        lat, lon, fields = _read_phase_index_file(phase_files[phase])
        if reference_lat is None:
            reference_lat, reference_lon = lat, lon
        elif (
            lat.shape != reference_lat.shape
            or lon.shape != reference_lon.shape
            or not np.allclose(lat, reference_lat)
            or not np.allclose(lon, reference_lon)
        ):
            raise HazardIndexError(
                f'Grid mismatch in phase index file {phase_files[phase]}'
            )
        by_phase[phase] = fields

    common_names = set.intersection(
        *(set(by_phase[phase]) for phase in phases)
    )
    if not common_names:
        raise HazardIndexError(
            f'No common phase-index variables for subset {subset!r}.'
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = output_path.with_suffix(output_path.suffix + '.tmp')
    with Dataset(temporary, 'w', format='NETCDF4') as dataset:
        dataset.createDimension('lat', len(reference_lat))
        dataset.createDimension('lon', len(reference_lon))
        lat_var = dataset.createVariable('lat', 'f8', ('lat',))
        lon_var = dataset.createVariable('lon', 'f8', ('lon',))
        lat_var[:] = reference_lat
        lon_var[:] = reference_lon
        lat_var.units = 'degrees_north'
        lon_var.units = 'degrees_east'
        dataset.subset = subset
        dataset.product = 'multiphase_hazard_indices'
        dataset.phases = json.dumps(phases)

        for name in sorted(common_names):
            arrays = np.stack(
                [by_phase[phase][name][0] for phase in phases], axis=0
            )
            attrs = by_phase[phases[0]][name][1]
            metric = str(attrs.get('metric', ''))
            base = f'{name}__multiphase'

            # Preserve each phase contribution in the combined file.
            for phase_index, phase in enumerate(phases):
                variable = dataset.createVariable(
                    f'{name}__phase_{_safe(phase)}',
                    'i2', ('lat', 'lon'), zlib=True, complevel=4,
                )
                variable[:] = arrays[phase_index].astype(np.int16)
                variable.metric = metric
                variable.phase = phase
                variable.combination_role = 'phase_component'

            if config.calculate_phase_sum:
                variable = dataset.createVariable(
                    f'{base}__sum',
                    'i2', ('lat', 'lon'), zlib=True, complevel=4,
                )
                variable[:] = np.sum(arrays, axis=0).astype(np.int16)
                variable.metric = metric
                variable.combination = 'unweighted_sum_of_phase_indices'
                variable.phases = json.dumps(phases)

            if config.calculate_weighted_index:
                weights = config.weights_by_metric[metric]
                selected_weights = np.asarray(
                    [float(weights[phase]) for phase in phases], dtype=float
                )
                if not math.isclose(
                    float(selected_weights.sum()), 1.0, abs_tol=1e-8
                ):
                    if config.require_all_phases:
                        raise HazardIndexError(
                            f'{metric}: available phase weights do not sum to 1.'
                        )
                    selected_weights = selected_weights / selected_weights.sum()
                weighted = np.tensordot(
                    selected_weights, arrays, axes=(0, 0)
                )
                variable = dataset.createVariable(
                    f'{base}__weighted',
                    'f4', ('lat', 'lon'), zlib=True, complevel=4,
                )
                variable[:] = weighted.astype(np.float32)
                variable.metric = metric
                variable.combination = 'weighted_average_of_phase_indices'
                variable.phase_weights = json.dumps(
                    {phase: float(weight) for phase, weight in zip(phases, selected_weights)}
                )

            if config.calculate_contributing_phase_count:
                variable = dataset.createVariable(
                    f'{base}__contributing_phase_count',
                    'i1', ('lat', 'lon'), zlib=True, complevel=4,
                )
                variable[:] = np.sum(arrays > 0, axis=0).astype(np.int8)
                variable.metric = metric
                variable.combination = 'number_of_phases_with_nonzero_index'

            if config.calculate_maximum_phase_index:
                variable = dataset.createVariable(
                    f'{base}__maximum_phase_index',
                    'i2', ('lat', 'lon'), zlib=True, complevel=4,
                )
                variable[:] = np.max(arrays, axis=0).astype(np.int16)
                variable.metric = metric
                variable.combination = 'maximum_phase_specific_index'

    temporary.replace(output_path)
    return output_path
