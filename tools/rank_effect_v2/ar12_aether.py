"""Full-blue AR9-family geometry and role palettes for AR12."""

from __future__ import annotations

from dataclasses import dataclass
import math
from types import MappingProxyType
from typing import Mapping

from xmodel_sculpt.mesh import MeshData, Vector3

from .ar11_bridge import (
    HALO_VERTICES,
    WING_ANCHOR_VERTICES,
    WING_BAND_COMPONENTS,
    _bounds,
    _components,
    _validate_halo_source,
)
from .armor_ranks import AtlasPalette, RoleAtlasDesign


AR12_HALO_SCALE = 1.10
AR12_HALO_SPAN_ENVELOPE = (1.099999, 1.100001)
AR12_WING_VERTICAL_LIFT = 0.58
AR12_WING_LATERAL_EXPANSION = 0.24
AR12_WING_INNER_LIMIT = 0.40
AR12_WING_OUTER_START = 0.60
AR12_WING_SHOULDER_WEIGHT = 0.25
AR12_WING_VERTICAL_SPAN_ENVELOPE = (1.163, 1.169)
AR12_WING_LATERAL_SPAN_ENVELOPE = (1.238, 1.242)
AR12_WING_TOP_LIFT_ENVELOPE = (0.57, 0.59)

_HALO = AtlasPalette(
    (0x08 / 255.0, 0x27 / 255.0, 0x55 / 255.0),
    (0x15 / 255.0, 0x5B / 255.0, 0x9F / 255.0),
    (0x41 / 255.0, 0x9B / 255.0, 0xD2 / 255.0),
    region=(0.0, 1.0, 0.0, 1.0),
)
_BUTTERFLY = AtlasPalette(
    (0x09 / 255.0, 0x2E / 255.0, 0x68 / 255.0),
    (0x17 / 255.0, 0x68 / 255.0, 0xB8 / 255.0),
    (0x43 / 255.0, 0xA1 / 255.0, 0xDE / 255.0),
    region=(0.0, 1.0, 0.0, 1.0),
)
_OUTER_WING = AtlasPalette(
    (0x06 / 255.0, 0x24 / 255.0, 0x5B / 255.0),
    (0x0E / 255.0, 0x55 / 255.0, 0xAC / 255.0),
    (0x2B / 255.0, 0x8A / 255.0, 0xDB / 255.0),
    region=(0.0, 1.0, 0.0, 1.0),
)
# The AR4 orbit stays saturated blue but sits one luminance step behind the
# butterfly, preserving character readability in the additive renderer.
_RUNE = AtlasPalette(
    (0x06 / 255.0, 0x27 / 255.0, 0x5C / 255.0),
    (0x12 / 255.0, 0x5A / 255.0, 0xA4 / 255.0),
    (0x37 / 255.0, 0x8F / 255.0, 0xCB / 255.0),
    region=(0.0, 1.0, 0.0, 1.0),
)
AR12_ROLE_ATLASES: Mapping[str, RoleAtlasDesign] = MappingProxyType(
    {
        "animated-core": RoleAtlasDesign(_HALO, 0.98, 214),
        "animated-butterfly": RoleAtlasDesign(_BUTTERFLY, 1.04, 232),
        "animated-rune": RoleAtlasDesign(_RUNE, 0.90, 218),
        "outer-wing": RoleAtlasDesign(_OUTER_WING, 1.01, 226),
    }
)


@dataclass(frozen=True, slots=True)
class Ar12WingMetrics:
    vertical_span_ratio: float
    lateral_span_ratio: float
    depth_span_ratio: float
    top_lift: float
    anchor_drift: float
    lateral_centroid_drift: float


def _halo_plan(mesh: MeshData) -> tuple[Vector3, ...]:
    _validate_halo_source(mesh)
    source = tuple(mesh.vertices)
    low, high = _bounds(source)
    center = tuple((low[axis] + high[axis]) / 2.0 for axis in range(3))
    return tuple(
        (
            center[0] + (point[0] - center[0]) * AR12_HALO_SCALE,
            center[1] + (point[1] - center[1]) * AR12_HALO_SCALE,
            point[2],
        )
        for point in source
    )


