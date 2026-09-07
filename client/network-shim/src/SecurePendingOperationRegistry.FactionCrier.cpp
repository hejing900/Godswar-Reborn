#include "SecurePendingOperationRegistry.h"

#include <cstring>
#include <limits>

namespace godswar::network {

SecureOperationRegistryResult
SecurePendingOperationRegistry::DescribeFactionCrierPacket(
    const void* packet,
    std::size_t packetBytes,
    std::uint64_t now,
    LegacyPacketDescriptor* descriptor,
    bool* recognized) noexcept {
    if (descriptor == nullptr || recognized == nullptr) {
        return SecureOperationRegistryResult::InvalidPacket;
    }
    *recognized = false;

    LegacyFactionCrierCommand command{};
    switch (ClassifyLegacyFactionCrierPacket(
                packet, packetBytes, &command)) {
        case LegacyFactionCrierPacketKind::Commit:
            *recognized = true;
            return DescribeFactionCrierCommand(
                command, now, descriptor);
        case LegacyFactionCrierPacketKind::Navigation:
            *recognized = true;
            return SecureOperationRegistryResult::Success;
        case LegacyFactionCrierPacketKind::InvalidMutation:
            *recognized = true;
            return SecureOperationRegistryResult::InvalidPacket;
        case LegacyFactionCrierPacketKind::Unrelated:
        default:
            return SecureOperationRegistryResult::Success;
    }
}

SecureOperationRegistryResult
SecurePendingOperationRegistry::DescribeFactionCrierCommand(
    const LegacyFactionCrierCommand& command,
    std::uint64_t now,
    LegacyPacketDescriptor* descriptor) noexcept {
    if (descriptor == nullptr || command.actionSubId <= 0) {
        return SecureOperationRegistryResult::InvalidPacket;
    }

    // Root sub-IDs 2, 3, and 4 describe only the page. The terminal nested
    // action is the command discriminator, and renewal also binds the exact
    // normalized source slot selected in FirstWin_ItemBtn1.
    const int identity[SecureGearSelectionCapacity]{
        command.actionSubId,
        command.operation == LegacyFactionCrierOperation::RenewNameplate
            ? command.sourceKitBagSlot
            : -1,
        -1,
        -1};
    const std::size_t identityCount =
        command.operation == LegacyFactionCrierOperation::RenewNameplate
        ? 2
        : 1;
    if (identityCount == 2 && command.sourceKitBagSlot < 0) {
        return SecureOperationRegistryResult::InvalidPacket;
    }

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

    // Both cities expose one character-scoped authority. A retry after a map
    // transfer must retain the same UUID for the same terminal action.
    Entry* entry = Find(
        SecureLegacyCommandFamily::FactionCrier,
        0,
        identity,
        identityCount);
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
        entry->family = SecureLegacyCommandFamily::FactionCrier;
        entry->characterId = characterId_;
        entry->npcId = 0;
        entry->selectionCount = identityCount;
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
