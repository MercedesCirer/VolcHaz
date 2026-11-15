"""Cartographic base helpers for Stage 6 using Cartopy."""

from __future__ import annotations

import numpy as np
import geopandas as gpd
import matplotlib.pyplot as plt
import cartopy.crs as ccrs
import cartopy.feature as cfeature
from matplotlib.patches import Rectangle
from pyproj import Geod


DATA_CRS = ccrs.PlateCarree()
WGS84_GEOD = Geod(ellps="WGS84")


def read_basemap(path):
    """Read the support shapefile and normalize it to EPSG:4326."""
    if not path.is_file():
        raise FileNotFoundError(f"Basemap shapefile not found: {path}")

    gdf = gpd.read_file(path)
    if gdf.crs is None:
        raise ValueError(f"Basemap has no CRS: {path}")

    return gdf.to_crs("EPSG:4326")


def build_map_projection(base_cfg):
    """Create the Cartopy display projection selected by the user."""
    name = base_cfg.projection
    p = dict(base_cfg.projection_parameters)

    if name == "plate_carree":
        return ccrs.PlateCarree(
            central_longitude=float(p.get("central_longitude", 0.0))
        )

    if name == "mercator":
        return ccrs.Mercator(
            central_longitude=float(p.get("central_longitude", 0.0)),
            min_latitude=float(p.get("min_latitude", -80.0)),
            max_latitude=float(p.get("max_latitude", 84.0)),
        )

    if name == "lambert_conformal":
        return ccrs.LambertConformal(
            central_longitude=float(p["central_longitude"]),
            central_latitude=float(p["central_latitude"]),
            standard_parallels=tuple(float(x) for x in p["standard_parallels"]),
            false_easting=float(p.get("false_easting", 0.0)),
            false_northing=float(p.get("false_northing", 0.0)),
            cutoff=float(p.get("cutoff", 0.0)),
        )

    if name == "albers_equal_area":
        return ccrs.AlbersEqualArea(
            central_longitude=float(p["central_longitude"]),
            central_latitude=float(p["central_latitude"]),
            standard_parallels=tuple(float(x) for x in p["standard_parallels"]),
            false_easting=float(p.get("false_easting", 0.0)),
            false_northing=float(p.get("false_northing", 0.0)),
        )

    if name == "epsg":
        return ccrs.epsg(int(p["epsg_code"]))

    raise ValueError(f"Unsupported projection: {name}")


def determine_extent(lon, lat, config):
    """Return geographic extent (west, east, south, north)."""
    if config.extent is not None:
        return tuple(float(x) for x in config.extent)

    return (
        float(np.nanmin(lon) - config.padding_deg),
        float(np.nanmax(lon) + config.padding_deg),
        float(np.nanmin(lat) - config.padding_deg),
        float(np.nanmax(lat) + config.padding_deg),
    )


def _add_basemap(ax, base_gdf, extent, base_cfg):
    """Draw support polygons using user-configurable appearance."""
    west, east, south, north = extent
    clipped = base_gdf.cx[west:east, south:north]
    if clipped.empty:
        return

    feature = cfeature.ShapelyFeature(
        clipped.geometry,
        DATA_CRS,
        facecolor=base_cfg.land_facecolor,
        edgecolor=base_cfg.land_edgecolor,
        linewidth=base_cfg.land_linewidth,
    )
    ax.add_feature(feature, zorder=1)


def _add_graticule(
    ax,
    extent,
    base_cfg,
    text_cfg,
):
    """Draw the geographic graticule with labels only on map borders.

    For Lambert and Albers, Cartopy may otherwise place longitude labels
    inline across the interior of the map. x_inline/y_inline are explicitly
    disabled here.
    """
    west, east, south, north = extent
    step = base_cfg.graticule_step_deg

    meridians = np.arange(
        np.floor(west / step) * step,
        np.ceil(east / step) * step
        + step * 0.5,
        step,
    )

    parallels = np.arange(
        np.floor(south / step) * step,
        np.ceil(north / step) * step
        + step * 0.5,
        step,
    )

    gridliner = ax.gridlines(
        crs=DATA_CRS,
        draw_labels=True,
        xlocs=meridians,
        ylocs=parallels,
        linewidth=0.8,
        linestyle="--",
        alpha=0.45,
        color="0.45",
        zorder=2,
        x_inline=False,
        y_inline=False,
    )

    gridliner.top_labels = False
    gridliner.right_labels = False
    gridliner.bottom_labels = True
    gridliner.left_labels = True
    gridliner.rotate_labels = False

    gridliner.xlabel_style = {
        "size": text_cfg.graticule_fontsize,
    }
    gridliner.ylabel_style = {
        "size": text_cfg.graticule_fontsize,
    }

def _add_user_extent(ax, base_cfg):
    if not base_cfg.show_user_extent or base_cfg.user_extent is None:
        return

    west, east, south, north = base_cfg.user_extent
    ax.add_patch(
        Rectangle(
            (west, south),
            east - west,
            north - south,
            fill=False,
            edgecolor="black",
            linewidth=1.2,
            linestyle="--",
            transform=DATA_CRS,
            zorder=60,
        )
    )


