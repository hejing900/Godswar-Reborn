#include "SecureFighterLevelSealCommandIdentity.h"

#include "SecureLegacyCommandIdentity.h"

namespace godswar::network {
namespace {

std::uint16_t ReadUInt16Little(
    const std::uint8_t* source) noexcept {
    return static_cast<std::uint16_t>(
        source[0] |
        (static_cast<std::uint16_t>(source[1]) << 8U));
}

std::uint32_t ReadUInt32Little(
    const std::uint8_t* source) noexcept {
    return source[0] |
        (static_cast<std::uint32_t>(source[1]) << 8U) |
        (static_cast<std::uint32_t>(source[2]) << 16U) |
        (static_cast<std::uint32_t>(source[3]) << 24U);
}

bool IsFighterLevelSealNpc(std::uint32_t npcId) noexcept {
    return npcId == LegacySpartaFighterLevelSealNpc ||
        npcId == LegacyAthensFighterLevelSealNpc;
}

bool HasCanonicalEmptyArguments(
    const std::uint8_t* bytes) noexcept {
    for (std::size_t index = 0;
         index < LegacyFighterLevelSealArgumentCount;
         ++index) {
        if (static_cast<std::int32_t>(
                ReadUInt32Little(bytes + 20 + index * 4)) != -1) {
            return false;
        }
    }
    return true;
}

} // namespace

LegacyFighterLevelSealPacketKind ClassifyLegacyFighterLevelSealPacket(
    const void* packet,
    std::size_t packetBytes,
    LegacyFighterLevelSealCommand* command) noexcept {
    if (packet == nullptr || packetBytes < 12) {
        return LegacyFighterLevelSealPacketKind::Unrelated;
    }

    const auto* bytes = static_cast<const std::uint8_t*>(packet);
    const auto opcode = ReadUInt16Little(bytes + 2);
    const auto npcId = ReadUInt32Little(bytes + 4);
    const auto dialog = static_cast<std::int32_t>(
        ReadUInt32Little(bytes + 8));
    if (opcode != LegacyNpcFunctionActionOpcode ||
        !IsFighterLevelSealNpc(npcId) ||
        dialog != LegacyFighterLevelSealDialog) {
        return LegacyFighterLevelSealPacketKind::Unrelated;
    }

    std::uint16_t parsedOpcode = 0;
    if (packetBytes != LegacyFighterLevelSealActionPacketBytes ||
        !TryReadLegacyPacketHeader(
            packet, packetBytes, &parsedOpcode) ||
        parsedOpcode != LegacyNpcFunctionActionOpcode) {
        return LegacyFighterLevelSealPacketKind::InvalidMutation;
    }

    const auto duplicateDialog = static_cast<std::int32_t>(
        ReadUInt32Little(bytes + 12));
    const auto subId = static_cast<std::int32_t>(
        ReadUInt32Little(bytes + 16));
    if (duplicateDialog != LegacyFighterLevelSealDialog) {
        return LegacyFighterLevelSealPacketKind::InvalidMutation;
    }

    const bool hasEmptyArguments = HasCanonicalEmptyArguments(bytes);
    if (subId == LegacyFighterLevelSealSealSubId ||
        subId == LegacyFighterLevelSealUnsealSubId) {
        if (!hasEmptyArguments) {
            return LegacyFighterLevelSealPacketKind::InvalidMutation;
        }
        if (command != nullptr) {
            command->npcId = npcId;
            command->action =
                subId == LegacyFighterLevelSealSealSubId
                ? LegacyFighterLevelSealAction::Seal
                : LegacyFighterLevelSealAction::Unseal;
        }
        return LegacyFighterLevelSealPacketKind::Commit;
    }

    if ((subId == -1 ||
         subId == LegacyFighterLevelSealDescriptionSubId) &&
        hasEmptyArguments) {
        return LegacyFighterLevelSealPacketKind::Navigation;
    }
    return LegacyFighterLevelSealPacketKind::Unrelated;
}

bool TryReadLegacyFighterLevelSealCommand(
    const void* packet,
    std::size_t packetBytes,
    LegacyFighterLevelSealCommand* command) noexcept {
    return command != nullptr &&
        ClassifyLegacyFighterLevelSealPacket(
            packet, packetBytes, command) ==
            LegacyFighterLevelSealPacketKind::Commit;
}

} // namespace godswar::network
