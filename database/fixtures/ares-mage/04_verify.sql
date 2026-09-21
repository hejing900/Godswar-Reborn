-- Talents were added by 03b before these derived vitals. Pet Merge, donor
-- benefits and statuses remain absent from this new identity.
-- The compatibility view omits runtime's per-item suit multiplier. Add that
-- exact integer-truncated delta (PostgresCharacterHolySuitProjectionSql).
CREATE TEMP TABLE mage_vitals ON COMMIT DROP AS
SELECT s.user_id,s.max_hp+bonus.hp AS max_hp,s.max_mp+bonus.mp AS max_mp,
 bonus.hp AS suit_hp,bonus.mp AS suit_mp
 FROM mage_context m JOIN character_stat_summary s ON s.user_id=m.character_id
 CROSS JOIN LATERAL (
  SELECT coalesce(sum(trunc(v.value*public.holy_suit_progression_points(i.holy_suit_code)/100.0))
   FILTER(WHERE k.key='MaxHP'),0)::integer hp,
   coalesce(sum(trunc(v.value*public.holy_suit_progression_points(i.holy_suit_code)/100.0))
   FILTER(WHERE k.key='MaxMP'),0)::integer mp
  FROM character_items i JOIN official_item_template_content t ON t.id=i.prop_id
  CROSS JOIN(VALUES('MaxHP'),('MaxMP')) k(key)
  CROSS JOIN LATERAL(SELECT string_to_array(t.stats->>k.key,',') AS vals) a
  CROSS JOIN LATERAL(SELECT coalesce(nullif(a.vals[least(greatest(i.item_quality::integer,1),array_length(a.vals,1))],'')::numeric,0) value) v
  WHERE i.user_id=m.character_id AND i.item_location=0
 ) bonus;
UPDATE character_base c SET "curHP"=s.max_hp,"curMP"=s.max_mp
 FROM mage_context m JOIN mage_vitals s ON s.user_id=m.character_id
 WHERE c.id=m.character_id;
INSERT INTO character_economy_baseline(character_id,account_id,wallet_revision,
 inventory_revision,silver,gold,binding_gold,item_count,baseline_source)
 SELECT c.id,c.account_id,c.wallet_revision,c.inventory_revision,"Money","Stone",
  "BindingGold",(SELECT count(*) FROM character_items i WHERE i.user_id=c.id),
  'character_creation' FROM character_base c JOIN mage_context m ON m.character_id=c.id;
INSERT INTO character_inventory_baseline_items(character_id,account_id,
 item_instance_id,item_location,slot_index,prop_id,state_contract_version,item_state)
 SELECT m.character_id,m.account_id,i.id,i.item_location,i.slot_index,i.prop_id,1,to_jsonb(i)
 FROM mage_context m JOIN character_items i ON i.user_id=m.character_id;

