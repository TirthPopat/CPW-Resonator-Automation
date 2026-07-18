"""
geometry.py
Fully parametric CPW quarter-wave resonator + coupled feedline geometry.

Pipeline:
  1. (numpy)   build centerline paths for the feedline and the meandered
               resonator, sized so the resonator's electrical length hits
               the target quarter-wave resonance.
  2. (shapely) offset those centerlines into 2D polygons: the metal trace
               itself, and the "keepout" region the ground plane must avoid.
               Ground plane = substrate footprint minus the union of keepouts.
  3. (cadquery) turn every 2D polygon into an extruded Solid of finite metal
               thickness (Niobium thin film, 200 nm default), plus a substrate
               Box.  Metal is placed on top of the substrate (+Z direction).

All lengths are in meters (SI units).
Every conductor is always a proper 3D Solid — never a zero-thickness Face.
"""
from __future__ import annotations
import logging
import math
from dataclasses import dataclass, field
from typing import List, Tuple, TYPE_CHECKING, Any, Literal
import numpy as np

if TYPE_CHECKING:
    from .materials import Substrate
    from .calculator import CPWDesign
    from shapely.geometry import Polygon

# Initialize logger for geometry operations
logger = logging.getLogger(__name__)

Point = Tuple[float, float]

# ── Global constant ──────────────────────────────────────────────────
METAL_THICKNESS = 200e-9  # 200 nm Niobium thin film


# ---------------------------------------------------------------------
# Metadata & Helper Dataclasses
# ---------------------------------------------------------------------
@dataclass(frozen=True, slots=True)
class Port:
    position: Point
    direction: Point
    width_m: float
    impedance_ohms: float


@dataclass(frozen=True, slots=True)
class LayoutMetadata:
    bounding_box: Tuple[float, float, float, float]  # (minx, miny, maxx, maxy)
    metal_area_sq_m: float
    ground_area_sq_m: float
    resonator_length_actual_m: float
    feedline_length_m: float


# ---------------------------------------------------------------------
# Parameters
# ---------------------------------------------------------------------
@dataclass
class CPWResonatorParams:
    # --- RF Targets & Materials ---
    f0_hz: float
    target_z0_ohms: float
    substrate: "Substrate"
    resonator_mode: Literal["quarter", "half"] = "quarter"

    # --- Cross section ---
    width_m: float = 10e-6           # center conductor width, m

    # --- Meander layout ---
    n_meanders: int = 3              # number of U-turns pairs U-turns
    meander_pitch_m: float = 150e-6  # vertical jog per turn, m
    coupling_length_m: float = 300e-6 # straight section for capacitive coupling, m
    coupling_gap_m: float = 20e-6    # gap between feedline and resonator, m

    # --- Feedline ---
    feed_width_m: float | None = None # defaults to width_m if None

    # --- Footprint / environment ---
    substrate_margin_x_m: float = 300e-6
    substrate_margin_y_m: float = 300e-6
    air_box_height_m: float = 1e-3    # 1 mm air above the chip

    # --- Metal & Terminations ---
    metal_thickness_m: float = METAL_THICKNESS
    short_strap_extension_m: float = 10e-6
    short_strap_width_margin_m: float = 20e-6

    # --- Fillet radius for meander corners (aids meshing) ---
    corner_fillet_m: float = 1e-6    # 1 µm realistic default for superconducting CPWs

    def __post_init__(self):
        if self.feed_width_m is None:
            self.feed_width_m = self.width_m
        if self.metal_thickness_m <= 0:
            self.metal_thickness_m = METAL_THICKNESS
        if self.f0_hz <= 0:
            raise ValueError("Resonance frequency must be positive.")
        if self.target_z0_ohms <= 0:
            raise ValueError("Target impedance must be positive.")
        if self.width_m <= 0 or self.feed_width_m <= 0:
            raise ValueError("Trace widths must be positive.")
        if self.coupling_gap_m <= 0:
            raise ValueError("Coupling gap must be positive.")
        if self.n_meanders < 1:
            raise ValueError("n_meanders must be >= 1.")


