"""Candidate eruption ensemble generation.

This module does not claim physical consistency. It produces candidates that
must later be paired with meteorology and evaluated by an MER model.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Iterable, Optional, Sequence
import numpy as np
import pandas as pd

from .parameter import ParameterConfig
from .distributions import sample_distribution


@dataclass
class EruptionCandidateSampler:
    parameters: Sequence[ParameterConfig]
    seed: Optional[int] = None
    candidate_prefix: str = "candidate"

    def __post_init__(self) -> None:
        self.parameters = tuple(self.parameters)
        if not self.parameters:
            raise ValueError("at least one parameter is required")
        keys = [p.key for p in self.parameters]
        columns = [p.column_name for p in self.parameters]
        if len(keys) != len(set(keys)):
            raise ValueError("parameter keys must be unique")
        if len(columns) != len(set(columns)):
            raise ValueError("output columns must be unique")

    def sample(self, number_of_candidates: int) -> pd.DataFrame:
        if number_of_candidates <= 0:
            raise ValueError("number_of_candidates must be > 0")
        seeds = np.random.SeedSequence(self.seed).spawn(len(self.parameters))
        data = {
            "candidate_id": [
                "%s_%06d" % (self.candidate_prefix, i)
                for i in range(1, number_of_candidates + 1)
            ],
            "candidate_status": ["unvalidated"] * number_of_candidates,
        }
        for config, child_seed in zip(self.parameters, seeds):
            rng = np.random.default_rng(child_seed)
            data[config.column_name] = sample_distribution(
                config, number_of_candidates, rng
            )
        return pd.DataFrame(data)


def sample_candidate_eruption_parameters(
    parameters: Iterable[ParameterConfig],
    number_of_candidates: int,
    seed: Optional[int] = None,
    candidate_prefix: str = "candidate",
) -> pd.DataFrame:
    return EruptionCandidateSampler(
        tuple(parameters), seed, candidate_prefix
    ).sample(number_of_candidates)
