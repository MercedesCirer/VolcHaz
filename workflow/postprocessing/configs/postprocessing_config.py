# HOW TO EDIT THIS FILE (NO PROGRAMMING REQUIRED)
# - The text after # explains a setting and is not executed.
# - Change only the value to the right of = or :; keep the name on the left.
# - A dictionary {...} is just a named group of settings, not a function.
# - Keep the quotes around text, commas between entries, and opening/closing brackets.
# - Write True or False exactly as shown. None means automatic/not specified.
# - (2010, 2020) is a pair; [ ... ] is a list of repeated entries.
# - Example: change 'SCENARIO_NAME': 'lascar_tmy' to 'SCENARIO_NAME': 'my_case'.
# - Do not change units without converting the corresponding numerical values.
# - After scientific changes, rerun the steps that generate the affected data.
# - Run workflow/run.py --check to validate the three configs and their consistency.
#
# =============================================================================
# POSTPROCESSING CONFIGURATION
# =============================================================================
# Edit data only: no imports, functions, or class instances.
# Scenario identity and phase names are inherited from preprocessing.



# =============================================================================
# 01. PROBABILITIES, POINT EXTRACTION, AND HAZARD INDICES
# =============================================================================
# Concentration: kg/m³; ground load: kg/m²; altitude: metres above sea level; time: h.
# Probabilities are percentages; hazard indices are ordinal, not joint probabilities.
# Multiphase weights must be justified for the scientific application.

# Probability, altitude, time, and point-analysis settings. Paths and phase names normally
# follow the selected preprocessing scenario.
ATLAS_POSTPROCESS_CONFIG = {
    # Airborne concentration exceedance thresholds in kg/m³; 2e-6 kg/m³ equals 2 mg/m³.
    # Include every concentration level used by enabled index rules.
    'c3d_thresholds_kg_m3': (2e-07, 2e-06, 4e-06),
    # Final ground-load exceedance thresholds in kg/m². Include every load level used by
    # enabled index rules.
    'gl_thresholds_kg_m2': (0.1, 1.0, 10.0, 100.0),
    # Probability configuration: a list of named inclusive altitude intervals. Map
    # configuration: None includes all intervals, or specify interval names to filter.
    'altitude_ranges': [
        # Entry 1: edit the named values within this block.
        {
            # Identifier of this altitude interval; descriptive labels are allowed and are
            # used in result fields and map filters.
            'name': 'FL000_200',
            # Inclusive lower altitude in metres above sea level.
            'minimum_m': 0.0,
            # Inclusive upper altitude in metres above sea level; greater than minimum_m.
            'maximum_m': 6096.0,
        },
        # Entry 2: edit the named values within this block.
        {
            # Identifier of this altitude interval; descriptive labels are allowed and are
            # used in result fields and map filters.
            'name': 'FL200_350',
            # Inclusive lower altitude in metres above sea level.
            'minimum_m': 6096.0,
            # Inclusive upper altitude in metres above sea level; greater than minimum_m.
            'maximum_m': 10668.0,
        },
        # Entry 3: edit the named values within this block.
        {
            # Identifier of this altitude interval; descriptive labels are allowed and are
            # used in result fields and map filters.
            'name': 'FL350_500',
            # Inclusive lower altitude in metres above sea level.
            'minimum_m': 10668.0,
            # Inclusive upper altitude in metres above sea level; greater than minimum_m.
            'maximum_m': 15240.0,
        },
    ],
    # "maximum" uses the highest concentration within the altitude interval; "mean" uses its
    # vertical mean when determining exceedance.
    'c3d_exceedance_vertical_operator': 'maximum',
    # "maximum" or "mean" vertical reduction used for arrival and persistence calculations;
    # may differ from the concentration-exceedance operator.
    'temporal_vertical_operator': 'mean',
    # Time thresholds in hours for P(arrival time <= threshold), measured from the model time
    # origin.
    'arrival_hours': (2, 4, 6, 12, 18, 24, 48, 72),
    # Time thresholds in hours for persistence probabilities. Persistence uses the contiguous
    # exceedance period following first arrival.
    'persistence_hours': (1, 2, 4, 6, 12, 24, 48, 72),
    # Hours represented by each saved ATLAS output record. Must match the actual output
    # interval, normally processing output_frequency_h.
    'dt_hours': 1.0,
    # Requested persistence products: "conditional", "unconditional", or both.
    'persistence_outputs': ('conditional', 'unconditional'),
    # Optional named month subsets for postprocessing; months are 1-12. Configured
    # independently of preprocessing SEASONS.
    'month_groups': [
        # Entry 1: edit the named values within this block.
        {
            # Identifier for this postprocessing month subset, such as "wet" or "dry".
            'name': 'dry',
            # Month numbers included in this subset; January=1 and December=12.
            'months': (4, 5, 6, 7, 8, 9, 10),
        },
        # Entry 2: edit the named values within this block.
        {
            # Identifier for this postprocessing month subset, such as "wet" or "dry".
            'name': 'wet',
            # Month numbers included in this subset; January=1 and December=12.
            'months': (11, 12, 1, 2, 3),
        },
    ],
    # Points specified directly as (point_id, latitude, longitude) tuples. Empty () adds no
    # inline points.
    'inline_points': (),
    # Spatial method and neighborhood settings for extracting probability values at point
    # locations.
    'point_extraction': {
        # Point interpolation method: "nearest" uses the nearest grid cell; "idw" uses
        # inverse-distance weighting.
        'method': 'nearest',
        # Maximum number of neighboring cells used for IDW; positive integer.
        'idw_k': 4,
        # Positive inverse-distance weighting exponent: weight is proportional to
        # 1/distance**power.
        'idw_power': 1.0,
        # Maximum IDW neighborhood radius in degrees; positive. Point extraction may use None
        # to omit a radius limit.
        'idw_radius_deg': None,
    },
    # True generates point hazard-curve products when points are available; False omits
    # automatic curve generation in step 01.
    'create_point_curves': False,
    # Threshold comparison: ">" is strict exceedance, ">=" includes exact equality.
    'probability_comparison': '>',
    # True records structurally invalid model outputs and continues with valid files; False
    # stops at the first invalid file.
    'skip_invalid_files': True,
    # Optional CSV path with point_id, latitude, and longitude columns. None disables CSV
    # points; inline_points can still be used.
    'point_table': 'workflow/atlas_points.csv',
}

