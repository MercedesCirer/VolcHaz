"""Create isoprobability and ordinal hazard-intensity maps."""

from __future__ import annotations

from pathlib import Path
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap, BoundaryNorm
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
from scipy.interpolate import RegularGridInterpolator
from scipy.spatial import cKDTree

from .base import (
    DATA_CRS,
    add_annotation,
    create_base_axes,
    determine_extent,
)
from .styling import safe_token, expand_colors


def _sorted_grid(field):
    lat_order = np.argsort(field.lat)
    lon_order = np.argsort(field.lon)
    lat = field.lat[lat_order]
    lon = field.lon[lon_order]
    values = field.values[np.ix_(lat_order, lon_order)]
    return lat, lon, values


def _target_grid(field, base_cfg):
    """Build the regular display grid used by every interpolation method."""
    lat, lon, values = _sorted_grid(field)

    cell = base_cfg.interpolation_cellsize_deg

    new_lat = np.arange(
        lat.min(),
        lat.max() + cell * 0.5,
        cell,
    )
    new_lon = np.arange(
        lon.min(),
        lon.max() + cell * 0.5,
        cell,
    )

    xx, yy = np.meshgrid(new_lon, new_lat)

    return lat, lon, values, new_lon, new_lat, xx, yy


def _idw_kdtree(
    lon_pts,
    lat_pts,
    values,
    xx,
    yy,
    power=1.0,
    k=12,
    radius=0.75,
):
    """Inverse Distance Weighting using the legacy mapping implementation.

    This reproduces the method used in the user's previous probability-map
    scripts:

        power = 1
        k = 12
        radius = 0.75 degrees

    Cells with no valid neighbour inside ``radius`` remain NaN.
    """
    lon_pts = np.asarray(lon_pts, dtype=float)
    lat_pts = np.asarray(lat_pts, dtype=float)
    values = np.asarray(values, dtype=float)

    valid_points = (
        np.isfinite(lon_pts)
        & np.isfinite(lat_pts)
        & np.isfinite(values)
    )

    lon_pts = lon_pts[valid_points]
    lat_pts = lat_pts[valid_points]
    values = values[valid_points]

    if len(values) == 0:
        return np.full(xx.shape, np.nan, dtype=float)

    points = np.column_stack([lon_pts, lat_pts])
    tree = cKDTree(points)

    grid = np.column_stack(
        [xx.ravel(), yy.ravel()]
    )

    distances, indices = tree.query(
        grid,
        k=k,
        distance_upper_bound=radius,
    )

    # scipy returns 1D arrays when k=1. Normalize to 2D.
    if np.ndim(distances) == 1:
        distances = distances[:, None]
        indices = indices[:, None]

    n = len(values)

    valid_neighbours = (
        np.isfinite(distances)
        & (indices < n)
    )

    result = np.full(
        grid.shape[0],
        np.nan,
        dtype=float,
    )

    # Exact grid/data matches: preserve the original point value.
    has_zero = np.any(
        (distances == 0) & valid_neighbours,
        axis=1,
    )

    if np.any(has_zero):
        rows = np.where(has_zero)[0]
        first_zero = np.argmax(
            (distances[rows] == 0)
            & valid_neighbours[rows],
            axis=1,
        )
        result[rows] = values[
            indices[rows, first_zero]
        ]

    # Standard IDW for all remaining cells.
    rows = np.where(~has_zero)[0]

    if len(rows):
        d = distances[rows]
        idx = indices[rows]
        valid = valid_neighbours[rows]

        weights = np.zeros_like(
            d,
            dtype=float,
        )
        weights[valid] = (
            1.0
            / np.power(
                d[valid],
                power,
            )
        )

        neighbour_values = np.zeros_like(
            d,
            dtype=float,
        )
        neighbour_values[valid] = values[
            idx[valid]
        ]

        weight_sum = np.sum(
            weights,
            axis=1,
        )
        weighted_sum = np.sum(
            weights * neighbour_values,
            axis=1,
        )

        usable = weight_sum > 0

        result[
            rows[usable]
        ] = (
            weighted_sum[usable]
            / weight_sum[usable]
        )

    return result.reshape(xx.shape)


