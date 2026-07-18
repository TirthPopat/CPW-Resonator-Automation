"""
exporter.py
Export a built CPWModel3D / CPWLayout to files: STEP, STL, and BREP for the 3D
solids (importable into COMSOL, Ansys, KLayout, etc.), JSON for the
design parameters, and a PNG of the 2D layout for a quick sanity check.
"""

from __future__ import annotations
import importlib.metadata
import json
import logging
import dataclasses
import datetime
import subprocess
from pathlib import Path
from typing import Dict, Any, Union, TYPE_CHECKING

if TYPE_CHECKING:
    from .geometry import CPWModel3D, CPWLayout, CPWCrossSection, CPWDesign

logger = logging.getLogger(__name__)

__all__ = [
    "ExportResult",
    "export_params_json",
    "export_manifest",
    "export_step",
    "export_stl",
    "export_brep",
    "plot_layout_png",
    "export_all",
    "verify_model",
    "print_export_statistics"
]


@dataclasses.dataclass(slots=True)
class ExportResult:
    """Collects the paths produced by a single export run.

    Uses ``slots=True`` to reduce per-instance memory and prevent
    accidental attribute creation via typos.
    """
    json_file: Path | None = None
    manifest_file: Path | None = None
    png_file: Path | None = None
    step_files: Dict[str, Path] = dataclasses.field(default_factory=dict)
    stl_files: Dict[str, Path] = dataclasses.field(default_factory=dict)
    brep_files: Dict[str, Path] = dataclasses.field(default_factory=dict)
    dxf_files: Dict[str, Path] = dataclasses.field(default_factory=dict)   # Future support
    svg_files: Dict[str, Path] = dataclasses.field(default_factory=dict)   # Future support


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_package_version(package_name: str = "cpw-resonator") -> str:
    """Return the installed package version, or ``'unknown'``."""
    try:
        return importlib.metadata.version(package_name)
    except importlib.metadata.PackageNotFoundError:
        return "unknown"


def _get_git_hash() -> str | None:
    """Return the short git hash of the current repo, or None."""
    try:
        return (
            subprocess.check_output(
                ["git", "rev-parse", "--short", "HEAD"],
                stderr=subprocess.DEVNULL,
            )
            .decode()
            .strip()
        )
    except Exception:
        return None


def _resolve_eps_eff(layout: CPWLayout) -> float:
    """
    Safely resolve ``eps_eff`` from *layout*, checking multiple possible
    nesting paths (``layout.params.eps_eff``, ``layout.design.eps_eff``,
    ``layout.cross_section.eps_eff``).
    """
    for attr_chain in (
        ("params", "eps_eff"),
        ("design", "eps_eff"),
        ("cross_section", "eps_eff"),
    ):
        obj = layout
        for attr in attr_chain:
            obj = getattr(obj, attr, None)
            if obj is None:
                break
        if isinstance(obj, (int, float)):
            return float(obj)
    return 0.0


def verify_model(model3d: CPWModel3D) -> None:
    """
    Verify the 3D model properties before export. Checks for null shapes,
    empty assemblies, and verifies objects are valid solids.
    """
    logger.info("Verifying model before export...")
    if not getattr(model3d, "assembly", None) or not model3d.assembly.objects:
        logger.warning("Assembly is empty or missing.")

    parts = {
        "substrate": model3d.substrate,
        "ground_plane": model3d.ground_plane,
        "feed_trace": model3d.feed_trace,
        "resonator_trace": model3d.resonator_trace,
    }

    for name, shape in parts.items():
        if shape is None:
            logger.error(f"Shape '{name}' is null.")
            continue
        
        # Check if the object is actually a Solid
        obj = shape.val() if hasattr(shape, "val") else shape
        geom_type = getattr(obj, "geomType", lambda: "Unknown")()
        if geom_type != "Solid":
            logger.warning(f"Shape '{name}' is not a Solid. Type: {geom_type}")


def print_export_statistics(result: ExportResult, model3d: CPWModel3D) -> None:
    """Print file sizes, geometric properties, and statistics for debugging."""
    print("\n" + "="*30)
    print("      EXPORT STATISTICS")
    print("="*30)

    def _get_dir_size_kb(files: Dict[str, Path]) -> float:
        return sum(f.stat().st_size for f in files.values() if f.exists()) / 1024.0

    if result.step_files:
        print(f"STEP size:       {_get_dir_size_kb(result.step_files):.2f} KB")
    if result.brep_files:
        print(f"BREP size:       {_get_dir_size_kb(result.brep_files):.2f} KB")
    if result.stl_files:
        print(f"STL size:        {_get_dir_size_kb(result.stl_files):.2f} KB")

    parts = [model3d.substrate, model3d.ground_plane, model3d.feed_trace, model3d.resonator_trace]
    solid_count = sum(1 for p in parts if p is not None)
    print(f"Solid count:     {solid_count}")

    if getattr(model3d, "assembly", None):
        print(f"Assembly items:  {len(model3d.assembly.objects)}")
    
    # Calculate bounding box from the substrate (serving as the domain boundary)
    if model3d.substrate is not None:
        try:
            obj = model3d.substrate.val() if hasattr(model3d.substrate, "val") else model3d.substrate
            bbox = obj.BoundingBox()
            print(f"Bounding Box:    (x: {bbox.xlen:.3e}, y: {bbox.ylen:.3e}, z: {bbox.zlen:.3e})")
        except Exception:
            pass
    print("="*30 + "\n")


