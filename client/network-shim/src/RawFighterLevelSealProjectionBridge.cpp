#include "RawFighterLevelSealProjectionBridge.h"

#include <bcrypt.h>

#include <cstring>
#include <limits>

namespace godswar::network {
namespace {

constexpr std::uint16_t NpcFunctionActionResponseOpcode = 10070;
constexpr std::size_t RequestTokenOffset = 12;
constexpr std::size_t ResponseResultOffset = 12;
constexpr std::size_t ResponseMarkerOffset = 16;
constexpr std::size_t ResponseTokenOffset = 20;
constexpr std::size_t ResponseCurrentExperienceOffset = 24;
constexpr std::size_t ResponseMaximumExperienceOffset = 28;
constexpr unsigned TokenGenerationAttempts = 4;

bool DefaultRandom(void*, std::uint32_t* random) noexcept {
    return random != nullptr &&
        BCryptGenRandom(
            nullptr,
            reinterpret_cast<PUCHAR>(random),
            sizeof(*random),
            BCRYPT_USE_SYSTEM_PREFERRED_RNG) >= 0;
}

bool DefaultClock(void*, std::uint64_t* milliseconds) noexcept {
    if (milliseconds == nullptr) {
        return false;
    }
    *milliseconds = GetTickCount64();
    return true;
}

bool HasReadableProtection(DWORD protection) noexcept {
    if ((protection & (PAGE_GUARD | PAGE_NOACCESS)) != 0) {
        return false;
    }
    switch (protection & 0xFF) {
        case PAGE_READONLY:
        case PAGE_READWRITE:
        case PAGE_WRITECOPY:
        case PAGE_EXECUTE_READ:
        case PAGE_EXECUTE_READWRITE:
        case PAGE_EXECUTE_WRITECOPY:
            return true;
        default:
            return false;
    }
}

bool HasWritableProtection(DWORD protection) noexcept {
    if ((protection & (PAGE_GUARD | PAGE_NOACCESS)) != 0) {
        return false;
    }
    switch (protection & 0xFF) {
        case PAGE_READWRITE:
        case PAGE_WRITECOPY:
        case PAGE_EXECUTE_READWRITE:
        case PAGE_EXECUTE_WRITECOPY:
            return true;
        default:
            return false;
    }
}

bool IsRangeAccessible(
    const void* address,
    std::size_t bytes,
    bool writable) noexcept {
    if (address == nullptr || bytes == 0) {
        return false;
    }
    MEMORY_BASIC_INFORMATION memory{};
    if (VirtualQuery(address, &memory, sizeof(memory)) == 0 ||
        memory.State != MEM_COMMIT ||
        (writable
            ? !HasWritableProtection(memory.Protect)
            : !HasReadableProtection(memory.Protect))) {
        return false;
    }
    const auto start = reinterpret_cast<std::uintptr_t>(address);
    const auto base = reinterpret_cast<std::uintptr_t>(memory.BaseAddress);
    return start >= base &&
        bytes <= memory.RegionSize - (start - base);
}

std::uint16_t Read16(const std::uint8_t* bytes) noexcept {
    return static_cast<std::uint16_t>(
        bytes[0] |
        (static_cast<std::uint16_t>(bytes[1]) << 8U));
}

std::uint32_t Read32(const std::uint8_t* bytes) noexcept {
    return bytes[0] |
        (static_cast<std::uint32_t>(bytes[1]) << 8U) |
        (static_cast<std::uint32_t>(bytes[2]) << 16U) |
        (static_cast<std::uint32_t>(bytes[3]) << 24U);
}

void Write16(std::uint8_t* bytes, std::uint16_t value) noexcept {
    bytes[0] = static_cast<std::uint8_t>(value);
    bytes[1] = static_cast<std::uint8_t>(value >> 8U);
}

void Write32(std::uint8_t* bytes, std::uint32_t value) noexcept {
    bytes[0] = static_cast<std::uint8_t>(value);
    bytes[1] = static_cast<std::uint8_t>(value >> 8U);
    bytes[2] = static_cast<std::uint8_t>(value >> 16U);
    bytes[3] = static_cast<std::uint8_t>(value >> 24U);
}

bool IsToken(std::uint32_t token) noexcept {
    return (token & RawFighterLevelSealRequestTokenPrefixMask) ==
            RawFighterLevelSealRequestTokenPrefix &&
        (token & RawFighterLevelSealRequestTokenRandomMask) != 0;
}

bool IsNpc(std::uint32_t npcId) noexcept {
    return npcId == LegacySpartaFighterLevelSealNpc ||
        npcId == LegacyAthensFighterLevelSealNpc;
}

bool IsResultForAction(
    LegacyFighterLevelSealAction action,
    std::uint32_t result) noexcept {
    if (result == LegacyFighterLevelSealUnavailableResult) {
        return true;
    }
    if (action == LegacyFighterLevelSealAction::Seal) {
        return result == LegacyFighterLevelSealSealedResult ||
            result == LegacyFighterLevelSealAlreadySealedResult;
    }
    if (action == LegacyFighterLevelSealAction::Unseal) {
        return result == LegacyFighterLevelSealInsufficientFundsResult ||
            result == LegacyFighterLevelSealUnsealedResult ||
            result == LegacyFighterLevelSealAlreadyUnsealedResult;
    }
    return false;
}

bool IsSuccessfulResult(
    LegacyFighterLevelSealAction action,
    std::uint32_t result) noexcept {
    return (action == LegacyFighterLevelSealAction::Seal &&
            result == LegacyFighterLevelSealSealedResult) ||
        (action == LegacyFighterLevelSealAction::Unseal &&
            result == LegacyFighterLevelSealUnsealedResult);
}

} // namespace

RawFighterLevelSealProjectionBridge::
RawFighterLevelSealProjectionBridge() noexcept
    : RawFighterLevelSealProjectionBridge(
          nullptr,
          DefaultRandom,
          DefaultClock) {
}

RawFighterLevelSealProjectionBridge::
RawFighterLevelSealProjectionBridge(
    void* dependencyContext,
    RawFighterLevelSealRandom random,
    RawFighterLevelSealClock clock) noexcept
    : dependencyContext_(dependencyContext),
      random_(random != nullptr ? random : DefaultRandom),
      clock_(clock != nullptr ? clock : DefaultClock) {
    InitializeSRWLock(&lock_);
}

bool RawFighterLevelSealProjectionBridge::TryPrepareClientPacket(
    const void* packet,
    int packetBytes,
    void* destination,
    std::size_t destinationBytes,
    RawFighterLevelSealPreparedSend* prepared) noexcept {
    if (prepared == nullptr) {
        return false;
    }
    *prepared = RawFighterLevelSealPreparedSend{};
    if (packet == nullptr || destination == nullptr ||
        packetBytes != LegacyFighterLevelSealActionPacketBytes ||
        destinationBytes < LegacyFighterLevelSealActionPacketBytes) {
        return false;
    }

    LegacyFighterLevelSealCommand command{};
    if (!TryReadLegacyFighterLevelSealCommand(
            packet,
            static_cast<std::size_t>(packetBytes),
            &command)) {
        return false;
    }

    std::uint64_t now = 0;
    if (!ReadNow(&now)) {
        return false;
    }
    AcquireSRWLockExclusive(&lock_);
    Prune(now);
    const bool hasCapacity =
        pendingCount_ < RawFighterLevelSealProjectionCapacity;
    ReleaseSRWLockExclusive(&lock_);
    if (!hasCapacity) {
        return false;
    }

    std::uint32_t token = 0;
    if (!GenerateToken(&token)) {
        return false;
    }
    std::memcpy(
        destination,
        packet,
        LegacyFighterLevelSealActionPacketBytes);
    Write32(
        static_cast<std::uint8_t*>(destination) + RequestTokenOffset,
        token);
    prepared->prepared = true;
    prepared->npcId = command.npcId;
    prepared->action = command.action;
    prepared->token = token;
    return true;
}

void RawFighterLevelSealProjectionBridge::CompleteClientSend(
    const RawFighterLevelSealPreparedSend& prepared,
    bool sent) noexcept {
    if (!sent || !prepared.prepared ||
        !IsNpc(prepared.npcId) || !IsToken(prepared.token)) {
        return;
    }
    std::uint64_t now = 0;
    if (!ReadNow(&now) ||
        now > (std::numeric_limits<std::uint64_t>::max)() -
            RawFighterLevelSealRequestLifetimeMilliseconds) {
        return;
    }

    AcquireSRWLockExclusive(&lock_);
    Prune(now);
    if (pendingCount_ < RawFighterLevelSealProjectionCapacity &&
        FindToken(prepared.token) < 0) {
        auto& pending = pending_[pendingCount_++];
        pending.npcId = prepared.npcId;
        pending.action = prepared.action;
        pending.token = prepared.token;
        pending.expiresAt =
            now + RawFighterLevelSealRequestLifetimeMilliseconds;
    }
    ReleaseSRWLockExclusive(&lock_);
}

RawFighterLevelSealObservation
RawFighterLevelSealProjectionBridge::ObserveServerMessage(
    void* message) noexcept {
    constexpr std::size_t PrefixBytes = sizeof(void*);
    if (!IsRangeAccessible(
            message,
            PrefixBytes + sizeof(std::uint16_t),
            false)) {
        return RawFighterLevelSealObservation::Unrelated;
    }
    auto* packet = static_cast<std::uint8_t*>(message) + PrefixBytes;
    std::uint16_t packetBytes = 0;
    __try {
        packetBytes = Read16(packet);
    }
    __except (EXCEPTION_EXECUTE_HANDLER) {
        return RawFighterLevelSealObservation::Unrelated;
    }
    if (packetBytes < 16 ||
        packetBytes > RawFighterLevelSealSuccessResponseBytes ||
        !IsRangeAccessible(packet, packetBytes, false) ||
        (packetBytes > 16 &&
         !IsRangeAccessible(packet, packetBytes, true))) {
        return RawFighterLevelSealObservation::Unrelated;
    }
    return ObserveServerPacket(packet, packetBytes);
}

RawFighterLevelSealObservation
RawFighterLevelSealProjectionBridge::ObserveServerPacket(
    void* packet,
    std::size_t packetBytes) noexcept {
    if (packet == nullptr ||
        (packetBytes != 16 &&
         packetBytes != RawFighterLevelSealFailureResponseBytes &&
         packetBytes != RawFighterLevelSealSuccessResponseBytes)) {
        return RawFighterLevelSealObservation::Unrelated;
    }

    auto* bytes = static_cast<std::uint8_t*>(packet);
    __try {
        if (Read16(bytes) != packetBytes ||
            Read16(bytes + 2) != NpcFunctionActionResponseOpcode ||
            !IsNpc(Read32(bytes + 4)) ||
            static_cast<std::int32_t>(Read32(bytes + 8)) !=
                LegacyFighterLevelSealDialog) {
            return RawFighterLevelSealObservation::Unrelated;
        }

        const auto npcId = Read32(bytes + 4);
        const auto result = Read32(bytes + ResponseResultOffset);

        if (packetBytes == 16) {
            std::uint64_t now = 0;
            if (!ReadNow(&now)) {
                return RawFighterLevelSealObservation::LegacyTerminal;
            }
            AcquireSRWLockExclusive(&lock_);
            Prune(now);
            if (pendingCount_ != 0 &&
                pending_[0].npcId == npcId &&
                IsResultForAction(pending_[0].action, result)) {
                RemovePending(0);
            }
            ReleaseSRWLockExclusive(&lock_);
            return RawFighterLevelSealObservation::LegacyTerminal;
        }

        if (Read32(bytes + ResponseMarkerOffset) !=
            RawFighterLevelSealResponseMarker) {
            return RawFighterLevelSealObservation::Unrelated;
        }

        const auto token = Read32(bytes + ResponseTokenOffset);
        const auto current =
            packetBytes == RawFighterLevelSealSuccessResponseBytes
                ? Read32(bytes + ResponseCurrentExperienceOffset)
                : 0;
        const auto maximum =
            packetBytes == RawFighterLevelSealSuccessResponseBytes
                ? Read32(bytes + ResponseMaximumExperienceOffset)
                : 0;

        // Once the exact extension marker is present, strip and clear the
        // extension even when it is stale or malformed. Origin receives only
        // the stock result and cannot interpret EXP words as extra sub-IDs.
        Write16(bytes, 16);
        SecureZeroMemory(
            bytes + ResponseMarkerOffset,
            packetBytes - ResponseMarkerOffset);
        if (!IsToken(token)) {
            return RawFighterLevelSealObservation::Normalized;
        }

        std::uint64_t now = 0;
        if (!ReadNow(&now)) {
            return RawFighterLevelSealObservation::Normalized;
        }

        AcquireSRWLockExclusive(&lock_);
        Prune(now);
        const int rawIndex = FindToken(token);
        if (rawIndex < 0) {
            ReleaseSRWLockExclusive(&lock_);
            return RawFighterLevelSealObservation::Normalized;
        }
        const auto index = static_cast<std::size_t>(rawIndex);
        const auto action = pending_[index].action;
        if (pending_[index].npcId != npcId ||
            !IsResultForAction(action, result)) {
            ReleaseSRWLockExclusive(&lock_);
            return RawFighterLevelSealObservation::Normalized;
        }

        bool published = false;
        if (packetBytes == RawFighterLevelSealSuccessResponseBytes &&
            IsSuccessfulResult(action, result)) {
            published = maximum != 0 &&
                (action != LegacyFighterLevelSealAction::Seal ||
                 maximum == (std::numeric_limits<std::uint32_t>::max)()) &&
                PublishProjection(current, maximum);
        }
        RemovePending(index);
        ReleaseSRWLockExclusive(&lock_);
        return published
            ? RawFighterLevelSealObservation::ProjectionQueued
            : RawFighterLevelSealObservation::Normalized;
    }
    __except (EXCEPTION_EXECUTE_HANDLER) {
        return RawFighterLevelSealObservation::Unrelated;
    }
}

bool RawFighterLevelSealProjectionBridge::TryTakeProjection(
    RawFighterExperienceProjection* projection) noexcept {
    if (projection == nullptr) {
        return false;
    }
    *projection = RawFighterExperienceProjection{};
    AcquireSRWLockExclusive(&lock_);
    if (projectionCount_ == 0) {
        ReleaseSRWLockExclusive(&lock_);
        return false;
    }
    *projection = projections_[projectionHead_];
    projections_[projectionHead_] = RawFighterExperienceProjection{};
    projectionHead_ =
        (projectionHead_ + 1) % RawFighterLevelSealProjectionCapacity;
    --projectionCount_;
    ReleaseSRWLockExclusive(&lock_);
    return true;
}

void RawFighterLevelSealProjectionBridge::Reset() noexcept {
    AcquireSRWLockExclusive(&lock_);
    SecureZeroMemory(pending_, sizeof(pending_));
    SecureZeroMemory(projections_, sizeof(projections_));
    pendingCount_ = 0;
    projectionHead_ = 0;
    projectionCount_ = 0;
    ReleaseSRWLockExclusive(&lock_);
}

bool RawFighterLevelSealProjectionBridge::ReadNow(
    std::uint64_t* now) const noexcept {
    return now != nullptr && clock_ != nullptr &&
        clock_(dependencyContext_, now);
}

bool RawFighterLevelSealProjectionBridge::GenerateToken(
    std::uint32_t* token) noexcept {
    if (token == nullptr || random_ == nullptr) {
        return false;
    }
    *token = 0;
    for (unsigned attempt = 0;
         attempt < TokenGenerationAttempts;
         ++attempt) {
        std::uint32_t random = 0;
        if (!random_(dependencyContext_, &random)) {
            return false;
        }
        const auto candidate =
            RawFighterLevelSealRequestTokenPrefix |
            (random & RawFighterLevelSealRequestTokenRandomMask);
        if (!IsToken(candidate)) {
            continue;
        }
        AcquireSRWLockShared(&lock_);
        const bool unique = FindToken(candidate) < 0;
        ReleaseSRWLockShared(&lock_);
        if (unique) {
            *token = candidate;
            return true;
        }
    }
    return false;
}

void RawFighterLevelSealProjectionBridge::Prune(
    std::uint64_t now) noexcept {
    std::size_t index = 0;
    while (index < pendingCount_) {
        if (pending_[index].expiresAt <= now) {
            RemovePending(index);
        } else {
            ++index;
        }
    }
}

int RawFighterLevelSealProjectionBridge::FindToken(
    std::uint32_t token) const noexcept {
    for (std::size_t index = 0; index < pendingCount_; ++index) {
        if (pending_[index].token == token) {
            return static_cast<int>(index);
        }
    }
    return -1;
}

void RawFighterLevelSealProjectionBridge::RemovePending(
    std::size_t index) noexcept {
    if (index >= pendingCount_) {
        return;
    }
    for (std::size_t cursor = index + 1;
         cursor < pendingCount_;
         ++cursor) {
        pending_[cursor - 1] = pending_[cursor];
    }
    --pendingCount_;
    pending_[pendingCount_] = Pending{};
}

bool RawFighterLevelSealProjectionBridge::PublishProjection(
    std::uint32_t currentExperience,
    std::uint32_t maximumExperience) noexcept {
    if (maximumExperience == 0 ||
        projectionCount_ >= RawFighterLevelSealProjectionCapacity) {
        return false;
    }
    const auto tail =
        (projectionHead_ + projectionCount_) %
        RawFighterLevelSealProjectionCapacity;
    projections_[tail].currentExperience = currentExperience;
    projections_[tail].maximumExperience = maximumExperience;
    ++projectionCount_;
    return true;
}

} // namespace godswar::network
