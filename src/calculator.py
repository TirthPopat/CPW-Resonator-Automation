"""
calculator.py
CPW transmission-line electromagnetics: characteristic impedance, effective
permittivity, and resonator length/frequency relations, using the standard
conformal-mapping (Simons / Ghione-Naldi) closed-form formulas.

Assumptions (same as the COMSOL reference model):
  - Ground planes are wide compared to the gap (effectively infinite)
  - Conductors are lossless (PEC)
  - Zero metal thickness in the impedance formula 

All lengths are strictly in meters (SI units).
"""

from __future__ import annotations
import numpy as np
from dataclasses import dataclass
from scipy.special import ellipk
from scipy.optimize import brentq

from .constants import C0
from .materials import Substrate


# --- Dataclasses for API Returns --------------------------------------

@dataclass(frozen=True, slots=True)
class CPWCrossSection:
    """Stores the fully solved cross-sectional properties of a CPW."""
    width_m: float
    gap_m: float
    z0_ohms: float
    eps_eff: float


@dataclass(frozen=True, slots=True)
class CPWDesign:
    """Stores the complete resonator design parameters for layout synthesis."""
    width_m: float
    gap_m: float
    eps_eff: float
    resonator_length_m: float
    z0_ohms: float
    frequency_hz: float
    mode: str


# --- Core Math Functions ----------------------------------------------

def _K(k: float) -> float:
    """
    Complete elliptic integral of the first kind, K(k).
    scipy.special.ellipk takes the parameter m = k**2, not the modulus k.
    """
    return float(ellipk(k**2))


def cpw_z0_eps_eff(w_m: float, s_m: float, substrate: Substrate) -> CPWCrossSection:
    """
    Characteristic impedance and effective permittivity of a symmetric CPW
    on a finite-thickness dielectric substrate with infinite ground planes.
    """
    if w_m <= 0 or s_m <= 0 or substrate.thickness_m <= 0:
        raise ValueError("Width, gap, and substrate thickness must all be positive.")

    h_m = substrate.thickness_m
    eps_r = substrate.eps_r

    k0 = w_m / (w_m + 2 * s_m)
    k0p = np.sqrt(1 - k0**2)

    k3 = np.tanh(np.pi * w_m / (4 * h_m)) / np.tanh(np.pi * (w_m + 2 * s_m) / (4 * h_m))
    k3p = np.sqrt(1 - k3**2)

    eps_eff = 1 + (eps_r - 1) / 2 * (_K(k3) / _K(k3p)) * (_K(k0p) / _K(k0))
    z0 = (30 * np.pi / np.sqrt(eps_eff)) * (_K(k0p) / _K(k0))
    
    return CPWCrossSection(width_m=w_m, gap_m=s_m, z0_ohms=float(z0), eps_eff=float(eps_eff))


# --- Solvers ----------------------------------------------------------

def solve_s_for_target_z0(
    w_m: float,
    target_z0_ohms: float,
    substrate: Substrate,
    s_bracket_m: tuple[float, float] = (1e-6, 10e-3),
) -> CPWCrossSection:
    """
    Given a fixed center conductor width, solve for the gap that hits the target impedance.
    """
    def residual(s: float) -> float:
        return cpw_z0_eps_eff(w_m, s, substrate).z0_ohms - target_z0_ohms

    s_lo, s_hi = s_bracket_m
    if residual(s_lo) * residual(s_hi) > 0:
        raise ValueError(
            f"No solution for s in bracket {s_bracket_m} m at w={w_m} m. "
            f"Try a different width, or widen the bracket."
        )
    
    s_sol = brentq(residual, s_lo, s_hi)
    return cpw_z0_eps_eff(w_m, s_sol, substrate)


def solve_w_for_target_z0(
    s_m: float,
    target_z0_ohms: float,
    substrate: Substrate,
    w_bracket_m: tuple[float, float] = (1e-6, 10e-3),
) -> CPWCrossSection:
    """
    Given a fixed gap, solve for the center conductor width that hits the target impedance.
    """
    def residual(w: float) -> float:
        return cpw_z0_eps_eff(w, s_m, substrate).z0_ohms - target_z0_ohms

    w_lo, w_hi = w_bracket_m
    if residual(w_lo) * residual(w_hi) > 0:
        raise ValueError(
            f"No solution for w in bracket {w_bracket_m} m at s={s_m} m. "
            f"Try a different gap, or widen the bracket."
        )
        
    w_sol = brentq(residual, w_lo, w_hi)
    return cpw_z0_eps_eff(w_sol, s_m, substrate)


