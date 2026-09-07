#include "SecureOnlineAwardCommandIdentity.h"

#include "SecureLegacyCommandIdentity.h"

namespace godswar::network {
namespace {

std::uint16_t ReadUInt16Little(const std::uint8_t* source) noexcept {
    return static_cast<std::uint16_t>(
        source[0] |
        (static_cast<std::uint16_t>(source[1]) << 8U));
}

std::uint32_t ReadUInt32Little(const std::uint8_t* source) noexcept {
    return source[0] |
        (static_cast<std::uint32_t>(source[1]) << 8U) |
        (static_cast<std::uint32_t>(source[2]) << 16U) |
        (static_cast<std::uint32_t>(source[3]) << 24U);
}

bool IsOnlineAwardNpc(std::uint32_t npcId) noexcept {
    return npcId == LegacyAthensOnlineAwardNpc ||
        npcId == LegacySpartaOnlineAwardNpc;
}

} // namespace

LegacyOnlineAwardPacketKind ClassifyLegacyOnlineAwardPacket(
    const void* packet,
    std::size_t packetBytes,
    LegacyOnlineAwardCommand* command) noexcept {
    if (packet == nullptr || packetBytes < 12) {
        return LegacyOnlineAwardPacketKind::Unrelated;
    }

    const auto* bytes = static_cast<const std::uint8_t*>(packet);
    const auto opcode = ReadUInt16Little(bytes + 2);
    const auto npcId = ReadUInt32Little(bytes + 4);
    const auto dialog = static_cast<std::int32_t>(
        ReadUInt32Little(bytes + 8));
    if (opcode != LegacyNpcFunctionActionOpcode ||
        !IsOnlineAwardNpc(npcId) ||
        dialog != LegacyOnlineAwardDialog) {
        return LegacyOnlineAwardPacketKind::Unrelated;
    }

    std::uint16_t parsedOpcode = 0;
    if (packetBytes != LegacyOnlineAwardActionPacketBytes ||
        !TryReadLegacyPacketHeader(
            packet, packetBytes, &parsedOpcode) ||
        parsedOpcode != LegacyNpcFunctionActionOpcode ||
        static_cast<std::int32_t>(ReadUInt32Little(bytes + 12)) !=
            LegacyOnlineAwardDialog ||
        static_cast<std::int32_t>(ReadUInt32Little(bytes + 16)) !=
            LegacyOnlineAwardInitialSubId) {
        return LegacyOnlineAwardPacketKind::InvalidMutation;
    }

    if (command != nullptr) {
        command->npcId = npcId;
    }
    return LegacyOnlineAwardPacketKind::Commit;
}

bool TryReadLegacyOnlineAwardCommand(
    const void* packet,
    std::size_t packetBytes,
    LegacyOnlineAwardCommand* command) noexcept {
    return command != nullptr &&
        ClassifyLegacyOnlineAwardPacket(
            packet, packetBytes, command) ==
            LegacyOnlineAwardPacketKind::Commit;
}

} // namespace godswar::network