# ---------------------------------------------------------------------------
# Individual exporters
# ---------------------------------------------------------------------------

def export_params_json(
    params: Any,
    path: Path | str,
) -> Path:
    """Dump a dataclass (e.g. CPWDesign, CPWCrossSection) to JSON."""
    path = Path(path)
    d = dataclasses.asdict(params)
    path.write_text(json.dumps(d, indent=2))
    return path


def export_manifest(
    layout: CPWLayout,
    path: Path | str,
    *,
    software_version: str | None = None,
    extra: Dict[str, Any] | None = None,
) -> Path:
    """Write a ``manifest.json`` with key design inputs and provenance metadata."""
    path = Path(path)
    extra = extra or {}

    if software_version is None:
        software_version = _get_package_version()

    params = getattr(layout, "params", None) or getattr(layout, "design", None)

    manifest: Dict[str, Any] = {
        "frequency_hz": getattr(params, "f0_hz", None),
        "impedance_ohm": getattr(params, "z0", None),
        "eps_eff": _resolve_eps_eff(layout),
        "substrate": {
            "name": getattr(params, "substrate_name", None),
            "eps_r": getattr(params, "eps_r", None),
            "height_m": getattr(params, "h", None),
            "loss_tangent": getattr(params, "loss_tangent", None),
        },
        "conductor": {
            "name": getattr(params, "conductor_name", None),
        },
        "versions": {
            "software_version": software_version,
            "calculator_version": extra.get("calculator_version", "unknown"),
            "geometry_version": extra.get("geometry_version", "unknown"),
            "viewer_version": extra.get("viewer_version", "unknown"),
        },
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "git_hash": _get_git_hash(),
    }

    if extra:
        manifest.update({k: v for k, v in extra.items() if not k.endswith("_version")})

    path.write_text(json.dumps(manifest, indent=2, default=str))
    return path


def export_step(
    model3d: CPWModel3D,
    out_dir: Path | str,
    prefix: str = "cpw",
    mode: str = "cad"
) -> Dict[str, Path]:
    """
    Export each part of a CPWModel3D as a separate STEP file, plus one
    combined assembly STEP file.
    
    Modes:
      "cad"    : Standard export.
      "comsol" / "ansys" : Applies topological healing before export and validates file.
    """
    import cadquery as cq

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    paths: Dict[str, Path] = {}

    # 1. Export the combined assembly cleanly using the generated instance
    if getattr(model3d, "assembly", None):
        combined_path = out_dir / f"{prefix}.step"
        try:
            model3d.assembly.save(str(combined_path))
            paths["assembly"] = combined_path
            
            # STEP Validation 
            if mode in ("comsol", "ansys"):
                try:
                    cq.importers.importStep(str(combined_path))
                    logger.info("STEP validation successful.")
                except Exception:
                    logger.error("STEP validation failed: could not reopen the assembly file.")
        except Exception:
            logger.exception("Failed to export assembly STEP")

    # 2. Export individual parts with healing logic applied
    parts = {
        "substrate": model3d.substrate,
        "ground_plane": model3d.ground_plane,
        "feed_trace": model3d.feed_trace,
        "resonator_trace": model3d.resonator_trace,
    }

    for name, shape in parts.items():
        if shape is None:
            continue
            
        p = out_dir / f"{prefix}_{name}.step"
        try:
            obj = shape.val() if hasattr(shape, "val") else shape
            
            if mode in ("comsol", "ansys"):
                # Clean, Fuse, and Heal topology for singular edges
                if hasattr(obj, "clean"):
                    obj = obj.clean()
                if hasattr(obj, "fix"):
                    obj = obj.fix()
            
            cq.exporters.export(obj, str(p))
            paths[name] = p
        except Exception:
            logger.exception("Failed to export STEP for %s", name)

    return paths


def export_stl(
    model3d: CPWModel3D,
    out_dir: Path | str,
    prefix: str = "cpw",
    tolerance: float = 1e-4,  # Changed default to a finer tolerance
) -> Dict[str, Path]:
    """Export each part as STL."""
    import cadquery as cq

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    parts = {
        "substrate": model3d.substrate,
        "ground_plane": model3d.ground_plane,
        "feed_trace": model3d.feed_trace,
        "resonator_trace": model3d.resonator_trace,
    }

    paths: Dict[str, Path] = {}
    for name, shape in parts.items():
        if shape is None:
            continue

        p = out_dir / f"{prefix}_{name}.stl"
        try:
            cq.exporters.export(shape, str(p), tolerance=tolerance)
            paths[name] = p
        except Exception:
            logger.exception("Failed to export STL for %s", name)

    return paths