def interpolate_field(
    field,
    base_cfg,
    method,
):
    """Interpolate one Stage 5 probability field.

    Parameters
    ----------
    method:
        "idw"
            Legacy inverse-distance weighting using cKDTree.

        "linear"
            Bilinear interpolation over the regular Stage 5 lat/lon grid
            using scipy RegularGridInterpolator.

        "nearest"
            Nearest-neighbour interpolation over the regular Stage 5 grid
            using scipy RegularGridInterpolator.
    """
    (
        lat,
        lon,
        values,
        new_lon,
        new_lat,
        xx,
        yy,
    ) = _target_grid(
        field,
        base_cfg,
    )

    if method == "idw":
        source_lon, source_lat = np.meshgrid(
            lon,
            lat,
        )

        zz = _idw_kdtree(
            lon_pts=source_lon.ravel(),
            lat_pts=source_lat.ravel(),
            values=values.ravel(),
            xx=xx,
            yy=yy,
            power=base_cfg.idw_power,
            k=base_cfg.idw_k,
            radius=base_cfg.idw_radius_deg,
        )

    elif method in {"linear", "nearest"}:
        interpolator = RegularGridInterpolator(
            (lat, lon),
            values,
            method=method,
            bounds_error=False,
            fill_value=np.nan,
        )

        points = np.column_stack(
            [yy.ravel(), xx.ravel()]
        )

        zz = interpolator(
            points
        ).reshape(xx.shape)

    else:
        raise ValueError(
            f"Unsupported interpolation method: {method}"
        )

    return new_lon, new_lat, zz


def _save(fig, base_path, output_cfg, dpi=300):
    saved = []

    for file_format in output_cfg.output_formats:
        path = base_path.with_suffix(f".{file_format}")

        # Windows-safe defensive creation immediately before savefig.
        path.parent.mkdir(parents=True, exist_ok=True)

        kwargs = {
            "bbox_inches": "tight",
            "transparent": output_cfg.transparent_background,
        }
        if file_format in {"png", "jpg"}:
            kwargs["dpi"] = dpi

        fig.savefig(path, **kwargs)
        saved.append(path)

    plt.close(fig)
    return saved


def _field_matches_common(field, metric_cfg):
    if metric_cfg.phases is not None and field.phase not in metric_cfg.phases:
        return False

    if metric_cfg.subsets is not None and field.subset not in metric_cfg.subsets:
        return False

    altitude_range = field.attrs.get("altitude_range")
    if (
        metric_cfg.altitude_ranges is not None
        and altitude_range not in metric_cfg.altitude_ranges
    ):
        return False

    threshold = field.attrs.get("threshold")
    if (
        metric_cfg.concentration_thresholds_kg_m3 is not None
        and threshold is not None
        and field.attrs.get("threshold_units") == "kg m-3"
    ):
        if not any(
            np.isclose(float(threshold), float(x))
            for x in metric_cfg.concentration_thresholds_kg_m3
        ):
            return False

    return True


def fields_for_metric(fields, metric_cfg):
    mapping = {
        "c3d": "c3d_probability_of_exceedance",
        "gl": "ground_load_probability_of_exceedance",
        "arrival": "arrival_probability",
        "persistence_conditional":
            "post_arrival_persistence_probability",
        "persistence_unconditional":
            "post_arrival_persistence_probability",
    }

    wanted = mapping[metric_cfg.metric]
    selected = []

    for field in fields:
        if field.metric != wanted:
            continue
        if not _field_matches_common(field, metric_cfg):
            continue

        if metric_cfg.metric == "persistence_conditional":
            if field.attrs.get("conditioning") != "conditional_on_arrival":
                continue

        if metric_cfg.metric == "persistence_unconditional":
            if field.attrs.get("conditioning") != "unconditional":
                continue

        selected.append(field)

    return selected