# ---------------------------------------------------------------------
# 1. Centerline path generation
# ---------------------------------------------------------------------
def polyline_length(pts: List[Point]) -> float:
    arr = np.asarray(pts, dtype=float)
    return float(np.sum(np.linalg.norm(np.diff(arr, axis=0), axis=1)))


def meander_path(
    total_length: float,
    n_meanders: int,
    pitch: float,
    start: Point = (0.0, 0.0),
    direction: int = 1,
    lead_in: float = 0.0,
) -> Tuple[List[Point], float]:
    n_turns = 2 * n_meanders
    n_legs = n_turns + 1
    vertical_budget = n_turns * pitch
    horizontal_budget = total_length - lead_in - vertical_budget
    
    if horizontal_budget <= 0:
        raise ValueError(
            f"total_length={total_length} too short for lead_in={lead_in}, "
            f"n_meanders={n_meanders}, pitch={pitch}. Reduce n_meanders/pitch "
            f"or target a lower frequency."
        )

    leg_length = horizontal_budget / n_legs
    pts = [start]
    x, y = start

    if lead_in > 0:
        x += lead_in
        pts.append((x, y))

    sign = direction
    for leg in range(n_legs):
        x += leg_length
        pts.append((x, y))
        if leg < n_legs - 1:
            y += sign * pitch
            pts.append((x, y))
            sign *= -1

    return pts, polyline_length(pts)


def straight_path(start: Point, end: Point) -> List[Point]:
    return [start, end]


# ---------------------------------------------------------------------
# 2. Centerline -> 2D polygons (shapely)
# ---------------------------------------------------------------------
def _require_shapely():
    try:
        import shapely  # noqa: F401
    except ImportError as e:
        raise ImportError(
            "shapely is required for CPW polygon generation. "
            "Install with: pip install shapely"
        ) from e


def validate_and_clean_polygon(poly: "Polygon", min_area: float = 1e-16) -> "Polygon":
    """
    Heals Shapely polygons and aggressively removes microscopic artifacts
    that cause CAD kernels to crash or meshes to fail.
    """
    _require_shapely()
    from shapely.validation import make_valid
    from shapely.geometry import Polygon, MultiPolygon, GeometryCollection
    from shapely.ops import unary_union
    
    if not poly.is_valid:
        poly = make_valid(poly)
        
    poly = poly.buffer(0)
    
    # Filter out microscopic fragments and zero-area slivers
    if isinstance(poly, (MultiPolygon, GeometryCollection)):
        valid_polys = [p for p in poly.geoms if isinstance(p, Polygon) and p.area > min_area]
        poly = unary_union(valid_polys)
    elif isinstance(poly, Polygon) and poly.area < min_area:
        logger.warning("Polygon area below minimum threshold.")
        return poly
        
    if not poly.is_valid:
        logger.warning("Polygon remains invalid.")
    return poly


def apply_fillet(poly: "Polygon", radius: float) -> "Polygon":
    """
    Applies a fillet to a polygon, ensuring the radius is clamped 
    to prevent the geometry from collapsing.
    """
    if radius <= 0:
        return poly

    try:
        safe_clearance = poly.minimum_clearance
        if not math.isfinite(safe_clearance):
            safe_clearance = radius
        elif safe_clearance <= 0:
            safe_clearance = 0

        clamped_radius = min(radius, safe_clearance * 0.25)

        # If the clamped radius is practically zero (< 1 nm), just return the original polygon
        if clamped_radius <= 1e-9:
            return validate_and_clean_polygon(poly)

        # Standard Shapely fillet approach
        filleted = (
            poly.buffer(clamped_radius, join_style=1)
                .buffer(-2 * clamped_radius, join_style=1)
                .buffer(clamped_radius, join_style=1)
        )

        if filleted.is_empty:
            logger.warning(
                "Fillet radius %.2f µm removed the polygon. Using original polygon.",
                clamped_radius * 1e6,
            )
            return validate_and_clean_polygon(poly)

        if filleted.area < poly.area * 0.05:
            logger.warning(
                "Fillet collapsed the polygon. Using original polygon."
            )
            return validate_and_clean_polygon(poly)

        return validate_and_clean_polygon(filleted)

    except Exception:
        logger.exception("Fillet failed.")
        return validate_and_clean_polygon(poly)


