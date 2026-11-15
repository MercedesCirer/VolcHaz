"""Configuration dataclasses for Stage 6 probability mapping."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class MapBaseConfig:
    """Base-map and interpolation settings.

    Parameters
    ----------
    basemap_shapefile:
        Path to a polygon shapefile used as geographic support. A global
        countries shapefile is recommended.

    extent:
        Optional map extent as:
            (west, east, south, north)
        in geographic degrees. If None, Stage 6 uses the probability-grid
        extent plus ``padding_deg``.

    padding_deg:
        Padding added around the probability grid when extent=None.

    interpolation_cellsize_deg:
        Cell size of the display/interpolation grid in geographic degrees.

    interpolation_methods:
        One or more interpolation methods. Allowed values:
            "idw"
            "linear"
            "nearest"

        Example:
            ("idw",)
        or:
            ("idw", "linear", "nearest")

        When several methods are requested, Stage 6 creates a separate output
        tree for each method so the maps can be compared directly.

    idw_power:
        Power used by inverse-distance weighting:
            weight = 1 / distance**idw_power
        The original mapping scripts used 1.0.

    idw_k:
        Maximum number of nearest neighbours used by IDW.
        The original mapping scripts used 12.

    idw_radius_deg:
        Maximum search radius in geographic degrees.
        The original mapping scripts used 0.75 degrees.
        If no valid neighbour exists inside this radius, the output cell is NaN.

    graticule_step_deg:
        Spacing of longitude/latitude grid labels in degrees.

    show_user_extent:
        If True and user_extent is not None, draw the requested user-domain
        rectangle on top of the map.

    user_extent:
        Optional rectangle:
            (west, east, south, north)

    scale_bar_km:
        Length of the scale bar.

    north_arrow:
        Draw north arrow when True.
    """

    basemap_shapefile: Path
    projection: str = "plate_carree"
    projection_parameters: dict[str, Any] = field(default_factory=dict)
    extent: tuple[float, float, float, float] | None = None
    padding_deg: float = 1.0
    interpolation_cellsize_deg: float = 0.10
    interpolation_methods: tuple[str, ...] = ("idw",)
    idw_power: float = 1.0
    idw_k: int = 12
    idw_radius_deg: float = 0.75
    graticule_step_deg: float = 3.0

    # BASEMAP APPEARANCE
    land_facecolor: str = "#D9D9D9"
    land_edgecolor: str = "0.50"
    land_linewidth: float = 0.6
    ocean_facecolor: str = "white"

    # OPTIONAL USER DOMAIN
    show_user_extent: bool = False
    user_extent: tuple[float, float, float, float] | None = None

    # DYNAMIC SCALE BAR
    # None => auto-select a conventional geodesic length.
    scale_bar_km: float | None = None
    scale_bar_position: tuple[float, float] = (0.08, 0.08)
    scale_bar_target_fraction: float = 0.18
    scale_bar_tick_fraction: float = 0.012
    scale_bar_label_gap_fraction: float = 0.018

    # DYNAMIC TRUE-NORTH ARROW
    north_arrow: bool = True
    north_arrow_position: tuple[float, float] = (0.90, 0.78)
    north_arrow_length_fraction: float = 0.085
    north_arrow_label_gap_fraction: float = 0.025
    north_arrow_linewidth: float = 2.0
    north_arrow_head_fraction: float = 0.030
    north_arrow_font_fraction: float = 0.030

    def __post_init__(self):
        allowed_projections = {
            "plate_carree",
            "mercator",
            "lambert_conformal",
            "albers_equal_area",
            "epsg",
        }
        if self.projection not in allowed_projections:
            raise ValueError(
                f"Unsupported projection {self.projection!r}. "
                f"Allowed: {sorted(allowed_projections)}"
            )

        if self.projection == "epsg" and "epsg_code" not in self.projection_parameters:
            raise ValueError(
                "projection='epsg' requires "
                "projection_parameters={'epsg_code': ...}"
            )

        if self.projection in {"lambert_conformal", "albers_equal_area"}:
            required = {
                "central_longitude",
                "central_latitude",
                "standard_parallels",
            }
            missing = required - set(self.projection_parameters)
            if missing:
                raise ValueError(
                    f"{self.projection} missing projection parameters: "
                    f"{sorted(missing)}"
                )
            if len(self.projection_parameters["standard_parallels"]) != 2:
                raise ValueError(
                    "standard_parallels must contain exactly two values"
                )

        if self.interpolation_cellsize_deg <= 0:
            raise ValueError("interpolation_cellsize_deg must be > 0")
        if not self.interpolation_methods:
            raise ValueError("interpolation_methods cannot be empty")

        allowed_methods = {"idw", "linear", "nearest"}
        unknown_methods = set(self.interpolation_methods) - allowed_methods
        if unknown_methods:
            raise ValueError(
                "interpolation_methods contains unsupported value(s): "
                f"{sorted(unknown_methods)}. "
                f"Allowed: {sorted(allowed_methods)}"
            )

        if len(set(self.interpolation_methods)) != len(self.interpolation_methods):
            raise ValueError("interpolation_methods cannot contain duplicates")

        if self.idw_power <= 0:
            raise ValueError("idw_power must be > 0")

        if self.idw_k <= 0:
            raise ValueError("idw_k must be > 0")

        if self.idw_radius_deg <= 0:
            raise ValueError("idw_radius_deg must be > 0")
        if self.graticule_step_deg <= 0:
            raise ValueError("graticule_step_deg must be > 0")

        if self.land_linewidth < 0:
            raise ValueError("land_linewidth must be >= 0")

        if self.scale_bar_km is not None and self.scale_bar_km <= 0:
            raise ValueError("scale_bar_km must be > 0 or None")

        for name, position in (
            ("scale_bar_position", self.scale_bar_position),
            ("north_arrow_position", self.north_arrow_position),
        ):
            if len(position) != 2:
                raise ValueError(f"{name} must contain exactly two values")
            if not all(0.0 <= float(v) <= 1.0 for v in position):
                raise ValueError(f"{name} values must be between 0 and 1")

        for name, value in (
            ("scale_bar_target_fraction", self.scale_bar_target_fraction),
            ("scale_bar_tick_fraction", self.scale_bar_tick_fraction),
            ("scale_bar_label_gap_fraction", self.scale_bar_label_gap_fraction),
            ("north_arrow_length_fraction", self.north_arrow_length_fraction),
            ("north_arrow_label_gap_fraction", self.north_arrow_label_gap_fraction),
            ("north_arrow_head_fraction", self.north_arrow_head_fraction),
            ("north_arrow_font_fraction", self.north_arrow_font_fraction),
        ):
            if value <= 0:
                raise ValueError(f"{name} must be > 0")

        if self.scale_bar_target_fraction >= 0.8:
            raise ValueError("scale_bar_target_fraction must be < 0.8")

        if self.north_arrow_linewidth <= 0:
            raise ValueError("north_arrow_linewidth must be > 0")

        for value, name in (
            (self.extent, "extent"),
            (self.user_extent, "user_extent"),
        ):
            if value is not None and len(value) != 4:
                raise ValueError(
                    f"{name} must be (west, east, south, north)"
                )


@dataclass(frozen=True)
class MapTextConfig:
    """Text/layout settings."""

    figure_size: tuple[float, float] = (10.0, 8.0)
    dpi: int = 300
    title_fontsize: float = 14.0
    label_fontsize: float = 12.0
    legend_fontsize: float = 10.0
    graticule_fontsize: float = 11.0

    # -------------------------------------------------------------------------
    # DESCRIPTIVE ANNOTATION BOX
    # -------------------------------------------------------------------------
    #
    # annotation_location controls the fallback behavior when
    # annotation_position is None.
    #
    # Allowed:
    #     "left"
    #     "right"
    #     "none"
    #
    annotation_location: str = "left"

    # Optional custom position in axes fractions:
    #
    #     (0, 0) = lower-left
    #     (1, 1) = upper-right
    #
    # If not None, this has priority over annotation_location.
    #
    annotation_position: tuple[float, float] | None = None

    annotation_fontsize: float = 10.0

    def __post_init__(self):
        if self.annotation_location not in {"left", "right", "none"}:
            raise ValueError(
                "annotation_location must be 'left', 'right' or 'none'"
            )

        if self.annotation_position is not None:
            if len(self.annotation_position) != 2:
                raise ValueError(
                    "annotation_position must contain exactly two values"
                )

            if not all(
                0.0 <= float(value) <= 1.0
                for value in self.annotation_position
            ):
                raise ValueError(
                    "annotation_position values must be between 0 and 1"
                )


@dataclass(frozen=True)
class MapOutputConfig:
    """Output settings. Supported formats: png, svg, pdf, jpg."""

    output_root: Path
    output_formats: tuple[str, ...] = ("png",)
    transparent_background: bool = False

    def __post_init__(self):
        allowed = {"png", "svg", "pdf", "jpg"}
        formats = tuple(str(x).lower().lstrip(".") for x in self.output_formats)
        if not formats:
            raise ValueError("output_formats cannot be empty")
        unknown = set(formats) - allowed
        if unknown:
            raise ValueError(
                f"Unsupported output format(s): {sorted(unknown)}. "
                f"Allowed: {sorted(allowed)}"
            )
        if len(set(formats)) != len(formats):
            raise ValueError("output_formats cannot contain duplicates")
        object.__setattr__(self, "output_formats", formats)


@dataclass(frozen=True)
class MapMetricConfig:
    """Configuration for one hazard metric.

    metric:
        One of:
            "c3d"
            "gl"
            "arrival"
            "persistence_conditional"
            "persistence_unconditional"

    enabled:
        Enable or disable this metric.

    isoprobability_levels_percent:
        Probability levels drawn on threshold-specific maps.
        Example: (1, 25, 50).

    intensity_probability_levels_percent:
        Fixed probability levels for ordinal hazard-intensity maps.
        Example: (1, 25, 50) creates one hazard-intensity map for each.

    level_values:
        Physical severity thresholds used to build the ordinal class map.

        C3D:
            kg m-3, increasing severity.
        GL:
            kg m-2, increasing severity.
        Arrival:
            hours ordered from LEAST severe to MOST severe, so normally:
            (72, 48, 24, 18, 12, 6, 4, 2).
        Persistence:
            hours ordered from LEAST severe to MOST severe, e.g.
            (2, 4, 6, 12, 24).

    level_labels:
        User-visible labels corresponding one-to-one with level_values.
        These labels are used in legends, so the user can rename the curves
        without changing the underlying numerical threshold.

    colors:
        One color per ordinal hazard class. The supplied defaults in the
        example reproduce the palettes used in the previous scripts.

    probability_colors:
        Colors used for the probability categories in isoprobability maps.
        If fewer than the number of probability levels, the last color is
        repeated.

    altitude_ranges:
        Optional names such as ("FL000_200",). None means all available ranges.

    subsets:
        Optional Stage 5 subsets/seasons such as ("all", "dry", "wet").
        None means all.

    phases:
        Optional phases. None means all discovered phases.

    concentration_thresholds_kg_m3:
        Optional filter for C3D concentration thresholds, principally for
        arrival and persistence maps.

    conditioning:
        Only used for persistence:
            "conditional_on_arrival"
            "unconditional"

    extent:
        Optional metric-specific map extent:
            (west, east, south, north)

        If None, Stage 6 falls back to MapBaseConfig.extent. If that is also
        None, the probability-grid extent plus padding_deg is used.
    """

    metric: str
    enabled: bool = True
    isoprobability_levels_percent: tuple[float, ...] = (1.0, 25.0, 50.0)
    intensity_probability_levels_percent: tuple[float, ...] = (
        1.0,
        25.0,
        50.0,
    )
    level_values: tuple[float, ...] = ()
    level_labels: tuple[str, ...] = ()
    colors: tuple[str, ...] = ()
    probability_colors: tuple[str, ...] = (
        "#fee8c8",
        "#fdbb84",
        "#d95f0e",
    )
    altitude_ranges: tuple[str, ...] | None = None
    subsets: tuple[str, ...] | None = None
    phases: tuple[str, ...] | None = None
    concentration_thresholds_kg_m3: tuple[float, ...] | None = None
    conditioning: str | None = None

    # Optional map extent specific to THIS metric:
    #
    #     (west, east, south, north)
    #
    # Priority used by Stage 6:
    #
    #     metric extent
    #         -> BASE_CONFIG.extent
    #         -> probability-grid extent + padding
    #
    # None keeps the general BASE_CONFIG behavior.
    extent: tuple[float, float, float, float] | None = None

    def __post_init__(self):
        allowed = {
            "c3d",
            "gl",
            "arrival",
            "persistence_conditional",
            "persistence_unconditional",
        }
        if self.metric not in allowed:
            raise ValueError(
                f"Unknown metric {self.metric!r}; expected one of {sorted(allowed)}"
            )
        if self.level_labels and len(self.level_labels) != len(self.level_values):
            raise ValueError(
                f"{self.metric}: level_labels must match level_values"
            )
        if self.colors and len(self.colors) != len(self.level_values):
            raise ValueError(
                f"{self.metric}: colors must match level_values"
            )
        for p in (
            *self.isoprobability_levels_percent,
            *self.intensity_probability_levels_percent,
        ):
            if not (0 <= p <= 100):
                raise ValueError("Probability levels must be between 0 and 100")

        if self.extent is not None:
            if len(self.extent) != 4:
                raise ValueError(
                    f"{self.metric}: extent must contain exactly four values "
                    "(west, east, south, north)"
                )

            west, east, south, north = (
                float(value)
                for value in self.extent
            )

            if west >= east:
                raise ValueError(
                    f"{self.metric}: extent requires west < east"
                )

            if south >= north:
                raise ValueError(
                    f"{self.metric}: extent requires south < north"
                )


@dataclass(frozen=True)
class ProbabilityMapConfig:
    """Top-level Stage 6 configuration."""

    probability_root: Path
    base: MapBaseConfig
    text: MapTextConfig
    output: MapOutputConfig
    metrics: tuple[MapMetricConfig, ...]
    minimum_probability_to_draw_percent: float | None = 0.5
