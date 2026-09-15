#pragma once

#include <cstddef>
#include <cstdint>

namespace godswar::network {

inline constexpr std::uint16_t LegacyFactionCrierActionPacketBytes = 92;
inline constexpr std::uint32_t LegacyAthensFactionCrierNpc = 5194;
inline constexpr std::uint32_t LegacyPublishedSpartaFactionCrierNpc = 5052;
inline constexpr std::uint32_t LegacySourceSpartaFactionCrierNpc = 5054;
inline constexpr std::int32_t LegacyFactionCrierDialog = 15;
inline constexpr std::size_t LegacyFactionCrierArgumentCount = 18;
inline constexpr std::size_t LegacyFactionCrierItemArgument = 6;
inline constexpr std::size_t LegacyFactionCrierFirstScratchArgument = 10;
inline constexpr std::size_t LegacyFactionCrierLastScratchArgument = 12;
inline constexpr std::int32_t LegacyFactionCrierBagPageCount = 4;
inline constexpr std::int32_t LegacyFactionCrierBagSlotsPerPage = 24;

enum class LegacyFactionCrierOperation : std::uint8_t {
    DailyClaim = 1,
    WeeklyReclaim = 2,
    RenewNameplate = 3,
    TurnInNameplates = 4,
};

enum class LegacyFactionCrierNameplateSet : std::uint8_t {
    None = 0,
    Single = 1,
    OddTriple = 2,
    EvenTriple = 3,
    AllSix = 4,
};

enum class LegacyFactionCrierRewardKind : std::uint8_t {
    None = 0,
    Experience = 1,
    TalentPoints = 2,
    ExperienceAndTalentPoints = 3,
};

enum class LegacyFactionCrierCurrency : std::uint8_t {
    None = 0,
    Silver = 1,
    BindingGold = 2,
    Gold = 3,
};

enum class LegacyFactionCrierPacketKind : std::uint8_t {
    Unrelated = 0,
    Navigation,
    Commit,
    InvalidMutation,
};

struct LegacyFactionCrierCommand final {
    LegacyFactionCrierOperation operation =
        LegacyFactionCrierOperation::DailyClaim;
    std::uint32_t npcId = 0;
    // The terminal nested choice. For exchanges this is 31..46 or 101..134,
    // not the root action (2, 3, or 4) retained by the stock client.
    int actionSubId = -1;
    int nameplateOrdinal = 0;
    LegacyFactionCrierNameplateSet nameplateSet =
        LegacyFactionCrierNameplateSet::None;
    LegacyFactionCrierRewardKind rewardKind =
        LegacyFactionCrierRewardKind::None;
    LegacyFactionCrierCurrency paymentCurrency =
        LegacyFactionCrierCurrency::None;
    int rewardMultiplier = 0;
    int sourceKitBagSlot = -1;
};

// Only exact stock mutations for NpcFunSignact dialog 15 receive an
// operation identity. Exact page-opening requests remain navigation, while a
// malformed request in a recognized mutation path fails closed.
LegacyFactionCrierPacketKind ClassifyLegacyFactionCrierPacket(
    const void* packet,
    std::size_t packetBytes,
    LegacyFactionCrierCommand* command) noexcept;

bool TryReadLegacyFactionCrierCommand(
    const void* packet,
    std::size_t packetBytes,
    LegacyFactionCrierCommand* command) noexcept;

} // namespace godswar::network
