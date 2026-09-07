Set-StrictMode -Version Latest

function Get-NameplateGrantApplySql(
    [string]$OperationHex,
    [string]$RequestHashHex
) {
    $sql = @"
BEGIN ISOLATION LEVEL SERIALIZABLE;
SET LOCAL lock_timeout='5s';
SET LOCAL statement_timeout='30s';

CREATE TEMP TABLE nameplate_grant_desired(
 ordinal smallint PRIMARY KEY,item_id integer UNIQUE NOT NULL);
INSERT INTO nameplate_grant_desired VALUES
 (1,3820),(2,3821),(3,3822),(4,3823),(5,3824),(6,3825);
CREATE TEMP TABLE nameplate_grant_context(
 account_id integer NOT NULL,character_id integer NOT NULL,
 old_inventory_revision bigint NOT NULL,new_inventory_revision bigint,
 publication_revision text NOT NULL,counts_before jsonb NOT NULL,
 preserved_items_hash text NOT NULL,nameplate_items_hash_before text NOT NULL,
 character_hash text NOT NULL,account_hash text NOT NULL);
CREATE TEMP TABLE nameplate_grant_mutations(
 ordinal bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 action text NOT NULL,item_instance_id bigint NOT NULL,
 slot_index smallint NOT NULL,prop_id integer NOT NULL,old_item jsonb,
 item_audit_id bigint);
CREATE TEMP TABLE nameplate_grant_result(
 audit_id bigint NOT NULL,old_revision bigint NOT NULL,
 new_revision bigint NOT NULL,mutation_count integer NOT NULL,
 item_audit_count integer NOT NULL,nameplate_items_hash text NOT NULL);

DO `$guard`$
DECLARE
 v_content_valid boolean; v_revision text; v_identity_count integer;
 v_inventory_revision bigint; v_invalid_rows integer;
 v_invalid_groups integer; v_missing_units integer;
 v_required_slots integer; v_empty_slots integer;
 v_counts jsonb; v_preserved_hash text; v_nameplate_hash text;
 v_character_hash text; v_account_hash text;
BEGIN
 PERFORM pg_advisory_xact_lock(13,3820);
 PERFORM a.id FROM public.accounts a WHERE a.id=13 FOR UPDATE;
 PERFORM c.id FROM public.character_base c WHERE c.id=2 FOR UPDATE;
 PERFORM i.id FROM public.character_items i WHERE i.user_id=2
   ORDER BY i.item_location,i.slot_index,i.id FOR UPDATE;
 PERFORM p.revision FROM public.item_template_content_publication p
   WHERE p.family='items' FOR SHARE;
 PERFORM r.revision FROM public.item_template_content_revisions r
   WHERE r.revision=(SELECT revision
     FROM public.item_template_content_publication WHERE family='items')
   FOR SHARE;
 PERFORM d.id FROM public.item_template_content_definitions d
   WHERE d.revision=(SELECT revision
     FROM public.item_template_content_publication WHERE family='items')
     AND d.id BETWEEN 3820 AND 3825 ORDER BY d.id FOR SHARE;
 PERFORM t.id FROM public.item_templates t
   WHERE t.id BETWEEN 3820 AND 3825 ORDER BY t.id FOR SHARE;

 IF EXISTS (SELECT 1 FROM public.command_audit a
   WHERE a.principal_type='developer' AND a.principal_key='13'
     AND a.aggregate_type='character_inventory'
     AND a.aggregate_key='character:2'
     AND a.command_family='faction_crier_nameplate_test_kit'
     AND a.operation_id=decode('__OPERATION_HEX__','hex')) THEN
   RAISE EXCEPTION 'The permanent Nameplate test-kit receipt already exists.';
 END IF;

 WITH $(Get-NameplateGrantContentCtesSql)
 SELECT revision,content_valid INTO v_revision,v_content_valid
 FROM content_state;
 IF NOT COALESCE(v_content_valid,false) THEN
   RAISE EXCEPTION 'Published Nameplate content is not exact.';
 END IF;

 WITH $(Get-NameplateGrantContentCtesSql),
      $(Get-NameplateGrantStateCtesSql)
 SELECT ids.exact_rows,ids.inventory_revision,
   inv.invalid_nameplate_rows,target.invalid_groups,
   target.missing_units,target.required_slots,inv.empty_slots,
   target.counts,inv.preserved_items_hash,inv.nameplate_items_hash,
   ids.non_inventory_character_hash,ids.account_hash
 INTO v_identity_count,v_inventory_revision,v_invalid_rows,
   v_invalid_groups,v_missing_units,v_required_slots,v_empty_slots,
   v_counts,v_preserved_hash,v_nameplate_hash,
   v_character_hash,v_account_hash
 FROM identity_state ids CROSS JOIN inventory_state inv
 CROSS JOIN target_state target;
 IF v_identity_count<>1 THEN
   RAISE EXCEPTION 'Account 13 / character 2 is not safely offline and exact.';
 END IF;
 IF v_invalid_rows<>0 OR v_invalid_groups<>0 OR v_missing_units<0 THEN
   RAISE EXCEPTION 'Existing Nameplate rows are invalid or exceed the target.';
 END IF;
 IF v_required_slots>v_empty_slots THEN
   RAISE EXCEPTION 'Nameplate kit needs % slots but only % are free.',
     v_required_slots,v_empty_slots;
 END IF;
 INSERT INTO nameplate_grant_context VALUES(
   13,2,v_inventory_revision,NULL,v_revision,v_counts,
   v_preserved_hash,v_nameplate_hash,v_character_hash,v_account_hash);
END
`$guard`$;

WITH before_state AS MATERIALIZED (
 SELECT i.id,i.slot_index,i.prop_id,to_jsonb(i) old_item
 FROM public.character_items i
 JOIN nameplate_grant_desired d ON d.item_id=i.prop_id
 WHERE i.user_id=2 AND i.item_location=1 AND i.stack<10
), updated AS (
 UPDATE public.character_items i SET stack=10,updated_at=now()
 FROM before_state b WHERE i.id=b.id
 RETURNING i.id,i.slot_index,i.prop_id
)
INSERT INTO nameplate_grant_mutations(
 action,item_instance_id,slot_index,prop_id,old_item)
SELECT 'stack_increase',u.id,u.slot_index,u.prop_id,b.old_item
FROM updated u JOIN before_state b ON b.id=u.id
ORDER BY u.prop_id;

WITH missing AS MATERIALIZED (
 SELECT d.*,row_number() OVER (ORDER BY d.ordinal) row_number
 FROM nameplate_grant_desired d
 WHERE NOT EXISTS (SELECT 1 FROM public.character_items i
   WHERE i.user_id=2 AND i.prop_id=d.item_id)
), empty_slots AS MATERIALIZED (
 SELECT slot_index::smallint,
   row_number() OVER (ORDER BY slot_index) row_number
 FROM generate_series(0,95) slot(slot_index)
 WHERE NOT EXISTS (SELECT 1 FROM public.character_items i
   WHERE i.user_id=2 AND i.item_location=1
     AND i.slot_index=slot.slot_index)
), inserted AS (
 INSERT INTO public.character_items(
   user_id,item_location,slot_index,prop_id,item_quality,item_grade,
   bound,stack,item_exp,holy_suit_code)
 SELECT 2,1,e.slot_index,m.item_id,1,1,1,10,0,0
 FROM missing m JOIN empty_slots e USING(row_number)
 ORDER BY m.ordinal
 RETURNING id,slot_index,prop_id
)
INSERT INTO nameplate_grant_mutations(
 action,item_instance_id,slot_index,prop_id,old_item)
SELECT 'add',id,slot_index,prop_id,NULL FROM inserted ORDER BY prop_id;

UPDATE nameplate_grant_context
SET new_inventory_revision=old_inventory_revision;
WITH mutation_count AS (
 SELECT count(*) count FROM nameplate_grant_mutations
), advanced AS (
 UPDATE public.character_base c
 SET inventory_revision=c.inventory_revision+1
 FROM nameplate_grant_context x,mutation_count m
 WHERE c.id=x.character_id AND c.account_id=x.account_id
   AND c.inventory_revision=x.old_inventory_revision AND m.count>0
 RETURNING c.inventory_revision
)
UPDATE nameplate_grant_context x
SET new_inventory_revision=a.inventory_revision FROM advanced a;

DO `$audits`$
DECLARE v_mutation record; v_audit_id bigint;
BEGIN
 FOR v_mutation IN
   SELECT * FROM nameplate_grant_mutations ORDER BY ordinal
 LOOP
   INSERT INTO public.character_item_audit(
     source,action,user_id,item_location,slot_index,prop_id,
     item_quality,item_grade,item_exp,old_item)
   VALUES('localdev-faction-crier-nameplate-test-kit-v1',
     v_mutation.action,2,1,v_mutation.slot_index,v_mutation.prop_id,
     1,1,0,v_mutation.old_item)
   RETURNING id INTO v_audit_id;
   UPDATE nameplate_grant_mutations SET item_audit_id=v_audit_id
   WHERE ordinal=v_mutation.ordinal;
 END LOOP;
END
`$audits`$;

DO `$verify`$
DECLARE
 v_context nameplate_grant_context%ROWTYPE; v_identity_count integer;
 v_inventory_revision bigint; v_invalid_rows integer;
 v_invalid_groups integer; v_target_exact boolean;
 v_preserved_hash text; v_nameplate_hash text;
 v_character_hash text; v_account_hash text;
 v_mutation_count integer; v_item_audit_count integer;
 v_item_audit_ids jsonb; v_item_instance_ids jsonb; v_audit_id bigint;
BEGIN
 SELECT * INTO STRICT v_context FROM nameplate_grant_context;
 SELECT count(*)::integer,count(item_audit_id)::integer
 INTO v_mutation_count,v_item_audit_count
 FROM nameplate_grant_mutations;
 IF v_context.new_inventory_revision<>
   v_context.old_inventory_revision+
     (CASE WHEN v_mutation_count>0 THEN 1 ELSE 0 END)
   OR v_item_audit_count<>v_mutation_count THEN
   RAISE EXCEPTION 'Inventory revision or item-audit cardinality is invalid.';
 END IF;

 WITH $(Get-NameplateGrantContentCtesSql),
      $(Get-NameplateGrantStateCtesSql)
 SELECT ids.exact_rows,ids.inventory_revision,
   inv.invalid_nameplate_rows,target.invalid_groups,target.target_exact,
   inv.preserved_items_hash,inv.nameplate_items_hash,
   ids.non_inventory_character_hash,ids.account_hash
 INTO v_identity_count,v_inventory_revision,v_invalid_rows,
   v_invalid_groups,v_target_exact,v_preserved_hash,v_nameplate_hash,
   v_character_hash,v_account_hash
 FROM identity_state ids CROSS JOIN inventory_state inv
 CROSS JOIN target_state target;
 IF v_identity_count<>1 OR v_inventory_revision<>
      v_context.new_inventory_revision
    OR v_invalid_rows<>0 OR v_invalid_groups<>0 OR NOT v_target_exact
    OR v_preserved_hash<>v_context.preserved_items_hash
    OR v_character_hash<>v_context.character_hash
    OR v_account_hash<>v_context.account_hash THEN
   RAISE EXCEPTION 'Post-grant preservation verification failed.';
 END IF;
 SELECT COALESCE(jsonb_agg(item_audit_id ORDER BY ordinal),'[]'::jsonb)
 INTO v_item_audit_ids FROM nameplate_grant_mutations;
 SELECT jsonb_agg(i.id ORDER BY i.prop_id)
 INTO v_item_instance_ids FROM public.character_items i
 WHERE i.user_id=2 AND i.prop_id BETWEEN 3820 AND 3825;
 IF jsonb_array_length(v_item_instance_ids)<>6 THEN
   RAISE EXCEPTION 'The verified Nameplate item identity set is incomplete.';
 END IF;

 INSERT INTO public.command_audit(
   principal_type,principal_key,aggregate_type,aggregate_key,
   command_family,operation_id,request_hash,outcome_code,
   detail_payload,retention_policy)
 VALUES('developer','13','character_inventory','character:2',
   'faction_crier_nameplate_test_kit',
   decode('__OPERATION_HEX__','hex'),
   decode('__REQUEST_HASH_HEX__','hex'),'applied',jsonb_build_object(
     'fixtureVersion',1,'source','offline_isolated_localdevelopment_grant',
     'accountId',13,'characterId',2,'realmId',1,
     'firstItemId',3820,'lastItemId',3825,'targetQuantityEach',10,
     'nameplateCountsBefore',v_context.counts_before,
     'previousInventoryRevision',v_context.old_inventory_revision,
     'currentInventoryRevision',v_context.new_inventory_revision,
     'publishedItemRevision',v_context.publication_revision,
     'mutationCount',v_mutation_count,
     'itemAuditIds',v_item_audit_ids,
     'itemInstanceIds',v_item_instance_ids,
     'preservedItemsSha256',v_preserved_hash,
     'nameplateItemsSha256',v_nameplate_hash,
     'nonInventoryCharacterSha256',v_character_hash,
     'accountSha256',v_account_hash),
   'permanent') RETURNING id INTO v_audit_id;
 INSERT INTO nameplate_grant_result VALUES(
   v_audit_id,v_context.old_inventory_revision,
   v_context.new_inventory_revision,v_mutation_count,
   v_item_audit_count,v_nameplate_hash);
END
`$verify`$;
COMMIT;
SELECT 'FACTION_NAMEPLATE_RESULT|' || jsonb_build_object(
 'status','Applied','changed',mutation_count>0,
 'accountId',13,'characterId',2,'characterName','test2',
 'targetQuantityEach',10,'inventoryRevisionBefore',old_revision,
 'inventoryRevisionAfter',new_revision,'mutationCount',mutation_count,
 'itemAuditCount',item_audit_count,'auditId',audit_id,
 'nameplateItemsSha256',nameplate_items_hash)::text
FROM nameplate_grant_result;
"@
    $sql.Replace('__OPERATION_HEX__', $OperationHex).
        Replace('__REQUEST_HASH_HEX__', $RequestHashHex)
}
