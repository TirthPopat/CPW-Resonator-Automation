"""
viewer.py
Interactive 3D viewing of the generated CPW model. Uses pyvista (via VTK).
Works in a plain script (opens a window) or inline in a Jupyter notebook
(pyvista.set_jupyter_backend('trame') recommended for best results).
"""

from __future__ import annotations
import tempfile
import logging
from pathlib import Path
from typing import Optional, Any

from .geometry import CPWModel3D

# Configure module-level logger
logger = logging.getLogger(__name__)


def _shape_to_pv_mesh(shape: Any):
    """Convert a cadquery Shape (Solid or Face) to a pyvista mesh via a temp STL."""
    import cadquery as cq
    import pyvista as pv

    val = shape.val() if hasattr(shape, "val") else shape
    with tempfile.TemporaryDirectory() as td:
        stl_path = str(Path(td) / "tmp.stl")
        
        if val.ShapeType() == "Face":
            # Faces can't export to STL directly; triangulate via a thin extrude instead.
            solid = cq.Solid.extrudeLinear(
                val.outerWire(), list(val.innerWires()), cq.Vector(0, 0, 1e-4)
            )
            # Binary export is generally the default in newer OCCT versions
            cq.exporters.export(cq.Workplane(obj=solid), stl_path)
        else:
            cq.exporters.export(shape, stl_path)
            
        mesh = pv.read(stl_path)
        
    return mesh


def view_model_3d(
    model3d: CPWModel3D,
    colors: Optional[dict[str, str]] = None,
    screenshot: Optional[str] = None,
    notebook: bool = False,
):
    """
    Open an interactive pyvista window (or inline notebook widget) showing
    substrate + ground plane + feed trace + resonator trace.
    """
    import pyvista as pv

    colors = colors or {
        "substrate": "#b0c4de",
        "ground_plane": "#c99a5a",
        "feed_trace": "#c99a5a",
        "resonator_trace": "#c99a5a",
    }

    # Initialize directly to avoid polluting global pyvista state
    plotter = pv.Plotter(
        notebook=notebook, 
        off_screen=(screenshot is not None)
    )
    
    plotter.set_background("white")
    plotter.add_title("CPW Resonator")

    parts = {
        "substrate": model3d.substrate,
        "ground_plane": model3d.ground_plane,
        "feed_trace": model3d.feed_trace,
        "resonator_trace": model3d.resonator_trace,
    }
    
    for name, shape in parts.items():
        if shape is None:
            continue

        try:
            mesh = _shape_to_pv_mesh(shape)
        except Exception as e:
            logger.warning("Could not display %s: %s", name, e)
            continue

        opacity = 0.35 if name == "substrate" else 1.0
        
        plotter.add_mesh(
            mesh, 
            color=colors.get(name, "gray"), 
            opacity=opacity, 
            label=name,
            smooth_shading=True,
            specular=0.2
        )

    plotter.add_legend()
    plotter.add_axes()
    plotter.show_grid()
    plotter.view_isometric()
    
    plotter.reset_camera()

    if screenshot:
        plotter.show(screenshot=screenshot, auto_close=not notebook)
    else:
        plotter.show()

    return plotter


def save_model_image(
    model3d: CPWModel3D, 
    filename: str = "cpw.png", 
    colors: Optional[dict[str, str]] = None
) -> str:
    """
    Automatically generate and save a 3D image of the model.
    Forces off-screen rendering for headless AI automated pipelines.
    Returns the filepath for easy chaining in automated workflows.
    """
    view_model_3d(model3d, colors=colors, screenshot=filename, notebook=False)
    return filename


def quick_layout_preview(layout: Any):
    """Fast matplotlib 2D preview without needing cadquery at all -- good for
    rapid parameter iteration in a notebook before generating full 3D solids."""
    from .exporter import plot_layout_png
    import tempfile
    from pathlib import Path
    import matplotlib.pyplot as plt
    import matplotlib.image as mpimg

    with tempfile.TemporaryDirectory() as td:
        p = str(Path(td) / "preview.png")
        plot_layout_png(layout, p)
        img = mpimg.imread(p)
        fig, ax = plt.subplots(figsize=(10, 6))
        ax.imshow(img)
        ax.axis("off")
        plt.show()

__all__ = [
    "view_model_3d",
    "save_model_image",
    "quick_layout_preview",
]