def _axes_fraction_to_projected(ax, x_frac, y_frac):
    """Convert axes-fraction coordinates to coordinates of the display CRS."""
    display_xy = ax.transAxes.transform((float(x_frac), float(y_frac)))
    data_xy = ax.transData.inverted().transform(display_xy)
    return float(data_xy[0]), float(data_xy[1])


def _axes_fraction_to_lonlat(ax, x_frac, y_frac):
    """Convert an axes-fraction location to geographic longitude/latitude."""
    x_proj, y_proj = _axes_fraction_to_projected(ax, x_frac, y_frac)
    lon, lat = DATA_CRS.transform_point(x_proj, y_proj, ax.projection)
    return float(lon), float(lat)


def _axes_pixel_metrics(ax):
    bbox = ax.get_window_extent()
    width_px = float(bbox.width)
    height_px = float(bbox.height)
    return width_px, height_px, min(width_px, height_px)


def _nice_scale_length_km(target_km):
    """Choose a conventional 1/2/2.5/5 x 10^n scale length <= target."""
    target_km = float(target_km)
    if not np.isfinite(target_km) or target_km <= 0:
        return 1.0
    exponent = np.floor(np.log10(target_km))
    base = 10.0 ** exponent
    normalized = target_km / base
    candidates = np.array([1.0, 2.0, 2.5, 5.0, 10.0])
    valid = candidates[candidates <= normalized]
    return float((valid[-1] if valid.size else 1.0) * base)


def _local_true_north_unit_display(ax, lon, lat):
    """Return local true-north as a unit vector in display-pixel coordinates."""
    lat2 = min(float(lat) + 0.05, 89.9)
    p0 = ax.projection.transform_point(float(lon), float(lat), DATA_CRS)
    p1 = ax.projection.transform_point(float(lon), lat2, DATA_CRS)
    d0 = np.asarray(ax.transData.transform(p0), dtype=float)
    d1 = np.asarray(ax.transData.transform(p1), dtype=float)
    vector = d1 - d0
    norm = float(np.hypot(vector[0], vector[1]))
    if not np.isfinite(norm) or norm == 0:
        return np.array([0.0, 1.0])
    return vector / norm


def add_north_arrow(ax, extent, base_cfg):
    """Draw a dynamically sized arrow that preserves local TRUE geographic north."""
    ax.figure.canvas.draw()

    base_x, base_y = base_cfg.north_arrow_position
    lon, lat = _axes_fraction_to_lonlat(ax, base_x, base_y)
    unit = _local_true_north_unit_display(ax, lon, lat)
    width_px, height_px, short_px = _axes_pixel_metrics(ax)

    length_px = base_cfg.north_arrow_length_fraction * short_px
    dx_axes = unit[0] * length_px / width_px
    dy_axes = unit[1] * length_px / height_px
    tip_x = base_x + dx_axes
    tip_y = base_y + dy_axes

    head_px = base_cfg.north_arrow_head_fraction * short_px
    head_points = head_px * 72.0 / ax.figure.dpi

    ax.annotate(
        "",
        xy=(tip_x, tip_y),
        xytext=(base_x, base_y),
        xycoords="axes fraction",
        textcoords="axes fraction",
        arrowprops=dict(
            arrowstyle="-|>",
            color="black",
            linewidth=base_cfg.north_arrow_linewidth,
            mutation_scale=max(8.0, head_points),
            shrinkA=0,
            shrinkB=0,
        ),
        annotation_clip=False,
        zorder=150,
    )

    gap_px = base_cfg.north_arrow_label_gap_fraction * short_px
    label_x = tip_x + unit[0] * gap_px / width_px
    label_y = tip_y + unit[1] * gap_px / height_px

    font_px = base_cfg.north_arrow_font_fraction * short_px
    font_points = font_px * 72.0 / ax.figure.dpi

    ax.text(
        label_x,
        label_y,
        "N",
        transform=ax.transAxes,
        ha="center",
        va="center",
        fontsize=max(8.0, font_points),
        fontweight="bold",
        color="black",
        clip_on=False,
        zorder=151,
    )


def _visible_width_km_at_axes_y(ax, y_frac):
    """Estimate visible geodesic map width at a relative vertical position."""
    left_lon, left_lat = _axes_fraction_to_lonlat(ax, 0.02, y_frac)
    right_lon, right_lat = _axes_fraction_to_lonlat(ax, 0.98, y_frac)
    _, _, distance_m = WGS84_GEOD.inv(left_lon, left_lat, right_lon, right_lat)
    return abs(float(distance_m)) / 1000.0


