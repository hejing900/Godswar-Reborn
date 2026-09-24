"""Generate the guild content migrations straight from the client's own files.

Everything the guild window can show already exists in the client
(Localization/<locale>/Settings/Sys/Consortia.xml and Consortia_Job.ini), so the
server's content tables are generated from those files rather than typed by
hand. Re-run this after a client update:

    python tools/generate-guild-content-migration.py

Two migrations come out of one run. The first is the original content seed
(20260916_159_guild_content); it has already been applied everywhere, so it is
reproduced byte for byte and never extended. The ten altars' per-level worship
impact (WorshipImpactType/WorshipImpactValue) therefore arrives as its own
migration afterwards.
"""

import os
import xml.etree.ElementTree as ET

CLIENT = r"D:\Godswar Origin"
OUTPUT = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "src", "Godswar.Server", "State", "DatabaseMigrations",
    "PostgresSchemaMigrationCatalog.GuildContent.Generated.cs")


def sql_literal(value):
    return "'" + str(value).replace("'", "''") + "'"


def read_guild_xml(locale):
    path = os.path.join(
        CLIENT, "Localization", locale, "Settings", "Sys", "Consortia.xml")
    return ET.parse(path).getroot()


# The column is NOT NULL, so a building level that carries no worship impact
# needs a value that cannot be mistaken for a real attribute id. Attribute ids
# are 0..20, so -1 means "this building level grants no worship bonus".
NO_WORSHIP_IMPACT = -1


def worship_impact(level):
    """One BuildingImpact level row's own worship impact, if it has one.

    Only the ten altars (client ids 10-19) carry these two attributes; every
    other building level has neither, and reads back as (-1, 0).
    """
    if "WorshipImpactType" not in level.attrib:
        return NO_WORSHIP_IMPACT, 0
    return (
        int(level.attrib["WorshipImpactType"]),
        int(level.attrib["WorshipImpactValue"]),
    )


def duties(locale):
    path = os.path.join(
        CLIENT, "Localization", locale, "Settings", "Sys",
        "Consortia_Job.ini")
    with open(path, "rb") as handle:
        text = handle.read().decode("gbk")
    # The file separates keys with a fullwidth equals sign, not ASCII '='.
    text = text.replace("\uff1d", "=")
    rows = []
    for line in text.splitlines():
        line = line.strip()
        if not line or "=" not in line or line.startswith("["):
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if not key.isdigit():
            continue
        rows.append((int(key), value.strip()))
    return sorted(rows)


