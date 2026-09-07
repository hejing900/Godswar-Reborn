#pragma once

#include <cstddef>
#include <cstdint>

namespace godswar::network {

inline constexpr std::uint16_t LegacyOnlineAwardActionPacketBytes = 92;
inline constexpr std::uint32_t LegacyAthensOnlineAwardNpc = 5271;
inline constexpr std::uint32_t LegacySpartaOnlineAwardNpc = 5129;
inline constexpr std::int32_t LegacyOnlineAwardDialog = 49;
inline constexpr std::int32_t LegacyOnlineAwardInitialSubId = -1;
inline constexpr std::size_t LegacyOnlineAwardArgumentCount = 18;
inline constexpr std::uint32_t LegacyOnlineAwardSuccessResult = 102;
inline constexpr std::uint32_t LegacyOnlineAwardAlreadyResult = 103;
inline constexpr std::uint32_t LegacyOnlineAwardBagFullResult = 104;
inline constexpr std::uint32_t LegacyOnlineAwardUnavailableResult = 105;

enum class LegacyOnlineAwardPacketKind : std::uint8_t {
    Unrelated = 0,
    Commit,
    InvalidMutation,
};

struct LegacyOnlineAwardCommand final {
    std::uint32_t npcId = 0;
};

// NpcFunStayReward dialog 49 is itself the daily claim. Only the exact
// 92-byte top-level request receives an operation identity. Its 18 argument
// words are unused native scratch state and are deliberately excluded from
// classification and identity; fixed fields still fail closed.
LegacyOnlineAwardPacketKind ClassifyLegacyOnlineAwardPacket(
    const void* packet,
    std::size_t packetBytes,
    LegacyOnlineAwardCommand* command) noexcept;

bool TryReadLegacyOnlineAwardCommand(
    const void* packet,
    std::size_t packetBytes,
    LegacyOnlineAwardCommand* command) noexcept;

} // namespace godswar::network
