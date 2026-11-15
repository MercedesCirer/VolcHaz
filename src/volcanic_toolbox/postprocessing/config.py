"""Configuration objects for ATLAS Stage 5 postprocessing."""
from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path

@dataclass(frozen=True)
class AltitudeRange:
    """Named inclusive altitude interval in metres above sea level."""
    name: str
    minimum_m: float
    maximum_m: float
    def __post_init__(self):
        if not self.name.strip(): raise ValueError("Altitude-range name cannot be empty")
        if self.maximum_m <= self.minimum_m: raise ValueError("maximum_m must exceed minimum_m")

@dataclass(frozen=True)
class MonthGroup:
    """Optional temporal subset selected from dates in run-folder/file names."""
    name: str
    months: tuple[int, ...]
    def __post_init__(self):
        if not self.months or any(m < 1 or m > 12 for m in self.months):
            raise ValueError("months must contain values from 1 to 12")

@dataclass(frozen=True)
class PointExtractionConfig:
    """Point extraction: nearest or IDW over the probability grid."""
    method: str = "nearest"
    idw_k: int = 4
    idw_power: float = 1.0
    idw_radius_deg: float | None = None
    def __post_init__(self):
        method=self.method.lower().strip(); object.__setattr__(self,"method",method)
        if method not in {"nearest","idw"}: raise ValueError("method must be nearest or idw")
        if self.idw_k <= 0 or self.idw_power <= 0: raise ValueError("IDW parameters must be positive")

@dataclass(frozen=True)
class AtlasPostprocessConfig:
    """Complete Stage 5 configuration.

    runs_root: recursively searched for *.part.nc.
    output_root: postprocessing output directory.
    phases: first-level run folders; None discovers all.
    thresholds: C3D in kg/m3 and GL in kg/m2.
    vertical operators: maximum or mean.
    dt_hours: hours represented by one output time index.
    point_table: optional CSV with point_id, latitude, longitude.
    inline_points: optional (id, lat, lon) tuples.
    """
    runs_root: Path
    output_root: Path
    phases: tuple[str,...] | None = None
    c3d_thresholds_kg_m3: tuple[float,...] = (0.2e-6,2e-6,4e-6)
    gl_thresholds_kg_m2: tuple[float,...] = (0.1,1.0,10.0,100.0)
    altitude_ranges: tuple[AltitudeRange,...] = (
        AltitudeRange("FL000_200", 0.0, 6096.0),
        AltitudeRange("FL200_350", 6096.0, 10668.0),
    )
    c3d_exceedance_vertical_operator: str = "maximum"
    temporal_vertical_operator: str = "mean"
    arrival_hours: tuple[float,...] = (2,4,6,12,18,24,48,72)
    persistence_hours: tuple[float,...] = (1,2,4,6,12,24,48,72)
    dt_hours: float = 1.0
    persistence_outputs: tuple[str,...] = ("conditional","unconditional")
    month_groups: tuple[MonthGroup,...] = ()
    point_table: Path | None = None
    inline_points: tuple[tuple[str,float,float],...] = ()
    point_extraction: PointExtractionConfig = field(default_factory=PointExtractionConfig)
    create_point_curves: bool = True
    probability_comparison: str = ">"
    skip_invalid_files: bool = True
    def __post_init__(self):
        object.__setattr__(self,"runs_root",Path(self.runs_root)); object.__setattr__(self,"output_root",Path(self.output_root))
        if self.point_table is not None: object.__setattr__(self,"point_table",Path(self.point_table))
        for field_name in ("c3d_exceedance_vertical_operator","temporal_vertical_operator"):
            value=getattr(self,field_name).lower().strip(); object.__setattr__(self,field_name,value)
            if value not in {"maximum","mean"}: raise ValueError(f"{field_name} must be maximum or mean")
        if self.dt_hours <= 0: raise ValueError("dt_hours must be positive")
        if self.probability_comparison not in {">",">="}: raise ValueError("comparison must be > or >=")
