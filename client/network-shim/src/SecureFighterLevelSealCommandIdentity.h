#pragma once

#include <cstddef>
#include <cstdint>

namespace godswar::network {

inline constexpr std::uint16_t
    LegacyFighterLevelSealActionPacketBytes = 92;
inline constexpr std::uint32_t LegacySpartaFighterLevelSealNpc = 5139;
inline constexpr std::uint32_t LegacyAthensFighterLevelSealNpc = 5281;
inline constexpr std::int32_t LegacyFighterLevelSealDialog = 116;
inline constexpr std::int32_t LegacyFighterLevelSealDescriptionSubId = 101;
inline constexpr std::int32_t LegacyFighterLevelSealSealSubId = 102;
inline constexpr std::int32_t LegacyFighterLevelSealUnsealSubId = 103;
inline constexpr std::size_t LegacyFighterLevelSealArgumentCount = 18;

inline constexpr std::uint32_t
    LegacyFighterLevelSealInsufficientFundsResult = 104;
inline constexpr std::uint32_t
    LegacyFighterLevelSealUnavailableResult = 105;
inline constexpr std::uint32_t LegacyFighterLevelSealSealedResult = 106;
inline constexpr std::uint32_t LegacyFighterLevelSealUnsealedResult = 107;
inline constexpr std::uint32_t
    LegacyFighterLevelSealAlreadyUnsealedResult = 108;
inline constexpr std::uint32_t
    LegacyFighterLevelSealAlreadySealedResult = 109;

enum class LegacyFighterLevelSealAction : std::uint8_t {
    Seal = 1,
    Unseal = 2,
};

enum class LegacyFighterLevelSealPacketKind : std::uint8_t {
    Unrelated = 0,
    Navigation,
    Commit,
    InvalidMutation,
};

struct LegacyFighterLevelSealCommand final {
    LegacyFighterLevelSealAction action =
        LegacyFighterLevelSealAction::Seal;
    std::uint32_t npcId = 0;
};

// Only exact stock mutations for NpcFunSeal dialog 116 receive an operation
// identity. Initial/description requests remain navigation. A recognized seal
// or unseal request with any changed fixed field or argument fails closed.
LegacyFighterLevelSealPacketKind ClassifyLegacyFighterLevelSealPacket(
    const void* packet,
    std::size_t packetBytes,
    LegacyFighterLevelSealCommand* command) noexcept;

bool TryReadLegacyFighterLevelSealCommand(
    const void* packet,
    std::size_t packetBytes,
    LegacyFighterLevelSealCommand* command) noexcept;

} // namespace godswar::network