def trace_polygon(points: List[Point], width: float, fillet: float = 0.0) -> "Polygon":
    _require_shapely()
    from shapely.geometry import LineString
    line = LineString(points)
    poly = line.buffer(width / 2.0, cap_style=2, join_style=2)  # 2=flat, 2=mitre
    poly = apply_fillet(poly, fillet)
    return validate_and_clean_polygon(poly)


def keepout_polygon(points: List[Point], width: float, gap: float, fillet: float = 0.0) -> "Polygon":
    _require_shapely()
    from shapely.geometry import LineString
    line = LineString(points)
    poly = line.buffer(width / 2.0 + gap, cap_style=2, join_style=2)
    poly = apply_fillet(poly, fillet)
    return validate_and_clean_polygon(poly)


def oriented_end_rect(
    end_point: Point, tangent: Point, length: float, width: float
) -> "Polygon":
    _require_shapely()
    from shapely.geometry import Polygon
    t = np.array(tangent, dtype=float)
    t = t / np.linalg.norm(t)
    n = np.array([-t[1], t[0]])

    p = np.array(end_point, dtype=float)
    p1 = p + n * (width / 2.0)
    p2 = p - n * (width / 2.0)
    p3 = p2 + t * length
    p4 = p1 + t * length
    return validate_and_clean_polygon(Polygon([p1, p2, p3, p4]))


# ---------------------------------------------------------------------
# 3. Full layout assembly
# ---------------------------------------------------------------------
@dataclass
class CPWLayout:
    substrate_footprint: "Polygon"
    ground_plane: "Polygon"
    feed_trace: "Polygon"
    resonator_trace: "Polygon"
    short_strap: "Polygon"
    feed_path: List[Point]
    resonator_path: List[Point]
    port1: Port
    port2: Port
    metadata: LayoutMetadata
    design: "CPWDesign"
    params: CPWResonatorParams


