"""VEI-related volume and mass constraints.

VEI is treated as a scenario constraint, not as an independently sampled
continuous parameter. Volume limits remain explicit because published VEI
boundaries and study-specific assumptions must be auditable.
"""

from __future__ import annotations
from dataclasses import dataclass


def volume_km3_to_mass_kg(volume_km3: float, bulk_density_kg_m3: float) -> float:
    """Convert bulk tephra volume to mass."""
    if volume_km3 <= 0:
        raise ValueError("volume_km3 must be > 0")
    if bulk_density_kg_m3 <= 0:
        raise ValueError("bulk_density_kg_m3 must be > 0")
    return float(volume_km3) * 1.0e9 * float(bulk_density_kg_m3)


@dataclass(frozen=True)
class VEIConfig:
    """VEI-dependent magnitude constraint.

    Parameters are deliberately explicit rather than silently inferred from a
    hard-coded table. This allows the user to cite and reproduce the selected
    volume convention and density.
    """

    vei: int
    minimum_volume_km3: float
    maximum_volume_km3: float
    bulk_density_kg_m3: float
    volume_basis: str = "bulk_tephra"
    source_reference: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.vei, int) or not 0 <= self.vei <= 8:
            raise ValueError("vei must be an integer between 0 and 8")
        if self.minimum_volume_km3 <= 0:
            raise ValueError("minimum_volume_km3 must be > 0")
        if self.maximum_volume_km3 <= self.minimum_volume_km3:
            raise ValueError("maximum_volume_km3 must exceed minimum")
        if self.bulk_density_kg_m3 <= 0:
            raise ValueError("bulk_density_kg_m3 must be > 0")

    @property
    def minimum_mass_kg(self) -> float:
        return volume_km3_to_mass_kg(
            self.minimum_volume_km3, self.bulk_density_kg_m3
        )

    @property
    def maximum_mass_kg(self) -> float:
        return volume_km3_to_mass_kg(
            self.maximum_volume_km3, self.bulk_density_kg_m3
        )

    def contains_mass(self, mass_kg: float) -> bool:
        return self.minimum_mass_kg <= mass_kg <= self.maximum_mass_kg

    def to_dict(self) -> dict:
        return {
            "vei": self.vei,
            "minimum_volume_km3": self.minimum_volume_km3,
            "maximum_volume_km3": self.maximum_volume_km3,
            "bulk_density_kg_m3": self.bulk_density_kg_m3,
            "minimum_mass_kg": self.minimum_mass_kg,
            "maximum_mass_kg": self.maximum_mass_kg,
            "volume_basis": self.volume_basis,
            "source_reference": self.source_reference,
        }