# Probability cutoff (0-100%) used to classify a hazard-index level. Distinct from the
# physical concentration or ground-load thresholds.
PROBABILITY_CUTOFF_PERCENT = 25.0

# Ordinal hazard-index classification and phase-combination settings; these products are not
# joint probabilities.
ATLAS_INDEX_CONFIG = {
    # True includes this metric/product; False skips it while retaining its settings.
    'enabled': True,
    # List of metric-specific ordinal index rules. Each enabled metric should occur once.
    'rules': [
        # Entry 1: edit the named values within this block.
        {
            # Metric identifier: c3d, gl, arrival, persistence_conditional, or
            # persistence_unconditional, depending on the product.
            'metric': 'c3d',
            # Index severity levels in metric units, ordered least to most severe. Arrival
            # levels decrease; concentration, load, and persistence levels increase.
            'levels': (2e-07, 2e-06, 4e-06),
            # True includes this metric/product; False skips it while retaining its settings.
            'enabled': True,
        },
        # Entry 2: edit the named values within this block.
        {
            # Metric identifier: c3d, gl, arrival, persistence_conditional, or
            # persistence_unconditional, depending on the product.
            'metric': 'gl',
            # Index severity levels in metric units, ordered least to most severe. Arrival
            # levels decrease; concentration, load, and persistence levels increase.
            'levels': (0.1, 1.0, 10.0, 100.0),
            # True includes this metric/product; False skips it while retaining its settings.
            'enabled': True,
        },
        # Entry 3: edit the named values within this block.
        {
            # Metric identifier: c3d, gl, arrival, persistence_conditional, or
            # persistence_unconditional, depending on the product.
            'metric': 'arrival',
            # Index severity levels in metric units, ordered least to most severe. Arrival
            # levels decrease; concentration, load, and persistence levels increase.
            'levels': (72, 48, 24, 18, 12, 6, 4, 2),
            # True includes this metric/product; False skips it while retaining its settings.
            'enabled': True,
        },
        # Entry 4: edit the named values within this block.
        {
            # Metric identifier: c3d, gl, arrival, persistence_conditional, or
            # persistence_unconditional, depending on the product.
            'metric': 'persistence_conditional',
            # Index severity levels in metric units, ordered least to most severe. Arrival
            # levels decrease; concentration, load, and persistence levels increase.
            'levels': (1, 2, 4, 6, 12, 24, 48, 72),
            # True includes this metric/product; False skips it while retaining its settings.
            'enabled': True,
        },
        # Entry 5: edit the named values within this block.
        {
            # Metric identifier: c3d, gl, arrival, persistence_conditional, or
            # persistence_unconditional, depending on the product.
            'metric': 'persistence_unconditional',
            # Index severity levels in metric units, ordered least to most severe. Arrival
            # levels decrease; concentration, load, and persistence levels increase.
            'levels': (1, 2, 4, 6, 12, 24, 48, 72),
            # True includes this metric/product; False skips it while retaining its settings.
            'enabled': True,
        },
    ],
    # True writes an unweighted sum of phase-specific ordinal indices; not a sum of
    # concentrations or probabilities.
    'calculate_phase_sum': True,
    # True combines indices with metric-specific phase weights. Disabled automatically for a
    # single active phase.
    'calculate_weighted_index': True,
    # Relative phase weights for each enabled metric. Every active phase must have a
    # nonnegative weight, and weights for each metric must sum to 1. Renaming phases requires
    # updating explicit weights.
    'weights_by_metric': {
        # Relative phase weights for the "c3d" metric. Supply one nonnegative value for each
        # active phase; their sum must equal 1.
        'c3d': {
            # Nonnegative relative weight for phase "extreme_intensity". Within this metric,
            # all active-phase weights must sum to 1.
            'extreme_intensity': 0.35,
            # Nonnegative relative weight for phase "high_intensity". Within this metric, all
            # active-phase weights must sum to 1.
            'high_intensity': 0.45,
            # Nonnegative relative weight for phase "low_intensity". Within this metric, all
            # active-phase weights must sum to 1.
            'low_intensity': 0.2,
        },
        # Relative phase weights for the "gl" metric. Supply one nonnegative value for each
        # active phase; their sum must equal 1.
        'gl': {
            # Nonnegative relative weight for phase "extreme_intensity". Within this metric,
            # all active-phase weights must sum to 1.
            'extreme_intensity': 0.15,
            # Nonnegative relative weight for phase "high_intensity". Within this metric, all
            # active-phase weights must sum to 1.
            'high_intensity': 0.3,
            # Nonnegative relative weight for phase "low_intensity". Within this metric, all
            # active-phase weights must sum to 1.
            'low_intensity': 0.55,
        },
        # Relative phase weights for the "arrival" metric. Supply one nonnegative value for
        # each active phase; their sum must equal 1.
        'arrival': {
            # Nonnegative relative weight for phase "extreme_intensity". Within this metric,
            # all active-phase weights must sum to 1.
            'extreme_intensity': 0.45,
            # Nonnegative relative weight for phase "high_intensity". Within this metric, all
            # active-phase weights must sum to 1.
            'high_intensity': 0.4,
            # Nonnegative relative weight for phase "low_intensity". Within this metric, all
            # active-phase weights must sum to 1.
            'low_intensity': 0.15,
        },
        # Relative phase weights for the "persistence_conditional" metric. Supply one
        # nonnegative value for each active phase; their sum must equal 1.
        'persistence_conditional': {
            # Nonnegative relative weight for phase "extreme_intensity". Within this metric,
            # all active-phase weights must sum to 1.
            'extreme_intensity': 0.1,
            # Nonnegative relative weight for phase "high_intensity". Within this metric, all
            # active-phase weights must sum to 1.
            'high_intensity': 0.25,
            # Nonnegative relative weight for phase "low_intensity". Within this metric, all
            # active-phase weights must sum to 1.
            'low_intensity': 0.65,
        },
        # Relative phase weights for the "persistence_unconditional" metric. Supply one
        # nonnegative value for each active phase; their sum must equal 1.
        'persistence_unconditional': {
            # Nonnegative relative weight for phase "extreme_intensity". Within this metric,
            # all active-phase weights must sum to 1.
            'extreme_intensity': 0.1,
            # Nonnegative relative weight for phase "high_intensity". Within this metric, all
            # active-phase weights must sum to 1.
            'high_intensity': 0.25,
            # Nonnegative relative weight for phase "low_intensity". Within this metric, all
            # active-phase weights must sum to 1.
            'low_intensity': 0.65,
        },
    },
    # True counts phases with a nonzero index at each grid cell.
    'calculate_contributing_phase_count': True,
    # True records the largest phase-specific index at each grid cell.
    'calculate_maximum_phase_index': True,
    # True requires all selected phases before generating a combined product, avoiding
    # incomplete event summaries.
    'require_all_phases': True,
}

