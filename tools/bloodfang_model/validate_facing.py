"""Check the authored front against the native pet's actual skinned facing.

Stock Dragon head and muzzle lie at negative native Z, with the tail at
positive Z. This check deliberately defines that geometric contract without
importing the exporter's presentation matrix or the pose validator's constant.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

from validate_animation import multiply, parse_native, require, row_point


def check_basis(matrix, tolerance=2e-5):
    expected = [((0., -1., 0.), (0., 0., -1.)),
                ((0., 0., 1.), (0., 1., 0.)),
                ((1., 0., 0.), (-1., 0., 0.))]
    for source, target in expected:
        require(math.dist(row_point(source, matrix), target) <= tolerance,
                "Facing contract failed: front -Y -> -Z, up +Z -> +Y, right +X -> -X")
    a, b, c = [matrix[i:i + 3] for i in (0, 4, 8)]
    determinant = (a[0] * (b[1] * c[2] - b[2] * c[1])
                   - a[1] * (b[0] * c[2] - b[2] * c[0])
                   + a[2] * (b[0] * c[1] - b[1] * c[0]))
    require(abs(determinant - 1.) <= tolerance,
            "Presentation must be a proper rotation, not a reflected mesh")
    return {"authored_forward": [0, -1, 0], "native_forward": [0, 0, -1],
            "native_up": [0, 1, 0], "determinant": determinant}


def group_centroid(positions, weights, group):
    total, centroid = 0., [0., 0., 0.]
    for position, influences in zip(positions, weights):
        weight = sum(value for name, value in influences.items() if name in group)
        total += weight
        centroid = [a + weight * b for a, b in zip(centroid, position)]
    require(total > 0, f"No skinned vertices for facing group {sorted(group)}")
    return [value / total for value in centroid]


def validate(document, encoded):
    require(document.get("coordinate_system") == "RH_Z_UP_FRONT_MINUS_Y",
            "Facing check requires authored front -Y")
    mesh, rest, parents, skins, weights, sets = parse_native(encoded)
    presentation = rest.get("BloodfangPresentationRoot")
    require(presentation is not None and parents["BloodfangPresentationRoot"] is None,
            "Missing top-level presentation frame")
    basis = check_basis(presentation)
    head = {name for name in skins if name.lower() in {"head", "jaw"}}
    tail = {name for name in skins if name.lower().startswith("tail")}
    require(head and tail, "Facing check requires original head/jaw and tail skin bones")
    source_weights = [{w["bone"]: w["weight"] for w in v["weights"]}
                      for v in document["vertices"]]
    source_positions = [v["position"] for v in document["vertices"]]
    source_head = group_centroid(source_positions, source_weights, head)
    source_tail = group_centroid(source_positions, source_weights, tail)
    require(source_head[1] < source_tail[1] - .05,
            "Authored head must lie ahead of its tail along -Y")
    require("nomal_run" in sets, "Missing native movement animation")
    tracks = sets["nomal_run"]
    times = sorted(set.intersection(*(set(keys) for keys in tracks.values())))
    require(len(times) >= 3, "Movement facing check needs at least three baked poses")
    samples = [("bind", {})]
    for index in sorted({0, (len(times) - 1) // 2, len(times) - 1}):
        tick = times[index]
        samples.append((f"nomal_run/{tick}", {name: keys[tick] for name, keys in tracks.items()}))
    rows = []
    for label, pose in samples:
        world = {}
        def bone_world(name):
            if name not in world:
                local, parent = pose.get(name, rest[name]), parents[name]
                world[name] = multiply(local, bone_world(parent)) if parent else local
            return world[name]
        transforms = {name: multiply(offset, bone_world(name)) for name, offset in skins.items()}
        positions = []
        for position, influences in zip(mesh.vertices, weights):
            points = [(row_point(position, transforms[name]), weight)
                      for name, weight in influences.items()]
            positions.append([sum(point[axis] * weight for point, weight in points) for axis in range(3)])
        head_center = group_centroid(positions, weights, head)
        tail_center = group_centroid(positions, weights, tail)
        # A native heading-zero movement along -Z must lead with the head.
        forward_margin = tail_center[2] - head_center[2]
        require(forward_margin > .05,
                f"{label}: head trails tail in native -Z movement (margin {forward_margin:.6g})")
        rows.append({"pose": label, "head_centroid": head_center, "tail_centroid": tail_center,
                     "head_ahead_along_native_minus_z": forward_margin})
    return {"status": "passed", "model_sha256": hashlib.sha256(encoded).hexdigest(),
            "basis": basis, "authored_head_centroid": source_head,
            "authored_tail_centroid": source_tail, "native_skinned_poses": rows}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("document", type=Path)
    parser.add_argument("model", type=Path)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    result = validate(json.loads(args.document.read_text(encoding="utf-8")), args.model.read_bytes())
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
