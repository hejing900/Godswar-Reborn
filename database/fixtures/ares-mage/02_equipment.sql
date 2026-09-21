CREATE TEMP TABLE mage_gear(slot smallint PRIMARY KEY,item integer,affixes integer[])
 ON COMMIT DROP;
-- Exact native allowed chains; terminal affixes have level5, singleton level1.
INSERT INTO mage_gear VALUES
 (0,2443,ARRAY[24,40,60,90,250]),
 (1,3163,ARRAY[50,70,104,144,170]),
 (2,2863,ARRAY[24,40,60,90,250]),
 (3,2263,ARRAY[14,34,104,134,170]),
 (4,2663,ARRAY[14,34,70,154,170]),
 (5,3063,ARRAY[14,34,70,104,134]),
 (6,2963,ARRAY[50,70,104,134,170]),
 (7,2763,ARRAY[14,34,70,154,170]),
 (8,3265,ARRAY[24,60,90,134,250]),
 (9,3265,ARRAY[24,60,90,134,250]),
 (10,1834,ARRAY[24,40,60,90,250]);
DO $gear_guard$
BEGIN
 IF (SELECT count(*) FROM mage_gear g JOIN official_item_template_content t ON t.id=g.item
   WHERE 3=ANY(t.class_ids) AND t.min_level<=140 AND t.max_level>=140
    AND (t.equipment_slot=g.slot OR (g.slot=9 AND t.equipment_slot=8)))<>11 THEN
  RAISE EXCEPTION 'Mage main11 equipment eligibility changed';
 END IF;
 IF NOT EXISTS(SELECT 1 FROM official_holy_suit_tier_content
    WHERE suit_type=4 AND display_name='Platinum' AND max_level=10 AND ware_item_id=9013) THEN
  RAISE EXCEPTION 'Platinum I definition changed';
 END IF;
END $gear_guard$;
INSERT INTO character_items(user_id,item_location,slot_index,prop_id,
 attribute1,attribute2,attribute3,attribute4,attribute5,
 attribute_level1,attribute_level2,attribute_level3,attribute_level4,attribute_level5,
 item_quality,item_grade,bound,stack,holy_suit_code)
SELECT c.character_id,0,g.slot,g.item,
 g.affixes[1],g.affixes[2],g.affixes[3],g.affixes[4],g.affixes[5],
 CASE WHEN g.affixes[1]%10=4 THEN 5 ELSE 1 END,
 CASE WHEN g.affixes[2]%10=4 THEN 5 ELSE 1 END,
 CASE WHEN g.affixes[3]%10=4 THEN 5 ELSE 1 END,
 CASE WHEN g.affixes[4]%10=4 THEN 5 ELSE 1 END,
 CASE WHEN g.affixes[5]%10=4 THEN 5 ELSE 1 END,
 10,12,1,1,401 FROM mage_context c CROSS JOIN mage_gear g;
-- Normal creation's ten HP and ten MP potions; no bonus currency or materials.
INSERT INTO character_items(user_id,item_location,slot_index,prop_id,
 item_quality,item_grade,bound,stack)
SELECT c.character_id,1,p.slot,p.item,1,1,0,10
 FROM mage_context c CROSS JOIN (VALUES(0,4000),(1,4030)) p(slot,item);
SELECT public.recompute_character_holy_suit_points(character_id) FROM mage_context;

CREATE TEMP TABLE mage_skills ON COMMIT DROP AS
SELECT DISTINCT ON(base_name) skill_id,skill_level::smallint FROM skill_templates
 WHERE 3=ANY(class_ids) AND skill_level IS NOT NULL AND min_level<=140 AND max_level>=140
 ORDER BY base_name,skill_level DESC,min_level DESC,skill_id DESC;
INSERT INTO character_skills(user_id,skill_id,skill_level,source)
 SELECT c.character_id,s.skill_id,s.skill_level,'ares-mage-provision-v1'
 FROM mage_context c CROSS JOIN mage_skills s;
-- Same-camp capital/suburb portals and compatible riding skill.
INSERT INTO character_skills(user_id,skill_id,skill_level,source)
 SELECT c.character_id,s.skill_id,1,'ares-mage-provision-v1'
 FROM mage_context c JOIN skill_templates s ON s.skill_id IN(3062,3063,4904)
 WHERE 3=ANY(s.class_ids) AND s.min_level<=140;
