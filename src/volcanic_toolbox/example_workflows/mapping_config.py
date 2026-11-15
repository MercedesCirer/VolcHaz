"""=============================================================================
STAGE 6 - PROBABILITY AND HAZARD-INTENSITY MAP CONFIGURATION
=============================================================================

This is the MAIN user-editable mapping file.

Stage 6 reads the probability NetCDF files created by Stage 5. It does NOT
recalculate probabilities and does NOT read the original ATLAS *.part.nc files.

Two map families are created:

1) ISOPROBABILITY MAPS
   -------------------
   One map for each physical threshold already present in Stage 5.

   Examples:
       C3D > 0.2 mg m-3
       GL > 10 kg m-2
       AT <= 6 h for C3D > 0.2 mg m-3
       PT >= 12 h for C3D > 2 mg m-3

   The user selects probability contours such as:
       1%, 25%, 50%
   but any values from 0 to 100 may be used.

2) HAZARD-INTENSITY MAPS
   ---------------------
   For one FIXED probability, classify each pixel according to the most severe
   physical threshold reached.

   Example for C3D at P = 25%:
       Class 1 -> P(C3D > 0.2 mg m-3) >= 25%
       Class 2 -> P(C3D > 2.0 mg m-3) >= 25%
       Class 3 -> P(C3D > 4.0 mg m-3) >= 25%

   These are ORDINAL hazard-intensity classes, not probabilities.

=============================================================================
DIRECTORY STRUCTURE
=============================================================================

Recommended project structure:

volcanic_toolbox_stage4_v2/
|
|-- data/
|   `-- basemaps/
|       `-- global/
|           |-- ne_10m_admin_0_countries.shp
|           |-- ne_10m_admin_0_countries.dbf
|           |-- ne_10m_admin_0_countries.shx
|           |-- ne_10m_admin_0_countries.prj
|           `-- ...
|
|-- workflow/
|   |-- mapping_config.py
|   `-- 18_make_probability_maps.py
|
|-- src/
|   `-- volcanic_toolbox/
|       `-- postprocessing/
|           `-- mapping/
|
`-- outputs/
    `-- <scenario>/
        `-- postprocessing/
            |-- atlas/
            `-- maps/

The shapefile may have any filename. Just update BASEMAP_SHP below.

IMPORTANT: keep ALL companion shapefile files (.shp, .dbf, .shx, .prj, etc.)
together in the same folder.

=============================================================================
"""
from pathlib import Path
import scenario_config as scenario
SCENARIO_NAME = scenario.SCENARIO_NAME
if not hasattr(scenario, 'ATLAS_AREA'):
    raise AttributeError('scenario_config.py does not define ATLAS_AREA. Stage 6 expects the same ATLAS_AREA used by the ERA5/ATLAS workflow, with order (north, west, south, east).')
ATLAS_AREA = scenario.ATLAS_AREA
from volcanic_toolbox.postprocessing.mapping import MapBaseConfig, MapMetricConfig, MapOutputConfig, MapTextConfig, ProbabilityMapConfig
SCENARIO_ROOT = Path('outputs') / SCENARIO_NAME
PROBABILITY_ROOT = SCENARIO_ROOT / 'postprocessing' / 'atlas'
MAP_OUTPUT_ROOT = SCENARIO_ROOT / 'postprocessing' / 'maps'
BASEMAP_SHP = Path('data') / 'basemaps' / 'global' / 'ne_10m_admin_0_countries.shp'
USER_MAP_EXTENT = getattr(scenario, 'MAP_EXTENT', None)
if USER_MAP_EXTENT is not None:
    if len(USER_MAP_EXTENT) != 4:
        raise ValueError('scenario_config.MAP_EXTENT must contain exactly four values in the order (west, east, south, north).')
    MAP_EXTENT = tuple((float(value) for value in USER_MAP_EXTENT))
    MAP_EXTENT_SOURCE = 'scenario_config.MAP_EXTENT'
