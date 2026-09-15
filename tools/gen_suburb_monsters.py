"""Plan the Sparta_Newbie (map 4) population from the quest tables.

Rules, taken from the map that already ships (map 0) and from the quest chain:

  * every kill objective of the chain that lives on map 4 becomes one spawn
    centre: the quest's own coordinate from Quest.xml, and the species its
    objective names;
  * the range of a centre is inferred from the quest points themselves - half
    the distance to the nearest other point, kept inside a sane band so a point
    is neither a dot nor a blob;
  * the number of monsters is the map-0 relationship between how many kills the
    quest asks for and how many of that species live around its point (map 0
    keeps 3-5 for a ten-kill quest, about 11-15 for twenty, 17-25 for thirty);
  * monsters are dealt evenly inside the range, on a centre point and rings, so
    a species is neither stacked on the objective nor spread off the ground the
    quest sends the player to;
  * a quest whose species the client ships nowhere on map 4 (the retired
    MinLevel-200 rows) plans nothing: there is no model to spawn.

Output: a readable plan next to the other notes, and the C# table the server
compiles in (SpartaNewbieSpawnPlan.Generated.cs).
"""

import importlib.util
import math
import os
import re
import sys

GENERATOR = r"D:\Godswar-Reborn-main\tools\gen_quest_objectives.py"
TEMPLATES = r"D:\Godswar Origin\npc-translation\monster_templates.txt"
PLAN_TEXT = r"D:\Godswar Origin\npc-translation\suburb-spawn-plan.txt"
MAP_SEEDS = (r"D:\Godswar-Reborn-main\src\Godswar.Server\State"
             r"\MapTemplateSeed.Generated.cs")
PLAN_DIR = (r"D:\Godswar-Reborn-main\src\Godswar.Server\Infrastructure"
            r"\WorldContent")

# The newbie map of each camp, and the class the generated plan lands in. Sparta
# is planned by this generator: no capture of its newbie map exists, so its
# population is derived from the quest chain. Athens is deliberately absent -
# that camp's city and newbie maps both replay the reference's own captured
# spawns (AthensCapturedSpawnPlan.Generated.cs), so a generated stand-in would
# only duplicate monsters.
PLANS = {
    4: ("SpartaNewbieSpawnPlan", "sparta-newbie"),
}

# Retired rows carry the level sentinel; nothing can reach them any more, so
# their legacy species are not a reason to invent monsters.
LEGACY_LEVEL = 200

# Range of a spawn centre, in map units, when the quest-point spacing allows.
MIN_RADIUS = 12.0
MAX_RADIUS = 30.0

# Monsters per spawn centre, by the kills the quest asks for. Every band is the
# count map 0 actually keeps within the same range of its own objective.
NEED_SPAWNS = ((5, 3), (10, 5), (15, 11), (20, 15), (30, 22))
OVERFLOW_SPAWNS = 30

# A single-target boss or elite is one monster, however map 0 pads its trash.
SOLE_TARGET_RANKS = ("boss", "elite")

# Map 0's captured tier-to-health relationship: 237 at tier 1, 681 at tier 16.
BASE_HEALTH = 237.0
HEALTH_PER_TIER = 29.6

spec = importlib.util.spec_from_file_location("gen", GENERATOR)
gen = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gen)


def fold(name):
    """Lowercase letters and digits only, without the [Elite]/[Pet] rank tags."""
    plain = re.sub(r"\[[^\]]*\]", " ", name)
    return " ".join(re.sub(r"[^0-9a-z]+", " ", plain.lower()).split())


def variants(name):
    """Every shape a plural quest target may be written in.

    The quest text says "Woodland Wolves", "Persian Spies" and "Animated Axes"
    while the client's template table holds the singular, so the plural is
    unfolded here instead of guessed at on the template side.
    """
    base = fold(name)
    words = base.split()
    if not words:
        return set()
    word = words[-1]
    stems = {word}
    if word.endswith("s"):
        stems.add(word[:-1])
    if word.endswith("es"):
        stems.add(word[:-2])
    if word.endswith("ies"):
        stems.add(word[:-3] + "y")
    if word.endswith("ves"):
        stems.add(word[:-3] + "f")
    found = {base}
    for stem in stems:
        found.add(" ".join(words[:-1] + [stem]).strip())
    return {value for value in found if value}