# True inherits phases and their order from preprocessing. False uses explicit postprocessing
# phase settings and therefore requires consistent phase names.
USE_SCENARIO_PHASES = True

# =============================================================================
# 02. OUTPUT INSPECTION AND 03. REPEATED POINT EXTRACTION
# =============================================================================
# These steps reuse the probability and point settings above.



# =============================================================================
# 04. POINT-HAZARD SUMMARY
# =============================================================================

# Point-summary probability tolerance in percentage points; values at or below this tolerance
# are treated as effectively zero for diagnostics.
ZERO_TOLERANCE_PERCENT = 0.0

# =============================================================================
# 05. HAZARD CURVES
# =============================================================================

# Minimum probability shown in point hazard curves, in percent.
MIN_PROBABILITY_TO_PLOT_PERCENT = 0.0

# =============================================================================
# 06. PROBABILITY MAPS
# =============================================================================

# Map projection, interpolation, geographic support, and decoration settings.
BASE_CONFIG = {
    # Map projection: plate_carree, mercator, lambert_conformal, albers_equal_area, or epsg.
    'projection': 'lambert_conformal',
    # Projection-specific values. Lambert/albers require central longitude, central latitude,
    # and two standard parallels; epsg requires epsg_code.
    'projection_parameters': {
        # Central meridian of the projection in decimal degrees.
        'central_longitude': -64.0,
        # Central latitude of the projection in decimal degrees.
        'central_latitude': -36.0,
        # Two standard parallel latitudes in decimal degrees for Lambert/albers projections.
        'standard_parallels': (-24.0, -48.0),
        # Lambert projection cutoff latitude in degrees, interpreted by the projection
        # library.
        'cutoff': 0.0,
    },
    # Geographic padding around an automatically derived map extent, in degrees.
    'padding_deg': 0.0,
    # Display/interpolation grid spacing in degrees. Smaller spacing gives finer display grids
    # but does not increase physical model resolution.
    'interpolation_cellsize_deg': 0.1,
    # Map interpolation methods, such as ("idw",), ("nearest",), or ("linear",). Multiple
    # methods generate separate products.
    'interpolation_methods': ('idw', 'linear', 'nearest'),
    # Positive inverse-distance weighting exponent: weight is proportional to
    # 1/distance**power.
    'idw_power': 1.0,
    # Maximum number of neighboring cells used for IDW; positive integer.
    'idw_k': 12,
    # Maximum IDW neighborhood radius in degrees; positive. Point extraction may use None to
    # omit a radius limit.
    'idw_radius_deg': 0.75,
    # Latitude/longitude graticule spacing in degrees; positive.
    'graticule_step_deg': 3.0,
    # True draws the user_extent rectangle over the map; False omits that overlay.
    'show_user_extent': False,
    # Optional overlay rectangle as (west, east, south, north), in decimal degrees. Distinct
    # from ATLAS_AREA ordering.
    'user_extent': (-73.0, -54.0, -39.0, -21.0),
    # Land fill color, as a named color or hexadecimal RGB string.
    'land_facecolor': '#D9D9D9',
    # Land boundary color; grayscale strings such as "0.50" are also accepted.
    'land_edgecolor': '0.50',
    # Land-boundary line width in points; nonnegative.
    'land_linewidth': 0.6,
    # Ocean/background color.
    'ocean_facecolor': 'white',
    # Scale-bar length in kilometres; None automatically chooses a suitable geodesic length.
    'scale_bar_km': None,
    # Scale-bar anchor as (x, y) fractions of the axes, each between 0 and 1.
    'scale_bar_position': (0.08, 0.08),
    # Approximate fraction of the map width targeted by the automatic scale bar; positive and
    # less than 0.8.
    'scale_bar_target_fraction': 0.18,
    # Scale-bar tick size as a positive fraction of the plotting area.
    'scale_bar_tick_fraction': 0.012,
    # Positive relative gap between the scale bar and its label.
    'scale_bar_label_gap_fraction': 0.018,
    # True draws a true-north arrow; False omits it.
    'north_arrow': True,
    # Arrow anchor as (x, y) fractions of the axes, each between 0 and 1.
    'north_arrow_position': (0.9, 0.78),
    # Arrow length as a positive fraction of the plotting area.
    'north_arrow_length_fraction': 0.065,
    # Positive relative gap between arrow and label.
    'north_arrow_label_gap_fraction': 0.025,
    # North-arrow line width in points; positive.
    'north_arrow_linewidth': 1.2,
    # Arrowhead size as a positive relative fraction.
    'north_arrow_head_fraction': 0.03,
    # North-label font scaling relative to the figure.
    'north_arrow_font_fraction': 0.03,
}