else:
    if not hasattr(scenario, 'ATLAS_AREA'):
        raise AttributeError('scenario_config.py must define ATLAS_AREA when MAP_EXTENT is missing or None. ATLAS_AREA must use the order (north, west, south, east).')
    if len(scenario.ATLAS_AREA) != 4:
        raise ValueError('scenario_config.ATLAS_AREA must contain exactly four values in the order (north, west, south, east).')
    ATLAS_NORTH, ATLAS_WEST, ATLAS_SOUTH, ATLAS_EAST = scenario.ATLAS_AREA
    MAP_EXTENT = (float(ATLAS_WEST), float(ATLAS_EAST), float(ATLAS_SOUTH), float(ATLAS_NORTH))
    MAP_EXTENT_SOURCE = 'scenario_config.ATLAS_AREA'
MAP_WEST, MAP_EAST, MAP_SOUTH, MAP_NORTH = MAP_EXTENT
if MAP_WEST >= MAP_EAST:
    raise ValueError(f'Invalid map extent: west must be smaller than east. Received {MAP_EXTENT}.')
if MAP_SOUTH >= MAP_NORTH:
    raise ValueError(f'Invalid map extent: south must be smaller than north. Received {MAP_EXTENT}.')
print(f'[Stage 6] Map extent source: {MAP_EXTENT_SOURCE}')
print(f'[Stage 6] Map extent: W={MAP_WEST:.4f}, E={MAP_EAST:.4f}, S={MAP_SOUTH:.4f}, N={MAP_NORTH:.4f}')
BASE_CONFIG = MapBaseConfig(basemap_shapefile=BASEMAP_SHP, projection='lambert_conformal', projection_parameters={'central_longitude': -64.0, 'central_latitude': -36.0, 'standard_parallels': (-24.0, -48.0), 'cutoff': 0.0}, extent=MAP_EXTENT, padding_deg=0.0, interpolation_cellsize_deg=0.1, interpolation_methods=('idw',), idw_power=1.0, idw_k=12, idw_radius_deg=0.75, graticule_step_deg=3.0, show_user_extent=False, user_extent=(-73.0, -54.0, -39.0, -21.0), land_facecolor='#D9D9D9', land_edgecolor='0.50', land_linewidth=0.6, ocean_facecolor='white', scale_bar_km=None, scale_bar_position=(0.08, 0.08), scale_bar_target_fraction=0.18, scale_bar_tick_fraction=0.012, scale_bar_label_gap_fraction=0.018, north_arrow=True, north_arrow_position=(0.9, 0.78), north_arrow_length_fraction=0.065, north_arrow_label_gap_fraction=0.025, north_arrow_linewidth=1.2, north_arrow_head_fraction=0.03, north_arrow_font_fraction=0.03)
TEXT_CONFIG = MapTextConfig(figure_size=(10.0, 8.0), dpi=300, title_fontsize=14, label_fontsize=12, legend_fontsize=10, graticule_fontsize=11, annotation_location='left', annotation_position=None, annotation_fontsize=10)
OUTPUT_CONFIG = MapOutputConfig(output_root=MAP_OUTPUT_ROOT, output_formats=('png',), transparent_background=False)
C3D = MapMetricConfig(metric='c3d', enabled=True, isoprobability_levels_percent=(1.0, 25.0, 50.0), intensity_probability_levels_percent=(1.0, 25.0, 50.0), level_values=(2e-07, 2e-06, 4e-06), level_labels=('Class 1: $\\geq$ P for 0.2 mg m$^{-3}$', 'Class 2: $\\geq$ P for 2 mg m$^{-3}$', 'Class 3: $\\geq$ P for 4 mg m$^{-3}$'), colors=('#E1BEE7', '#CE93D8', '#AB47BC'), probability_colors=('#E1BEE7', '#CE93D8', '#AB47BC'), altitude_ranges=None, subsets=None, phases=None)
GL = MapMetricConfig(metric='gl', enabled=True, isoprobability_levels_percent=(1.0, 25.0, 50.0), intensity_probability_levels_percent=(1.0, 25.0, 50.0), level_values=(0.1, 1.0, 10.0, 100.0), level_labels=('Class 1: $\\geq$ P for 0.1 kg m$^{-2}$', 'Class 2: $\\geq$ P for 1 kg m$^{-2}$', 'Class 3: $\\geq$ P for 10 kg m$^{-2}$', 'Class 4: $\\geq$ P for 100 kg m$^{-2}$'), colors=('#A7FFEB', '#4DB6AC', '#00897B', '#004D40'), probability_colors=('#A7FFEB', '#4DB6AC', '#004D40'), subsets=None, phases=None)
AT = MapMetricConfig(metric='arrival', enabled=False, isoprobability_levels_percent=(1.0, 25.0, 50.0), intensity_probability_levels_percent=(1.0, 25.0, 50.0), level_values=(72.0, 48.0, 24.0, 18.0, 12.0, 6.0, 4.0, 2.0), level_labels=('Class 1: AT $\\leq$ 72 h', 'Class 2: AT $\\leq$ 48 h', 'Class 3: AT $\\leq$ 24 h', 'Class 4: AT $\\leq$ 18 h', 'Class 5: AT $\\leq$ 12 h', 'Class 6: AT $\\leq$ 6 h', 'Class 7: AT $\\leq$ 4 h', 'Class 8: AT $\\leq$ 2 h'), colors=('#FFF9C4', '#FFE082', '#FFB74D', '#FFA726', '#FF9100', '#F57C00', '#E65100', '#5E2200'), probability_colors=('#FFF9C4', '#FF9100', '#5E2200'), altitude_ranges=None, subsets=None, phases=None, concentration_thresholds_kg_m3=None)
PT_CONDITIONAL = MapMetricConfig(metric='persistence_conditional', enabled=False, isoprobability_levels_percent=(1.0, 25.0, 50.0), intensity_probability_levels_percent=(1.0, 25.0, 50.0), level_values=(2.0, 4.0, 6.0, 12.0, 24.0), level_labels=('Class 1: PT $\\geq$ 2 h', 'Class 2: PT $\\geq$ 4 h', 'Class 3: PT $\\geq$ 6 h', 'Class 4: PT $\\geq$ 12 h', 'Class 5: PT $\\geq$ 24 h'), colors=('#FEE8C8', '#FDBB84', '#FC8D59', '#D95F0E', '#7F2704'), probability_colors=('#FEE8C8', '#FC8D59', '#7F2704'), altitude_ranges=None, subsets=None, phases=None, concentration_thresholds_kg_m3=None, conditioning='conditional_on_arrival')
PT_UNCONDITIONAL = MapMetricConfig(metric='persistence_unconditional', enabled=False, isoprobability_levels_percent=(1.0, 25.0, 50.0), intensity_probability_levels_percent=(1.0, 25.0, 50.0), level_values=(2.0, 4.0, 6.0, 12.0, 24.0), level_labels=('Class 1: PT $\\geq$ 2 h', 'Class 2: PT $\\geq$ 4 h', 'Class 3: PT $\\geq$ 6 h', 'Class 4: PT $\\geq$ 12 h', 'Class 5: PT $\\geq$ 24 h'), colors=('#FEE8C8', '#FDBB84', '#FC8D59', '#D95F0E', '#7F2704'), probability_colors=('#FEE8C8', '#FC8D59', '#7F2704'), altitude_ranges=None, subsets=None, phases=None, concentration_thresholds_kg_m3=None, conditioning='unconditional')
MAP_CONFIG = ProbabilityMapConfig(probability_root=PROBABILITY_ROOT, base=BASE_CONFIG, text=TEXT_CONFIG, output=OUTPUT_CONFIG, metrics=(C3D, GL, AT, PT_CONDITIONAL, PT_UNCONDITIONAL), minimum_probability_to_draw_percent=0.5)