def add_scale_bar(ax, extent, base_cfg):
    """Draw a dynamic geodesic scale bar with relative graphic placement."""
    ax.figure.canvas.draw()

    x0_frac, y0_frac = base_cfg.scale_bar_position
    start_lon, start_lat = _axes_fraction_to_lonlat(ax, x0_frac, y0_frac)

    if base_cfg.scale_bar_km is None:
        visible_width_km = _visible_width_km_at_axes_y(ax, y0_frac)
        target_km = visible_width_km * base_cfg.scale_bar_target_fraction
        length_km = _nice_scale_length_km(target_km)
    else:
        length_km = float(base_cfg.scale_bar_km)

    end_lon, end_lat, _ = WGS84_GEOD.fwd(
        start_lon, start_lat, 90.0, length_km * 1000.0
    )

    start_proj = ax.projection.transform_point(start_lon, start_lat, DATA_CRS)
    end_proj = ax.projection.transform_point(end_lon, end_lat, DATA_CRS)
    start_display = np.asarray(ax.transData.transform(start_proj), dtype=float)
    end_display = np.asarray(ax.transData.transform(end_proj), dtype=float)

    width_px, height_px, short_px = _axes_pixel_metrics(ax)
    end_axes = ax.transAxes.inverted().transform(end_display)
    end_x_frac, end_y_frac = float(end_axes[0]), float(end_axes[1])

    bar_vector = end_display - start_display
    bar_norm = float(np.hypot(bar_vector[0], bar_vector[1]))
    if not np.isfinite(bar_norm) or bar_norm == 0:
        return

    bar_unit = bar_vector / bar_norm
    normal_unit = np.array([-bar_unit[1], bar_unit[0]], dtype=float)

    tick_half_px = 0.5 * base_cfg.scale_bar_tick_fraction * short_px
    tick_dx_axes = normal_unit[0] * tick_half_px / width_px
    tick_dy_axes = normal_unit[1] * tick_half_px / height_px

    ax.plot(
        [x0_frac, end_x_frac],
        [y0_frac, end_y_frac],
        transform=ax.transAxes,
        color="black",
        linewidth=3.0,
        solid_capstyle="butt",
        clip_on=False,
        zorder=140,
    )

    for x_frac, y_frac in ((x0_frac, y0_frac), (end_x_frac, end_y_frac)):
        ax.plot(
            [x_frac - tick_dx_axes, x_frac + tick_dx_axes],
            [y_frac - tick_dy_axes, y_frac + tick_dy_axes],
            transform=ax.transAxes,
            color="black",
            linewidth=1.4,
            clip_on=False,
            zorder=141,
        )

    midpoint_display = (start_display + end_display) / 2.0
    label_gap_px = base_cfg.scale_bar_label_gap_fraction * short_px
    label_display = midpoint_display + normal_unit * label_gap_px
    label_axes = ax.transAxes.inverted().transform(label_display)

    ax.text(
        float(label_axes[0]),
        float(label_axes[1]),
        f"{length_km:g} km",
        transform=ax.transAxes,
        ha="center",
        va="center",
        fontsize=10,
        fontweight="bold",
        clip_on=False,
        bbox=dict(
            boxstyle="square,pad=0.15",
            facecolor="white",
            edgecolor="none",
            alpha=0.7,
        ),
        zorder=142,
    )


def create_base_axes(base_gdf, extent, base_cfg, text_cfg):
    """Create projected GeoAxes and common cartographic decorations."""
    projection = build_map_projection(base_cfg)
    fig = plt.figure(figsize=text_cfg.figure_size)
    ax = fig.add_subplot(1, 1, 1, projection=projection)

    ax.set_facecolor(base_cfg.ocean_facecolor)

    # Extent is always interpreted as geographic lon/lat.
    ax.set_extent(extent, crs=DATA_CRS)

    _add_basemap(ax, base_gdf, extent, base_cfg)
    _add_graticule(ax, extent, base_cfg, text_cfg)
    _add_user_extent(ax, base_cfg)

    if base_cfg.north_arrow:
        add_north_arrow(ax, extent, base_cfg)

    add_scale_bar(ax, extent, base_cfg)
    return fig, ax


def add_annotation(
    ax,
    text,
    text_cfg,
):
    """Draw the descriptive threshold / AT / PT information box.

    Position priority:
        1. annotation_location == "none" -> do not draw
        2. annotation_position != None   -> custom axes-fraction position
        3. otherwise                     -> legacy left/right fallback

    Axes fractions are independent of geographic extent, projection and
    figure size:
        (0, 0) = lower-left
        (1, 1) = upper-right
    """
    if (
        not text
        or text_cfg.annotation_location == "none"
    ):
        return

    if text_cfg.annotation_position is not None:
        xy = tuple(
            float(value)
            for value in text_cfg.annotation_position
        )

        # Automatic horizontal alignment according to the chosen position.
        if xy[0] < 0.40:
            ha = "left"
        elif xy[0] > 0.60:
            ha = "right"
        else:
            ha = "center"

        va = "top"

    elif text_cfg.annotation_location == "left":
        xy = (
            0.025,
            0.975,
        )
        ha = "left"
        va = "top"

    else:
        xy = (
            0.975,
            0.975,
        )
        ha = "right"
        va = "top"

    ax.text(
        *xy,
        text,
        transform=ax.transAxes,
        ha=ha,
        va=va,
        fontsize=text_cfg.annotation_fontsize,
        bbox=dict(
            boxstyle="round,pad=0.35",
            facecolor="white",
            edgecolor="0.5",
            alpha=0.9,
        ),
        zorder=160,
    )