def _probability_category(values, levels):
    levels = sorted(float(x) for x in levels)
    result = np.full(values.shape, np.nan, dtype=float)

    for index, level in enumerate(levels, start=1):
        result[values >= level] = index

    return result


def _compact_number(value):
    """Compact number token safe for Windows filenames.

    Examples
    --------
    0.2  -> 0p2
    2.0  -> 2
    0.25 -> 0p25
    """
    value = float(value)

    if np.isclose(value, round(value)):
        token = str(int(round(value)))
    else:
        token = f"{value:g}"

    return (
        token
        .replace("-", "m")
        .replace(".", "p")
    )


def _metric_alias(metric_name):
    """Short metric labels for filenames."""
    aliases = {
        "c3d": "C3D",
        "gl": "GL",
        "arrival": "AT",
        "persistence_conditional": "PTc",
        "persistence_unconditional": "PTu",
    }
    return aliases.get(
        metric_name,
        safe_token(metric_name),
    )


def _phase_alias(phase):
    """Short common phase names while preserving unknown names safely."""
    aliases = {
        "extreme_intensity": "extreme",
        "high_intensity": "high",
        "low_intensity": "low",
    }
    return aliases.get(
        str(phase),
        safe_token(phase),
    )


def _projection_alias(base_cfg):
    """Short projection directory name."""
    aliases = {
        "plate_carree": "geographic",
        "mercator": "mercator",
        "lambert_conformal": "lambert",
        "albers_equal_area": "albers",
    }

    if base_cfg.projection == "epsg":
        epsg_code = (
            base_cfg.projection_parameters
            .get("epsg_code", "custom")
        )
        return f"epsg{epsg_code}"

    return aliases.get(
        base_cfg.projection,
        safe_token(base_cfg.projection),
    )


def _altitude_token(field):
    altitude = field.attrs.get(
        "altitude_range"
    )
    if altitude in {
        None,
        "",
    }:
        return None
    return safe_token(
        altitude
    )


def _concentration_token(field):
    """Return C3D threshold token in mg m-3, e.g. C0p2, C2, C4."""
    threshold = field.attrs.get(
        "threshold"
    )
    units = field.attrs.get(
        "threshold_units",
        "",
    )

    if (
        threshold is None
        or units != "kg m-3"
    ):
        return None

    mg_m3 = float(
        threshold
    ) * 1e6

    return (
        "C"
        + _compact_number(
            mg_m3
        )
    )


def _ground_load_token(field):
    threshold = field.attrs.get(
        "threshold"
    )
    units = field.attrs.get(
        "threshold_units",
        "",
    )

    if threshold is None:
        return None

    if units == "kg m-2":
        return (
            "GL"
            + _compact_number(
                threshold
            )
        )

    return None


def _time_token(field):
    value = field.attrs.get(
        "time_threshold_h"
    )

    if value is None:
        return None

    return (
        "T"
        + _compact_number(
            value
        )
    )


def _compact_field_tokens(
    field,
    metric_name,
):
    """Build short but unambiguous filename tokens."""
    tokens = [
        _metric_alias(
            metric_name
        ),
        _phase_alias(
            field.phase
        ),
        safe_token(
            field.subset
        ),
    ]

    altitude = _altitude_token(
        field
    )
    if altitude:
        tokens.append(
            altitude
        )

    if metric_name == "c3d":
        concentration = (
            _concentration_token(
                field
            )
        )
        if concentration:
            tokens.append(
                concentration
            )

    elif metric_name == "gl":
        ground_load = (
            _ground_load_token(
                field
            )
        )
        if ground_load:
            tokens.append(
                ground_load
            )

    elif metric_name in {
        "arrival",
        "persistence_conditional",
        "persistence_unconditional",
    }:
        concentration = (
            _concentration_token(
                field
            )
        )
        if concentration:
            tokens.append(
                concentration
            )

        time_value = (
            _time_token(
                field
            )
        )
        if time_value:
            tokens.append(
                time_value
            )

    return tokens


