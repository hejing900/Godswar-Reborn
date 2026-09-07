Set-StrictMode -Version Latest

function Get-NameplateGrantStatusSql(
    [string]$OperationHex,
    [string]$RequestHashHex
) {
    $sql = @"
BEGIN READ ONLY;
WITH
$(Get-NameplateGrantContentCtesSql),
$(Get-NameplateGrantStateCtesSql),
receipt AS (
 SELECT a.* FROM public.command_audit a
 WHERE a.principal_type='developer' AND a.principal_key='13'
   AND a.aggregate_type='character_inventory'
   AND a.aggregate_key='character:2'
   AND a.command_family='faction_crier_nameplate_test_kit'
   AND a.operation_id=decode('__OPERATION_HEX__','hex')
), receipt_state AS (
 SELECT count(*) receipt_count,
   COALESCE(bool_and(
     r.request_hash=decode('__REQUEST_HASH_HEX__','hex')
     AND r.outcome_code='applied'
     AND r.retention_policy='permanent'
     AND r.detail_payload->>'fixtureVersion'='1'
     AND r.detail_payload->>'accountId'='13'
     AND r.detail_payload->>'characterId'='2'
     AND r.detail_payload->>'realmId'='1'
     AND r.detail_payload->>'targetQuantityEach'='10'
     AND r.detail_payload->>'firstItemId'='3820'
     AND r.detail_payload->>'lastItemId'='3825'
     AND r.detail_payload->>'publishedItemRevision'=
       'AC11E2A725B0450B93D9C71F021F2D95B19EB4204ACC8E36B54CFEF1F8B9A063'
     AND jsonb_typeof(r.detail_payload->'itemAuditIds')='array'
     AND jsonb_typeof(r.detail_payload->'itemInstanceIds')='array'
     AND jsonb_array_length(r.detail_payload->'itemAuditIds')=
       (r.detail_payload->>'mutationCount')::integer
     AND jsonb_array_length(r.detail_payload->'itemInstanceIds')=6
     AND (r.detail_payload->>'currentInventoryRevision')::bigint=
       (r.detail_payload->>'previousInventoryRevision')::bigint +
       CASE WHEN (r.detail_payload->>'mutationCount')::integer>0
         THEN 1 ELSE 0 END),false) receipt_fields_valid,
   min(r.id) audit_id,
   (array_agg(r.detail_payload ORDER BY r.id))[1] detail_payload
 FROM receipt r
), linked_audits AS (
 SELECT count(*) linked_count
 FROM receipt r
 CROSS JOIN LATERAL jsonb_array_elements_text(CASE
   WHEN jsonb_typeof(r.detail_payload->'itemAuditIds')='array'
   THEN r.detail_payload->'itemAuditIds' ELSE '[]'::jsonb END) linked(id)
 JOIN public.character_item_audit a ON a.id=linked.id::bigint
 WHERE a.source='localdev-faction-crier-nameplate-test-kit-v1'
   AND a.action IN ('add','stack_increase') AND a.user_id=2
   AND a.item_location=1 AND a.slot_index BETWEEN 0 AND 95
   AND a.prop_id BETWEEN 3820 AND 3825
   AND a.item_quality=1 AND a.item_grade=1 AND a.item_exp=0
), classified AS (
 SELECT cs.*,ids.*,inv.*,target.*,
   cs.content_valid AND ids.exact_rows=1
     AND inv.invalid_nameplate_rows=0 AND target.invalid_groups=0
     AND target.missing_units>=0
     AND target.required_slots<=inv.empty_slots AS source_ready,
   rs.receipt_count=1 AND rs.receipt_fields_valid
     AND la.linked_count=
       COALESCE((rs.detail_payload->>'mutationCount')::integer,-1)
     AND cs.content_valid AND ids.exact_rows=1 AND target.target_exact
     AND ids.inventory_revision=
       (rs.detail_payload->>'currentInventoryRevision')::bigint
     AND inv.preserved_items_hash=
       rs.detail_payload->>'preservedItemsSha256'
     AND inv.nameplate_items_hash=
       rs.detail_payload->>'nameplateItemsSha256'
     AND ids.non_inventory_character_hash=
       rs.detail_payload->>'nonInventoryCharacterSha256'
     AND ids.account_hash=rs.detail_payload->>'accountSha256'
       AS post_ready,
   rs.receipt_count,rs.receipt_fields_valid,rs.audit_id,
   rs.detail_payload,la.linked_count
 FROM content_state cs CROSS JOIN identity_state ids
 CROSS JOIN inventory_state inv CROSS JOIN target_state target
 CROSS JOIN receipt_state rs CROSS JOIN linked_audits la
)
SELECT 'FACTION_NAMEPLATE_STATUS|' || jsonb_build_object(
 'contentValid',c.content_valid,'publishedItemRevision',c.revision,
 'identityReady',c.exact_rows=1,'sourceReady',c.source_ready,
 'postReady',c.post_ready,'inventoryRevision',c.inventory_revision,
 'bagRows',c.bag_rows,'bagUnits',c.bag_units,
 'totalItemRows',c.total_item_rows,'emptySlots',c.empty_slots,
 'nameplateRows',c.nameplate_rows,
 'invalidNameplateRows',c.invalid_nameplate_rows,
 'invalidNameplateGroups',c.invalid_groups,
 'nameplateCounts',c.counts,'missingUnits',c.missing_units,
 'requiredSlots',c.required_slots,
 'preservedItemsSha256',c.preserved_items_hash,
 'nameplateItemsSha256',c.nameplate_items_hash,
 'nonInventoryCharacterSha256',c.non_inventory_character_hash,
 'accountSha256',c.account_hash,'receiptCount',c.receipt_count,
 'receiptValid',c.receipt_count=1 AND c.receipt_fields_valid
   AND c.linked_count=COALESCE(
     (c.detail_payload->>'mutationCount')::integer,-1),
 'receiptAuditId',c.audit_id,'linkedItemAuditCount',c.linked_count,
 'receiptDetail',c.detail_payload)::text
FROM classified c;
COMMIT;
"@
    $sql.Replace('__OPERATION_HEX__', $OperationHex).
        Replace('__REQUEST_HASH_HEX__', $RequestHashHex)
}
