"""Compare native JCS skinning with independently baked Blender world poses.

This reads the binary export rather than using exporter reconstruction helpers.
It verifies every bone and vertex in the bind pose and representative baked
frames, including the native Y-up presentation transform. It does not claim
in-game playback or interpolation verification. Uses only the Python stdlib.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass, field
import hashlib
import json
import math
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from erebus_lion.model_codec import expand_xof_mszip
from xmodel_sculpt.binary_x import float_list, integer_list, parse_tokens
from xmodel_sculpt.mesh import discover_meshes

IDENTITY = [float(r == c) for r in range(4) for c in range(4)]
# Independent column-vector expectation: (-X,Z,Y), up +Y and forward -Z.
# This proper rotation also turns the authored right vector; no reflection.
PRESENTATION = [-1., 0., 0., 0., 0., 0., 1., 0.,
                0., 1., 0., 0., 0., 0., 0., 1.]
ACTION_NAMES = {"idle": "nomal_stand", "move": "nomal_run", "run": "nomal_run",
                "attack": "nomal_attack", "death": "nomal_die",
                "angry": "nomal_angry", "happy": "nomal_happy"}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def multiply(a, b):
    return [sum(a[r * 4 + k] * b[k * 4 + c] for k in range(4))
            for r in range(4) for c in range(4)]


def transpose(a):
    return [a[c * 4 + r] for r in range(4) for c in range(4)]


def column_point(matrix, point):
    v = (*point, 1.)
    return [sum(matrix[r * 4 + c] * v[c] for c in range(4)) for r in range(3)]


def row_point(point, matrix):
    v = (*point, 1.)
    return [sum(v[r] * matrix[r * 4 + c] for r in range(4)) for c in range(3)]


def matrix_values(values, label):
    require(len(values) == 16 and all(math.isfinite(v) for v in values),
            f"{label}: expected 16 finite matrix values")
    return values


@dataclass
class Node:
    kind: str
    name: str
    data: list = field(default_factory=list)
    children: list = field(default_factory=list)
    references: list = field(default_factory=list)


def read_nodes(tokens):
    pairs, stack = {}, []
    for index, token in enumerate(tokens):
        if token.kind == 10:
            stack.append(index)
        elif token.kind == 11:
            require(stack, "Unmatched binary-X closing brace")
            pairs[stack.pop()] = index
    require(not stack, "Unmatched binary-X opening brace")

    def decode(value):
        return value.decode("ascii")

    def body(start, end, parent):
        cursor = start
        while cursor < end:
            token = tokens[cursor]
            if token.kind == 31:
                require(cursor + 2 < end and tokens[cursor + 2].kind == 10,
                        "Malformed template declaration")
                cursor = pairs[cursor + 2] + 1
            elif token.kind == 1:
                kind, name = decode(token.value), ""
                opening = cursor + 1
                if tokens[opening].kind == 1:
                    name = decode(tokens[opening].value)
                    opening += 1
                require(tokens[opening].kind == 10, f"{kind}: missing object brace")
                closing = pairs[opening]
                child = Node(kind, name)
                body(opening + 1, closing, child)
                parent.children.append(child)
                cursor = closing + 1
            elif token.kind == 10:
                closing = pairs[cursor]
                require(closing == cursor + 2 and tokens[cursor + 1].kind == 1,
                        "Unsupported native object reference")
                parent.references.append(decode(tokens[cursor + 1].value))
                cursor = closing + 1
            else:
                parent.data.append(token)
                cursor += 1
    root = Node("file", "")
    body(0, len(tokens), root)
    return root


def children(node, kind):
    return [child for child in node.children if child.kind == kind]


def one_child(node, kind):
    matches = children(node, kind)
    require(len(matches) == 1, f"{node.kind} {node.name}: expected one {kind}")
    return matches[0]


def parse_native(encoded):
    data = expand_xof_mszip(encoded, "animation-validation.jcs")
    tokens = parse_tokens(data)
    meshes = discover_meshes(data, tokens)
    require(len(meshes) == 1, "Animation validation requires one native Mesh")
    mesh, root = meshes[0], read_nodes(tokens)
    rest, parents, mesh_nodes = {}, {}, []

    def frames(node, parent=None):
        for child in node.children:
            if child.kind == "Frame":
                require(child.name and child.name not in rest,
                        f"Duplicate or unnamed Frame: {child.name!r}")
                matrix = one_child(child, "FrameTransformMatrix")
                require(len(matrix.data) == 1, f"Frame {child.name}: invalid rest matrix")
                rest[child.name] = matrix_values(float_list(data, matrix.data[0]), child.name)
                parents[child.name] = parent
                frames(child, child.name)
            elif child.kind == "Mesh":
                mesh_nodes.append(child)
    frames(root)
    require(len(mesh_nodes) == 1, "Native Mesh must be inside the Frame hierarchy")
    skins, weights = {}, [{} for _ in mesh.vertices]
    for skin in children(mesh_nodes[0], "SkinWeights"):
        require(len(skin.data) == 3 and skin.data[0].kind == 2,
                "Invalid SkinWeights token layout")
        bone = skin.data[0].value.decode("ascii")
        require(bone in rest and bone not in skins, f"Missing/duplicate skin bone {bone}")
        ints, values = integer_list(data, skin.data[1]), float_list(data, skin.data[2])
        count = ints[0]
        require(count > 0 and len(ints) == count + 1 and len(values) == count + 16,
                f"Skin bone {bone}: inconsistent weight/index counts")
        skins[bone] = matrix_values(values[-16:], f"{bone} offset")
        for index, weight in zip(ints[1:], values[:count]):
            require(index < len(weights) and 0 < weight <= 1 and math.isfinite(weight),
                    f"Skin bone {bone}: invalid vertex index or weight")
            require(bone not in weights[index], f"Skin bone {bone}: duplicate vertex {index}")
            weights[index][bone] = weight
    for index, value in enumerate(weights):
        require(value and abs(sum(value.values()) - 1) <= 1e-5,
                f"Native vertex {index}: missing weights or sum differs from one")
    sets = {}
    for animation_set in children(root, "AnimationSet"):
        label = animation_set.name
        require(label and label not in sets, f"Duplicate/unnamed animation set {label!r}")
        tracks = {}
        for animation in children(animation_set, "Animation"):
            require(len(animation.references) == 1, f"{label}: animation needs one bone reference")
            bone = animation.references[0]
            require(bone in rest and bone not in tracks, f"{label}: missing/duplicate bone {bone}")
            key = one_child(animation, "AnimationKey")
            require(len(key.data) >= 4 and len(key.data) % 2 == 0,
                    f"{label}/{bone}: invalid matrix-key layout")
            header = integer_list(data, key.data[0])
            require(len(header) == 4 and header[0] == 4 and header[1] == len(key.data) // 2,
                    f"{label}/{bone}: expected AnimationKey type 4 and exact key count")
            samples, previous = {}, -1
            for offset in range(0, len(key.data), 2):
                ints = integer_list(data, key.data[offset])
                if offset == 0:
                    ints = ints[2:]
                require(len(ints) == 2 and ints[1] == 16 and ints[0] > previous,
                        f"{label}/{bone}: invalid or non-increasing matrix-key time")
                previous = ints[0]
                samples[previous] = matrix_values(float_list(data, key.data[offset + 1]),
                                                   f"{label}/{bone}/{previous}")
            tracks[bone] = samples
        sets[label] = tracks
    return mesh, rest, parents, skins, weights, sets


def compare(document, encoded, *, samples=5, ticks_per_second=4800, tolerance=2e-5):
    require(document.get("coordinate_system") == "RH_Z_UP_FRONT_MINUS_Y",
            "Unsupported authored coordinate system")
    require(samples >= 2 and ticks_per_second > 0 and tolerance > 0,
            "Samples, export timebase, or tolerance is invalid")
    mesh, rest, parents, skins, native_weights, sets = parse_native(encoded)
    presentation = rest.get("BloodfangPresentationRoot")
    require(presentation is not None and parents["BloodfangPresentationRoot"] is None,
            "Missing top-level Bloodfang presentation frame")
    require(max(abs(a - b) for a, b in zip(presentation, transpose(PRESENTATION))) <= tolerance,
            "Native facing mismatch: authored front -Y must map to native -Z")
    bones = {bone["name"]: bone for bone in document["bones"]}
    require(bones and len(bones) == len(document["bones"]), "Missing/duplicate authored bone names")
    require(set(bones) <= set(rest), f"Missing native frames: {sorted(set(bones) - set(rest))}")
    require(set(skins) <= set(bones), "Native skin uses a bone absent from authored JSON")
    for name, bone in bones.items():
        require(bone["parent"] is None or bone["parent"] in bones,
                f"{name}: missing authored parent")
        if bone["parent"] is not None:
            require(parents[name] == bone["parent"], f"{name}: native bone parent differs")
        for field_name in ("matrix_world", "inverse_bind_matrix"):
            require(field_name in bone, f"{name}: missing authored {field_name}")
            matrix_values(bone[field_name], f"{name} {field_name}")
        identity = multiply(bone["matrix_world"], bone["inverse_bind_matrix"])
        require(max(abs(a - b) for a, b in zip(identity, IDENTITY)) <= tolerance,
                f"{name}: authored inverse bind matrix is inconsistent")
    require(len(mesh.faces) == len(document["triangles"]), "Native/authored triangle counts differ")
    mapping = {}
    for face, triangle in zip(mesh.faces, document["triangles"]):
        require(len(face) == len(triangle["vertices"]) == 3, "Expected triangular topology")
        for native, source in zip(face, triangle["vertices"]):
            require(0 <= source < len(document["vertices"]), "Invalid authored vertex index")
            require(native not in mapping or mapping[native] == source,
                    f"Native vertex {native} maps to inconsistent authored triangle corners")
            mapping[native] = source
    require(len(mapping) == len(mesh.vertices), "Unreferenced native vertices cannot be matched")
    source_weights = {}
    for native, source in mapping.items():
        vertex = document["vertices"][source]
        require("weights" in vertex and vertex["weights"],
                f"Authored vertex {source}: missing skin weights")
        require(max(abs(a - b) for a, b in zip(mesh.vertices[native], vertex["position"])) <= tolerance,
                f"Native vertex {native}: bind-space position differs from authored vertex {source}")
        weights = {entry["bone"]: entry["weight"] for entry in vertex["weights"]}
        require(len(weights) == len(vertex["weights"]) and weights and set(weights) <= set(bones),
                f"Authored vertex {source}: missing, duplicate, or unknown bone weights")
        require(all(math.isfinite(w) and 0 < w <= 1 for w in weights.values())
                and abs(sum(weights.values()) - 1) <= 1e-5,
                f"Authored vertex {source}: invalid weights")
        require(set(weights) == set(native_weights[native]),
                f"Native vertex {native}: skin influence bones differ from authored vertex {source}")
        require(max(abs(w - native_weights[native][name]) for name, w in weights.items()) <= tolerance,
                f"Native vertex {native}: skin weights differ from authored vertex {source}")
        source_weights[source] = weights

    def evaluate(label, native_pose, authored_pose):
        world, visiting = {}, set()
        def native_world(name):
            if name not in world:
                require(name not in visiting, f"{label}: cyclic native bone hierarchy")
                visiting.add(name)
                local = native_pose.get(name, rest[name])
                parent = parents[name]
                world[name] = multiply(local, native_world(parent)) if parent else local
                visiting.remove(name)
            return world[name]
        matrix_error = 0.
        for name in bones:
            expected = multiply(PRESENTATION, matrix_values(authored_pose[name], f"{label}/{name}"))
            error = max(abs(a - b) for a, b in zip(transpose(native_world(name)), expected))
            matrix_error = max(matrix_error, error)
            require(error <= tolerance, f"{label}: bone {name} world-pose mismatch ({error:.7g})")
        native_deform = {name: multiply(offset, native_world(name)) for name, offset in skins.items()}
        expected_deform = {name: multiply(PRESENTATION, multiply(authored_pose[name], bone["inverse_bind_matrix"]))
                           for name, bone in bones.items()}
        vertex_error = 0.
        for native, source in mapping.items():
            native_pos, expected_pos = [0., 0., 0.], [0., 0., 0.]
            for name, weight in native_weights[native].items():
                point = row_point(mesh.vertices[native], native_deform[name])
                native_pos = [a + weight * b for a, b in zip(native_pos, point)]
            for name, weight in source_weights[source].items():
                point = column_point(expected_deform[name], document["vertices"][source]["position"])
                expected_pos = [a + weight * b for a, b in zip(expected_pos, point)]
            error = math.dist(native_pos, expected_pos)
            vertex_error = max(vertex_error, error)
            require(error <= tolerance,
                    f"{label}: native vertex {native}/authored {source} deformation mismatch ({error:.7g})")
        return {"maximum_bone_matrix_error": matrix_error, "maximum_vertex_distance": vertex_error}

    bind = evaluate("bind pose", {}, {name: bone["matrix_world"] for name, bone in bones.items()})
    expected_sets = {}
    for action in document["actions"]:
        label = ACTION_NAMES.get(action["name"].lower(), action["name"])
        require(label not in expected_sets, f"Duplicate authored action mapping {label}")
        expected_sets[label] = action
        if label == "nomal_attack":
            expected_sets["nomal_attack_01"] = action
    require(set(sets) == set(expected_sets),
            f"Animation sets differ: missing {sorted(set(expected_sets) - set(sets))}; unexpected {sorted(set(sets) - set(expected_sets))}")
    reports = []
    for label, action in expected_sets.items():
        frames = action["keyframes"]
        require(len(frames) >= 2 and action["fps"] > 0, f"{label}: invalid authored frame sequence")
        times = [round((f["frame"] - action["frame_start"]) * ticks_per_second / action["fps"]) for f in frames]
        require(all(b > a for a, b in zip(times, times[1:])), f"{label}: duplicate authored key times")
        tracks = sets[label]
        require(set(tracks) == set(bones), f"{label}: missing or unexpected animation bone tracks")
        for name, keys in tracks.items():
            require(list(keys) == times, f"{label}/{name}: native key times differ from authored export times")
        count = min(samples, len(frames))
        indices = sorted({round(i * (len(frames) - 1) / (count - 1)) for i in range(count)})
        for index in indices:
            frame, tick = frames[index], times[index]
            require(set(frame["bones"]) == set(bones), f"{label}: authored pose has missing/extra bones")
            for name in bones:
                require("world_pose_matrix" in frame["bones"][name],
                        f"{label}/{name}: missing independently baked world_pose_matrix")
            result = evaluate(f"{label} frame {frame['frame']}",
                              {name: keys[tick] for name, keys in tracks.items()},
                              {name: frame["bones"][name]["world_pose_matrix"] for name in bones})
            reports.append({"animation": label, "authored_frame": frame["frame"], "export_tick": tick, **result})
    return {"status": "native-skinning-matches-authored-world-poses", "bones": len(bones),
            "skin_bones": len(skins), "vertices": len(mesh.vertices), "triangles": len(mesh.faces),
            "tolerance": tolerance, "export_ticks_per_second": ticks_per_second,
            "in_game_playback_verified": False, "interpolation_verified": False,
            "bind_pose": bind, "animation_sets": list(expected_sets), "sampled_poses": reports,
            "vertex_comparisons": len(mesh.vertices) * (len(reports) + 1),
            "maximum_vertex_distance": max([bind["maximum_vertex_distance"]] + [r["maximum_vertex_distance"] for r in reports])}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("document", type=Path)
    parser.add_argument("model", type=Path)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--samples", type=int, default=5, help="Baked poses per animation, including endpoints")
    parser.add_argument("--ticks-per-second", type=int, default=4800, help="Chosen export timebase, not measured game speed")
    parser.add_argument("--tolerance", type=float, default=2e-5)
    args = parser.parse_args()
    source, encoded = args.document.read_bytes(), args.model.read_bytes()
    result = compare(json.loads(source), encoded, samples=args.samples,
                     ticks_per_second=args.ticks_per_second, tolerance=args.tolerance)
    result.update({"document": str(args.document), "model": str(args.model),
                   "document_sha256": hashlib.sha256(source).hexdigest(),
                   "model_sha256": hashlib.sha256(encoded).hexdigest()})
    if args.report:
        args.report.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in result.items() if k != "sampled_poses"}, indent=2))


if __name__ == "__main__":
    main()