def _compact_isoprobability_name(
    field,
    metric_name,
):
    return "_".join(
        _compact_field_tokens(
            field,
            metric_name,
        )
        + ["iso"]
    )


def _compact_intensity_name(
    field,
    metric_name,
    fixed_probability,
):
    """Short filename for fixed-probability ordinal hazard maps."""
    tokens = [
        _metric_alias(
            metric_name
        ),
        _phase_alias(
            field.phase
        ),
        safe_token(
            field.subset
        ),
    ]

    altitude = (
        _altitude_token(
            field
        )
    )
    if altitude:
        tokens.append(
            altitude
        )

    if metric_name in {
        "arrival",
        "persistence_conditional",
        "persistence_unconditional",
    }:
        concentration = (
            _concentration_token(
                field
            )
        )
        if concentration:
            tokens.append(
                concentration
            )

    tokens.append(
        "P"
        + _compact_number(
            fixed_probability
        )
    )

    return "_".join(
        tokens
    )

def _annotation_for_field(field):
    lines = []

    if "threshold" in field.attrs:
        threshold = float(field.attrs["threshold"])
        units = field.attrs.get("threshold_units", "")

        if units == "kg m-3":
            lines.append(
                rf"C threshold = {threshold * 1e6:g} mg m$^{{-3}}$"
            )
        elif units:
            lines.append(
                f"Threshold = {threshold:g} {units}"
            )

    if "time_threshold_h" in field.attrs:
        t = float(field.attrs["time_threshold_h"])
        if field.metric == "arrival_probability":
            lines.append(rf"AT $\leq$ {t:g} h")
        elif field.metric == "post_arrival_persistence_probability":
            lines.append(rf"PT $\geq$ {t:g} h")

    if "altitude_range" in field.attrs:
        lines.append(
            str(field.attrs["altitude_range"])
        )

    conditioning = field.attrs.get("conditioning")
    if conditioning:
        lines.append(
            "Conditional on arrival"
            if conditioning == "conditional_on_arrival"
            else "Unconditional"
        )

    return "\n".join(lines)


def make_isoprobability_map(
    field,
    metric_cfg,
    global_basemap,
    base_cfg,
    text_cfg,
    output_cfg,
    min_probability=None,
    interpolation_method="idw",
):
    lon, lat, probability = interpolate_field(
        field,
        base_cfg,
        interpolation_method,
    )

    if min_probability is not None:
        probability = np.where(
            probability >= min_probability,
            probability,
            np.nan,
        )

    levels = sorted(
        metric_cfg.isoprobability_levels_percent
    )

    category = _probability_category(
        probability,
        levels,
    )

    # Map framing priority:
    # 1) metric-specific extent
    # 2) general BASE_CONFIG.extent
    # 3) probability-grid extent + padding_deg
    if metric_cfg.extent is not None:
        extent = tuple(
            float(value)
            for value in metric_cfg.extent
        )
    else:
        extent = determine_extent(
            lon,
            lat,
            base_cfg,
        )

    fig, ax = create_base_axes(
        global_basemap,
        extent,
        base_cfg,
        text_cfg,
    )

    probability_colors = expand_colors(
        metric_cfg.probability_colors,
        len(levels),
    )

    cmap = ListedColormap(probability_colors)
    cmap.set_bad((1, 1, 1, 0))
    norm = BoundaryNorm(
        np.arange(0.5, len(levels) + 1.5, 1),
        cmap.N,
    )

    xx, yy = np.meshgrid(lon, lat)

    ax.pcolormesh(
        xx,
        yy,
        category,
        transform=DATA_CRS,
        cmap=cmap,
        norm=norm,
        shading="auto",
        alpha=0.35,
        zorder=5,
    )

    for level, color in zip(levels, probability_colors):
        finite = probability[np.isfinite(probability)]
        if finite.size and finite.min() <= level <= finite.max():
            ax.contour(
                xx,
                yy,
                probability,
                levels=[level],
                colors=[color],
                transform=DATA_CRS,
                linewidths=1.5,
                zorder=15,
            )

    handles = [
        Patch(
            facecolor=color,
            edgecolor=color,
            alpha=0.35,
            label=rf"$\geq$ {level:g}%",
        )
        for level, color in zip(levels, probability_colors)
    ]

    ax.legend(
        handles=handles,
        loc="lower right",
        fontsize=text_cfg.legend_fontsize,
        frameon=True,
        title="Probability",
    )

    title_metric = {
        "c3d_probability_of_exceedance":
            "C3D probability of exceedance",
        "ground_load_probability_of_exceedance":
            "Ground-load probability of exceedance",
        "arrival_probability":
            "Arrival-time probability",
        "post_arrival_persistence_probability":
            "Persistence-time probability",
    }.get(field.metric, field.metric)

    ax.set_title(
        f"{title_metric} | {field.phase} | {field.subset} | "
        f"{interpolation_method.upper()}",
        fontsize=text_cfg.title_fontsize,
    )

    add_annotation(
        ax,
        _annotation_for_field(field),
        text_cfg,
    )

    # Keep the directory tree intentionally shallow for Windows MAX_PATH.
    #
    # Example:
    #   maps/idw/lambert/iso/C3D_extreme_all_FL000_200_C0p2_iso.png
    #
    outdir = (
        output_cfg.output_root
        / safe_token(
            interpolation_method
        )
        / _projection_alias(
            base_cfg
        )
        / "iso"
    )
    outdir.mkdir(
        parents=True,
        exist_ok=True,
    )

    base_path = (
        outdir
        / _compact_isoprobability_name(
            field,
            metric_cfg.metric,
        )
    )

    return _save(
        fig,
        base_path,
        output_cfg,
        dpi=text_cfg.dpi,
    )


