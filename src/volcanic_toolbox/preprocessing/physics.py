"""Mass eruption rate and mass-balance calculations."""

from __future__ import annotations
from dataclasses import dataclass
import numpy as np


@dataclass(frozen=True)
class MERConfig:
    vent_elevation_m: float
    alpha: float = 0.1
    beta: float = 0.5
    source_temperature_k: float = 1200.0
    source_heat_capacity_j_kg_k: float = 1250.0
    z1: float = 2.8

    def __post_init__(self):
        if self.vent_elevation_m < 0:
            raise ValueError("vent_elevation_m must be >= 0")
        if self.alpha <= 0 or self.beta <= 0:
            raise ValueError("alpha and beta must be > 0")


def pressure_from_height(height_m: float) -> float:
    R_d, g = 287.0, 9.81
    if height_m <= 11000:
        T = 288.15 - 0.0065 * height_m
        return 101325 * (T / 288.15) ** (-g / (-0.0065 * R_d))
    if height_m <= 20000:
        T = 216.65
        return 22632 * np.exp(-g * (height_m - 11000) / (R_d * T))
    T = 216.65 + 0.002 * (height_m - 20000)
    return 5474.89 * (T / 216.65) ** (-g / (0.002 * R_d))


def temperature_from_height(height_m: float) -> float:
    if height_m <= 11000:
        return 288.15 - 0.0065 * height_m
    if height_m <= 20000:
        return 216.65
    return 216.65 + 0.002 * (height_m - 20000)


def calculate_mer_degruyter_bonadonna(
    plume_height_m: float,
    wind_speed_m_s: float,
    vent_elevation_m: float,
    config: MERConfig | None = None,
    height_reference: str = "asl",
) -> float:
    """Calculate MER from plume height and wind speed.

    Parameters
    ----------
    plume_height_m
        Plume height supplied by the scenario table.
    wind_speed_m_s
        Representative wind speed in m/s.
    vent_elevation_m
        Vent elevation above sea level in metres.
    config
        Optional MER configuration.
    height_reference
        Vertical reference used by ``plume_height_m``:

        - ``"asl"``: plume-top altitude above sea level.
        - ``"above_vent"``: plume height above the eruptive vent/crater.

    Notes
    -----
    The Degruyter-Bonadonna scaling uses plume height above the vent (H).
    Therefore, when the scenario already supplies height above the vent,
    the value is used directly. The vent elevation is only subtracted when
    the supplied value is an absolute plume-top altitude above sea level.
    """
    cfg = config or MERConfig(vent_elevation_m=vent_elevation_m)

    reference = str(height_reference).strip().lower()

    if reference == "asl":
        H = float(plume_height_m) - float(vent_elevation_m)
    elif reference == "above_vent":
        H = float(plume_height_m)
    else:
        raise ValueError(
            "height_reference must be 'asl' or 'above_vent'"
        )

    if H <= 0:
        raise ValueError("plume height above vent must be > 0")
    if wind_speed_m_s < 0:
        raise ValueError("wind speed cannot be negative")

    g, R_d, C_d = 9.81, 287.0, 1004.0
    theta_a0 = temperature_from_height(vent_elevation_m)
    P0 = pressure_from_height(vent_elevation_m)
    rho_a0 = P0 / (R_d * theta_a0)
    gprime = g * (
        cfg.source_heat_capacity_j_kg_k * cfg.source_temperature_k
        - C_d * theta_a0
    ) / (C_d * theta_a0)

    H1, H2 = 12000.0, 20000.0
    grads = (-6.5e-3, 0.0, 2.0e-3)
    G = [g**2 / (C_d * theta_a0) * (1 + (C_d / g) * grad)
         for grad in grads]
    if H <= H1:
        Gbar = G[0]
    elif H <= H2:
        Gbar = (G[0] * H1 + G[1] * (H - H1)) / H
    else:
        Gbar = (G[0] * H1 + G[1] * (H2-H1) + G[2]*(H-H2)) / H
    if Gbar <= 0:
        raise ValueError("non-positive atmospheric stability term")
    Nbar = np.sqrt(Gbar)

    mer = (
        np.pi * rho_a0 / gprime
        * (
            (2 ** 2.5) * cfg.alpha**2 * Nbar**3 / cfg.z1**4 * H**4
            + (cfg.beta**2 * Nbar**2 * float(wind_speed_m_s) / 6.0) * H**3
        )
    )
    if not np.isfinite(mer) or mer <= 0:
        raise ValueError("invalid MER")
    return float(mer)


def mass_from_mer_duration(mer_kg_s: float, duration_h: float) -> float:
    if mer_kg_s <= 0 or duration_h <= 0:
        raise ValueError("MER and duration must be > 0")
    return float(mer_kg_s) * float(duration_h) * 3600.0