DO $verify$
DECLARE m record;
BEGIN
 SELECT * INTO STRICT m FROM mage_context;
 IF NOT EXISTS(SELECT 1 FROM mage_vitals WHERE user_id=m.character_id
    AND suit_hp=4365 AND suit_mp=990) THEN
  RAISE EXCEPTION 'Reviewed Q10 Platinum I native vitals delta changed';
 END IF;
 IF NOT EXISTS(SELECT 1 FROM character_base c JOIN mage_vitals s ON s.user_id=c.id
  WHERE c.id=m.character_id AND c.account_id=m.account_id AND c.name='AresMage'
   AND camp=0 AND c.profession=3 AND fighter_job_lv=140 AND fighter_job_exp=0
   AND "Map"=0 AND "Pos_X"=165 AND "Pos_Z"=-97 AND "Money"=10000 AND "Stone"=10
   AND "BindingGold"=0 AND "GM"=0 AND holy_suit_points=341
   AND "curHP"=s.max_hp AND "curMP"=s.max_mp AND "curHP">0 AND "curMP">0
   AND wallet_revision=0 AND inventory_revision=0 AND checkpoint_owner_id IS NULL
   AND checkpoint_owner_generation=0 AND lifecycle_state='active') THEN
  RAISE EXCEPTION 'New mage identity, progression, wallet or vitals failed';
 END IF;
 IF (SELECT count(*) FROM character_items WHERE user_id=m.character_id)<>13
 OR (SELECT count(*) FROM character_items i JOIN mage_gear g
  ON i.slot_index=g.slot AND i.prop_id=g.item WHERE i.user_id=m.character_id
  AND i.item_location=0 AND i.item_quality=10 AND i.item_grade=12 AND i.holy_suit_code=401
  AND i.bound=1 AND i.stack=1 AND i.holy_socket_count=0
  AND i.class_attribute1 IS NULL AND i.class_attribute2 IS NULL
  AND i.elemental_attribute1 IS NULL AND i.elemental_attribute2 IS NULL)<>11
 OR (SELECT count(*) FROM character_inventory_baseline_items WHERE character_id=m.character_id)<>13
 OR EXISTS(SELECT 1 FROM character_inventory_baseline_items b JOIN character_items i ON i.id=b.item_instance_id
  WHERE b.character_id=m.character_id AND b.item_state<>to_jsonb(i)) THEN
  RAISE EXCEPTION 'New mage equipment or baseline mismatch';
 END IF;
 IF (SELECT count(*) FROM mage_skills)<>11
 OR (SELECT count(*) FROM character_skills WHERE user_id=m.character_id)<>14
 OR EXISTS(SELECT 1 FROM character_skills cs JOIN skill_templates s ON s.skill_id=cs.skill_id
  WHERE cs.user_id=m.character_id AND (NOT 3=ANY(s.class_ids) OR s.min_level>140)) THEN
  RAISE EXCEPTION 'New mage skill manifest mismatch';
 END IF;
 IF (SELECT count(*) FROM character_talents WHERE user_id=m.character_id)<>18
 OR (SELECT count(*) FROM character_talents t JOIN mage_talents expected
   ON expected.talent_id=t.talent_id WHERE t.user_id=m.character_id
    AND t.rank=60 AND t.outbox_revision=0)<>18
 OR NOT EXISTS(SELECT 1 FROM character_base WHERE id=m.character_id
   AND "SkillPoint"=10 AND "SkillExp"=0) THEN
  RAISE EXCEPTION 'New mage level-140 maximum talents or unspent points mismatch';
 END IF;
 IF NOT EXISTS(SELECT 1 FROM character_pets WHERE id=m.pet_id AND user_id=m.character_id
  AND species_id=12 AND level=120 AND aptitude=10 AND rank=1 AND completed_rebirths=0
  AND completed_pet_merges=0 AND initial_savvy_baseline_total=180 AND talent_mask=26
  AND NOT contributes_to_character AND NOT is_summoned AND is_carried)
 OR (SELECT count(*) FROM character_pet_stat_values WHERE pet_id=m.pet_id)<>6
 OR (SELECT sum(initial_savvy) FROM character_pet_stat_values WHERE pet_id=m.pet_id)<>1500
 OR EXISTS(SELECT 1 FROM character_pet_stat_values WHERE pet_id=m.pet_id
  AND (added_savvy<>360 OR base_growth_rate<>3 OR growth_acceleration<>0
   OR birth_initial_savvy<>30 OR rarity_added_savvy<>30))
 OR (SELECT count(*) FROM character_pet_skills WHERE pet_id=m.pet_id AND skill_id IN(800,2800))<>2 THEN
  RAISE EXCEPTION 'New mage pet state mismatch';
 END IF;
END $verify$;

DO $unchanged$
DECLARE t record; m record; predicate text; n bigint; h text;
BEGIN
 SELECT * INTO STRICT m FROM mage_context;
 FOR t IN SELECT * FROM mage_before ORDER BY table_name LOOP
  predicate:=CASE t.table_name
   WHEN 'accounts' THEN format('id<>%s',m.account_id)
   WHEN 'account_realm' THEN format('account_id<>%s',m.account_id)
   WHEN 'character_base' THEN format('id<>%s',m.character_id)
   WHEN 'character_items' THEN format('user_id<>%s',m.character_id)
   WHEN 'character_skills' THEN format('user_id<>%s',m.character_id)
   WHEN 'character_talents' THEN format('user_id<>%s',m.character_id)
   WHEN 'character_pets' THEN format('user_id<>%s',m.character_id)
   WHEN 'character_pet_stat_values' THEN format('pet_id<>%s',m.pet_id)
   WHEN 'character_pet_skills' THEN format('pet_id<>%s',m.pet_id)
   WHEN 'character_economy_baseline' THEN format('character_id<>%s',m.character_id)
   WHEN 'character_inventory_baseline_items' THEN format('character_id<>%s',m.character_id)
   ELSE 'true' END;
  EXECUTE format('SELECT count(*),md5(coalesce(string_agg(h,'''' ORDER BY h),'''')) FROM (SELECT md5(to_jsonb(r)::text) h FROM public.%I r WHERE %s) q',t.table_name,predicate) INTO n,h;
  IF n<>t.rows OR h<>t.digest THEN
   RAISE EXCEPTION 'Unrelated existing data changed in %; rolling back',t.table_name;
  END IF;
 END LOOP;
END $unchanged$;
SELECT 'ARES_MAGE_RECEIPT|' || json_build_object(
 'account_id',m.account_id,'character_id',m.character_id,'pet_id',m.pet_id,
 'username','aresmage','character_name','AresMage','profession',3,'level',140,
 'camp',0,'map',0,'gear_count',11,'quality',10,'grade',12,'holy_suit_code',401,
 'holy_suit_points',341,'pet_species',12,'pet_level',120,'pet_basic_savvy',1500,
 'talent_count',(SELECT count(*) FROM character_talents WHERE user_id=m.character_id),
 'talent_rank',(SELECT min(rank) FROM character_talents WHERE user_id=m.character_id),
 'max_hp',s.max_hp,'max_mp',s.max_mp,'prior_tables_unchanged',(SELECT count(*) FROM mage_before))::text
 FROM mage_context m JOIN mage_vitals s ON s.user_id=m.character_id;
COMMIT;
