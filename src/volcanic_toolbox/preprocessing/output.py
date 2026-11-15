"""Consistent output directories for VolcHaz workflows."""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import re

def sanitize_name(value: str) -> str:
    value = re.sub(r"[^A-Za-z0-9_-]+", "_", value.strip())
    value = re.sub(r"_+", "_", value).strip("_")
    if not value:
        raise ValueError("scenario or phase name cannot be empty")
    return value

@dataclass(frozen=True)
class ScenarioOutputManager:
    """Stage-aware output paths for one named scientific scenario."""
    scenario_name: str
    root: Path | str = Path("outputs")

    def __post_init__(self):
        object.__setattr__(self,"scenario_name",sanitize_name(self.scenario_name))
        object.__setattr__(self,"root",Path(self.root))

    @property
    def scenario_dir(self): return self.root/self.scenario_name
    @property
    def preprocessing_dir(self): return self.scenario_dir/'preprocessing'
    @property
    def configuration_dir(self): return self.preprocessing_dir/'configuration'
    @property
    def eruption_dir(self): return self.preprocessing_dir/'eruption'
    @property
    def meteorology_dir(self): return self.preprocessing_dir/'meteorology'
    def phase_meteorology_dir(self, phase_name): return self.meteorology_dir/sanitize_name(phase_name)
    @property
    def scenarios_dir(self): return self.preprocessing_dir/'scenarios'
    @property
    def figures_dir(self): return self.preprocessing_dir/'figures'
    @property
    def pairplots_dir(self): return self.figures_dir/'pairplots'
    @property
    def wind_rose_dir(self): return self.figures_dir/'wind_roses'

    @property
    def processing_dir(self): return self.scenario_dir/'processing'
    @property
    def atlas_dir(self): return self.processing_dir/'atlas'
    @property
    def atlas_era5_dir(self): return self.atlas_dir/'era5'
    def atlas_phase_era5_dir(self, phase_name): return self.atlas_era5_dir/sanitize_name(phase_name)
    @property
    def atlas_manifests_dir(self): return self.atlas_dir/'manifests'
    @property
    def atlas_inputs_dir(self): return self.atlas_dir/'inputs'
    @property
    def atlas_runs_dir(self): return self.atlas_dir/'runs'
    @property
    def postprocessing_dir(self): return self.scenario_dir/'postprocessing'

    def ensure(self, phase_names=()):
        for path in (
            self.scenario_dir,self.preprocessing_dir,self.configuration_dir,
            self.eruption_dir,self.meteorology_dir,self.scenarios_dir,
            self.figures_dir,self.pairplots_dir,self.wind_rose_dir,
            self.processing_dir,self.atlas_dir,self.atlas_era5_dir,
            self.atlas_manifests_dir,self.atlas_inputs_dir,self.atlas_runs_dir,
            self.postprocessing_dir,
        ):
            path.mkdir(parents=True,exist_ok=True)
        for phase in phase_names:
            self.phase_meteorology_dir(phase).mkdir(parents=True,exist_ok=True)
            self.atlas_phase_era5_dir(phase).mkdir(parents=True,exist_ok=True)
        return self
