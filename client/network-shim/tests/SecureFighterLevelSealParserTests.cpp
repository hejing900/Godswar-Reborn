#include "SecureFighterLevelSealTestSupport.h"

namespace {

using namespace fighter_level_seal_test;

void CheckParser(Checks* checks) {
    std::uint8_t packet[LegacyFighterLevelSealActionPacketBytes + 1]{};
    LegacyFighterLevelSealCommand command{};
    BuildFighterLevelSealPacket(
        packet,
        LegacyFighterLevelSealSealSubId,
        LegacySpartaFighterLevelSealNpc);
    checks->Require(
        TryReadLegacyFighterLevelSealCommand(
            packet,
            LegacyFighterLevelSealActionPacketBytes,
            &command) &&
        command.npcId == LegacySpartaFighterLevelSealNpc &&
        command.action == LegacyFighterLevelSealAction::Seal,
        "Sparta Level Sealer seal action did not parse");

    BuildFighterLevelSealPacket(
        packet,
        LegacyFighterLevelSealUnsealSubId,
        LegacyAthensFighterLevelSealNpc);
    checks->Require(
        TryReadLegacyFighterLevelSealCommand(
            packet,
            LegacyFighterLevelSealActionPacketBytes,
            &command) &&
        command.npcId == LegacyAthensFighterLevelSealNpc &&
        command.action == LegacyFighterLevelSealAction::Unseal,
        "Athens Level Sealer unseal action did not parse");

    const std::int32_t navigationSubIds[]{
        -1,
        LegacyFighterLevelSealDescriptionSubId};
    for (const auto subId : navigationSubIds) {
        BuildFighterLevelSealPacket(packet, subId);
        checks->Require(
            ClassifyLegacyFighterLevelSealPacket(
                packet,
                LegacyFighterLevelSealActionPacketBytes,
                nullptr) ==
                LegacyFighterLevelSealPacketKind::Navigation,
            "Level Sealer navigation was classified as a mutation");
    }

    BuildFighterLevelSealPacket(packet, 109);
    checks->Require(
        ClassifyLegacyFighterLevelSealPacket(
            packet,
            LegacyFighterLevelSealActionPacketBytes,
            nullptr) == LegacyFighterLevelSealPacketKind::Unrelated,
        "Level Sealer native result sub-id became a client mutation");
    BuildFighterLevelSealPacket(packet, 102, 5000);
    checks->Require(
        ClassifyLegacyFighterLevelSealPacket(
            packet,
            LegacyFighterLevelSealActionPacketBytes,
            nullptr) == LegacyFighterLevelSealPacketKind::Unrelated,
        "another NPC was mistaken for Level Sealer");
}

void CheckFailClosedParser(Checks* checks) {
    std::uint8_t packet[LegacyFighterLevelSealActionPacketBytes + 1]{};
    for (std::size_t index = 0;
         index < LegacyFighterLevelSealArgumentCount;
         ++index) {
        BuildFighterLevelSealPacket(
            packet, LegacyFighterLevelSealSealSubId);
        SetArgument(packet, index, static_cast<std::int32_t>(index));
        checks->Require(
            ClassifyLegacyFighterLevelSealPacket(
                packet,
                LegacyFighterLevelSealActionPacketBytes,
                nullptr) ==
                LegacyFighterLevelSealPacketKind::InvalidMutation,
            "Level Sealer accepted a non-empty mutation argument");
    }

    BuildFighterLevelSealPacket(
        packet, LegacyFighterLevelSealUnsealSubId);
    Write32(packet + 12, LegacyFighterLevelSealDialog + 1);
    checks->Require(
        ClassifyLegacyFighterLevelSealPacket(
            packet,
            LegacyFighterLevelSealActionPacketBytes,
            nullptr) ==
            LegacyFighterLevelSealPacketKind::InvalidMutation,
        "Level Sealer accepted a changed duplicate dialog");

    BuildFighterLevelSealPacket(
        packet, LegacyFighterLevelSealUnsealSubId);
    checks->Require(
        ClassifyLegacyFighterLevelSealPacket(
            packet,
            LegacyFighterLevelSealActionPacketBytes - 1,
            nullptr) ==
                LegacyFighterLevelSealPacketKind::InvalidMutation &&
        ClassifyLegacyFighterLevelSealPacket(
            packet,
            LegacyFighterLevelSealActionPacketBytes + 1,
            nullptr) ==
                LegacyFighterLevelSealPacketKind::InvalidMutation,
        "Level Sealer accepted a non-92-byte recognized request");
}

} // namespace

int RunSecureFighterLevelSealParserTests() {
    Checks checks{};
    CheckParser(&checks);
    CheckFailClosedParser(&checks);
    return checks.failures;
}