def _severity_value(field, metric_name):
    if metric_name in {"c3d", "gl"}:
        return float(field.attrs["threshold"])

    if metric_name in {
        "arrival",
        "persistence_conditional",
        "persistence_unconditional",
    }:
        return float(field.attrs["time_threshold_h"])

    raise ValueError(metric_name)


def _intensity_group_key(field, metric_name):
    """Fields that belong in the same hazard-intensity map."""
    altitude = field.attrs.get("altitude_range", "")

    concentration = (
        float(field.attrs["threshold"])
        if field.attrs.get("threshold_units") == "kg m-3"
        else None
    )

    conditioning = field.attrs.get("conditioning", "")

    if metric_name == "c3d":
        return (
            field.phase,
            field.subset,
            altitude,
        )

    if metric_name == "gl":
        return (
            field.phase,
            field.subset,
        )

    if metric_name == "arrival":
        return (
            field.phase,
            field.subset,
            altitude,
            concentration,
        )

    return (
        field.phase,
        field.subset,
        altitude,
        concentration,
        conditioning,
    )


def group_fields_for_intensity(fields, metric_name):
    groups = {}
    for field in fields:
        groups.setdefault(
            _intensity_group_key(field, metric_name),
            [],
        ).append(field)
    return groups


def make_intensity_map(
    grouped_fields,
    metric_cfg,
    fixed_probability,
    global_basemap,
    base_cfg,
    text_cfg,
    output_cfg,
    interpolation_method="idw",
):
    """Build ordinal intensity classes at one fixed probability level."""

    if not grouped_fields:
        return []

    # Interpolate every physical-threshold probability field to the same grid.
    interpolated = {}

    reference_lon = reference_lat = None

    for field in grouped_fields:
        severity = _severity_value(
            field,
            metric_cfg.metric,
        )

        lon, lat, probability = interpolate_field(
            field,
            base_cfg,
            interpolation_method,
        )

        if reference_lon is None:
            reference_lon = lon
            reference_lat = lat

        interpolated[severity] = probability

    class_map = np.full(
        interpolated[next(iter(interpolated))].shape,
        np.nan,
        dtype=float,
    )

    # level_values are explicitly ordered from low -> high severity.
    for class_index, level in enumerate(
        metric_cfg.level_values,
        start=1,
    ):
        matching = None

        for severity, probability in interpolated.items():
            if np.isclose(float(severity), float(level)):
                matching = probability
                break

        if matching is None:
            continue

        class_map[
            matching >= fixed_probability
        ] = class_index

    first = grouped_fields[0]

    # Use the same metric-specific framing for hazard-intensity products.
    if metric_cfg.extent is not None:
        extent = tuple(
            float(value)
            for value in metric_cfg.extent
        )
    else:
        extent = determine_extent(
            reference_lon,
            reference_lat,
            base_cfg,
        )

    fig, ax = create_base_axes(
        global_basemap,
        extent,
        base_cfg,
        text_cfg,
    )

    colors = expand_colors(
        metric_cfg.colors,
        len(metric_cfg.level_values),
    )

    cmap = ListedColormap(colors)
    cmap.set_bad((1, 1, 1, 0))
    norm = BoundaryNorm(
        np.arange(
            0.5,
            len(metric_cfg.level_values) + 1.5,
            1,
        ),
        cmap.N,
    )

    xx, yy = np.meshgrid(
        reference_lon,
        reference_lat,
    )

    ax.pcolormesh(
        xx,
        yy,
        class_map,
        transform=DATA_CRS,
        cmap=cmap,
        norm=norm,
        shading="auto",
        alpha=0.45,
        zorder=5,
    )

    # Overlay each physical threshold contour at the same fixed probability.
    for class_index, level in enumerate(
        metric_cfg.level_values,
        start=1,
    ):
        probability = None

        for severity, candidate in interpolated.items():
            if np.isclose(float(severity), float(level)):
                probability = candidate
                break

        if probability is None:
            continue

        finite = probability[np.isfinite(probability)]
        if (
            finite.size
            and finite.min() <= fixed_probability <= finite.max()
        ):
            ax.contour(
                xx,
                yy,
                probability,
                levels=[fixed_probability],
                colors=[colors[class_index - 1]],
                transform=DATA_CRS,
                linewidths=1.5,
                zorder=15,
            )

    labels = (
        metric_cfg.level_labels
        if metric_cfg.level_labels
        else tuple(
            f"Class {i}"
            for i in range(1, len(colors) + 1)
        )
    )

    handles = [
        Patch(
            facecolor=color,
            edgecolor=color,
            alpha=0.45,
            label=label,
        )
        for color, label in zip(colors, labels)
    ]

    ax.legend(
        handles=handles,
        loc="lower right",
        fontsize=text_cfg.legend_fontsize,
        frameon=True,
        title=f"Hazard intensity at {fixed_probability:g}%",
    )

    title = (
        f"{metric_cfg.metric} hazard intensity | "
        f"P = {fixed_probability:g}% | "
        f"{first.phase} | {first.subset} | "
        f"{interpolation_method.upper()}"
    )
    ax.set_title(
        title,
        fontsize=text_cfg.title_fontsize,
    )

    # For AT/PT display concentration/range/conditioning at LEFT by default.
    if metric_cfg.metric in {
        "arrival",
        "persistence_conditional",
        "persistence_unconditional",
    }:
        add_annotation(
            ax,
            _annotation_for_field(first),
            text_cfg,
        )

    # Shallow Windows-safe output tree.
    #
    # Example:
    #   maps/idw/lambert/intensity/C3D_extreme_all_FL000_200_P25.png
    #
    outdir = (
        output_cfg.output_root
        / safe_token(
            interpolation_method
        )
        / _projection_alias(
            base_cfg
        )
        / "intensity"
    )
    outdir.mkdir(
        parents=True,
        exist_ok=True,
    )

    base_path = (
        outdir
        / _compact_intensity_name(
            first,
            metric_cfg.metric,
            fixed_probability,
        )
    )

    return _save(
        fig,
        base_path,
        output_cfg,
        dpi=text_cfg.dpi,
    )