# Map figure size, resolution, and text/annotation appearance.
TEXT_CONFIG = {
    # Map figure width and height in inches, as (width, height).
    'figure_size': (10.0, 8.0),
    # Raster resolution in dots per inch; 300 is a common manuscript-export setting.
    'dpi': 300,
    # Map title font size in points.
    'title_fontsize': 14,
    # Map axis/label font size in points.
    'label_fontsize': 12,
    # Legend font size in points.
    'legend_fontsize': 10,
    # Latitude/longitude label font size in points.
    'graticule_fontsize': 11,
    # Automatic descriptive-box position: "left", "right", or "none". Used when
    # annotation_position is None.
    'annotation_location': 'left',
    # Manual annotation anchor as (x, y) axes fractions, or None for automatic placement.
    'annotation_position': None,
    # Descriptive annotation font size in points.
    'annotation_fontsize': 10,
}

# Output map file formats and background transparency.
OUTPUT_CONFIG = {
    # Map file extensions to save, such as ("png",) or ("png", "pdf").
    'output_formats': ('png',),
    # True exports a transparent background; False uses the specified background colors.
    'transparent_background': False,
}

# Airborne concentration map settings. Concentration levels are in kg/m³.
C3D = {
    # Metric identifier: c3d, gl, arrival, persistence_conditional, or
    # persistence_unconditional, depending on the product.
    'metric': 'c3d',
    # True includes this metric/product; False skips it while retaining its settings.
    'enabled': True,
    # Probability cutoffs in percent for isoprobability maps, such as (1, 25, 50).
    'isoprobability_levels_percent': (1.0, 25.0, 50.0),
    # Probability cutoffs in percent for severity/intensity maps.
    'intensity_probability_levels_percent': (1.0, 25.0, 50.0),
    # Physical or time severity levels in this metric’s units. They should correspond to
    # levels present in the computed probability products.
    'level_values': (2e-07, 2e-06, 4e-06),
    # Legend text for each severity level; keep the number and order of labels consistent with
    # level_values.
    'level_labels': ('Class 1: $\\geq$ P for 0.2 mg m$^{-3}$', 'Class 2: $\\geq$ P for 2 mg m$^{-3}$', 'Class 3: $\\geq$ P for 4 mg m$^{-3}$'),
    # Colors associated with severity categories; keep sufficient colors for the selected
    # categories.
    'colors': ('#E1BEE7', '#CE93D8', '#AB47BC'),
    # Colors for probability categories, separate from severity-category colors.
    'probability_colors': ('#E1BEE7', '#CE93D8', '#AB47BC'),
    # Probability configuration: a list of named inclusive altitude intervals. Map
    # configuration: None includes all intervals, or specify interval names to filter.
    'altitude_ranges': None,
    # None includes all generated month/time subsets; a tuple of subset names restricts maps.
    'subsets': None,
    # None includes all available/inherited phases; a tuple of names filters the product.
    # Explicit names must remain consistent after renaming phases.
    'phases': None,
    # Display extent for this metric only, in decimal degrees: (west, east, south, north).
    # Applies to both probability and intensity maps. None inherits the general map extent
    # (MAP_EXTENT or ATLAS_AREA); grid bounds plus padding are the library fallback.
    # This framing does not change ERA5, ATLAS, probability values, or interpolation grids.
    # The values below reproduce the Lascar framing in the supplied reference version;
    # adjust them for another study area. West must be < east and south must be < north.
    'extent': (-73.0, -51.0, -39.0, -21.0),
}