def _wing_plan(mesh: MeshData) -> tuple[tuple[Vector3, ...], tuple[int, ...]]:
    source = tuple(mesh.vertices)
    low, high = _bounds(source)
    lateral_axis = (low[1] + high[1]) / 2.0
    components = _components(mesh)
    centers = [
        tuple(
            sum(source[index][axis] for index in component) / len(component)
            for axis in range(3)
        )
        for component in components
    ]
    maximum_lateral_shift = (
        AR12_WING_LATERAL_EXPANSION * (high[1] - low[1]) / 2.0
    )

    output = list(source)
    anchors: list[int] = []
    bands = [0, 0, 0]
    for component, center in zip(components, centers):
        distance = abs(center[1] - lateral_axis)
        if distance <= AR12_WING_INNER_LIMIT:
            band, amount = 0, 0.0
            anchors.extend(component)
        elif distance < AR12_WING_OUTER_START:
            band, amount = 1, AR12_WING_SHOULDER_WEIGHT
        else:
            band, amount = 2, 1.0
        bands[band] += 1
        direction = 1.0 if center[1] >= lateral_axis else -1.0
        shift = (
            AR12_WING_VERTICAL_LIFT * amount,
            direction * maximum_lateral_shift * amount,
            0.0,
        )
        for index in component:
            output[index] = tuple(
                source[index][axis] + shift[axis] for axis in range(3)
            )  # type: ignore[assignment]
    if tuple(bands) != WING_BAND_COMPONENTS or len(anchors) != WING_ANCHOR_VERTICES:
        raise ValueError("AR12 AR9-family wing component bands changed")
    return tuple(output), tuple(anchors)


class Ar12HaloTransform:
    """Grow the AR9 halo in-plane while preserving its centre and depth."""

    def __init__(self) -> None:
        self._mesh: MeshData | None = None
        self._outputs: tuple[Vector3, ...] = ()

    def __call__(self, mesh: MeshData, index: int, _point: Vector3) -> Vector3:
        if mesh is not self._mesh:
            self._outputs = _halo_plan(mesh)
            self._mesh = mesh
        return self._outputs[index]


class Ar12WingTransform:
    """Lift/spread only the shoulder and outer AR9 wing components."""

    def __init__(self) -> None:
        self._mesh: MeshData | None = None
        self._outputs: tuple[Vector3, ...] = ()

    def __call__(self, mesh: MeshData, index: int, _point: Vector3) -> Vector3:
        if mesh is not self._mesh:
            self._outputs, _anchors = _wing_plan(mesh)
            self._mesh = mesh
        return self._outputs[index]


def validate_ar12_halo(source: MeshData, output: tuple[Vector3, ...]) -> None:
    planned = _halo_plan(source)
    if len(output) != HALO_VERTICES or max(
        math.dist(left, right) for left, right in zip(planned, output)
    ) > 1e-6:
        raise ValueError("AR12 halo differs from its reviewed AR9 transform")
    source_low, source_high = _bounds(tuple(source.vertices))
    output_low, output_high = _bounds(output)
    for axis in range(3):
        source_span = source_high[axis] - source_low[axis]
        output_span = output_high[axis] - output_low[axis]
        ratio = output_span / source_span
        if axis < 2:
            if not AR12_HALO_SPAN_ENVELOPE[0] <= ratio <= AR12_HALO_SPAN_ENVELOPE[1]:
                raise ValueError("AR12 halo exceeded its planar envelope")
        elif not math.isclose(ratio, 1.0, rel_tol=0.0, abs_tol=1e-7):
            raise ValueError("AR12 halo changed depth")
    source_center = tuple(
        (source_low[axis] + source_high[axis]) / 2.0 for axis in range(3)
    )
    output_center = tuple(
        (output_low[axis] + output_high[axis]) / 2.0 for axis in range(3)
    )
    if any(
        not math.isclose(before, after, rel_tol=0.0, abs_tol=1e-7)
        for before, after in zip(source_center, output_center)
    ):
        raise ValueError("AR12 halo centre drifted")


