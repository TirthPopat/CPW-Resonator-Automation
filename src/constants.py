"""
constants.py
Physical constants used throughout CPWPY.
All lengths in this package are in millimetres (mm) unless noted otherwise,
to match the COMSOL reference model (Geometry -> Length unit -> mm).
Frequencies are in Hz, impedances in Ohm.
"""

C0 = 299_792_458.0          # speed of light in vacuum, m/s
C0_MM_PER_S = C0 * 1000.0   # speed of light, mm/s  (handy since we work in mm)
MU0 = 4e-7 * 3.141592653589793   # vacuum permeability, H/m
EPS0 = 8.8541878128e-12          # vacuum permittivity, F/m

# Superconducting-qubit-relevant band, from the COMSOL model documentation
QUBIT_BAND_GHZ = (4.0, 8.0)

# Default aluminum superconducting gap frequency mentioned in the reference doc
AL_GAP_FREQ_GHZ = 82.0