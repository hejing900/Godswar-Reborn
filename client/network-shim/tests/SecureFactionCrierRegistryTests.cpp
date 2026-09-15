#include "SecureFactionCrierTestSupport.h"

namespace {

using namespace faction_crier_test;

SecureOperationRegistryResult Describe(
    SecurePendingOperationRegistry* registry,
    std::uint8_t* packet,
    LegacyPacketDescriptor* descriptor) {
    return registry->DescribePacket(
        packet,
        LegacyFactionCrierActionPacketBytes,
        descriptor);
}

void CheckPrincipalCharacterAndNavigation(Checks* checks) {
    Hooks hooks{};
    SecurePendingOperationRegistry registry(
        &hooks, Random, &hooks, Clock);
    std::uint8_t packet[LegacyFactionCrierActionPacketBytes]{};
    BuildFactionCrierPacket(packet, 1);
    LegacyPacketDescriptor descriptor{};
    checks->Require(
        Describe(&registry, packet, &descriptor) ==
            SecureOperationRegistryResult::NoPrincipal,
        "Faction Crier mutation did not require a principal");

    std::uint8_t login[LoginPacketBytes]{};
    BuildLoginPacket(80, login);
    checks->Require(
        registry.DescribePacket(
            login, sizeof(login), &descriptor) ==
                SecureOperationRegistryResult::Success &&
        Describe(&registry, packet, &descriptor) ==
            SecureOperationRegistryResult::NoCharacter &&
        registry.SetCharacter(930) ==
            SecureOperationRegistryResult::Success,
        "Faction Crier mutation did not require a character");

    BuildFactionCrierPacket(packet, 2);
    SetArgument(packet, 0, 20);
    SetArgument(packet, 1, 107);
    checks->Require(
        Describe(&registry, packet, &descriptor) ==
                SecureOperationRegistryResult::Success &&
        !descriptor.hasOperation &&
        registry.Snapshot().pending == 0,
        "Faction Crier page navigation received an operation UUID");
}

void CheckNestedActionIdentity(Checks* checks) {
    Hooks hooks{};
    SecurePendingOperationRegistry registry(
        &hooks, Random, &hooks, Clock);
    checks->Require(Establish(&registry),
        "Faction Crier identity setup failed");

    std::uint8_t packet[LegacyFactionCrierActionPacketBytes]{};
    BuildFactionCrierPacket(packet, 2);
    SetArgument(packet, 0, 20);
    SetArgument(packet, 1, 107);
    SetArgument(packet, 2, 112);
    LegacyPacketDescriptor first{};
    LegacyPacketDescriptor retry{};
    checks->Require(
        Describe(&registry, packet, &first) ==
                SecureOperationRegistryResult::Success &&
        first.hasOperation &&
        first.operation.opcode == LegacyNpcFunctionActionOpcode &&
        first.operation.packetBytes ==
            LegacyFactionCrierActionPacketBytes &&
        Describe(&registry, packet, &retry) ==
                SecureOperationRegistryResult::Success &&
        SameOperation(first, retry),
        "Faction Crier retry did not retain one UUID");

    SetArgument(packet, 2, 113);
    LegacyPacketDescriptor nextOffer{};
    checks->Require(
        Describe(&registry, packet, &nextOffer) ==
                SecureOperationRegistryResult::Success &&
        !SameOperation(first, nextOffer),
        "Faction Crier keyed a nested mutation by root sub-ID 2");

    BuildFactionCrierPacket(
        packet, 2, LegacyAthensFactionCrierNpc);
    SetArgument(packet, 0, 20);
    SetArgument(packet, 1, 107);
    SetArgument(packet, 2, 112);
    LegacyPacketDescriptor otherCity{};
    checks->Require(
        Describe(&registry, packet, &otherCity) ==
                SecureOperationRegistryResult::Success &&
        SameOperation(first, otherCity),
        "Equivalent city Faction Criers changed retry identity");
}

void CheckRenewalSlotIdentity(Checks* checks) {
    Hooks hooks{};
    SecurePendingOperationRegistry registry(
        &hooks, Random, &hooks, Clock);
    checks->Require(Establish(&registry),
        "Faction Crier renewal identity setup failed");

    std::uint8_t packet[LegacyFactionCrierActionPacketBytes]{};
    BuildFactionCrierPacket(packet, 4);
    SetArgument(packet, 0, 46);
    SetArgument(packet, LegacyFactionCrierItemArgument, 101);
    LegacyPacketDescriptor first{};
    LegacyPacketDescriptor retry{};
    checks->Require(
        Describe(&registry, packet, &first) ==
                SecureOperationRegistryResult::Success &&
        Describe(&registry, packet, &retry) ==
                SecureOperationRegistryResult::Success &&
        SameOperation(first, retry),
        "Faction Crier renewal retry changed UUID");

    SetArgument(packet, LegacyFactionCrierItemArgument, 102);
    LegacyPacketDescriptor anotherSource{};
    checks->Require(
        Describe(&registry, packet, &anotherSource) ==
                SecureOperationRegistryResult::Success &&
        !SameOperation(first, anotherSource),
        "Faction Crier renewal ignored its source item slot");
}

void CheckInvalidAndSettlement(Checks* checks) {
    Hooks hooks{};
    SecurePendingOperationRegistry registry(
        &hooks, Random, &hooks, Clock);
    checks->Require(Establish(&registry),
        "Faction Crier settlement setup failed");

    std::uint8_t packet[LegacyFactionCrierActionPacketBytes]{};
    BuildFactionCrierPacket(packet, 2);
    SetArgument(packet, 0, 20);
    SetArgument(packet, 1, 107);
    SetArgument(packet, 2, 120);
    LegacyPacketDescriptor descriptor{};
    checks->Require(
        Describe(&registry, packet, &descriptor) ==
                SecureOperationRegistryResult::InvalidPacket &&
        !descriptor.hasOperation &&
        registry.Snapshot().pending == 0,
        "Malformed Faction Crier action allocated operation state");

    BuildFactionCrierPacket(packet, 3);
    SetArgument(packet, 0, 31);
    checks->Require(
        Describe(&registry, packet, &descriptor) ==
                SecureOperationRegistryResult::Success &&
        descriptor.hasOperation,
        "Faction Crier weekly reclaim did not receive a UUID");

    auto wrong = ResultFor(descriptor);
    wrong.commandFamily = SecureLegacyCommandFamily::HolyStoneDrill;
    checks->Require(
        registry.Resolve(wrong) ==
                SecureOperationRegistryResult::FamilyConflict &&
        registry.Snapshot().pending == 1,
        "Faction Crier accepted another result family");

    const auto result = ResultFor(descriptor);
    checks->Require(
        registry.Resolve(result) ==
                SecureOperationRegistryResult::Success &&
        registry.Resolve(result) ==
                SecureOperationRegistryResult::Success &&
        registry.Snapshot().pending == 0 &&
        registry.Snapshot().resolved == 1,
        "Faction Crier result did not settle idempotently");
}

void CheckResultCodec(Checks* checks) {
    checks->Require(
        static_cast<std::uint16_t>(
            SecureLegacyCommandFamily::FactionCrier) == 56,
        "Faction Crier secure family no longer matches the server");

    SecureLegacyCommandResult input{};
    input.disposition = SecureLegacyCommandDisposition::Applied;
    input.commandFamily = SecureLegacyCommandFamily::FactionCrier;
    input.resultCode = 365;
    input.inventoryRevision = 9;
    for (std::size_t index = 0;
         index < sizeof(input.operationId);
         ++index) {
        input.operationId[index] =
            static_cast<std::uint8_t>(index + 1);
    }
    std::uint8_t encoded[
        SecureLegacyCommandResultPayloadBytes]{};
    SecureLegacyCommandResult decoded{};
    checks->Require(
        TryEncodeSecureLegacyCommandResult(
            input, encoded, sizeof(encoded)) &&
        TryDecodeSecureLegacyCommandResult(
            encoded, sizeof(encoded), &decoded) &&
        decoded.commandFamily ==
            SecureLegacyCommandFamily::FactionCrier &&
        decoded.resultCode == input.resultCode &&
        decoded.inventoryRevision == input.inventoryRevision &&
        std::memcmp(
            decoded.operationId,
            input.operationId,
            sizeof(input.operationId)) == 0,
        "Faction Crier secure result family did not round-trip");
}

} // namespace

int RunSecureFactionCrierRegistryTests() {
    Checks checks{};
    CheckPrincipalCharacterAndNavigation(&checks);
    CheckNestedActionIdentity(&checks);
    CheckRenewalSlotIdentity(&checks);
    CheckInvalidAndSettlement(&checks);
    CheckResultCodec(&checks);
    return checks.failures;
}