def validate_ar12_wings(
    source: MeshData, output: tuple[Vector3, ...]
) -> Ar12WingMetrics:
    planned, anchors = _wing_plan(source)
    if len(output) != len(planned) or max(
        math.dist(left, right) for left, right in zip(planned, output)
    ) > 1e-6:
        raise ValueError("AR12 wings differ from their reviewed AR9 transform")

    source_points = tuple(source.vertices)
    source_low, source_high = _bounds(source_points)
    output_low, output_high = _bounds(output)
    source_centroid = tuple(
        sum(point[axis] for point in source_points) / len(source_points)
        for axis in range(3)
    )
    output_centroid = tuple(
        sum(point[axis] for point in output) / len(output) for axis in range(3)
    )
    metrics = Ar12WingMetrics(
        (output_high[0] - output_low[0]) / (source_high[0] - source_low[0]),
        (output_high[1] - output_low[1]) / (source_high[1] - source_low[1]),
        (output_high[2] - output_low[2]) / (source_high[2] - source_low[2]),
        output_high[0] - source_high[0],
        max(math.dist(source_points[index], output[index]) for index in anchors),
        abs(output_centroid[1] - source_centroid[1]),
    )
    checks = (
        (
            AR12_WING_VERTICAL_SPAN_ENVELOPE[0]
            <= metrics.vertical_span_ratio
            <= AR12_WING_VERTICAL_SPAN_ENVELOPE[1],
            "vertical span",
        ),
        (
            AR12_WING_LATERAL_SPAN_ENVELOPE[0]
            <= metrics.lateral_span_ratio
            <= AR12_WING_LATERAL_SPAN_ENVELOPE[1],
            "lateral span",
        ),
        (math.isclose(metrics.depth_span_ratio, 1.0, abs_tol=1e-7), "depth span"),
        (
            AR12_WING_TOP_LIFT_ENVELOPE[0]
            <= metrics.top_lift
            <= AR12_WING_TOP_LIFT_ENVELOPE[1],
            "top lift",
        ),
        (metrics.anchor_drift <= 1e-7, "anchor drift"),
        (metrics.lateral_centroid_drift <= 1e-6, "lateral symmetry"),
    )
    failed = [label for valid, label in checks if not valid]
    if failed:
        raise ValueError("AR12 wing invariant failed: " + ", ".join(failed))
    return metrics


def validate_ar12_role_catalogue() -> None:
    if tuple(AR12_ROLE_ATLASES) != (
        "animated-core",
        "animated-butterfly",
        "animated-rune",
        "outer-wing",
    ):
        raise ValueError("AR12 role palette catalogue is incomplete")
    for role, design in AR12_ROLE_ATLASES.items():
        palette = design.palette
        if (
            palette.region != (0.0, 1.0, 0.0, 1.0)
            or not 0.9 <= design.luma_gain <= 1.1
            or not 190 <= design.maximum_channel <= 235
        ):
            raise ValueError(f"AR12 {role} palette exceeds its safety envelope")
        for stop in (palette.shadow, palette.middle, palette.highlight):
            if not stop[2] > stop[1] > stop[0]:
                raise ValueError(f"AR12 {role} must remain visibly aether-blue")
    gains = {role: atlas.luma_gain for role, atlas in AR12_ROLE_ATLASES.items()}
    if not (
        gains["animated-rune"]
        < gains["animated-core"]
        < gains["outer-wing"]
        < gains["animated-butterfly"]
    ):
        raise ValueError("AR12 role luminance hierarchy changed")


validate_ar12_role_catalogue()


__all__ = [
    "AR12_HALO_SCALE",
    "AR12_ROLE_ATLASES",
    "AR12_WING_LATERAL_EXPANSION",
    "AR12_WING_SHOULDER_WEIGHT",
    "AR12_WING_VERTICAL_LIFT",
    "Ar12HaloTransform",
    "Ar12WingMetrics",
    "Ar12WingTransform",
    "validate_ar12_halo",
    "validate_ar12_role_catalogue",
    "validate_ar12_wings",
]