def main():
    root = read_guild_xml("zh_cn")
    english = read_guild_xml("en_us")

    english_buildings = {
        int(node.attrib["ID"]): node.attrib["Name"]
        for node in english.find("BuildInfo")
    }
    chinese_buildings = {
        int(node.attrib["ID"]): node.attrib["Name"]
        for node in root.find("BuildInfo")
    }

    levels = [
        (int(node.attrib["found"]), int(node.attrib["bijou"]))
        for node in root.find("ConsortiaLevelUp")
    ]

    impacts = {}
    worship_impacts = []
    for node in root.find("BuildingImpact"):
        build_id = int(node.attrib["ID"])
        per_level = []
        for level in node:
            per_level.append((
                int(level.attrib["Clevel"]),
                int(level.attrib["found"]),
                int(level.attrib["bijou"]),
            ))
            impact_type, impact_value = worship_impact(level)
            worship_impacts.append(
                (build_id, int(level.attrib["Clevel"]), impact_type,
                 impact_value))
        impacts[build_id] = sorted(per_level)
    worship_impacts.sort()
    worship_rows = [row for row in worship_impacts
                    if row[2] != NO_WORSHIP_IMPACT]
    worship_altars = sorted({row[0] for row in worship_rows})

    consumes = [
        (
            int(node.attrib["Condition"]),
            int(node.attrib["ContributePoint"]),
            int(node.attrib["ConsumeValue"]),
        )
        for node in root.find("BuildingConsume")
    ]

    defaults = [
        (node.tag, node.attrib["ID"], node.attrib["Value"])
        for node in root.find("CorsortiaDefaultValue")
    ]

    duty_rows = duties("zh_cn")
    duty_en = dict(duties("en_us")) if os.path.exists(os.path.join(
        CLIENT, "Localization", "en_us", "Settings", "Sys",
        "Consortia_Job.ini")) else {}

    parts = []
    parts.append("""
            CREATE TABLE public.guild_duties (
                duty smallint PRIMARY KEY,
                display_name character varying(32) NOT NULL,
                rank smallint NOT NULL,
                CONSTRAINT ck_guild_duties_rank CHECK (rank >= 0)
            );

            INSERT INTO public.guild_duties (duty, display_name, rank) VALUES""")
    parts.append(",\n".join(
        f"                ({duty}, {sql_literal(name)}, {duty})"
        for duty, name in duty_rows) + ";")

    parts.append("""
            ALTER TABLE public.guild_members
                ADD CONSTRAINT fk_guild_members_duty
                FOREIGN KEY (duty) REFERENCES public.guild_duties(duty)
                ON DELETE RESTRICT;""")

    parts.append("""
            CREATE TABLE public.guild_levels (
                level integer PRIMARY KEY,
                upgrade_found bigint NOT NULL CHECK (upgrade_found >= 0),
                upgrade_bijou bigint NOT NULL CHECK (upgrade_bijou >= 0),
                CONSTRAINT ck_guild_levels_level CHECK (level BETWEEN 1 AND 12)
            );

            INSERT INTO public.guild_levels (level, upgrade_found, upgrade_bijou)
            VALUES""")
    parts.append(",\n".join(
        f"                ({index + 1}, {found}, {bijou})"
        for index, (found, bijou) in enumerate(levels)) + ";")

    parts.append("""
            CREATE TABLE public.guild_building_types (
                building_type integer PRIMARY KEY,
                name_key character varying(64) NOT NULL,
                display_name character varying(96) NOT NULL,
                maximum_level smallint NOT NULL CHECK (maximum_level BETWEEN 1 AND 12)
            );

            INSERT INTO public.guild_building_types (
                building_type, name_key, display_name, maximum_level)
            VALUES""")
    type_rows = []
    for build_id in sorted(english_buildings):
        name_en = english_buildings[build_id]
        name_cn = chinese_buildings.get(build_id, name_en)
        type_rows.append(
            f"                ({build_id}, {sql_literal(name_en)}, "
            f"{sql_literal(name_cn)}, {len(impacts[build_id])})")
    parts.append(",\n".join(type_rows) + ";")

    parts.append("""
            CREATE TABLE public.guild_building_levels (
                building_type integer NOT NULL
                    REFERENCES public.guild_building_types(building_type)
                    ON DELETE CASCADE,
                level smallint NOT NULL CHECK (level BETWEEN 1 AND 12),
                upgrade_found bigint NOT NULL CHECK (upgrade_found >= 0),
                upgrade_bijou bigint NOT NULL CHECK (upgrade_bijou >= 0),
                PRIMARY KEY (building_type, level)
            );

            INSERT INTO public.guild_building_levels (
                building_type, level, upgrade_found, upgrade_bijou)
            VALUES""")
    level_rows = []
    for build_id in sorted(impacts):
        for level, found, bijou in impacts[build_id]:
            level_rows.append(
                f"                ({build_id}, {level}, {found}, {bijou})")
    parts.append(",\n".join(level_rows) + ";")

    parts.append("""
            CREATE TABLE public.guild_building_consume (
                condition_level smallint PRIMARY KEY,
                contribute_point bigint NOT NULL CHECK (contribute_point >= 0),
                consume_value bigint NOT NULL CHECK (consume_value >= 0)
            );

            INSERT INTO public.guild_building_consume (
                condition_level, contribute_point, consume_value)
            VALUES""")
    parts.append(",\n".join(
        f"                ({condition}, {point}, {value})"
        for condition, point, value in consumes) + ";")

    parts.append("""
            CREATE TABLE public.guild_defaults (
                setting_key character varying(64) PRIMARY KEY,
                setting_order smallint NOT NULL,
                setting_value character varying(32) NOT NULL
            );

            INSERT INTO public.guild_defaults (
                setting_key, setting_order, setting_value)
            VALUES""")
    parts.append(",\n".join(
        f"                ({sql_literal(key)}, {order}, {sql_literal(value)})"
        for key, order, value in defaults) + ";")

    parts.append("""
            COMMENT ON TABLE public.guild_duties IS
                'Client duty names from Settings/Sys/Consortia_Job.ini (GBK): 0 none, 1 见习会员 ... 6 会长.';
            COMMENT ON TABLE public.guild_levels IS
                'Guild level upgrade costs from Consortia.xml ConsortiaLevelUp; the curve matches every building level.';
            COMMENT ON TABLE public.guild_building_types IS
                'The 17 guild buildings the client ships in Consortia.xml BuildInfo. Ids are the client''s own and are not contiguous.';
            COMMENT ON TABLE public.guild_building_levels IS
                'Per building level costs from Consortia.xml BuildingImpact; every building has twelve levels.';
            COMMENT ON TABLE public.guild_building_consume IS
                'Contribution points and consume value from Consortia.xml BuildingConsume.';
            COMMENT ON TABLE public.guild_defaults IS
                'Defaults and caps from Consortia.xml CorsortiaDefaultValue (the client spells it that way).';""")

    body = "\n".join(parts)

    worship = []
    worship.append("""
            ALTER TABLE public.guild_building_levels
                ADD COLUMN worship_impact_type smallint NOT NULL
                    DEFAULT -1
                    CONSTRAINT ck_guild_building_levels_worship_impact_type
                    CHECK (worship_impact_type BETWEEN -1 AND 20),
                ADD COLUMN worship_impact_value integer NOT NULL
                    DEFAULT 0
                    CONSTRAINT ck_guild_building_levels_worship_impact_value
                    CHECK (worship_impact_value >= 0);

            UPDATE public.guild_building_levels AS l
            SET worship_impact_type = v.impact_type,
                worship_impact_value = v.impact_value
            FROM (VALUES""")
    worship.append(",\n".join(
        f"                ({build_id}, {level}, {impact_type}, {impact_value})"
        for build_id, level, impact_type, impact_value in worship_rows) + f"""
            ) AS v (building_type, level, impact_type, impact_value)
            WHERE l.building_type = v.building_type
              AND l.level = v.level;

            COMMENT ON COLUMN public.guild_building_levels.worship_impact_type IS
                'Client WorshipImpactType from Consortia.xml BuildingImpact: the attribute a worshipped altar level grants. -1 = this building level grants no worship bonus (only the ten altars at client ids {worship_altars[0]}-{worship_altars[-1]} carry one).';
            COMMENT ON COLUMN public.guild_building_levels.worship_impact_value IS
                'Client WorshipImpactValue for this altar level: the attribute value the altar grants. The client''s GH87 grants a percentage of it from offering points (1000000 points = 150%, one step per 50000), so this is the base the percentage is taken from, not the final bonus.';""")

    worship_body = "\n".join(worship)

    source = f'''namespace Godswar.Server.State;

// Generated by tools/generate-guild-content-migration.py from the client's
// Localization/*/Settings/Sys files. Do not edit by hand: re-run the generator
// so the server's guild content stays identical to the shipped client.
internal static partial class PostgresSchemaMigrationCatalog
{{
    private static PostgresSchemaMigration CreateGuildContent() =>
        new(
            "20260916_159_guild_content",
            "Seed guild duties, levels, buildings and defaults from the client",
            """
{body}
            """);

    /// <summary>
    /// The attribute bonus each altar level grants, taken from the client's own
    /// <c>WorshipImpactType</c>/<c>WorshipImpactValue</c>.
    /// </summary>
    /// <remarks>
    /// The seed migration above keeps only the levels' upgrade prices, so the ten
    /// altars' own impact never reached the database and the offering points had
    /// nothing to be a percentage of. This adds those two columns and fills them
    /// from the same <c>BuildingImpact</c> block the prices come from.
    ///
    /// The values are the client's, exactly: altar <c>13</c> is 135 at level one and
    /// 540 at level twelve, which is the number <c>NF_L0_GH87</c>'s percentage is
    /// taken from. A separate migration rather than an edit of the seed because the
    /// seed has already been applied and its checksum recorded.
    /// </remarks>
    private static PostgresSchemaMigration CreateGuildWorshipImpact() =>
        new(
            "20260923_164_guild_worship_impact",
            "Seed each altar level's worship impact from the client",
            """
{worship_body}
            """);
}}
'''
    with open(OUTPUT, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(source)
    print(f"wrote {OUTPUT}")
    print(f"  duties={len(duty_rows)} levels={len(levels)} "
          f"types={len(type_rows)} building_levels={len(level_rows)} "
          f"consumes={len(consumes)} defaults={len(defaults)}")
    print(f"  worship_impacts={len(worship_rows)} "
          f"altars={worship_altars}")


if __name__ == "__main__":
    main()
