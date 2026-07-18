"""
materials.py
Expanded material database for microwave and superconducting quantum circuits.
"""

from dataclasses import dataclass

@dataclass(frozen=True)
class Substrate:
    """
    Represents a dielectric substrate used for RF and superconducting CPW resonators.
    """
    name: str
    eps_r: float          # relative permittivity
    thickness_m: float    # wafer thickness in meters
    loss_tangent: float = 0.0
    mu_r: float = 1.0     # relative permeability
    density_kg_per_m3: float | None = None
    thermal_conductivity_W_per_mK: float | None = None
    thermal_expansion_ppm_per_K: float | None = None
    color: str = "gray"
    valid_frequency_min_Hz: float | None = None
    valid_frequency_max_Hz: float | None = None

    def __post_init__(self):
        if self.eps_r <= 1:
            raise ValueError("Relative permittivity must be greater than 1.")
        if self.thickness_m <= 0:
            raise ValueError("Substrate thickness must be positive.")


@dataclass(frozen=True)
class Conductor:
    """
    Represents a conducting layer, either a perfect electric conductor (PEC) 
    or a lossy/superconducting metal film.
    """
    name: str
    is_pec: bool = True          # perfect electric conductor (lossless)
    thickness_m: float = 0.0     # 0.0 => modeled as a zero-thickness 2D sheet
    conductivity_S_per_m: float | None = None
    Tc_K: float | None = None
    penetration_depth_m: float | None = None
    roughness_m: float | None = None
    color: str = "silver"

    def __post_init__(self):
        if self.thickness_m < 0:
            raise ValueError("Conductor thickness cannot be negative.")


# --- Built-in library -------------------------------------------------

# Substrates
SILICON = Substrate(name="Silicon", eps_r=11.7, thickness_m=500e-6, color="darkgray")
SAPPHIRE = Substrate(name="Sapphire", eps_r=10.0, thickness_m=430e-6, color="lightblue")  
QUARTZ = Substrate(name="Quartz", eps_r=3.78, thickness_m=500e-6, loss_tangent=0.0001, color="whitesmoke")
ALUMINA = Substrate(name="Alumina", eps_r=9.9, thickness_m=635e-6, loss_tangent=0.0001, color="white")
FR4 = Substrate(name="FR4", eps_r=4.4, thickness_m=1.6e-3, loss_tangent=0.02, color="darkkhaki")
ROGERS_4350B = Substrate(name="Rogers 4350B", eps_r=3.48, thickness_m=508e-6, loss_tangent=0.0037, color="white")
ROGERS_5880 = Substrate(name="Rogers 5880", eps_r=2.2, thickness_m=254e-6, loss_tangent=0.0009, color="black")
GAAS = Substrate(name="GaAs", eps_r=12.9, thickness_m=500e-6, loss_tangent=0.002, color="dimgray")

# Conductors
NIOBIUM_PEC_SHEET = Conductor(
    name="Niobium (lossless, PEC approx.)", 
    is_pec=True, 
    thickness_m=0.0, 
    Tc_K=9.2,
    color="lightsteelblue"
)

ALUMINUM_PEC_SHEET = Conductor(
    name="Aluminum (lossless, PEC approx.)", 
    is_pec=True, 
    thickness_m=0.0, 
    Tc_K=1.2,
    color="silver"
)

NIOBIUM_THIN_FILM = Conductor(
    name="Niobium thin film", 
    is_pec=True, 
    thickness_m=200e-9,  # 200 nm
    Tc_K=9.2, 
    penetration_depth_m=39e-9,
    roughness_m=2e-9,
    color="lightsteelblue"
)


# --- Material Registries ----------------------------------------------

SUBSTRATES = {
    "silicon": SILICON,
    "sapphire": SAPPHIRE,
    "quartz": QUARTZ,
    "alumina": ALUMINA,
    "fr4": FR4,
    "rogers_4350b": ROGERS_4350B,
    "rogers_5880": ROGERS_5880,
    "gaas": GAAS,
}

CONDUCTORS = {
    "niobium_pec_sheet": NIOBIUM_PEC_SHEET,
    "aluminum_pec_sheet": ALUMINUM_PEC_SHEET,
    "niobium_thin_film": NIOBIUM_THIN_FILM,
}


# --- Getters & Utilities ----------------------------------------------

def get_substrate(name: str) -> Substrate:
    key = name.strip().lower()
    if key not in SUBSTRATES:
        raise KeyError(f"Unknown substrate '{name}'. Options: {list_substrates()}")
    return SUBSTRATES[key]

def get_conductor(name: str) -> Conductor:
    key = name.strip().lower()
    if key not in CONDUCTORS:
        raise KeyError(f"Unknown conductor '{name}'. Options: {list_conductors()}")
    return CONDUCTORS[key]

def list_substrates() -> list[str]:
    """Returns a list of all available substrate keys for GUI dropdowns."""
    return list(SUBSTRATES.keys())

def list_conductors() -> list[str]:
    """Returns a list of all available conductor keys for GUI dropdowns."""
    return list(CONDUCTORS.keys())


__all__ = [
    "Substrate",
    "Conductor",
    
    "SILICON",
    "SAPPHIRE",
    "QUARTZ",
    "ALUMINA",
    "FR4",
    "ROGERS_4350B",
    "ROGERS_5880",
    "GAAS",
    
    "NIOBIUM_PEC_SHEET",
    "ALUMINUM_PEC_SHEET",
    "NIOBIUM_THIN_FILM",
    
    "get_substrate",
    "get_conductor",
    "list_substrates",
    "list_conductors"
]