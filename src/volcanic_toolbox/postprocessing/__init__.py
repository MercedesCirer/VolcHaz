"""Postprocessing tools for probabilistic volcanic-hazard analyses."""

from .config import (
    AtlasPostprocessConfig,
    AltitudeRange,
    MonthGroup,
    PointExtractionConfig,
)
from .indices import (
    HazardIndexError,
    MetricIndexRule,
    MultiphaseIndexConfig,
)
from .workflow import run_atlas_postprocessing

__all__ = [
    'AtlasPostprocessConfig',
    'AltitudeRange',
    'MonthGroup',
    'PointExtractionConfig',
    'HazardIndexError',
    'MetricIndexRule',
    'MultiphaseIndexConfig',
    'run_atlas_postprocessing',
]

from .point_diagnostics import (
    point_hazard_summary,
    print_point_hazard_summary,
)