# Ground-load map settings. Load levels are in kg/m².
GL = {
    # Metric identifier: c3d, gl, arrival, persistence_conditional, or
    # persistence_unconditional, depending on the product.
    'metric': 'gl',
    # True includes this metric/product; False skips it while retaining its settings.
    'enabled': True,
    # Probability cutoffs in percent for isoprobability maps, such as (1, 25, 50).
    'isoprobability_levels_percent': (1.0, 25.0, 50.0),
    # Probability cutoffs in percent for severity/intensity maps.
    'intensity_probability_levels_percent': (1.0, 25.0, 50.0),
    # Physical or time severity levels in this metric’s units. They should correspond to
    # levels present in the computed probability products.
    'level_values': (0.1, 1.0, 10.0, 100.0),
    # Legend text for each severity level; keep the number and order of labels consistent with
    # level_values.
    'level_labels': ('Class 1: $\\geq$ P for 0.1 kg m$^{-2}$', 'Class 2: $\\geq$ P for 1 kg m$^{-2}$', 'Class 3: $\\geq$ P for 10 kg m$^{-2}$', 'Class 4: $\\geq$ P for 100 kg m$^{-2}$'),
    # Colors associated with severity categories; keep sufficient colors for the selected
    # categories.
    'colors': ('#A7FFEB', '#4DB6AC', '#00897B', '#004D40'),
    # Colors for probability categories, separate from severity-category colors.
    'probability_colors': ('#A7FFEB', '#4DB6AC', '#004D40'),
    # None includes all generated month/time subsets; a tuple of subset names restricts maps.
    'subsets': None,
    # None includes all available/inherited phases; a tuple of names filters the product.
    # Explicit names must remain consistent after renaming phases.
    'phases': None,
    # Display extent for this metric only, in decimal degrees: (west, east, south, north).
    # Applies to both probability and intensity maps. None inherits the general map extent
    # (MAP_EXTENT or ATLAS_AREA); grid bounds plus padding are the library fallback.
    # This framing does not change ERA5, ATLAS, probability values, or interpolation grids.
    # The values below reproduce the Lascar framing in the supplied reference version;
    # adjust them for another study area. West must be < east and south must be < north.
    'extent': (-70.5, -65.0, -26.0, -21.0),
}

