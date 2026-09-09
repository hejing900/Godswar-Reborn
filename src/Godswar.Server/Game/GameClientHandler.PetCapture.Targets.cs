using Godswar.Server.Application.Pets;
using Godswar.Server.Application.WorldInstances;
using Godswar.Server.Protocol;

namespace Godswar.Server.Game;

internal sealed partial class GameClientHandler
{
    private readonly record struct PetCaptureKind(uint EggItemId,
        MedusaEncounterDifficulty Difficulty, PetCaptureContext Context = PetCaptureContext.Medusa);

    private bool TryResolvePetCaptureTarget(PetCaptureRequest request,
        out MonsterRuntimeSnapshot target, out PetCaptureKind kind)
    {
        target = default!;
        kind = default;
        var character = _character;
        if (character is null || !_registry.TryGetMonsterSnapshot(_session,
                character.CurrentMap, request.TargetObjectId, out var candidate) ||
            !candidate.IsAlive || !candidate.IsSpawned ||
            !_registry.IsMonsterVisibleTo(_session, candidate.ObjectId, candidate.SpawnGeneration) ||
            !IsWithinPetCaptureRange(character, candidate))
        {
            return false;
        }

        if (character.CurrentMap == 200 &&
            _registry.TryGetActiveMedusaCaptureDifficulty(_session, out var difficulty) &&
            WorldObjectIds.IsMedusaBabyRockElf(request.TargetObjectId) &&
            candidate.Definition.TemplateKey == MedusaIslandAmbientSpawnPolicy.BabyRockElfTemplateKey)
        {
            kind = new(RockElfEggItemId, difficulty);
        }
        else if (character.CurrentMap == 205 &&
            AtlantisPetSpawnPolicy.Matches(candidate.ObjectId, candidate.Definition.TemplateKey) &&
            _registry.CanCaptureAtlantisPet(_session, candidate.ObjectId))
        {
            kind = new(AtlantisPetSpawnPolicy.MermanEggItemId,
                MedusaEncounterDifficulty.Normal, PetCaptureContext.AtlantisMerman);
        }
        else
        {
            return false;
        }
        target = candidate;
        return true;
    }

    private bool IsPetCaptureCompletionValid(PetCaptureRequest request,
        MonsterRuntimeSnapshot expected, PetCaptureKind expectedKind) =>
        _character is { } character &&
        HasPetCaptureInventoryCapacity(character, request.KitBagSlot) &&
        TryResolvePetCaptureTarget(request, out var current, out var currentKind) &&
        currentKind == expectedKind && current.RuntimeInstanceId == expected.RuntimeInstanceId &&
        current.SpawnGeneration == expected.SpawnGeneration && current.HealthRevision == expected.HealthRevision;
}