def export_brep(
    model3d: CPWModel3D,
    out_dir: Path | str,
    prefix: str = "cpw",
) -> Dict[str, Path]:
    """Export each part of a CPWModel3D as native CadQuery BREP."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    parts = {
        "substrate": model3d.substrate,
        "ground_plane": model3d.ground_plane,
        "feed_trace": model3d.feed_trace,
        "resonator_trace": model3d.resonator_trace,
    }

    paths: Dict[str, Path] = {}
    for name, shape in parts.items():
        if shape is None:
            continue
        p = out_dir / f"{prefix}_{name}.brep"
        try:
            # Robust unwrapping handling both Workplane and Solid targets
            obj = shape.val() if hasattr(shape, "val") else shape
            obj.exportBrep(str(p))
            paths[name] = p
        except Exception:
            logger.exception("Failed to export BREP for %s", name)

    return paths


def plot_layout_png(
    layout: CPWLayout,
    path: Path | str,
    figsize: tuple[int, int] = (10, 6),
    dpi: int = 150,
) -> Path:
    """
    Quick 2D sanity-check plot of the layout using matplotlib.
    Automatically converts SI metre coordinates to millimetres for plotting.
    """
    import matplotlib.pyplot as plt
    from shapely.geometry import MultiPolygon

    path = Path(path)
    fig, ax = plt.subplots(figsize=figsize)

    def _draw(poly, color, label=None, alpha=1.0):
        if poly is None or poly.is_empty:
            return
        geoms = poly.geoms if isinstance(poly, MultiPolygon) else [poly]
        first = True
        for g in geoms:
            xs = [x * 1e3 for x in g.exterior.xy[0]]
            ys = [y * 1e3 for y in g.exterior.xy[1]]

            ax.fill(xs, ys, color=color, alpha=alpha, label=label if first else None)

            for hole in g.interiors:
                hx = [x * 1e3 for x in hole.xy[0]]
                hy = [y * 1e3 for y in hole.xy[1]]
                ax.fill(hx, hy, color="white")
            first = False

    _draw(layout.substrate_footprint, "#dddddd", "substrate", alpha=0.5)
    _draw(layout.ground_plane, "#c99a5a", "ground plane")
    _draw(layout.feed_trace, "#c99a5a", "feed trace")
    _draw(layout.resonator_trace, "#c99a5a", "resonator trace")

    ax.set_aspect("equal")
    ax.set_xlabel("x (mm)")
    ax.set_ylabel("y (mm)")

    params = getattr(layout, "params", None) or getattr(layout, "design", None)
    length_m = getattr(params, "resonator_length_m", getattr(params, "resonator_length", 0.0))
    length_mm = length_m * 1e3
    f0_hz = getattr(params, "f0_hz", 0.0)
    eps_eff = _resolve_eps_eff(layout)

    ax.set_title(
        f"CPW resonator layout | f0={f0_hz / 1e9:.4f} GHz  "
        f"L={length_mm:.4f} mm  eps_eff={eps_eff:.3f}"
    )

    handles, labels = ax.get_legend_handles_labels()
    by_label = dict(zip(labels, handles))
    ax.legend(by_label.values(), by_label.keys(), loc="upper right", fontsize=8)

    fig.tight_layout()
    fig.savefig(str(path), dpi=dpi)
    plt.close(fig)
    return path


# ---------------------------------------------------------------------------
# Batch export
# ---------------------------------------------------------------------------

def export_all(
    model3d: CPWModel3D,
    layout: CPWLayout,
    out_dir: Path | str = "exports",
    prefix: str = "cpw",
    mode: str = "cad",
) -> ExportResult:
    """
    Batch command to generate all relevant export files (JSON, PNG, STEP,
    STL, BREP, manifest) into a single target directory.
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    
    # Pre-flight check
    verify_model(model3d)

    result = ExportResult()

    # 1. Export JSON
    json_path = out_dir / f"{prefix}.json"
    params = getattr(layout, "params", None) or getattr(layout, "design", None)
    try:
        result.json_file = export_params_json(params, json_path)
    except Exception:
        logger.exception("Failed to export JSON")

    # 2. Export manifest
    manifest_path = out_dir / f"{prefix}_manifest.json"
    try:
        # Example showing how version dictionaries can be passed down
        extra_meta = {
            "calculator_version": "1.2.0",
            "geometry_version": "2.0.1",
            "viewer_version": "1.0.0"
        }
        result.manifest_file = export_manifest(layout, manifest_path, extra=extra_meta)
    except Exception:
        logger.exception("Failed to export manifest")

    # 3. Export PNG
    png_path = out_dir / f"{prefix}.png"
    try:
        result.png_file = plot_layout_png(layout, png_path)
    except Exception:
        logger.exception("Failed to export PNG")

    # 4. Export STEP
    result.step_files = export_step(model3d, out_dir, prefix=prefix, mode=mode)

    # 5. Export STL
    result.stl_files = export_stl(model3d, out_dir, prefix=prefix, tolerance=1e-4)

    # 6. Export BREP
    result.brep_files = export_brep(model3d, out_dir, prefix=prefix)

    logger.info("Successfully batch exported project to %s", out_dir.resolve())
    
    # 7. Print debug and statistical information 
    print_export_statistics(result, model3d)

    return result