# Arrival-time map settings. Time levels are in hours; shorter arrival times are more severe.
AT = {
    # Metric identifier: c3d, gl, arrival, persistence_conditional, or
    # persistence_unconditional, depending on the product.
    'metric': 'arrival',
    # True includes this metric/product; False skips it while retaining its settings.
    'enabled': True,
    # Probability cutoffs in percent for isoprobability maps, such as (1, 25, 50).
    'isoprobability_levels_percent': (1.0, 25.0, 50.0),
    # Probability cutoffs in percent for severity/intensity maps.
    'intensity_probability_levels_percent': (1.0, 25.0, 50.0),
    # Physical or time severity levels in this metric’s units. They should correspond to
    # levels present in the computed probability products.
    'level_values': (72.0, 48.0, 24.0, 18.0, 12.0, 6.0, 4.0, 2.0),
    # Legend text for each severity level; keep the number and order of labels consistent with
    # level_values.
    'level_labels': ('Class 1: AT $\\leq$ 72 h', 'Class 2: AT $\\leq$ 48 h', 'Class 3: AT $\\leq$ 24 h', 'Class 4: AT $\\leq$ 18 h', 'Class 5: AT $\\leq$ 12 h', 'Class 6: AT $\\leq$ 6 h', 'Class 7: AT $\\leq$ 4 h', 'Class 8: AT $\\leq$ 2 h'),
    # Colors associated with severity categories; keep sufficient colors for the selected
    # categories.
    'colors': ('#FFF9C4', '#FFE082', '#FFB74D', '#FFA726', '#FF9100', '#F57C00', '#E65100', '#5E2200'),
    # Colors for probability categories, separate from severity-category colors.
    'probability_colors': ('#FFF9C4', '#FF9100', '#5E2200'),
    # Probability configuration: a list of named inclusive altitude intervals. Map
    # configuration: None includes all intervals, or specify interval names to filter.
    'altitude_ranges': None,
    # None includes all generated month/time subsets; a tuple of subset names restricts maps.
    'subsets': None,
    # None includes all available/inherited phases; a tuple of names filters the product.
    # Explicit names must remain consistent after renaming phases.
    'phases': None,
    # Optional concentration-threshold filter for arrival/persistence maps; None uses all
    # available thresholds.
    'concentration_thresholds_kg_m3': None,
    # Display extent for this metric only, in decimal degrees: (west, east, south, north).
    # Applies to both probability and intensity maps. None inherits the general map extent
    # (MAP_EXTENT or ATLAS_AREA); grid bounds plus padding are the library fallback.
    # This framing does not change ERA5, ATLAS, probability values, or interpolation grids.
    # The values below reproduce the Lascar framing in the supplied reference version;
    # adjust them for another study area. West must be < east and south must be < north.
    'extent': (-73.0, -51.0, -39.0, -21.0),
}

