-- Smart Blue Crystal Dragon: normal rank1, no rebirths, no forced owner Merge.
-- Birth floor180 is a valid Smart roll; developed Basic is explicitly1500.
-- Revealed Smart Growth18 is within16..23, eachAdded=3*level120=360.
DO $pet_guard$
BEGIN
 IF NOT EXISTS(SELECT 1 FROM pet_content_aptitude_definitions
   WHERE revision=(SELECT revision FROM pet_content_publication WHERE family='pets')
    AND aptitude=10 AND 180 BETWEEN minimum_initial_savvy AND maximum_initial_savvy
    AND 18 BETWEEN minimum_total_growth AND maximum_total_growth AND innate_talent_mask=26)
 OR NOT EXISTS(SELECT 1 FROM pet_content_hatch_rank_steps
   WHERE revision=(SELECT revision FROM pet_content_publication WHERE family='pets')
    AND aptitude=10 AND outcome_order=0 AND rank=1 AND weight=60)
 OR NOT EXISTS(SELECT 1 FROM pet_content_native_profiles
   WHERE revision=(SELECT revision FROM pet_content_publication WHERE family='pets')
    AND species_id=12 AND aptitude=10 AND starter_skill_id=2800 AND lifetime=1500)
 OR (SELECT count(*) FROM pet_skill_curve_steps
   WHERE revision=(SELECT revision FROM pet_skill_content_publication)
    AND runtime_skill_id IN(800,2800) AND minimum_pet_rank<=1)<>2 THEN
  RAISE EXCEPTION 'Reviewed mage pet content changed';
 END IF;
END $pet_guard$;
WITH p AS (
 INSERT INTO character_pets(user_id,species_id,name,sex,level,experience,aptitude,rank,
  completed_rebirths,rebirths_remaining,completed_pet_merges,has_soul_contract,
  has_owner_merge_talent,current_energy,maximum_energy,amity,satiety,remaining_lifetime,
  available_stat_points,growth_revealed,bound,activity_state,is_carried,is_summoned,
  contributes_to_character,revision,initial_savvy_baseline_total,initial_savvy_policy_version,
  rarity_added_savvy_baseline_total,rarity_added_savvy_policy_version,initial_savvy_source_version,
  talent_mask,opened_skill_slots,available_skill_slots,growth_activation_policy_version,
  birth_rank,hatch_rank_roll,hatch_rank_outcome_order,hatch_rank_content_revision)
 SELECT c.character_id,12,'AresMageBond',0,120,0,
  10,1,0,0,0,false,true,100,100,100,100,1500,0,true,true,
  'owned',true,false,false,0,180,'project-v3',180,'project-v3','basic-plus-scaled-growth-v3',
  26,2,2,'weak-until-phoenix-v1',1,0,0,
  (SELECT revision FROM pet_content_publication WHERE family='pets')
 FROM mage_context c RETURNING id
) UPDATE mage_context SET pet_id=p.id FROM p;
INSERT INTO character_pet_stat_values(pet_id,stat_code,initial_savvy,added_savvy,
 growth_acceleration,revision,base_growth_rate,birth_initial_savvy,rarity_added_savvy)
 SELECT c.pet_id,s.code,s.basic,360,0,0,3,30,30 FROM mage_context c
 CROSS JOIN (VALUES(1,600),(2,100),(3,200),(4,150),(5,150),(6,300)) s(code,basic);
INSERT INTO character_pet_skills(pet_id,skill_id,slot_index,skill_rank,
 skill_experience,is_active,revision)
 SELECT c.pet_id,s.skill,s.slot,1,0,true,0 FROM mage_context c
 CROSS JOIN (VALUES(2800,0),(800,1)) s(skill,slot);
