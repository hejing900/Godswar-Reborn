[CmdletBinding(SupportsShouldProcess = $true, ConfirmImpact = 'High')]
param(
    [ValidateSet('Status', 'Apply')]
    [string]$Mode = 'Status',

    [string]$Container = 'godswar-postgres',
    [string]$Database = 'godswar_local',
    [string]$DatabaseUser = 'godswar'
)

# Grants character 2 (account 1, the local 'test' character) exactly one Dodo
# Magic Jade and the six Eagle Eye pet-skill books I-VI.
#
# Evidence for every id:
#   Localization/en_us/UI/Base/LuaText.lua  hallo_11062 = "[Magic Jade: Dodo]"
#   artifacts/pet-skill-books-client-map.txt family 13 Dodo:
#     10301->2900 I, 10302->2904 II, 10303->2908 III,
#     10404->2912 IV, 10405->2916 V, 10406->2920 VI
#   src/Godswar.Server/State/PetSkillBookActivationPolicy.Books.cs pins the same
#     six mappings, and all seven templates are published consume items.
#
# Status is read-only. Apply runs one transaction that locks the character, the
# bag, and the pets, refuses to run twice, inserts the seven rows into free bag
# slots at bag slots 80-86, writes one character_item_audit row per item, and
# advances character_base.inventory_revision by one. It writes no command_audit
# receipt: no player command and no wire opcode produced these rows.
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$characterId = 2
$accountId = 1
$kit = @(
    [pscustomobject]@{ Slot = 80; Id = 11062; Name = 'Magic Jade: Dodo' },
    [pscustomobject]@{ Slot = 81; Id = 10301; Name = 'Pet Skill: Eagle Eye I' },
    [pscustomobject]@{ Slot = 82; Id = 10302; Name = 'Pet Skill: Eagle Eye II' },
    [pscustomobject]@{ Slot = 83; Id = 10303; Name = 'Pet Skill: Eagle Eye III' },
    [pscustomobject]@{ Slot = 84; Id = 10404; Name = 'Pet Skill: Eagle Eye IV' },
    [pscustomobject]@{ Slot = 85; Id = 10405; Name = 'Pet Skill: Eagle Eye V' },
    [pscustomobject]@{ Slot = 86; Id = 10406; Name = 'Pet Skill: Eagle Eye VI' }
)
$auditSource = 'localdev-dodo-pet-kit'
$kitIds = ($kit | ForEach-Object { $_.Id }) -join ', '

