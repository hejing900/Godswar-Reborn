-- Level 140 permits talent rank 60; rank 61 requires level 141.
-- This is initial character provisioning, not a paid upgrade command.
-- The earlier identity fragment forbids any pre-existing AresMage identity.
CREATE TEMP TABLE mage_talents(talent_id integer PRIMARY KEY) ON COMMIT DROP;
INSERT INTO mage_talents VALUES
 (100),(101),(102),(103),(104),(105),(106),(107),(108),
 (109),(110),(111),(112),(113),(114),(115),(116),(117);

DO $talents$
BEGIN
 IF NOT EXISTS(SELECT 1 FROM mage_context m JOIN character_base c ON c.id=m.character_id
   WHERE c.account_id=m.account_id AND c.profession=3 AND c.fighter_job_lv=140
    AND c.lifecycle_state='active' AND c.checkpoint_owner_id IS NULL)
 OR (SELECT count(*) FROM gameplay_talent_definitions d
   JOIN gameplay_content_publication p ON p.family='gameplay' AND p.revision=d.revision
   WHERE d.class_id=3)<>18
 OR (SELECT count(*) FROM mage_talents m JOIN gameplay_talent_definitions d ON d.id=m.talent_id
   JOIN gameplay_content_publication p ON p.family='gameplay' AND p.revision=d.revision
   WHERE d.class_id=3 AND d.required_prefix_rank=0 AND d.required_total_rank=0
    AND d.equip_request=-1)<>18 THEN
  RAISE EXCEPTION 'Reviewed level-140 mage talent manifest changed';
 END IF;
 IF EXISTS(SELECT 1 FROM character_talents t JOIN mage_context m ON m.character_id=t.user_id) THEN
  RAISE EXCEPTION 'Initial mage talents already exist; no overwrite allowed';
 END IF;
END $talents$;

INSERT INTO character_talents(user_id,talent_id,rank,outbox_revision,updated_at)
 SELECT c.character_id,t.talent_id,60,0,now() FROM mage_context c CROSS JOIN mage_talents t;
