#pragma once

#include "SecureFighterLevelSealCommandIdentity.h"

#include <Windows.h>

#include <cstddef>
#include <cstdint>

namespace godswar::network {

inline constexpr std::uint32_t
    RawFighterLevelSealRequestTokenPrefix = 0xA1000000U;
inline constexpr std::uint32_t
    RawFighterLevelSealRequestTokenPrefixMask = 0xFF000000U;
inline constexpr std::uint32_t
    RawFighterLevelSealRequestTokenRandomMask = 0x00FFFFFFU;
// Numeric little-endian representation of the response marker "RXP1".
inline constexpr std::uint32_t
    RawFighterLevelSealResponseMarker = 0x31505852U;
inline constexpr std::uint16_t
    RawFighterLevelSealFailureResponseBytes = 24;
inline constexpr std::uint16_t
    RawFighterLevelSealSuccessResponseBytes = 32;
inline constexpr std::size_t
    RawFighterLevelSealProjectionCapacity = 8;
inline constexpr std::uint64_t
    RawFighterLevelSealRequestLifetimeMilliseconds = 60'000;

using RawFighterLevelSealRandom = bool (*)(
    void* context,
    std::uint32_t* random) noexcept;
using RawFighterLevelSealClock = bool (*)(
    void* context,
    std::uint64_t* milliseconds) noexcept;

struct RawFighterLevelSealPreparedSend final {
    bool prepared = false;
    std::uint32_t npcId = 0;
    LegacyFighterLevelSealAction action =
        LegacyFighterLevelSealAction::Seal;
    std::uint32_t token = 0;
};

struct RawFighterExperienceProjection final {
    std::uint32_t currentExperience = 0;
    std::uint32_t maximumExperience = 0;
};

enum class RawFighterLevelSealObservation : std::uint8_t {
    Unrelated = 0,
    LegacyTerminal,
    Normalized,
    ProjectionQueued,
};

// Raw legacy sessions have no authenticated command-result stream: this is
// correlation, not authentication. The capability token occupies a field
// ignored by older Reborn servers while retaining their 92-byte envelope; a
// marked response is normalized to the stock 16-byte shape before Origin.
class RawFighterLevelSealProjectionBridge final {
public:
    RawFighterLevelSealProjectionBridge() noexcept;
    RawFighterLevelSealProjectionBridge(
        void* dependencyContext,
        RawFighterLevelSealRandom random,
        RawFighterLevelSealClock clock) noexcept;

    RawFighterLevelSealProjectionBridge(
        const RawFighterLevelSealProjectionBridge&) = delete;
    RawFighterLevelSealProjectionBridge& operator=(
        const RawFighterLevelSealProjectionBridge&) = delete;

    bool TryPrepareClientPacket(
        const void* packet,
        int packetBytes,
        void* destination,
        std::size_t destinationBytes,
        RawFighterLevelSealPreparedSend* prepared) noexcept;
    void CompleteClientSend(
        const RawFighterLevelSealPreparedSend& prepared,
        bool sent) noexcept;

    RawFighterLevelSealObservation ObserveServerMessage(
        void* message) noexcept;
    RawFighterLevelSealObservation ObserveServerPacket(
        void* packet,
        std::size_t packetBytes) noexcept;

    bool TryTakeProjection(
        RawFighterExperienceProjection* projection) noexcept;
    void Reset() noexcept;

private:
    struct Pending final {
        std::uint32_t npcId = 0;
        LegacyFighterLevelSealAction action =
            LegacyFighterLevelSealAction::Seal;
        std::uint32_t token = 0;
        std::uint64_t expiresAt = 0;
    };

    bool ReadNow(std::uint64_t* now) const noexcept;
    bool GenerateToken(std::uint32_t* token) noexcept;
    void Prune(std::uint64_t now) noexcept;
    int FindToken(std::uint32_t token) const noexcept;
    void RemovePending(std::size_t index) noexcept;
    bool PublishProjection(
        std::uint32_t currentExperience,
        std::uint32_t maximumExperience) noexcept;

    void* dependencyContext_ = nullptr;
    RawFighterLevelSealRandom random_ = nullptr;
    RawFighterLevelSealClock clock_ = nullptr;
    SRWLOCK lock_{};
    Pending pending_[RawFighterLevelSealProjectionCapacity]{};
    std::size_t pendingCount_ = 0;
    RawFighterExperienceProjection
        projections_[RawFighterLevelSealProjectionCapacity]{};
    std::size_t projectionHead_ = 0;
    std::size_t projectionCount_ = 0;
};

} // namespace godswar::network
