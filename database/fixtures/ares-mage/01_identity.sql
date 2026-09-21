-- Dedicated new identity only. Invoked by ProvisionAresMage.py after offline guards.
BEGIN ISOLATION LEVEL SERIALIZABLE;
SET LOCAL lock_timeout='5s';
SET LOCAL statement_timeout='120s';
SELECT pg_advisory_xact_lock(6919401401500);
LOCK TABLE accounts,account_realm,character_base IN SHARE ROW EXCLUSIVE MODE;
DO $guard$
BEGIN
 IF current_database()<>'godswar' OR NOT EXISTS(
   SELECT 1 FROM server WHERE id=1 AND name='Tempest' AND enabled) THEN
  RAISE EXCEPTION 'AresMage requires the enabled local Tempest realm';
 END IF;
 IF EXISTS(SELECT 1 FROM accounts WHERE lower(username)='aresmage') OR
    EXISTS(SELECT 1 FROM character_base WHERE lower(name)='aresmage') THEN
  RAISE EXCEPTION 'AresMage account or character already exists; no overwrite allowed';
 END IF;
 IF EXISTS(SELECT 1 FROM pg_stat_activity WHERE datname=current_database()
    AND pid<>pg_backend_pid() AND backend_type='client backend') THEN
  RAISE EXCEPTION 'Another database client is connected; stop server and probes first';
 END IF;
 IF NOT EXISTS(SELECT 1 FROM item_template_content_publication WHERE family='items'
   AND revision='A45EA650680C8EA4D5D2FCAA831E97EEEF652BAB55351D860BFB95330FA97EB1')
 OR NOT EXISTS(SELECT 1 FROM gameplay_content_publication WHERE family='gameplay'
   AND revision='AEC094E63E44CFCB9F75DE76E807BD69ADAD14031656E665979AC7B5371AD178')
 OR NOT EXISTS(SELECT 1 FROM pet_content_publication WHERE family='pets'
   AND revision='F5CC3B3EFAA33AB275AC35F8A3CF9FAB4DE26D7DAD3E13B90BAB88CC0B09F9FD')
 OR NOT EXISTS(SELECT 1 FROM pet_skill_content_publication
   WHERE revision='64748AC27B0D815B9C30CFF78A7CE8AD519AE83DF528CB5CDFF4374503ABB473') THEN
  RAISE EXCEPTION 'Reviewed published content changed';
 END IF;
END $guard$;

-- Snapshot every existing public base table. The final fragment excludes only
-- this transaction's new rows, and rejects ANY changed/removed/unrelated row.
CREATE TEMP TABLE mage_before(table_name text PRIMARY KEY,rows bigint,digest text)
 ON COMMIT DROP;
DO $snapshot$
DECLARE t record;
BEGIN
 FOR t IN SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename LOOP
  EXECUTE format('INSERT INTO mage_before SELECT %L,count(*),md5(coalesce(string_agg(h,'''' ORDER BY h),'''')) FROM (SELECT md5(to_jsonb(r)::text) h FROM public.%I r) q',t.tablename,t.tablename);
 END LOOP;
END $snapshot$;

CREATE TEMP TABLE mage_context(account_id integer,character_id integer,pet_id bigint)
 ON COMMIT DROP;
WITH a AS (
 INSERT INTO accounts(username,password,status,login_status,character_lifecycle_version)
 VALUES('aresmage',__PRIVATE_VERIFIER__,0,0,1) RETURNING id
) INSERT INTO mage_context(account_id) SELECT id FROM a;
INSERT INTO account_realm(account_id,realm_id,character_lifecycle_version)
 SELECT account_id,1,1 FROM mage_context;
WITH c AS (
 INSERT INTO character_base(account_id,server_id,name,gender,"GM",camp,profession,
  fighter_job_lv,fighter_job_exp,scholar_job_lv,scholar_job_exp,"curHP","curMP",
  belief,"Map","Pos_X","Pos_Z","Money","Stone","BindingGold","SkillPoint",
  "SkillExp","MaxHP","MaxMP",character_slot,lifecycle_state,lifecycle_version,
  zodiac_type,zodiac_level,holy_suit_points)
 SELECT account_id,1,'AresMage','male',0,0,3,140,0,0,0,1500,177,1,0,165,-97,
  10000,10,0,10,0,1500,177,0,'active',1,0,1,0 FROM mage_context RETURNING id
) UPDATE mage_context SET character_id=c.id FROM c;
