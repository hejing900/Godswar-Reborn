#include "SecurePendingOperationRegistry.h"

#include <cstring>
#include <limits>

namespace godswar::network {

SecureOperationRegistryResult
SecurePendingOperationRegistry::DescribeFighterLevelSealPacket(
    const void* packet,
    std::size_t packetBytes,
    std::uint64_t now,
    LegacyPacketDescriptor* descriptor,
    bool* recognized) noexcept {
    if (descriptor == nullptr || recognized == nullptr) {
        return SecureOperationRegistryResult::InvalidPacket;
    }
    *recognized = false;

    LegacyFighterLevelSealCommand command{};
    switch (ClassifyLegacyFighterLevelSealPacket(
                packet, packetBytes, &command)) {
        case LegacyFighterLevelSealPacketKind::Commit:
            *recognized = true;
            return DescribeFighterLevelSealCommand(
                command, now, descriptor);
        case LegacyFighterLevelSealPacketKind::Navigation:
            *recognized = true;
            return SecureOperationRegistryResult::Success;
        case LegacyFighterLevelSealPacketKind::InvalidMutation:
            *recognized = true;
            return SecureOperationRegistryResult::InvalidPacket;
        case LegacyFighterLevelSealPacketKind::Unrelated:
        default:
            return SecureOperationRegistryResult::Success;
    }
}

SecureOperationRegistryResult
SecurePendingOperationRegistry::DescribeFighterLevelSealCommand(
    const LegacyFighterLevelSealCommand& command,
    std::uint64_t now,
    LegacyPacketDescriptor* descriptor) noexcept {
    if (descriptor == nullptr ||
        (command.npcId != LegacySpartaFighterLevelSealNpc &&
         command.npcId != LegacyAthensFighterLevelSealNpc) ||
        (command.action != LegacyFighterLevelSealAction::Seal &&
         command.action != LegacyFighterLevelSealAction::Unseal)) {
        return SecureOperationRegistryResult::InvalidPacket;
    }

    const int identity[SecureGearSelectionCapacity]{
        command.action == LegacyFighterLevelSealAction::Seal
            ? LegacyFighterLevelSealSealSubId
            : LegacyFighterLevelSealUnsealSubId,
        -1,
        -1,
        -1};
    AcquireSRWLockExclusive(&lock_);
    Prune(now);
    if (!hasPrincipal_) {
        ReleaseSRWLockExclusive(&lock_);
        return SecureOperationRegistryResult::NoPrincipal;
    }
    if (!hasCharacter_) {
        ReleaseSRWLockExclusive(&lock_);
        return SecureOperationRegistryResult::NoCharacter;
    }

    // Both city NPCs mutate the same character-scoped seal state. Normalize
    // their IDs while retaining the requested seal/unseal action.
    Entry* entry = Find(
        SecureLegacyCommandFamily::FighterLevelSeal,
        0,
        identity,
        1);
    if (entry == nullptr) {
        if (now >
            (std::numeric_limits<std::uint64_t>::max)() -
                SecurePendingOperationLifetimeMilliseconds) {
            ReleaseSRWLockExclusive(&lock_);
            return SecureOperationRegistryResult::ClockFailure;
        }
        entry = FindAvailable();
        if (entry == nullptr) {
            ReleaseSRWLockExclusive(&lock_);
            return SecureOperationRegistryResult::Capacity;
        }
        if (!CreateOperationId(entry->operationId)) {
            ClearEntry(entry);
            ReleaseSRWLockExclusive(&lock_);
            return SecureOperationRegistryResult::RandomFailure;
        }

        entry->occupied = true;
        std::memcpy(
            entry->principal,
            principal_,
            sizeof(entry->principal));
        entry->family = SecureLegacyCommandFamily::FighterLevelSeal;
        entry->characterId = characterId_;
        entry->npcId = 0;
        entry->selectionCount = 1;
        std::memcpy(
            entry->bagSlots,
            identity,
            sizeof(entry->bagSlots));
        entry->capturesSelectionState = false;
        entry->expiresAt =
            now + SecurePendingOperationLifetimeMilliseconds;
    }

    descriptor->hasOperation = true;
    descriptor->operation.packetBytes = descriptor->packetBytes;
    descriptor->operation.opcode = descriptor->opcode;
    std::memcpy(
        descriptor->operation.operationId,
        entry->operationId,
        sizeof(descriptor->operation.operationId));
    ReleaseSRWLockExclusive(&lock_);
    return SecureOperationRegistryResult::Success;
}

} // namespace godswar::network