def load_templates():
    """Every (template key, display name, rank, map id) the client ships."""
    rows = []
    with open(TEMPLATES, "r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            parts = line.strip().split("|")
            if len(parts) != 4:
                continue
            key, name, rank, map_id = parts
            rows.append((key, name, rank, int(map_id)))
    return rows


def resolve_template(target, map_id, templates):
    """The template the client ships for this target on this map, if any.

    Only templates registered against this map are usable: the template key
    carries the scene the client builds the model in, so a species borrowed from
    another map would be spawned against the wrong scene.
    """
    shapes = variants(target)
    if not shapes:
        return None, "empty target"
    on_map = [row for row in templates if row[3] == map_id]
    for key, name, _, _ in on_map:
        if fold(name) == fold(target):
            return (key, name), ""
    for key, name, _, _ in on_map:
        if fold(name) in shapes:
            return (key, name), "plural"
    elsewhere = [row for row in templates
                 if row[3] != map_id and fold(row[1]) in shapes]
    if elsewhere:
        return None, f"client ships it on map {elsewhere[0][3]} only"
    return None, "no template for this map"


def objectives(rows, chain):
    """One entry per kill objective: quest, species, kills, map, point, level."""
    found = []
    for quest_id in chain:
        attributes = rows.get(quest_id)
        if attributes is None:
            continue
        text = gen.objectives_text(quest_id)
        if not text:
            continue
        parsed = gen.parse_objectives(text)
        spots = gen.positions(attributes)
        if not parsed or not spots:
            continue
        level = int(attributes.get("MinLevel") or 0)
        for index, (target, count) in enumerate(parsed):
            map_id, x, z = spots[min(index, len(spots) - 1)]
            found.append((quest_id, target, count, map_id, x, z, level))
    return found


def spawn_count(need, rank):
    if need <= 1 and rank in SOLE_TARGET_RANKS:
        return 1
    for limit, count in NEED_SPAWNS:
        if need <= limit:
            return count
    return OVERFLOW_SPAWNS


def ring_points(cx, cz, radius, count, phase):
    """A centre point plus one or two evenly spaced rings inside the range."""
    if count <= 0:
        return []
    if count == 1:
        return [(cx, cz)]
    points = [(cx, cz)]
    inner = min(6, count - 1)
    if inner:
        for index in range(inner):
            angle = phase + (2 * math.pi * index / inner)
            points.append((cx + (radius * 0.5 * math.cos(angle)),
                           cz + (radius * 0.5 * math.sin(angle))))
    outer = count - len(points)
    if outer:
        for index in range(outer):
            angle = phase + (2 * math.pi * index / outer)
            points.append((cx + (radius * math.cos(angle)),
                           cz + (radius * math.sin(angle))))
    return points


def health_for(tier):
    return int(round(BASE_HEALTH + (HEALTH_PER_TIER * (tier - 1))))


def plan(target_map, rows, chain, templates):
    """Every spawn the map needs, grouped by quest point."""
    everything = objectives(rows, chain)
    points = [item for item in everything if item[3] == target_map]
    grounds = []
    for quest_id, species, need, map_id, x, z, level in points:
        if level >= LEGACY_LEVEL:
            continue
        nearest = None
        for other in points:
            if (other[4], other[5]) == (x, z):
                continue
            distance = math.dist((x, z), (other[4], other[5]))
            if nearest is None or distance < nearest:
                nearest = distance
        radius = MIN_RADIUS if nearest is None else nearest / 2
        radius = max(MIN_RADIUS, min(MAX_RADIUS, radius))
        resolved, note = resolve_template(species, target_map, templates)
        grounds.append({
            "quest": quest_id,
            "species": species,
            "need": need,
            "level": level,
            "x": x,
            "z": z,
            "radius": radius,
            "template": resolved[0] if resolved else None,
            "display": resolved[1] if resolved else None,
            "rank": None,
            "note": note,
        })

    # A point can carry several species; each gets its own phase so two species
    # of one objective do not stand on the same coordinates.
    for x, z in {(ground["x"], ground["z"]) for ground in grounds}:
        sharing = [ground for ground in grounds
                   if (ground["x"], ground["z"]) == (x, z)]
        for index, ground in enumerate(sharing):
            ground["phase"] = 2 * math.pi * index / len(sharing)

    for ground in grounds:
        if ground["template"] is None:
            ground["points"] = []
            ground["count"] = 0
            continue
        rank = next(row[2] for row in templates
                    if row[0] == ground["template"])
        ground["rank"] = rank
        ground["count"] = spawn_count(ground["need"], rank)
        ground["points"] = ring_points(
            ground["x"], ground["z"], ground["radius"],
            ground["count"], ground["phase"])
    return grounds


def scene_key(target_map):
    """The client's own scene key for a map, read from the generated map seeds."""
    for line in open(MAP_SEEDS, "r", encoding="utf-8"):
        match = re.match(r'\s*new\((\d+), "([^"]+)",', line)
        if match and int(match.group(1)) == target_map:
            return match.group(2)
    return f"map_{target_map}"


def write_plan(path, target_map, grounds):
    placed = [ground for ground in grounds if ground["template"]]
    missing = [ground for ground in grounds if not ground["template"]]
    lines = [
        f"map {target_map} ({scene_key(target_map)}) spawn plan "
        "- generated by tools/gen_suburb_monsters.py",
        "",
        "range = half the distance to the nearest quest point, kept in "
        f"{MIN_RADIUS:.0f}..{MAX_RADIUS:.0f}",
        "count = the map-0 population for the same kill requirement",
        "",
        f"{'quest':>6} {'level':>5} {'target':<26} {'need':>5} {'rank':<7} "
        f"{'center':<18} {'range':>6} {'spawns':>7}  template",
    ]
    for ground in grounds:
        lines.append(
            f"{ground['quest']:>6} {ground['level']:>5} "
            f"{ground['species']:<26} {ground['need']:>5} "
            f"{(ground['rank'] or '-'):<7} "
            f"({ground['x']:>7.1f},{ground['z']:>7.1f}) "
            f"{ground['radius']:>6.1f} {ground['count']:>7}  "
            f"{ground['template'] or '-  ' + ground['note']}")
    lines += [
        "",
        f"spawn centres with a client model: {len(placed)}",
        f"monsters placed: {sum(g['count'] for g in placed)}",
        "no client model on this map:",
    ]
    for ground in missing:
        lines.append(f"  quest {ground['quest']:>4} level {ground['level']:>3} "
                     f"{ground['species']} ({ground['note']})")
    with open(path, "w", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")
    return placed, missing


def write_code(path, target_map, grounds):
    placed = [ground for ground in grounds if ground["template"]]
    total = sum(ground["count"] for ground in placed)
    class_name, label = PLANS[target_map]
    scene = scene_key(target_map)
    out = [
        "// <auto-generated>",
        "//     Generated by tools/gen_suburb_monsters.py from Quest.xml, the",
        "//     quest objective text and the captured map-0 population. Every row",
        "//     is one monster: the quest point it guards, the species its quest",
        "//     kills and the level that quest unlocks at. Do not edit by hand.",
        "// </auto-generated>",
        "",
        "namespace Godswar.Server.Infrastructure.WorldContent;",
        "",
        "/// <summary>",
        f"/// The authored {label} (map {target_map}, {scene}) population.",
        "///",
        "/// The published baseline only ever captured map 0 (Sparta city), so this",
        "/// camp's newbie map carries no captured spawns. The table is derived",
        "/// instead from the quest chain that lives out there: each kill objective",
        "/// contributes its own coordinate as a spawn centre, the range is half the",
        "/// distance to the nearest other centre, and the population matches what",
        "/// map 0 keeps around a quest point for the same kill requirement.",
        "/// </summary>",
        f"internal static class {class_name}",
        "{",
        f"    internal const short MapId = {target_map};",
        f'    internal const string SceneKey = "{scene}";',
        f"    internal const int SpawnCount = {total};",
        "",
        "    /// <summary>One monster: species, level, health and position.</summary>",
        "    internal readonly record struct Spawn(",
        "        string TemplateKey,",
        "        uint Tier,",
        "        uint MaximumHealth,",
        "        float X,",
        "        float Z);",
        "",
        "    internal static readonly Spawn[] Spawns =",
        "    [",
    ]
    for ground in placed:
        health = health_for(ground["level"])
        out.append(
            f"        // quest {ground['quest']} (lv {ground['level']}): "
            f"{ground['need']}x {ground['species']}, {ground['count']} spawns "
            f"within {ground['radius']:.1f} of "
            f"({ground['x']:.2f}, {ground['z']:.2f})")
        for x, z in ground["points"]:
            out.append(
                f"        new(\"{ground['template']}\", {ground['level']}, "
                f"{health}, {x:.2f}f, {z:.2f}f),")
    out += [
        "    ];",
        "}",
    ]
    with open(path, "w", encoding="utf-8") as handle:
        handle.write("\n".join(out) + "\n")
    return total


def main():
    target_map = int(sys.argv[1]) if len(sys.argv) > 1 else 4
    if target_map not in PLANS:
        raise SystemExit(f"no plan is registered for map {target_map}")
    class_name, _ = PLANS[target_map]
    code_path = os.path.join(PLAN_DIR, f"{class_name}.Generated.cs")
    rows = gen.quest_rows()
    chain = gen.chain_ids()
    templates = load_templates()
    grounds = plan(target_map, rows, chain, templates)
    text_path = PLAN_TEXT.replace(".txt", f"-map{target_map}.txt")
    placed, missing = write_plan(text_path, target_map, grounds)
    total = write_code(code_path, target_map, grounds)
    print(f"templates known: {len(templates)}")
    print(f"map {target_map} ({scene_key(target_map)}) quest points: "
          f"{len(grounds)}")
    print(f"quest points with a client model: {len(placed)}")
    print(f"monsters placed: {total}  (code written to {code_path})")
    print(f"unplaceable objectives: {len(missing)}")
    for ground in missing:
        print(f"  quest {ground['quest']:>4} lv {ground['level']:>3} "
              f"{ground['species']} - {ground['note']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
