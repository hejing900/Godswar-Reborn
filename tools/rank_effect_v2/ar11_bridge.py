"""Bounded AR9-family geometry transforms for the animated AR11 bridge rank."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import hashlib
import math
import struct

from xmodel_sculpt.mesh import MeshData, Vector3


HALO_SCALE = 1.05
WING_VERTICAL_LIFT = 0.42
WING_LATERAL_EXPANSION = 0.18
WING_INNER_LIMIT = 0.40
WING_OUTER_START = 0.60
WING_SHOULDER_WEIGHT = 0.25
WING_VERTICAL_SPAN_ENVELOPE = (1.115, 1.125)
WING_LATERAL_SPAN_ENVELOPE = (1.175, 1.185)
WING_TOP_LIFT_ENVELOPE = (0.41, 0.43)

HALO_VERTICES = 116
HALO_FACES = 100
HALO_SOURCE_BOUNDS = (
    (-1.0, -0.9727795124053955, -1.0),
    (3.782240298733086e-09, 0.9727795124053955, 1.0025540590286255),
)
HALO_FACE_WIDTHS = Counter({3: 100})
HALO_MESH_SHA256 = "20cbabc38435e173a8468aea8730c962fe1d2d2c0f4c8f3e591dd3c515136d12"
WING_VERTICES = 976
WING_FACES = 848
WING_SOURCE_BOUNDS = (
    (0.16377556324005127, -2.3022091388702393, -1.8261324167251587),
    (2.7877533435821533, 2.181636095046997, -0.05695020779967308),
)
WING_FACE_WIDTHS = Counter({3: 848})
WING_MESH_SHA256 = "80b4c41d7421eec3a1119858eb566af20c7bbd92fb106978b0cee21dbd980f74"
WING_COMPONENTS = 64
WING_COMPONENT_SIZES = Counter({16: 56, 10: 8})
WING_COMPONENT_FACE_COUNTS = Counter({14: 56, 8: 8})
WING_BAND_COMPONENTS = (32, 12, 20)
WING_ANCHOR_VERTICES = 512
WING_CHANGED_VERTICES = 464


@dataclass(frozen=True, slots=True)
class Ar11WingMetrics:
    vertical_span_ratio: float
    lateral_span_ratio: float
    depth_span_ratio: float
    top_lift: float
    anchor_drift: float
    lateral_centroid_drift: float


def _bounds(points: tuple[Vector3, ...]) -> tuple[Vector3, Vector3]:
    low = tuple(min(point[axis] for point in points) for axis in range(3))
    high = tuple(max(point[axis] for point in points) for axis in range(3))
    return low, high  # type: ignore[return-value]


def _mesh_sha256(mesh: MeshData) -> str:
    """Fingerprint the exact vertex and face payload exposed by ``MeshData``."""

    digest = hashlib.sha256()
    digest.update(struct.pack("<II", len(mesh.vertices), len(mesh.faces)))
    for point in mesh.vertices:
        digest.update(struct.pack("<3f", *point))
    for face in mesh.faces:
        digest.update(struct.pack("<I", len(face)))
        digest.update(struct.pack(f"<{len(face)}I", *face))
    return digest.hexdigest()


def _validate_source_mesh(
    mesh: MeshData,
    *,
    label: str,
    vertices: int,
    faces: int,
    bounds: tuple[Vector3, Vector3],
    face_widths: Counter[int],
    fingerprint: str,
) -> None:
    if len(mesh.vertices) != vertices or len(mesh.faces) != faces:
        raise ValueError(f"{label} vertex/face contract changed")
    if mesh.index != 0 or mesh.name != b"" or mesh.normals or mesh.normal_faces:
        raise ValueError(f"{label} mesh container contract changed")
    if Counter(map(len, mesh.faces)) != face_widths:
        raise ValueError(f"{label} face-width contract changed")
    if any(
        not math.isclose(actual, expected, rel_tol=0.0, abs_tol=1e-6)
        for actual_vector, expected_vector in zip(mesh.bounds, bounds)
        for actual, expected in zip(actual_vector, expected_vector)
    ):
        raise ValueError(f"{label} source bounds changed")
    if _mesh_sha256(mesh) != fingerprint:
        raise ValueError(f"{label} reviewed mesh fingerprint changed")


def _validate_halo_source(mesh: MeshData) -> None:
    _validate_source_mesh(
        mesh,
        label="AR11 halo",
        vertices=HALO_VERTICES,
        faces=HALO_FACES,
        bounds=HALO_SOURCE_BOUNDS,
        face_widths=HALO_FACE_WIDTHS,
        fingerprint=HALO_MESH_SHA256,
    )


def _validate_wing_source(mesh: MeshData) -> None:
    _validate_source_mesh(
        mesh,
        label="AR11 wings",
        vertices=WING_VERTICES,
        faces=WING_FACES,
        bounds=WING_SOURCE_BOUNDS,
        face_widths=WING_FACE_WIDTHS,
        fingerprint=WING_MESH_SHA256,
    )


def _components(mesh: MeshData) -> tuple[tuple[int, ...], ...]:
    _validate_wing_source(mesh)
    adjacency = [set() for _ in mesh.vertices]
    for face in mesh.faces:
        for left, right in zip(face, face[1:] + face[:1]):
            adjacency[left].add(right)
            adjacency[right].add(left)
    found: list[tuple[int, ...]] = []
    visited: set[int] = set()
    for start in range(len(mesh.vertices)):
        if start in visited:
            continue
        pending = [start]
        visited.add(start)
        component: list[int] = []
        while pending:
            current = pending.pop()
            component.append(current)
            for neighbour in adjacency[current]:
                if neighbour not in visited:
                    visited.add(neighbour)
                    pending.append(neighbour)
        found.append(tuple(sorted(component)))
    if len(found) != WING_COMPONENTS or Counter(map(len, found)) != WING_COMPONENT_SIZES:
        raise ValueError("AR9 animated-wing component topology changed")
    component_for_vertex = [-1] * len(mesh.vertices)
    for component_index, component in enumerate(found):
        for vertex_index in component:
            component_for_vertex[vertex_index] = component_index
    component_faces = [0] * len(found)
    for face in mesh.faces:
        owners = {component_for_vertex[index] for index in face}
        if len(owners) != 1 or -1 in owners:
            raise ValueError("AR9 animated-wing face crosses component boundaries")
        component_faces[owners.pop()] += 1
    if Counter(component_faces) != WING_COMPONENT_FACE_COUNTS:
        raise ValueError("AR9 animated-wing component face histogram changed")
    return tuple(found)


def _halo_plan(mesh: MeshData) -> tuple[Vector3, ...]:
    _validate_halo_source(mesh)
    source = tuple(mesh.vertices)
    low, high = _bounds(source)
    center = tuple((low[axis] + high[axis]) / 2.0 for axis in range(3))
    return tuple(
        (
            center[0] + (point[0] - center[0]) * HALO_SCALE,
            center[1] + (point[1] - center[1]) * HALO_SCALE,
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
        WING_LATERAL_EXPANSION * (high[1] - low[1]) / 2.0
    )

    output = list(source)
    anchors: list[int] = []
    bands = [0, 0, 0]
    for component, center in zip(components, centers):
        distance = abs(center[1] - lateral_axis)
        if distance <= WING_INNER_LIMIT:
            band, amount = 0, 0.0
            anchors.extend(component)
        elif distance < WING_OUTER_START:
            band, amount = 1, WING_SHOULDER_WEIGHT
        else:
            band, amount = 2, 1.0
        bands[band] += 1
        direction = 1.0 if center[1] >= lateral_axis else -1.0
        shift = (
            WING_VERTICAL_LIFT * amount,
            direction * maximum_lateral_shift * amount,
            0.0,
        )
        for index in component:
            output[index] = tuple(
                source[index][axis] + shift[axis] for axis in range(3)
            )  # type: ignore[assignment]
    if tuple(bands) != WING_BAND_COMPONENTS or len(anchors) != WING_ANCHOR_VERTICES:
        raise ValueError("AR11 wing component bands changed")
    return tuple(output), tuple(anchors)


class Ar11HaloTransform:
    """Increase the animated AR9 halo in-plane without moving it in depth."""

    def __init__(self) -> None:
        self._mesh: MeshData | None = None
        self._outputs: tuple[Vector3, ...] = ()

    def _plan(self, mesh: MeshData) -> tuple[Vector3, ...]:
        return _halo_plan(mesh)

    def __call__(self, mesh: MeshData, index: int, _point: Vector3) -> Vector3:
        if mesh is not self._mesh:
            self._outputs = self._plan(mesh)
            self._mesh = mesh
        return self._outputs[index]


class Ar11WingTransform:
    """Lift and spread only the outer animated AR9 wing components."""

    def __init__(self) -> None:
        self._mesh: MeshData | None = None
        self._outputs: tuple[Vector3, ...] = ()

    def __call__(self, mesh: MeshData, index: int, _point: Vector3) -> Vector3:
        if mesh is not self._mesh:
            self._outputs, _anchors = _wing_plan(mesh)
            self._mesh = mesh
        return self._outputs[index]


def validate_ar11_halo(source: MeshData, output: tuple[Vector3, ...]) -> None:
    planned = _halo_plan(source)
    if len(output) != len(planned):
        raise ValueError("AR11 halo vertex count changed")
    maximum_error = max(math.dist(left, right) for left, right in zip(planned, output))
    if maximum_error > 1e-6:
        raise ValueError("AR11 halo output differs from the reviewed planar transform")
    if any(
        not math.isclose(before[2], after[2], rel_tol=0.0, abs_tol=1e-7)
        for before, after in zip(source.vertices, output)
    ):
        raise ValueError("AR11 halo changed per-vertex depth")
    source_low, source_high = _bounds(tuple(source.vertices))
    output_low, output_high = _bounds(output)
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
        raise ValueError("AR11 halo center drifted")
    for axis, expected_ratio in enumerate((HALO_SCALE, HALO_SCALE, 1.0)):
        source_span = source_high[axis] - source_low[axis]
        output_span = output_high[axis] - output_low[axis]
        if not math.isclose(output_span / source_span, expected_ratio, abs_tol=1e-6):
            raise ValueError("AR11 halo did not retain its bounded planar scale")


def validate_ar11_wings(
    source: MeshData, output: tuple[Vector3, ...]
) -> Ar11WingMetrics:
    planned, anchors = _wing_plan(source)
    if len(output) != len(planned):
        raise ValueError("AR11 wing vertex count changed")
    maximum_error = max(math.dist(left, right) for left, right in zip(planned, output))
    if maximum_error > 1e-6:
        raise ValueError("AR11 wing output differs from the reviewed transform")

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
    metrics = Ar11WingMetrics(
        (output_high[0] - output_low[0]) / (source_high[0] - source_low[0]),
        (output_high[1] - output_low[1]) / (source_high[1] - source_low[1]),
        (output_high[2] - output_low[2]) / (source_high[2] - source_low[2]),
        output_high[0] - source_high[0],
        max(math.dist(source_points[index], output[index]) for index in anchors),
        abs(output_centroid[1] - source_centroid[1]),
    )
    checks = (
        (
            WING_VERTICAL_SPAN_ENVELOPE[0]
            <= metrics.vertical_span_ratio
            <= WING_VERTICAL_SPAN_ENVELOPE[1],
            "vertical span",
        ),
        (
            WING_LATERAL_SPAN_ENVELOPE[0]
            <= metrics.lateral_span_ratio
            <= WING_LATERAL_SPAN_ENVELOPE[1],
            "lateral span",
        ),
        (math.isclose(metrics.depth_span_ratio, 1.0, abs_tol=1e-7), "depth span"),
        (
            WING_TOP_LIFT_ENVELOPE[0]
            <= metrics.top_lift
            <= WING_TOP_LIFT_ENVELOPE[1],
            "top lift",
        ),
        (metrics.anchor_drift <= 1e-7, "anchor drift"),
        (metrics.lateral_centroid_drift <= 0.005, "lateral symmetry"),
    )
    failed = [label for valid, label in checks if not valid]
    if failed:
        raise ValueError("AR11 wing invariant failed: " + ", ".join(failed))
    return metrics
