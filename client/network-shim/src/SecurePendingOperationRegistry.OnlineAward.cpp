#include "SecurePendingOperationRegistry.h"

#include <cstring>
#include <limits>

namespace godswar::network {

SecureOperationRegistryResult
SecurePendingOperationRegistry::DescribeOnlineAwardPacket(
    const void* packet,
    std::size_t packetBytes,
    std::uint64_t now,
    LegacyPacketDescriptor* descriptor,
    bool* recognized) noexcept {
    if (descriptor == nullptr || recognized == nullptr) {
        return SecureOperationRegistryResult::InvalidPacket;
    }
    *recognized = false;

    LegacyOnlineAwardCommand command{};
    switch (ClassifyLegacyOnlineAwardPacket(
                packet, packetBytes, &command)) {
        case LegacyOnlineAwardPacketKind::Commit:
            *recognized = true;
            return DescribeOnlineAwardCommand(
                command, now, descriptor);
        case LegacyOnlineAwardPacketKind::InvalidMutation:
            *recognized = true;
            return SecureOperationRegistryResult::InvalidPacket;
        case LegacyOnlineAwardPacketKind::Unrelated:
        default:
            return SecureOperationRegistryResult::Success;
    }
}

SecureOperationRegistryResult
SecurePendingOperationRegistry::DescribeOnlineAwardCommand(
    const LegacyOnlineAwardCommand& command,
    std::uint64_t now,
    LegacyPacketDescriptor* descriptor) noexcept {
    if (descriptor == nullptr ||
        (command.npcId != LegacyAthensOnlineAwardNpc &&
         command.npcId != LegacySpartaOnlineAwardNpc)) {
        return SecureOperationRegistryResult::InvalidPacket;
    }

    const int identity[SecureGearSelectionCapacity]{
        LegacyOnlineAwardDialog, -1, -1, -1};
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

    // Athens and Sparta expose one character/day authority. Normalize away
    // city NPC identity so a map transfer cannot mint a second retry UUID.
    Entry* entry = Find(
        SecureLegacyCommandFamily::OnlineAward,
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
        entry->family = SecureLegacyCommandFamily::OnlineAward;
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