# Conditional persistence maps, based on persistence given ash arrival.
PT_CONDITIONAL = {
    # Metric identifier: c3d, gl, arrival, persistence_conditional, or
    # persistence_unconditional, depending on the product.
    'metric': 'persistence_conditional',
    # True includes this metric/product; False skips it while retaining its settings.
    'enabled': True,
    # Probability cutoffs in percent for isoprobability maps, such as (1, 25, 50).
    'isoprobability_levels_percent': (1.0, 25.0, 50.0),
    # Probability cutoffs in percent for severity/intensity maps.
    'intensity_probability_levels_percent': (1.0, 25.0, 50.0),
    # Physical or time severity levels in this metric’s units. They should correspond to
    # levels present in the computed probability products.
    'level_values': (2.0, 4.0, 6.0, 12.0, 24.0),
    # Legend text for each severity level; keep the number and order of labels consistent with
    # level_values.
    'level_labels': ('Class 1: PT $\\geq$ 2 h', 'Class 2: PT $\\geq$ 4 h', 'Class 3: PT $\\geq$ 6 h', 'Class 4: PT $\\geq$ 12 h', 'Class 5: PT $\\geq$ 24 h'),
    # Colors associated with severity categories; keep sufficient colors for the selected
    # categories.
    'colors': ('#FEE8C8', '#FDBB84', '#FC8D59', '#D95F0E', '#7F2704'),
    # Colors for probability categories, separate from severity-category colors.
    'probability_colors': ('#FEE8C8', '#FC8D59', '#7F2704'),
    # Probability configuration: a list of named inclusive altitude intervals. Map
    # configuration: None includes all intervals, or specify interval names to filter.
    'altitude_ranges': None,
    # None includes all generated month/time subsets; a tuple of subset names restricts maps.
    'subsets': None,
    # None includes all available/inherited phases; a tuple of names filters the product.
    # Explicit names must remain consistent after renaming phases.
    'phases': None,
    # Optional concentration-threshold filter for arrival/persistence maps; None uses all
    # available thresholds.
    'concentration_thresholds_kg_m3': None,
    # Persistence conditioning label: conditional_on_arrival or unconditional, matching the
    # selected metric.
    'conditioning': 'conditional_on_arrival',
    # Display extent for this metric only, in decimal degrees: (west, east, south, north).
    # Applies to both probability and intensity maps. None inherits the general map extent
    # (MAP_EXTENT or ATLAS_AREA); grid bounds plus padding are the library fallback.
    # This framing does not change ERA5, ATLAS, probability values, or interpolation grids.
    # The values below reproduce the Lascar framing in the supplied reference version;
    # adjust them for another study area. West must be < east and south must be < north.
    'extent': (-73.0, -51.0, -39.0, -21.0),
}