function Invoke-Psql([string]$Sql, [string]$Marker) {
    $output = $Sql | & docker exec -i $Container `
        psql -X -q -A -t -v ON_ERROR_STOP=1 `
        -U $DatabaseUser -d $Database 2>&1
    $exitCode = $LASTEXITCODE
    $lines = @($output | ForEach-Object { $_.ToString() })
    if ($exitCode -ne 0) {
        throw "The grant failed and rolled back:`n$($lines -join "`n")"
    }
    $receipt = $lines | Where-Object {
        $_.StartsWith($Marker, [StringComparison]::Ordinal)
    } | Select-Object -Last 1
    if ([string]::IsNullOrWhiteSpace($receipt)) {
        throw "The database returned no receipt for marker $Marker."
    }
    $receipt.Substring($Marker.Length) | ConvertFrom-Json
}

$statusSql = @"
BEGIN;
WITH character_state AS (
    SELECT character.id, character.account_id, character.name,
           character.inventory_revision
    FROM public.character_base character
    WHERE character.id = $characterId AND character.account_id = $accountId
), granted AS (
    SELECT item.slot_index, item.prop_id
    FROM public.character_items item
    WHERE item.user_id = $characterId
      AND item.item_location = 1
      AND item.prop_id IN ($kitIds)
), audited AS (
    SELECT audit.id
    FROM public.character_item_audit audit
    WHERE audit.user_id = $characterId
      AND audit.source = '$auditSource'
), available AS (
    SELECT candidate.slot_index
    FROM generate_series(0, 95) candidate(slot_index)
    WHERE NOT EXISTS (
        SELECT 1 FROM public.character_items occupied
        WHERE occupied.user_id = $characterId
          AND occupied.item_location = 1
          AND occupied.slot_index = candidate.slot_index
    )
)
SELECT 'DODO_KIT_STATUS|' || jsonb_build_object(
    'characterId', character_state.id,
    'characterName', character_state.name,
    'accountId', character_state.account_id,
    'inventoryRevision', character_state.inventory_revision,
    'grantedCount', (SELECT count(*) FROM granted),
    'granted', (SELECT COALESCE(jsonb_agg(jsonb_build_object(
                   'slot', slot_index, 'item', prop_id) ORDER BY slot_index), '[]'::jsonb)
                FROM granted),
    'auditCount', (SELECT count(*) FROM audited),
    'freeSlotCount', (SELECT count(*) FROM available),
    'publishedTemplates', (SELECT count(*) FROM public.item_templates template
                           WHERE template.id IN ($kitIds)),
    'nextFreeSlots', (SELECT COALESCE(jsonb_agg(slot_index ORDER BY slot_index), '[]'::jsonb)
                      FROM (SELECT slot_index FROM available ORDER BY slot_index LIMIT 10) head)
)::text
FROM character_state;
ROLLBACK;
"@

$applySql = @"
BEGIN;
DO `$dodo_kit`$
DECLARE
    v_revision bigint;
    v_item record;
    v_item_id bigint;
    v_audit bigint;
    v_audit_ids bigint[] := ARRAY[]::bigint[];
    v_conflict integer;
    v_audited integer;
BEGIN
    PERFORM character.id FROM public.character_base character
    WHERE character.id = $characterId AND character.account_id = $accountId
    FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Character $characterId is not owned by account $accountId.';
    END IF;
    PERFORM item.id FROM public.character_items item
    WHERE item.user_id = $characterId
    ORDER BY item.item_location, item.slot_index, item.id
    FOR UPDATE;
    PERFORM pet.id FROM public.character_pets pet
    WHERE pet.user_id = $characterId ORDER BY pet.id FOR UPDATE;

    SELECT count(*) INTO v_conflict
    FROM public.character_items existing
    WHERE existing.user_id = $characterId
      AND existing.item_location = 1
      AND existing.prop_id IN ($kitIds);
    SELECT count(*) INTO v_audited
    FROM public.character_item_audit audit
    WHERE audit.user_id = $characterId AND audit.source = '$auditSource';
    IF v_conflict > 0 OR v_audited > 0 THEN
        RAISE EXCEPTION 'The Dodo pet kit is already present in character % inventory.', $characterId;
    END IF;

    IF (SELECT count(*) FROM public.item_templates template
        WHERE template.id IN ($kitIds)) <> 7 THEN
        RAISE EXCEPTION 'The seven Dodo pet-kit templates are not all published.';
    END IF;

    FOR v_item IN
        SELECT * FROM (VALUES
            (80, 11062), (81, 10301), (82, 10302), (83, 10303),
            (84, 10404), (85, 10405), (86, 10406)
        ) AS kit(slot_index, prop_id)
    LOOP
        IF EXISTS (
            SELECT 1 FROM public.character_items occupied
            WHERE occupied.user_id = $characterId
              AND occupied.item_location = 1
              AND occupied.slot_index = v_item.slot_index
        ) THEN
            RAISE EXCEPTION 'Bag slot % is already occupied.', v_item.slot_index;
        END IF;

        INSERT INTO public.character_items(
            user_id, item_location, slot_index, prop_id,
            item_quality, item_grade, bound, stack)
        VALUES ($characterId, 1, v_item.slot_index, v_item.prop_id, 1, 1, 0, 1)
        RETURNING id INTO v_item_id;

        INSERT INTO public.character_item_audit(
            source, action, user_id, item_location, slot_index,
            prop_id, item_quality, item_grade, item_exp, old_item)
        VALUES ('$auditSource', 'create', $characterId, 1,
                v_item.slot_index, v_item.prop_id, 1, 1, 0, NULL)
        RETURNING id INTO v_audit;
        v_audit_ids := v_audit_ids || v_audit;
    END LOOP;

    UPDATE public.character_base
    SET inventory_revision = inventory_revision + 1
    WHERE id = $characterId AND account_id = $accountId
    RETURNING inventory_revision INTO v_revision;
    IF v_revision IS NULL THEN
        RAISE EXCEPTION 'The inventory revision did not advance.';
    END IF;

    IF (SELECT count(*) FROM public.character_items item
        WHERE item.user_id = $characterId
          AND item.item_location = 1
          AND item.prop_id IN ($kitIds)) <> 7 THEN
        RAISE EXCEPTION 'The Dodo pet kit did not land as exactly seven items.';
    END IF;
END
`$dodo_kit`$;

SELECT 'DODO_KIT_APPLIED|' || jsonb_build_object(
    'characterId', base.id,
    'inventoryRevision', base.inventory_revision,
    'itemAuditIds', (SELECT COALESCE(jsonb_agg(audit.id ORDER BY audit.id), '[]'::jsonb)
                     FROM public.character_item_audit audit
                     WHERE audit.user_id = $characterId
                       AND audit.source = '$auditSource'),
    'granted', (SELECT COALESCE(jsonb_agg(jsonb_build_object(
                    'slot', slot_index, 'item', prop_id) ORDER BY slot_index), '[]'::jsonb)
                FROM public.character_items item
                WHERE item.user_id = $characterId
                  AND item.item_location = 1
                  AND item.prop_id IN ($kitIds))
)::text
FROM public.character_base base
WHERE base.id = $characterId;
COMMIT;
"@

$status = Invoke-Psql $statusSql 'DODO_KIT_STATUS|'
$summary = [pscustomobject]@{
    Mode                  = $Mode
    CharacterId           = $status.characterId
    CharacterName         = $status.characterName
    AccountId             = $status.accountId
    InventoryRevision     = $status.inventoryRevision
    GrantedItems          = $status.grantedCount
    AuditRows             = $status.auditCount
    FreeSlotCount         = $status.freeSlotCount
    PublishedTemplates    = $status.publishedTemplates
    NextFreeSlots         = $status.nextFreeSlots
    Kit                   = $kit
}

if ($Mode -eq 'Status') { return $summary }

if ($status.grantedCount -ne 0 -or $status.auditCount -ne 0) {
    throw 'The Dodo pet kit is already granted; nothing to apply.'
}
if ($status.publishedTemplates -ne 7) {
    throw 'The seven Dodo pet-kit templates are not all published.'
}

if (-not $PSCmdlet.ShouldProcess(
        "character $characterId ($($status.characterName)) bag slots 80-86",
        'Append one Dodo Magic Jade and six Eagle Eye skill books')) {
    return $summary
}

$applied = Invoke-Psql $applySql 'DODO_KIT_APPLIED|'
$verified = Invoke-Psql $statusSql 'DODO_KIT_STATUS|'
if ($verified.grantedCount -ne 7 -or $verified.auditCount -ne 7 -or
    $verified.inventoryRevision -ne ($status.inventoryRevision + 1)) {
    throw 'The committed Dodo pet kit failed read-back verification.'
}

[pscustomobject]@{
    Result               = 'Applied'
    CharacterId          = $applied.characterId
    InventoryRevision    = $applied.inventoryRevision
    ItemAuditIds         = $applied.itemAuditIds
    VerifiedGrantedItems = $verified.grantedCount
    VerifiedAuditRows    = $verified.auditCount
    VerifiedGranted      = $verified.granted
}
