BEGIN;

CREATE TABLE IF NOT EXISTS public.monster_loot_tables (
    template_key varchar(64) COLLATE "C" PRIMARY KEY,
    maximum_drops smallint NOT NULL
        CHECK (maximum_drops BETWEEN 1 AND 32),
    enabled boolean NOT NULL DEFAULT true,
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT ck_monster_loot_tables_template_key
        CHECK (length(btrim(template_key)) > 0)
);

CREATE TABLE IF NOT EXISTS public.monster_loot_rules (
    template_key varchar(64) COLLATE "C" NOT NULL,
    loot_index smallint NOT NULL CHECK (loot_index BETWEEN 0 AND 31),
    item_id integer NOT NULL REFERENCES public.item_templates(id),
    chance_basis_points integer NOT NULL
        CHECK (chance_basis_points BETWEEN 1 AND 10000),
    minimum_quantity smallint NOT NULL
        CHECK (minimum_quantity BETWEEN 1 AND 255),
    maximum_quantity smallint NOT NULL
        CHECK (maximum_quantity BETWEEN minimum_quantity AND 255),
    enabled boolean NOT NULL DEFAULT true,
    updated_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (template_key, loot_index),
    FOREIGN KEY (template_key)
        REFERENCES public.monster_loot_tables(template_key)
        ON DELETE CASCADE
);

INSERT INTO public.monster_loot_tables (template_key, maximum_drops)
VALUES
    ('A_normal_stub_001', 1),
    ('A_normal_stub_002', 2),
    ('A_normal_deer_001', 1)
ON CONFLICT (template_key) DO NOTHING;

INSERT INTO public.monster_loot_rules (
    template_key, loot_index, item_id,
    chance_basis_points, minimum_quantity, maximum_quantity)
VALUES
    ('A_normal_stub_001', 0, 4529, 2500, 1, 1),
    ('A_normal_stub_002', 0, 12030, 2500, 1, 1),
    ('A_normal_stub_002', 1, 4529, 2500, 1, 1),
    ('A_normal_stub_002', 2, 4150, 2500, 1, 1),
    ('A_normal_stub_002', 3, 4003, 2500, 1, 1),
    ('A_normal_stub_002', 4, 4224, 2500, 1, 1),
    ('A_normal_stub_002', 5, 12040, 2500, 1, 1),
    ('A_normal_deer_001', 0, 4001, 2500, 1, 1)
ON CONFLICT (template_key, loot_index) DO NOTHING;

SELECT header.template_key, header.maximum_drops, count(rule.*) AS rules
FROM public.monster_loot_tables header
LEFT JOIN public.monster_loot_rules rule
  ON rule.template_key = header.template_key
GROUP BY header.template_key, header.maximum_drops
ORDER BY header.template_key;

ROLLBACK;