# Unconditional persistence maps, including the probability that ash arrives.
PT_UNCONDITIONAL = {
    # Metric identifier: c3d, gl, arrival, persistence_conditional, or
    # persistence_unconditional, depending on the product.
    'metric': 'persistence_unconditional',
    # True includes this metric/product; False skips it while retaining its settings.
    'enabled': True,
    # Probability cutoffs in percent for isoprobability maps, such as (1, 25, 50).
    'isoprobability_levels_percent': (1.0, 25.0, 50.0),
    # Probability cutoffs in percent for severity/intensity maps.
    'intensity_probability_levels_percent': (1.0, 25.0, 50.0),
    # Physical or time severity levels in this metric’s units. They should correspond to
    # levels present in the computed probability products.
    'level_values': (2.0, 4.0, 6.0, 12.0, 24.0),
    # Legend text for each severity level; keep the number and order of labels consistent with
    # level_values.
    'level_labels': ('Class 1: PT $\\geq$ 2 h', 'Class 2: PT $\\geq$ 4 h', 'Class 3: PT $\\geq$ 6 h', 'Class 4: PT $\\geq$ 12 h', 'Class 5: PT $\\geq$ 24 h'),
    # Colors associated with severity categories; keep sufficient colors for the selected
    # categories.
    'colors': ('#FEE8C8', '#FDBB84', '#FC8D59', '#D95F0E', '#7F2704'),
    # Colors for probability categories, separate from severity-category colors.
    'probability_colors': ('#FEE8C8', '#FC8D59', '#7F2704'),
    # Probability configuration: a list of named inclusive altitude intervals. Map
    # configuration: None includes all intervals, or specify interval names to filter.
    'altitude_ranges': None,
    # None includes all generated month/time subsets; a tuple of subset names restricts maps.
    'subsets': None,
    # None includes all available/inherited phases; a tuple of names filters the product.
    # Explicit names must remain consistent after renaming phases.
    'phases': None,
    # Optional concentration-threshold filter for arrival/persistence maps; None uses all
    # available thresholds.
    'concentration_thresholds_kg_m3': None,
    # Persistence conditioning label: conditional_on_arrival or unconditional, matching the
    # selected metric.
    'conditioning': 'unconditional',
    # Display extent for this metric only, in decimal degrees: (west, east, south, north).
    # Applies to both probability and intensity maps. None inherits the general map extent
    # (MAP_EXTENT or ATLAS_AREA); grid bounds plus padding are the library fallback.
    # This framing does not change ERA5, ATLAS, probability values, or interpolation grids.
    # The values below reproduce the Lascar framing in the supplied reference version;
    # adjust them for another study area. West must be < east and south must be < north.
    'extent': (-73.0, -51.0, -39.0, -21.0),
}

# Shared map-generation controls.
MAP_CONFIG = {
    # Suppresses map values below this probability percentage; a visual cutoff, not a change
    # to the probability calculation.
    'minimum_probability_to_draw_percent': 0.5,
}

# Basemap polygon shapefile path, absolute or relative to the toolbox root. Keep .shp, .dbf,
# .shx, and .prj companions together.
BASEMAP_SHP = 'data/basemaps/global/ne_10m_admin_0_countries.shp'