def build_layout(params: CPWResonatorParams) -> CPWLayout:
    _require_shapely()
    from shapely.geometry import box
    from shapely.ops import unary_union
    from . import calculator as calc

    res_design = calc.design_cpw(
        frequency_hz=params.f0_hz,
        impedance_ohms=params.target_z0_ohms,
        substrate=params.substrate,
        width_m=params.width_m,
        mode=params.resonator_mode
    )
    
    if params.feed_width_m != params.width_m:
        feed_design = calc.design_cpw(
            frequency_hz=params.f0_hz,
            impedance_ohms=params.target_z0_ohms,
            substrate=params.substrate,
            width_m=params.feed_width_m,
            mode=params.resonator_mode
        )
        feed_gap_m = feed_design.gap_m
    else:
        feed_gap_m = res_design.gap_m

    # --- feedline ---
    feed_extent_x = (
        params.coupling_length_m
        + 2 * params.substrate_margin_x_m
        + params.n_meanders * params.meander_pitch_m
    )
    feed_path = straight_path((0.0, 0.0), (feed_extent_x, 0.0))

    # --- resonator ---
    coupled_y = params.feed_width_m / 2 + feed_gap_m + params.coupling_gap_m + params.width_m / 2
    coupled_start = (params.substrate_margin_x_m, coupled_y)

    remaining_length = res_design.resonator_length_m - params.coupling_length_m
    resonator_path, achieved_res_len = meander_path(
        total_length=remaining_length,
        n_meanders=params.n_meanders,
        pitch=params.meander_pitch_m,
        start=(coupled_start[0] + params.coupling_length_m, coupled_y),
        direction=1,
    )
    resonator_path = [coupled_start] + resonator_path
    achieved_res_len += params.coupling_length_m

    # --- polygons (with fillets) ---
    f_rad = params.corner_fillet_m
    feed_trace = trace_polygon(feed_path, params.feed_width_m, f_rad)
    feed_keepout = keepout_polygon(feed_path, params.feed_width_m, feed_gap_m, f_rad)
    resonator_trace = trace_polygon(resonator_path, params.width_m, f_rad)
    resonator_keepout = keepout_polygon(resonator_path, params.width_m, res_design.gap_m, f_rad)

    # short-circuit strap
    p_end = resonator_path[-1]
    p_prev = resonator_path[-2]
    tangent = (p_end[0] - p_prev[0], p_end[1] - p_prev[1])
    strap_len = 2 * res_design.gap_m + params.short_strap_extension_m
    strap_width = params.width_m + 2 * res_design.gap_m + params.short_strap_width_margin_m
    short_strap = oriented_end_rect(p_end, tangent, strap_len, strap_width)
    
    # Append strap to resonator
    resonator_trace = validate_and_clean_polygon(unary_union([resonator_trace, short_strap]))

    # --- substrate footprint ---
    xs = [p[0] for p in feed_path + resonator_path]
    ys = [p[1] for p in feed_path + resonator_path]
    substrate_footprint = validate_and_clean_polygon(box(
        min(xs) - params.substrate_margin_x_m, 
        min(ys) - params.substrate_margin_y_m - params.width_m, 
        max(xs) + params.substrate_margin_x_m, 
        max(ys) + params.substrate_margin_y_m
    ))

    # --- ground plane ---
    all_keepout = validate_and_clean_polygon(unary_union([feed_keepout, resonator_keepout]))
    ground_plane = validate_and_clean_polygon(substrate_footprint.difference(all_keepout))
    ground_plane = validate_and_clean_polygon(ground_plane.difference(resonator_trace))
    ground_plane = ground_plane.buffer(0)

    # --- Ports & Metadata Extraction ---
    port1 = Port(position=feed_path[0], direction=(-1.0, 0.0), width_m=params.feed_width_m, impedance_ohms=params.target_z0_ohms)
    port2 = Port(position=feed_path[-1], direction=(1.0, 0.0), width_m=params.feed_width_m, impedance_ohms=params.target_z0_ohms)
    
    metadata = LayoutMetadata(
        bounding_box=substrate_footprint.bounds,
        metal_area_sq_m=feed_trace.area + resonator_trace.area,
        ground_area_sq_m=ground_plane.area,
        resonator_length_actual_m=achieved_res_len,
        feedline_length_m=polyline_length(feed_path)
    )

    return CPWLayout(
        substrate_footprint=substrate_footprint,
        ground_plane=ground_plane,
        feed_trace=feed_trace,
        resonator_trace=resonator_trace,
        short_strap=short_strap,
        feed_path=feed_path,
        resonator_path=resonator_path,
        port1=port1,
        port2=port2,
        metadata=metadata,
        design=res_design,
        params=params,
    )


# ---------------------------------------------------------------------
# 4. 2D polygons -> 3D solids (cadquery)
# ---------------------------------------------------------------------
def _require_cadquery():
    try:
        import cadquery  # noqa: F401
    except ImportError as e:
        raise ImportError(
            "cadquery is required for 3D solid generation. "
            "Install with: pip install cadquery"
        ) from e


def _ring_to_wire(coords, z):
    import cadquery as cq
    pts = [cq.Vector(float(x), float(y), float(z)) for x, y in coords]
    if pts[0].toTuple() != pts[-1].toTuple():
        pts.append(pts[0])
    return cq.Wire.makePolygon(pts)


def _simplify_wire(wire):
    try:
        return wire.clean()
    except Exception:
        return wire


def _as_shape(obj: Any) -> Any:
    """Return the underlying CadQuery Shape (Solid/Compound/...) whether
    `obj` is already a Shape or is a Workplane wrapping one."""
    import cadquery as cq
    if isinstance(obj, cq.Workplane):
        return obj.val()
    return obj


