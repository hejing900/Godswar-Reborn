#include "SecureFactionCrierTestSupport.h"

namespace {

using namespace faction_crier_test;

void CheckClaimsAndRenewal(Checks* checks) {
    std::uint8_t packet[LegacyFactionCrierActionPacketBytes]{};
    LegacyFactionCrierCommand command{};

    BuildFactionCrierPacket(packet, 1, LegacyAthensFactionCrierNpc);
    checks->Require(
        TryReadLegacyFactionCrierCommand(
            packet, sizeof(packet), &command) &&
        command.operation == LegacyFactionCrierOperation::DailyClaim &&
        command.actionSubId == 1 &&
        command.npcId == LegacyAthensFactionCrierNpc,
        "Faction Crier daily claim did not parse");

    BuildFactionCrierPacket(packet, 3);
    SetArgument(packet, 0, 36);
    checks->Require(
        TryReadLegacyFactionCrierCommand(
            packet, sizeof(packet), &command) &&
        command.operation ==
            LegacyFactionCrierOperation::WeeklyReclaim &&
        command.actionSubId == 36 &&
        command.nameplateOrdinal == 6 &&
        command.paymentCurrency == LegacyFactionCrierCurrency::Gold,
        "Faction Crier weekly reclaim did not use nested action 36");

    BuildFactionCrierPacket(
        packet, 4, LegacySourceSpartaFactionCrierNpc);
    SetArgument(packet, 0, 46);
    SetArgument(packet, LegacyFactionCrierItemArgument, 307);
    SetArgument(packet, LegacyFactionCrierFirstScratchArgument, 19);
    SetArgument(packet, LegacyFactionCrierLastScratchArgument, 27);
    checks->Require(
        TryReadLegacyFactionCrierCommand(
            packet, sizeof(packet), &command) &&
        command.operation ==
            LegacyFactionCrierOperation::RenewNameplate &&
        command.actionSubId == 46 &&
        command.nameplateOrdinal == 6 &&
        command.sourceKitBagSlot == 79 &&
        command.paymentCurrency == LegacyFactionCrierCurrency::Gold,
        "Faction Crier renewal did not read args[6] page-slot coordinate");
}

void CheckTurnInOffers(Checks* checks) {
    std::uint8_t packet[LegacyFactionCrierActionPacketBytes]{};
    LegacyFactionCrierCommand command{};

    BuildFactionCrierPacket(packet, 2);
    SetArgument(packet, 0, 10);
    SetArgument(packet, 1, 105);
    checks->Require(
        TryReadLegacyFactionCrierCommand(
            packet, sizeof(packet), &command) &&
        command.actionSubId == 105 &&
        command.nameplateOrdinal == 5 &&
        command.nameplateSet ==
            LegacyFactionCrierNameplateSet::Single &&
        command.rewardKind ==
            LegacyFactionCrierRewardKind::Experience &&
        command.paymentCurrency == LegacyFactionCrierCurrency::None &&
        command.rewardMultiplier == 1,
        "Faction Crier single turn-in did not parse nested action 105");

    struct Offer final {
        int parent;
        int action;
        LegacyFactionCrierNameplateSet set;
        LegacyFactionCrierRewardKind reward;
        LegacyFactionCrierCurrency currency;
        int multiplier;
    };
    const Offer offers[]{
        {107, 110, LegacyFactionCrierNameplateSet::OddTriple,
            LegacyFactionCrierRewardKind::Experience,
            LegacyFactionCrierCurrency::Silver, 6},
        {107, 113, LegacyFactionCrierNameplateSet::OddTriple,
            LegacyFactionCrierRewardKind::TalentPoints,
            LegacyFactionCrierCurrency::BindingGold, 9},
        {107, 118, LegacyFactionCrierNameplateSet::OddTriple,
            LegacyFactionCrierRewardKind::Experience,
            LegacyFactionCrierCurrency::Gold, 12},
        {108, 121, LegacyFactionCrierNameplateSet::EvenTriple,
            LegacyFactionCrierRewardKind::TalentPoints,
            LegacyFactionCrierCurrency::Silver, 6},
        {108, 126, LegacyFactionCrierNameplateSet::EvenTriple,
            LegacyFactionCrierRewardKind::Experience,
            LegacyFactionCrierCurrency::BindingGold, 12},
        {108, 129, LegacyFactionCrierNameplateSet::EvenTriple,
            LegacyFactionCrierRewardKind::TalentPoints,
            LegacyFactionCrierCurrency::Gold, 12},
        {109, 130, LegacyFactionCrierNameplateSet::AllSix,
            LegacyFactionCrierRewardKind::ExperienceAndTalentPoints,
            LegacyFactionCrierCurrency::Silver, 12},
        {109, 131, LegacyFactionCrierNameplateSet::AllSix,
            LegacyFactionCrierRewardKind::ExperienceAndTalentPoints,
            LegacyFactionCrierCurrency::BindingGold, 18},
        {109, 134, LegacyFactionCrierNameplateSet::AllSix,
            LegacyFactionCrierRewardKind::ExperienceAndTalentPoints,
            LegacyFactionCrierCurrency::Gold, 24},
    };
    for (const auto& offer : offers) {
        BuildFactionCrierPacket(packet, 2);
        SetArgument(packet, 0, 20);
        SetArgument(packet, 1, offer.parent);
        SetArgument(packet, 2, offer.action);
        checks->Require(
            TryReadLegacyFactionCrierCommand(
                packet, sizeof(packet), &command) &&
            command.actionSubId == offer.action &&
            command.nameplateSet == offer.set &&
            command.rewardKind == offer.reward &&
            command.paymentCurrency == offer.currency &&
            command.rewardMultiplier == offer.multiplier,
            "Faction Crier nested premium offer mapping changed");
    }
}

void CheckNavigation(Checks* checks) {
    std::uint8_t packet[LegacyFactionCrierActionPacketBytes]{};
    const int roots[]{-1, 2, 3, 4};
    for (const int root : roots) {
        BuildFactionCrierPacket(packet, root);
        checks->Require(
            ClassifyLegacyFactionCrierPacket(
                packet, sizeof(packet), nullptr) ==
                LegacyFactionCrierPacketKind::Navigation,
            "Faction Crier root navigation was marked valuable");
    }

    const int paths[][2]{{10, -1}, {20, -1}, {20, 107},
        {20, 108}, {20, 109}};
    for (const auto& path : paths) {
        BuildFactionCrierPacket(packet, 2);
        SetArgument(packet, 0, path[0]);
        if (path[1] >= 0) {
            SetArgument(packet, 1, path[1]);
        }
        checks->Require(
            ClassifyLegacyFactionCrierPacket(
                packet, sizeof(packet), nullptr) ==
                LegacyFactionCrierPacketKind::Navigation,
            "Faction Crier nested page navigation was marked valuable");
    }

    BuildFactionCrierPacket(packet, 4);
    SetArgument(packet, 0, 41);
    checks->Require(
        ClassifyLegacyFactionCrierPacket(
            packet, sizeof(packet), nullptr) ==
            LegacyFactionCrierPacketKind::Navigation,
        "Faction Crier empty renewal attempt was marked valuable");
}

void CheckMalformedAndUnrelated(Checks* checks) {
    std::uint8_t packet[LegacyFactionCrierActionPacketBytes + 1]{};
    BuildFactionCrierPacket(packet, 2);
    SetArgument(packet, 0, 20);
    SetArgument(packet, 1, 107);
    SetArgument(packet, 2, 120);
    checks->Require(
        ClassifyLegacyFactionCrierPacket(
            packet,
            LegacyFactionCrierActionPacketBytes,
            nullptr) == LegacyFactionCrierPacketKind::InvalidMutation,
        "Faction Crier accepted an action outside its selected set");

    BuildFactionCrierPacket(packet, 2);
    SetArgument(packet, 0, 10);
    SetArgument(packet, 1, 101);
    SetArgument(packet, 3, 9);
    checks->Require(
        ClassifyLegacyFactionCrierPacket(
            packet,
            LegacyFactionCrierActionPacketBytes,
            nullptr) == LegacyFactionCrierPacketKind::InvalidMutation,
        "Faction Crier accepted a non-padding nested tail");

    BuildFactionCrierPacket(packet, 4);
    SetArgument(packet, 0, 41);
    SetArgument(packet, LegacyFactionCrierItemArgument, 24);
    checks->Require(
        ClassifyLegacyFactionCrierPacket(
            packet,
            LegacyFactionCrierActionPacketBytes,
            nullptr) == LegacyFactionCrierPacketKind::InvalidMutation,
        "Faction Crier accepted an impossible page-zero item coordinate");
    SetArgument(packet, LegacyFactionCrierItemArgument, 400);
    checks->Require(
        ClassifyLegacyFactionCrierPacket(
            packet,
            LegacyFactionCrierActionPacketBytes,
            nullptr) == LegacyFactionCrierPacketKind::InvalidMutation,
        "Faction Crier accepted an out-of-range item page");

    BuildFactionCrierPacket(packet, 1);
    Write32(packet + 12, LegacyFactionCrierDialog + 1);
    checks->Require(
        ClassifyLegacyFactionCrierPacket(
            packet,
            LegacyFactionCrierActionPacketBytes,
            nullptr) == LegacyFactionCrierPacketKind::InvalidMutation,
        "Faction Crier accepted a changed duplicate dialog");

    BuildFactionCrierPacket(packet, 1);
    checks->Require(
        ClassifyLegacyFactionCrierPacket(
            packet,
            LegacyFactionCrierActionPacketBytes - 1,
            nullptr) == LegacyFactionCrierPacketKind::InvalidMutation &&
        ClassifyLegacyFactionCrierPacket(
            packet,
            LegacyFactionCrierActionPacketBytes + 1,
            nullptr) == LegacyFactionCrierPacketKind::InvalidMutation,
        "Faction Crier accepted a non-92-byte mutation");

    BuildFactionCrierPacket(packet, 1);
    Write16(packet + 2, LegacyNpcFunctionActionOpcode - 1);
    checks->Require(
        ClassifyLegacyFactionCrierPacket(
            packet,
            LegacyFactionCrierActionPacketBytes,
            nullptr) == LegacyFactionCrierPacketKind::Unrelated,
        "Another opcode was mistaken for Faction Crier");
    BuildFactionCrierPacket(packet, 1, 5000);
    checks->Require(
        ClassifyLegacyFactionCrierPacket(
            packet,
            LegacyFactionCrierActionPacketBytes,
            nullptr) == LegacyFactionCrierPacketKind::Unrelated,
        "Another NPC was mistaken for Faction Crier");
    checks->Require(
        ClassifyLegacyFactionCrierPacket(nullptr, 0, nullptr) ==
            LegacyFactionCrierPacketKind::Unrelated &&
        !TryReadLegacyFactionCrierCommand(nullptr, 0, nullptr),
        "Faction Crier null parser contract changed");
}

} // namespace

int RunSecureFactionCrierParserTests() {
    Checks checks{};
    CheckClaimsAndRenewal(&checks);
    CheckTurnInOffers(&checks);
    CheckNavigation(&checks);
    CheckMalformedAndUnrelated(&checks);
    return checks.failures;
}