def z0_for_ratio(ratio_w_over_s: float, substrate: Substrate, w_ref_m: float = 5e-6) -> float:
    """
    Characteristic impedance implied by a fixed w/s ratio, in the thin-trace limit.
    Useful as a quick design check before calling the exact solvers.
    """
    s_ref_m = w_ref_m / ratio_w_over_s
    return cpw_z0_eps_eff(w_ref_m, s_ref_m, substrate).z0_ohms


# --- Wave Kinematics --------------------------------------------------

def phase_velocity(eps_eff: float) -> float:
    """Phase velocity on the line in m/s."""
    return C0 / np.sqrt(eps_eff)


def guided_wavelength(f0_hz: float, eps_eff: float) -> float:
    """Wavelength of the signal propagating in the CPW structure [m]."""
    return phase_velocity(eps_eff) / f0_hz


def quarter_wave_length(f0_hz: float, eps_eff: float) -> float:
    """Physical length for an open-short (lambda/4) resonator [m]."""
    return guided_wavelength(f0_hz, eps_eff) / 4.0


def half_wave_length(f0_hz: float, eps_eff: float) -> float:
    """Physical length for an open-open or short-short (lambda/2) resonator [m]."""
    return guided_wavelength(f0_hz, eps_eff) / 2.0


def resonator_length(f0_hz: float, eps_eff: float, mode: str = "quarter") -> float:
    """General dispatcher for calculating resonator length."""
    if mode == "quarter":
        return quarter_wave_length(f0_hz, eps_eff)
    elif mode == "half":
        return half_wave_length(f0_hz, eps_eff)
    raise ValueError("mode must be 'quarter' or 'half'")


def resonant_frequency(length_m: float, eps_eff: float, mode: str = "quarter") -> float:
    """Inverse of resonator_length(): resonance frequency in Hz for a physical length."""
    v = phase_velocity(eps_eff)
    if mode == "quarter":
        return v / (4.0 * length_m)
    elif mode == "half":
        return v / (2.0 * length_m)
    raise ValueError("mode must be 'quarter' or 'half'")


# --- High Level API ---------------------------------------------------

def design_cpw(
    frequency_hz: float,
    impedance_ohms: float,
    substrate: Substrate,
    width_m: float | None = None,
    gap_m: float | None = None,
    mode: str = "quarter"
) -> CPWDesign:
    """
    High-level layout generation API.
    Provide the target frequency, impedance, and substrate.
    Provide ONE layout constraint (either width_m or gap_m).
    """
    if frequency_hz <= 0:
        raise ValueError("Frequency must be greater than 0 Hz.")
    if impedance_ohms <= 0:
        raise ValueError("Target impedance must be greater than 0 Ohms.")
        
    if width_m is None and gap_m is None:
        # Default fallback to a standard w=10um trace if no constraint is given
        width_m = 10e-6
        
    if width_m is not None and gap_m is not None:
        raise ValueError("Overconstrained: specify width_m OR gap_m, not both.")
        
    # Solve for cross section
    if width_m is not None:
        cs = solve_s_for_target_z0(w_m=width_m, target_z0_ohms=impedance_ohms, substrate=substrate)
    else:
        cs = solve_w_for_target_z0(s_m=gap_m, target_z0_ohms=impedance_ohms, substrate=substrate) # type: ignore
        
    # Solve for length
    length_m = resonator_length(frequency_hz, cs.eps_eff, mode=mode)
    
    return CPWDesign(
        width_m=cs.width_m,
        gap_m=cs.gap_m,
        eps_eff=cs.eps_eff,
        resonator_length_m=length_m,
        z0_ohms=cs.z0_ohms,
        frequency_hz=frequency_hz,
        mode=mode
    )