def polygon_to_solid(poly: Any, z: float, thickness: float) -> Any:
    _require_cadquery()
    import cadquery as cq
    from shapely.geometry import MultiPolygon

    if thickness <= 0:
        raise ValueError("Metal thickness must be > 0 for solid extrusion.")

    if isinstance(poly, MultiPolygon):
        solids = [polygon_to_solid(p, z, thickness) for p in poly.geoms]
        # Repeated 3D fuse() calls tend to leave sliver/residual faces behind,
        # which is exactly the kind of topology strict STEP importers (e.g.
        # COMSOL) reject. Bundle the already-valid solids into a Compound
        # instead of boolean-fusing them.
        compound = cq.Compound.makeCompound([s.wrapped for s in solids])
        compound = compound.clean()
        # Return a Workplane (not a raw Compound) so callers always get a
        # consistent CadQuery object type, matching the single-Polygon branch.
        return cq.Workplane("XY").add(compound)

    # Validate/clean the polygon immediately before extrusion so the CAD
    # kernel always starts from the cleanest possible input geometry
    # (removes slivers, microscopic edges, and other artifacts that
    # buffer(0) alone can leave behind).
    poly = validate_and_clean_polygon(poly)

    outer = _simplify_wire(_ring_to_wire(list(poly.exterior.coords), z))
    inners = [_simplify_wire(_ring_to_wire(list(r.coords), z)) for r in poly.interiors]

    solid = cq.Solid.extrudeLinear(outer, inners, cq.Vector(0, 0, thickness))
    solid = solid.clean()

    if not solid.isValid():
        raise RuntimeError(
            "Extruded solid is invalid (failed OpenCascade validity check). "
            "This usually indicates a degenerate or self-intersecting polygon "
            "was passed to polygon_to_solid()."
        )

    return solid


@dataclass
class CPWModel3D:
    substrate: "object"
    ground_plane: "object"
    feed_trace: "object"
    resonator_trace: "object"
    air_box: "object" | None
    layout: CPWLayout
    assembly: "object"  # CadQuery Assembly instance

    def export_step(self, filename: str, heal: bool = True):
        """
        Exports the entire assembly to a STEP file.
        If heal=True, explicitly triggers CAD topology cleanup to prevent singular edges.
        """
        _require_cadquery()
        if heal:
            # Re-fusing or calling clean ensures BRepBuilderAPI_Sewing cleans loose edges
            for name, component in self.assembly.objects.items():
                if hasattr(component.obj, 'clean'):
                    component.obj = component.obj.clean()
        self.assembly.save(filename, exportType="STEP")


