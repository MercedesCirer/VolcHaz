"""Recursive discovery of ATLAS particle outputs."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import re
from .config import AtlasPostprocessConfig, MonthGroup
DATE=re.compile(r"(?<!\d)((?:19|20)\d{6})(?!\d)")
@dataclass(frozen=True)
class AtlasSimulation:
    phase: str; run_folder: str; path: Path; date: datetime|None
    @property
    def month(self): return None if self.date is None else self.date.month

def _date(*texts):
    for text in texts:
        m=DATE.search(text)
        if m:
            try: return datetime.strptime(m.group(1),"%Y%m%d")
            except ValueError: pass
    return None

def discover_simulations(config: AtlasPostprocessConfig):
    root=config.runs_root
    if not root.is_dir(): raise FileNotFoundError(root)
    allowed=None if config.phases is None else set(config.phases)
    result={}
    for path in sorted(root.rglob("*.part.nc")):
        rel=path.relative_to(root)
        if len(rel.parts)<2: continue
        phase,run=rel.parts[0],rel.parts[1]
        if allowed is not None and phase not in allowed: continue
        result.setdefault(phase,[]).append(AtlasSimulation(phase,run,path,_date(run,path.name)))
    if not result: raise FileNotFoundError(f"No *.part.nc files below {root}")
    return result

def temporal_subsets(simulations, groups: tuple[MonthGroup,...]):
    result={"all":list(simulations)}
    for group in groups: result[group.name]=[s for s in simulations if s.month in group.months]
    return result
