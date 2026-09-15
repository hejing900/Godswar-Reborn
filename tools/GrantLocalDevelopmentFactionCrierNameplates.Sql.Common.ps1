Set-StrictMode -Version Latest

function Get-NameplateGrantContentCtesSql {
    @'
desired_nameplates(ordinal,item_id,name_key,display_name,icon) AS (
 VALUES
  (1,3820,'Nameplate1','Nameplate 1','216,936'),
  (2,3821,'Nameplate2','Nameplate 2','252,936'),
  (3,3822,'Nameplate3','Nameplate 3','288,936'),
  (4,3823,'Nameplate4','Nameplate 4','324,936'),
  (5,3824,'Nameplate5','Nameplate 5','360,936'),
  (6,3825,'Nameplate6','Nameplate 6','396,936')
), item_release AS (
 SELECT p.revision,r.source,r.manifest_version,r.entry_count,r.sealed_at
 FROM public.item_template_content_publication p
 JOIN public.item_template_content_revisions r USING(revision)
 WHERE p.family='items'
), content_rows AS (
 SELECT count(*) FILTER (WHERE d.id IS NOT NULL) definition_count,
   count(*) FILTER (WHERE t.id IS NOT NULL) runtime_count,
   COALESCE(bool_and(
     d.kind='consume item' AND d.name_key=n.name_key
     AND d.display_name=n.display_name AND d.equipment_slot=0
     AND cardinality(d.class_ids)=0 AND d.min_level IS NULL
     AND d.max_level IS NULL AND d.hand IS NULL
     AND d.skill_flag IS NULL
     AND d.texture='./Localization/en_us/UI/Texture/Icon.gwo'
     AND d.icon=n.icon
     AND d.stats=jsonb_build_object(
       'ID',n.item_id::text,'Type','consume item',
       'Texture','./Localization/en_us/UI/Texture/Icon.gwo',
       'Icon',n.icon,'Random','0','Distribution','150,200',
       'Money','0','Overlap','99','BindType','1')
     AND to_jsonb(t)=to_jsonb(d)-'revision'),false) rows_valid
 FROM desired_nameplates n
 LEFT JOIN item_release r ON true
 LEFT JOIN public.item_template_content_definitions d
   ON d.revision=r.revision AND d.id=n.item_id
 LEFT JOIN public.item_templates t ON t.id=n.item_id
), content_state AS (
 SELECT r.revision,
   r.revision=
     'AC11E2A725B0450B93D9C71F021F2D95B19EB4204ACC8E36B54CFEF1F8B9A063'
   AND r.source=
     'items-v9+holy-v3+element-v1+sockets-v1+holy-stones-v2+zephyr-v1+mount-speed-v3+pets-v4+nameplates-v1'
   AND r.manifest_version=9 AND r.entry_count=1770
   AND r.sealed_at IS NOT NULL AND c.definition_count=6
   AND c.runtime_count=6 AND c.rows_valid AS content_valid
 FROM item_release r CROSS JOIN content_rows c
)
'@
}

function Get-NameplateGrantStateCtesSql {
    @'
identity_state AS (
 SELECT count(*) FILTER (WHERE a.username='test2'
     AND a.login_status=0 AND a.login_presence_token IS NULL
     AND c.name='test2' AND c.server_id=1
     AND c.lifecycle_state='active' AND c.deleted_at IS NULL
     AND c.checkpoint_owner_id IS NULL) exact_rows,
   max(c.inventory_revision) inventory_revision,
   max(encode(sha256(convert_to(
     (to_jsonb(c)-'inventory_revision')::text,'UTF8')),'hex'))
       non_inventory_character_hash,
   max(encode(sha256(convert_to(to_jsonb(a)::text,'UTF8')),'hex'))
       account_hash
 FROM public.accounts a
 JOIN public.character_base c ON c.account_id=a.id
 WHERE a.id=13 AND c.id=2
), nameplate_counts AS (
 SELECT n.ordinal,n.item_id,
   COALESCE(sum(i.stack) FILTER (WHERE i.id IS NOT NULL),0)::integer units,
   count(i.id)::integer row_count
 FROM desired_nameplates n
 LEFT JOIN public.character_items i
   ON i.user_id=2 AND i.prop_id=n.item_id
 GROUP BY n.ordinal,n.item_id
), inventory_state AS (
 SELECT
   count(*) FILTER (WHERE i.item_location=1) bag_rows,
   COALESCE(sum(i.stack) FILTER (WHERE i.item_location=1),0) bag_units,
   count(*) total_item_rows,
   count(*) FILTER (WHERE i.prop_id BETWEEN 3820 AND 3825)
       nameplate_rows,
   count(*) FILTER (WHERE i.prop_id BETWEEN 3820 AND 3825 AND (
       i.item_location<>1 OR i.slot_index NOT BETWEEN 0 AND 95
       OR i.bound<>1 OR i.stack NOT BETWEEN 1 AND 10
       OR i.item_quality<>1 OR i.item_grade<>1 OR i.item_exp<>0
       OR i.holy_suit_code<>0 OR i.holy_socket_count<>0
       OR num_nonnulls(i.attribute1,i.attribute2,i.attribute3,
          i.attribute4,i.attribute5,i.attribute_level1,
          i.attribute_level2,i.attribute_level3,i.attribute_level4,
          i.attribute_level5,i.class_attribute1,i.class_attribute2,
          i.elemental_attribute1,i.elemental_attribute2,
          i.holy_socket1_effect_id,i.holy_socket1_level,
          i.holy_socket2_effect_id,i.holy_socket2_level,
          i.holy_socket3_effect_id,i.holy_socket3_level,
          i.holy_socket4_effect_id,i.holy_socket4_level,
          i.holy_socket5_effect_id,i.holy_socket5_level,
          i.holy_socket6_effect_id,i.holy_socket6_level,
          i.holy_socket1_value,i.holy_socket2_value,
          i.holy_socket3_value,i.holy_socket4_value)<>0))
       invalid_nameplate_rows,
   (SELECT count(*) FROM generate_series(0,95) slot(slot_index)
     WHERE NOT EXISTS (SELECT 1 FROM public.character_items occupied
       WHERE occupied.user_id=2 AND occupied.item_location=1
       AND occupied.slot_index=slot.slot_index)) empty_slots,
   encode(sha256(convert_to(COALESCE(jsonb_agg(to_jsonb(i)
     ORDER BY i.item_location,i.slot_index,i.id) FILTER (WHERE
       i.prop_id NOT BETWEEN 3820 AND 3825),'[]'::jsonb)::text,
       'UTF8')),'hex') preserved_items_hash,
   encode(sha256(convert_to(COALESCE(jsonb_agg(to_jsonb(i)
     ORDER BY i.prop_id,i.item_location,i.slot_index,i.id) FILTER (WHERE
       i.prop_id BETWEEN 3820 AND 3825),'[]'::jsonb)::text,
       'UTF8')),'hex') nameplate_items_hash
 FROM public.character_items i WHERE i.user_id=2
), target_state AS (
 SELECT jsonb_object_agg(item_id::text,units ORDER BY ordinal) counts,
   sum(10-units)::integer missing_units,
   count(*) FILTER (WHERE row_count=0)::integer required_slots,
   count(*) FILTER (WHERE row_count>1 OR units>10)::integer invalid_groups,
   bool_and(row_count=1 AND units=10) target_exact
 FROM nameplate_counts
)
'@
}