def build_3d_model(layout: CPWLayout) -> CPWModel3D:
    _require_cadquery()
    import cadquery as cq

    # --- 2. Heal the polygons to remove tiny topology issues before CAD extrusion ---
    # We execute this right before extrusion to guarantee clean kernels.
    # Use the same aggressive cleaner as everywhere else in the pipeline
    # instead of a bare buffer(0), which only fixes self-intersections and
    # leaves slivers/microscopic artifacts behind.
    ground_poly = validate_and_clean_polygon(layout.ground_plane)
    feed_poly = validate_and_clean_polygon(layout.feed_trace)
    res_poly = validate_and_clean_polygon(layout.resonator_trace)

    # --- Pre-Extrusion Validity Guards ---
    if not ground_poly.is_valid:
        logger.warning("Ground plane polygon topology is broken prior to CAD extrusion.")
    if not feed_poly.is_valid:
        logger.warning("Feed trace polygon topology is broken prior to CAD extrusion.")
    if not res_poly.is_valid:
        logger.warning("Resonator trace polygon topology is broken prior to CAD extrusion.")

    # --- Polygon diagnostics ---
    # A large vertex count is a common cause of OpenCascade STEP import
    # failures, so surface it right after cleaning.
    def _vertex_count(poly_):
        from shapely.geometry import MultiPolygon
        if isinstance(poly_, MultiPolygon):
            return sum(len(part.exterior.coords) for part in poly_.geoms)
        return len(poly_.exterior.coords)

    print("\nPolygon diagnostics")
    print("-------------------------")
    print("Ground vertices    :", _vertex_count(ground_poly))
    print("Feed vertices      :", _vertex_count(feed_poly))
    print("Resonator vertices :", _vertex_count(res_poly))

    print("Ground valid :", ground_poly.is_valid)
    print("Feed valid   :", feed_poly.is_valid)
    print("Res valid    :", res_poly.is_valid)

    p = layout.params
    t_metal = p.metal_thickness_m
    minx, miny, maxx, maxy = layout.metadata.bounding_box

    # ── Substrate ──
    substrate = (
        cq.Workplane("XY")
        .box(maxx - minx, maxy - miny, p.substrate.thickness_m, centered=(False, False, False))
        .translate((minx, miny, -p.substrate.thickness_m))
        .clean()
    )

    # ── Air box ──
    air_box = None
    if p.air_box_height_m > 0:
        air_box = (
            cq.Workplane("XY")
            .box(maxx - minx, maxy - miny, p.air_box_height_m, centered=(False, False, False))
            .translate((minx, miny, 0.0))
            .clean()
        )

    # ── Metal conductors ──
    z_top = 0.0  
    ground_solid = polygon_to_solid(ground_poly, z=z_top, thickness=t_metal)
    feed_solid = polygon_to_solid(feed_poly, z=z_top, thickness=t_metal)
    resonator_solid = polygon_to_solid(res_poly, z=z_top, thickness=t_metal)

    # --- Validity guards: catch invalid solids before they ever reach
    # the STEP exporter / COMSOL's stricter OpenCascade importer ---
    # polygon_to_solid() can return either a raw Solid/Compound or a
    # Workplane wrapping one, so unwrap with _as_shape() before checking.
    for name, solid in {
        "ground": ground_solid,
        "feed": feed_solid,
        "resonator": resonator_solid,
    }.items():
        if not _as_shape(solid).isValid():
            raise RuntimeError(f"{name} solid is invalid")

    # --- Shape type diagnostics ---
    # All three should report "Solid". If any reports "Compound", "Shell",
    # or "Face" instead, that's the clue that the metal geometry (not the
    # substrate) is what COMSOL's OpenCascade importer is choking on.
    print("Ground solid:", _as_shape(ground_solid).ShapeType())
    print("Feed solid:", _as_shape(feed_solid).ShapeType())
    print("Resonator solid:", _as_shape(resonator_solid).ShapeType())

    ground_plane = cq.Workplane("XY").add(_as_shape(ground_solid))
    feed_trace = cq.Workplane("XY").add(_as_shape(feed_solid))
    resonator_trace = cq.Workplane("XY").add(_as_shape(resonator_solid))

    assembly = cq.Assembly()
    assembly.add(substrate, name="substrate")
    assembly.add(ground_plane, name="ground_plane")
    assembly.add(feed_trace, name="feed_trace")
    assembly.add(resonator_trace, name="resonator_trace")
    if air_box is not None:
        assembly.add(air_box, name="air_box")

    return CPWModel3D(
        substrate=substrate,
        ground_plane=ground_plane,
        feed_trace=feed_trace,
        resonator_trace=resonator_trace,
        air_box=air_box,
        layout=layout,
        assembly=assembly
    )


# ---------------------------------------------------------------------
# 5. High-Level API
# ---------------------------------------------------------------------
def build_design(
    f0_hz: float, 
    target_z0_ohms: float, 
    substrate: "Substrate", 
    **kwargs
) -> CPWModel3D:
    params = CPWResonatorParams(
        f0_hz=f0_hz,
        target_z0_ohms=target_z0_ohms,
        substrate=substrate,
        **kwargs
    )
    layout = build_layout(params)
    return build_3d_model(layout)


__all__ = [
    "METAL_THICKNESS",
    "CPWResonatorParams",
    "CPWLayout",
    "CPWModel3D",
    "build_layout",
    "build_3d_model",
    "build_design",
]