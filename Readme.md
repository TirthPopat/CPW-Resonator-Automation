# CPW Resonator Automation

<p align="center">

![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)
![CadQuery](https://img.shields.io/badge/CAD-CadQuery-orange)
![COMSOL](https://img.shields.io/badge/Simulation-COMSOL-red)
![License](https://img.shields.io/badge/License-MIT-green)

</p>

---

## AI-Assisted CPW Resonator Design and COMSOL Automation

CPW Resonator Automation is an open-source Python framework for designing, generating, visualizing, and exporting **Coplanar Waveguide (CPW) Quarter-Wavelength Resonators** for microwave, RF, and quantum computing applications.

The project combines analytical microwave calculations with parametric CAD generation to automate the resonator design process and prepare geometries for electromagnetic simulation software such as **COMSOL Multiphysics**.

This project is being developed as part of the **RIT Quantathon Hackathon** with the long-term vision of creating an AI-assisted resonator design platform.

---

# Features

## Analytical Microwave Design

- Characteristic impedance calculation
- Effective dielectric constant calculation
- Guided wavelength computation
- Quarter-wave resonator length estimation
- CPW transmission line synthesis

---

## Parametric Geometry Generation

Generate complete resonator layouts by specifying only:

- Resonant Frequency
- Characteristic Impedance
- Substrate Material
- Substrate Thickness
- Metal Thickness
- Coupling Gap
- CPW Dimensions

The complete geometry is generated automatically.

---

## 3D Model Generation

The software creates complete 3D CAD models consisting of:

- Substrate
- Ground Plane
- Feed Line
- Quarter-Wave Resonator

using **CadQuery**.

---

## CAD Export

Supported export formats include:

- STEP
- STL
- BREP
- PNG Preview
- JSON Parameter File

---

## Visualization

Interactive 3D visualization using **PyVista**.

Features include:

- Rotate
- Zoom
- Pan
- Wireframe Mode
- Surface Rendering
- Image Export

---

## Material Support

Current supported substrates include:

- Silicon
- Sapphire
- Quartz
- FR4
- Rogers RO4003C
- Rogers RO4350B
- Custom Materials

---

# Project Structure

```text
CPW-Resonator-Automation
│
├── assets/
│
├── data/
│
├── docs/
│
├── exports/
│
├── models/
│
├── notebooks/
│   ├── CPW_Model.ipynb
│   ├── Test_calculator.ipynb
│   ├── Test_geometry.ipynb
│   ├── Test_exporter.ipynb
│   ├── Test_materials.ipynb
│   └── Test_viewer.ipynb
│
├── src/
│   ├── calculator.py
│   ├── constants.py
│   ├── exporter.py
│   ├── geometry.py
│   ├── materials.py
│   ├── utils.py
│   └── viewer.py
│
├── tests/
│
├── README.md
├── LICENSE
├── requirements.txt
└── .gitignore
```

---

# Installation

Clone the repository

```bash
git clone https://github.com/TirthPopat/CPW-Resonator-Automation.git
```

Move into the project

```bash
cd CPW-Resonator-Automation
```

Create a virtual environment

Windows

```bash
python -m venv CPWPY
```

Linux

```bash
python3 -m venv CPWPY
```

Activate the environment

Windows

```bash
CPWPY\Scripts\activate
```

Linux

```bash
source CPWPY/bin/activate
```

Install dependencies

```bash
pip install -r requirements.txt
```

---

# Quick Start

Launch Jupyter Notebook

```bash
jupyter notebook
```

Open

```text
notebooks/CPW_Model.ipynb
```

Modify the design parameters

```python
FREQUENCY = 6e9
IMPEDANCE = 50
SUBSTRATE = "Sapphire"
```

Run all notebook cells.

The software automatically:

- Calculates microwave parameters
- Generates CPW geometry
- Creates 3D CAD models
- Displays the model
- Exports CAD files

---

# Example Outputs

Generated files include

```text
cpw_quarterwave.step

cpw_quarterwave.stl

cpw_quarterwave_feed_trace.step

cpw_quarterwave_ground_plane.step

cpw_quarterwave_resonator_trace.step

cpw_quarterwave_substrate.step

cpw_quarterwave.json

cpw_quarterwave_manifest.json

cpw_quarterwave.png
```

---

# Technology Stack

- Python
- CadQuery
- OpenCascade
- PyVista
- NumPy
- SciPy
- Shapely
- Jupyter Notebook

---

# Current Workflow

```text
User Specifications
        │
        ▼
Microwave Calculations
        │
        ▼
CPW Geometry Generation
        │
        ▼
3D CAD Model Generation
        │
        ▼
STEP / STL / BREP Export
        │
        ▼
Import into COMSOL
        │
        ▼
Electromagnetic Simulation
```

---

# Future Roadmap

## Phase 1 (Current)

- CPW Calculator
- Geometry Generator
- CAD Export
- 3D Viewer

---

## Phase 2

- Improved COMSOL compatibility
- DXF Export
- GDSII Export
- HFSS Export
- Automatic Mesh Generation

---

## Phase 3

AI-Based Design Optimization

- Bayesian Optimization
- Genetic Algorithms
- Neural Network Surrogate Models
- Multi-objective Optimization

---

## Phase 4

Complete AI-Assisted COMSOL Automation

```text
User Specifications

↓

AI Design Optimization

↓

Geometry Generation

↓

Automatic COMSOL Launch

↓

Material Assignment

↓

Physics Selection

↓

Mesh Generation

↓

Simulation

↓

Result Extraction

↓

AI Optimization Loop

↓

Optimized Resonator
```

---

# Applications

Potential applications include:

- Superconducting Quantum Circuits
- Coplanar Waveguide Resonators
- Microwave Filters
- RF Components
- Quantum Computing Research
- Electromagnetic Simulation
- Microwave Education

---

# Current Status

| Module | Status |
|----------|--------|
| Microwave Calculator | ✅ |
| Geometry Generator | ✅ |
| 3D CAD Generation | ✅ |
| STEP Export | ✅ |
| STL Export | ✅ |
| BREP Export | ✅ |
| Visualization | ✅ |
| COMSOL Import Workflow | 🚧 In Progress |
| AI Optimization | 🚧 Planned |
| Automatic COMSOL Automation | 🚧 Planned |

---

# Contributing

Contributions are welcome.

Possible areas include:

- Geometry improvements
- Additional export formats
- Material database expansion
- COMSOL automation
- AI optimization algorithms
- Documentation
- Testing

Please fork the repository and submit a Pull Request.

---

# License

This project is licensed under the MIT License.

See the LICENSE file for details.

---

# Author

**Tirth Popat**

B.Tech Electronics Engineering (VLSI Design & Technology)

VIT Chennai

---

# Acknowledgements

Special thanks to:

- CadQuery
- OpenCascade Technology
- PyVista
- COMSOL Multiphysics
- Python Scientific Community

---

## If you find this project useful, please consider giving it a ⭐ on GitHub!
