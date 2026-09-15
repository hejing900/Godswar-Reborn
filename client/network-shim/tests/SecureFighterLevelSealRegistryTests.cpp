#include "SecureFighterLevelSealTestSupport.h"

namespace {

using namespace fighter_level_seal_test;

void CheckRegistryIdentity(Checks* checks) {
    Hooks hooks{};
    SecurePendingOperationRegistry registry(
        &hooks, Random, &hooks, Clock);
    std::uint8_t packet[LegacyFighterLevelSealActionPacketBytes]{};
    BuildFighterLevelSealPacket(
        packet, LegacyFighterLevelSealSealSubId);
    LegacyPacketDescriptor first{};
    checks->Require(
        Describe(&registry, packet, &first) ==
            SecureOperationRegistryResult::NoPrincipal,
        "Level Sealer mutation did not require a principal");

    std::uint8_t login[LoginPacketBytes]{};
    BuildLoginPacket(login);
    checks->Require(
        registry.DescribePacket(login, sizeof(login), &first) ==
                SecureOperationRegistryResult::Success &&
        Describe(&registry, packet, &first) ==
                SecureOperationRegistryResult::NoCharacter &&
        registry.SetCharacter(930) ==
                SecureOperationRegistryResult::Success,
        "Level Sealer mutation did not require a character");

    BuildFighterLevelSealPacket(packet, -1);
    checks->Require(
        Describe(&registry, packet, &first) ==
                SecureOperationRegistryResult::Success &&
        !first.hasOperation &&
        registry.Snapshot().pending == 0,
        "Level Sealer initial navigation received an operation UUID");
    BuildFighterLevelSealPacket(
        packet, LegacyFighterLevelSealDescriptionSubId);
    checks->Require(
        Describe(&registry, packet, &first) ==
                SecureOperationRegistryResult::Success &&
        !first.hasOperation,
        "Level Sealer description navigation received an operation UUID");

    BuildFighterLevelSealPacket(
        packet,
        LegacyFighterLevelSealSealSubId,
        LegacySpartaFighterLevelSealNpc);
    LegacyPacketDescriptor retry{};
    checks->Require(
        Describe(&registry, packet, &first) ==
                SecureOperationRegistryResult::Success &&
        Describe(&registry, packet, &retry) ==
                SecureOperationRegistryResult::Success &&
        SameOperation(first, retry),
        "Level Sealer retry did not retain one UUID");

    BuildFighterLevelSealPacket(
        packet,
        LegacyFighterLevelSealSealSubId,
        LegacyAthensFighterLevelSealNpc);
    LegacyPacketDescriptor otherCity{};
    checks->Require(
        Describe(&registry, packet, &otherCity) ==
                SecureOperationRegistryResult::Success &&
        SameOperation(first, otherCity),
        "city transfer changed the Level Sealer retry UUID");

    BuildFighterLevelSealPacket(
        packet, LegacyFighterLevelSealUnsealSubId);
    LegacyPacketDescriptor unseal{};
    checks->Require(
        Describe(&registry, packet, &unseal) ==
                SecureOperationRegistryResult::Success &&
        unseal.hasOperation &&
        !SameOperation(first, unseal) &&
        registry.Snapshot().pending == 2,
        "seal and unseal did not receive distinct identities");

    SetArgument(packet, 0, 0);
    LegacyPacketDescriptor malformed{};
    checks->Require(
        Describe(&registry, packet, &malformed) ==
                SecureOperationRegistryResult::InvalidPacket &&
        !malformed.hasOperation &&
        registry.Snapshot().pending == 2,
        "malformed Level Sealer mutation allocated operation state");
}

void CheckActionBoundSettlement(Checks* checks) {
    Hooks hooks{};
    SecurePendingOperationRegistry registry(
        &hooks, Random, &hooks, Clock);
    checks->Require(Establish(&registry),
        "Level Sealer settlement setup failed");

    const auto seal = CreatePending(
        &registry, LegacyFighterLevelSealSealSubId);
    auto wrongFamily = ResultFor(
        seal,
        SecureLegacyCommandDisposition::Applied,
        LegacyFighterLevelSealSealedResult,
        1);
    wrongFamily.commandFamily = SecureLegacyCommandFamily::HolyStoneDrill;
    wrongFamily.hasFighterExperienceProjection = false;
    wrongFamily.currentExperience = 0;
    wrongFamily.maximumExperience = 0;
    checks->Require(
        registry.Resolve(wrongFamily) ==
                SecureOperationRegistryResult::FamilyConflict &&
        registry.Snapshot().pending == 1,
        "Level Sealer accepted another result family");

    const auto wrongAction = ResultFor(
        seal,
        SecureLegacyCommandDisposition::Applied,
        LegacyFighterLevelSealUnsealedResult,
        1);
    checks->Require(
        registry.Resolve(wrongAction) ==
                SecureOperationRegistryResult::InvalidPacket &&
        registry.Snapshot().pending == 1,
        "unseal result retired a pending seal UUID");

    const SecureLegacyCommandResult invalid[] {
        ResultFor(
            seal,
            SecureLegacyCommandDisposition::Rejected,
            LegacyFighterLevelSealSealedResult,
            0),
        ResultFor(
            seal,
            SecureLegacyCommandDisposition::Applied,
            LegacyFighterLevelSealAlreadySealedResult,
            1),
        ResultFor(
            seal,
            SecureLegacyCommandDisposition::Applied,
            999,
            1),
    };
    for (const auto& result : invalid) {
        checks->Require(
            registry.Resolve(result) ==
                    SecureOperationRegistryResult::InvalidPacket &&
            registry.Snapshot().pending == 1,
            "invalid Level Sealer result retired the pending UUID");
    }

    const auto success = ResultFor(
        seal,
        SecureLegacyCommandDisposition::Applied,
        LegacyFighterLevelSealSealedResult,
        1);
    checks->Require(
        registry.Resolve(success) ==
                SecureOperationRegistryResult::Success &&
        registry.Resolve(success) ==
                SecureOperationRegistryResult::Success &&
        registry.Snapshot().fighterExperienceProjectionCount == 1,
        "Level Sealer success did not settle idempotently");
    SecureFighterExperienceProjection projection{};
    checks->Require(
        registry.TryTakeFighterExperienceProjection(&projection) &&
        projection.currentExperience == 12'345 &&
        projection.maximumExperience == 0xFFFFFFFFU &&
        projection.authoritativeRevision == 1 &&
        !registry.TryTakeFighterExperienceProjection(&projection),
        "Level Sealer duplicate result republished its EXP projection");

    const auto unseal = CreatePending(
        &registry, LegacyFighterLevelSealUnsealSubId);
    const auto sealCodeForUnseal = ResultFor(
        unseal,
        SecureLegacyCommandDisposition::Applied,
        LegacyFighterLevelSealSealedResult,
        2);
    checks->Require(
        registry.Resolve(sealCodeForUnseal) ==
                SecureOperationRegistryResult::InvalidPacket &&
        registry.Snapshot().pending == 1,
        "seal result retired a pending unseal UUID");
    const auto insufficient = ResultFor(
        unseal,
        SecureLegacyCommandDisposition::Rejected,
        LegacyFighterLevelSealInsufficientFundsResult,
        0);
    checks->Require(
        registry.Resolve(insufficient) ==
                SecureOperationRegistryResult::Success &&
        registry.Snapshot().pending == 0,
        "Level Sealer insufficient-funds result did not settle");
}

void CheckResultMatrixAndCodec(Checks* checks) {
    struct Terminal final {
        std::int32_t action;
        SecureLegacyCommandDisposition disposition;
        std::uint32_t code;
        std::uint64_t revision;
    };
    const Terminal terminals[] {
        {LegacyFighterLevelSealSealSubId,
            SecureLegacyCommandDisposition::Applied,
            LegacyFighterLevelSealSealedResult, 1},
        {LegacyFighterLevelSealSealSubId,
            SecureLegacyCommandDisposition::Replayed,
            LegacyFighterLevelSealSealedResult, 2},
        {LegacyFighterLevelSealSealSubId,
            SecureLegacyCommandDisposition::Rejected,
            LegacyFighterLevelSealAlreadySealedResult, 0},
        {LegacyFighterLevelSealSealSubId,
            SecureLegacyCommandDisposition::Rejected,
            LegacyFighterLevelSealUnavailableResult, 0},
        {LegacyFighterLevelSealSealSubId,
            SecureLegacyCommandDisposition::Conflict,
            LegacyFighterLevelSealUnavailableResult, 1},
        {LegacyFighterLevelSealUnsealSubId,
            SecureLegacyCommandDisposition::Applied,
            LegacyFighterLevelSealUnsealedResult, 3},
        {LegacyFighterLevelSealUnsealSubId,
            SecureLegacyCommandDisposition::Replayed,
            LegacyFighterLevelSealUnsealedResult, 4},
        {LegacyFighterLevelSealUnsealSubId,
            SecureLegacyCommandDisposition::Rejected,
            LegacyFighterLevelSealInsufficientFundsResult, 0},
        {LegacyFighterLevelSealUnsealSubId,
            SecureLegacyCommandDisposition::Rejected,
            LegacyFighterLevelSealAlreadyUnsealedResult, 0},
        {LegacyFighterLevelSealUnsealSubId,
            SecureLegacyCommandDisposition::Rejected,
            LegacyFighterLevelSealUnavailableResult, 0},
        {LegacyFighterLevelSealUnsealSubId,
            SecureLegacyCommandDisposition::Conflict,
            LegacyFighterLevelSealUnavailableResult, 2},
    };

    Hooks hooks{};
    SecurePendingOperationRegistry registry(
        &hooks, Random, &hooks, Clock);
    checks->Require(Establish(&registry),
        "Level Sealer terminal matrix setup failed");
    for (const auto& terminal : terminals) {
        const auto descriptor = CreatePending(
            &registry, terminal.action);
        const auto result = ResultFor(
            descriptor,
            terminal.disposition,
            terminal.code,
            terminal.revision);
        checks->Require(
            descriptor.hasOperation &&
            registry.Resolve(result) ==
                SecureOperationRegistryResult::Success,
            "valid Level Sealer terminal result did not settle");
    }
    checks->Require(
        registry.Snapshot().pending == 0 &&
        registry.Snapshot().resolved == 11,
        "Level Sealer terminal matrix left inconsistent evidence");

    checks->Require(
        static_cast<std::uint16_t>(
            SecureLegacyCommandFamily::FighterLevelSeal) == 60,
        "Level Sealer secure family no longer matches the server");
    const auto descriptor = CreatePending(
        &registry, LegacyFighterLevelSealSealSubId);
    const auto source = ResultFor(
        descriptor,
        SecureLegacyCommandDisposition::Applied,
        LegacyFighterLevelSealSealedResult,
        11);
    std::uint8_t encoded[
        SecureLegacyCommandResultV2PayloadBytes]{};
    SecureLegacyCommandResult decoded{};
    checks->Require(
        TryEncodeSecureLegacyCommandResult(
            source, encoded, sizeof(encoded)) &&
        TryDecodeSecureLegacyCommandResult(
            encoded, sizeof(encoded), &decoded) &&
        decoded.commandFamily ==
            SecureLegacyCommandFamily::FighterLevelSeal &&
        decoded.resultCode == LegacyFighterLevelSealSealedResult &&
        decoded.inventoryRevision == 11 &&
        decoded.hasFighterExperienceProjection &&
        decoded.currentExperience == 12'345 &&
        decoded.maximumExperience == 0xFFFFFFFFU &&
        std::memcmp(
            decoded.operationId,
            source.operationId,
            sizeof(source.operationId)) == 0,
        "Level Sealer family 60 result did not round-trip");
}

void CheckProjectionAuthorizationAndOrdering(Checks* checks) {
    Hooks hooks{};
    SecurePendingOperationRegistry registry(
        &hooks, Random, &hooks, Clock);
    checks->Require(
        Establish(&registry),
        "Level Sealer EXP projection setup failed");

    const auto seal = CreatePending(
        &registry, LegacyFighterLevelSealSealSubId);
    auto missingProjection = ResultFor(
        seal,
        SecureLegacyCommandDisposition::Applied,
        LegacyFighterLevelSealSealedResult,
        21);
    missingProjection.hasFighterExperienceProjection = false;
    missingProjection.currentExperience = 0;
    missingProjection.maximumExperience = 0;
    checks->Require(
        registry.Resolve(missingProjection) ==
                SecureOperationRegistryResult::InvalidPacket &&
        registry.Snapshot().pending == 1 &&
        registry.Snapshot().fighterExperienceProjectionCount == 0,
        "successful Level Sealer v1 result retired UUID without EXP projection");

    const auto sealed = ResultFor(
        seal,
        SecureLegacyCommandDisposition::Applied,
        LegacyFighterLevelSealSealedResult,
        21);
    checks->Require(
        registry.Resolve(sealed) ==
                SecureOperationRegistryResult::Success,
        "sealed EXP projection did not resolve");

    const auto unseal = CreatePending(
        &registry, LegacyFighterLevelSealUnsealSubId);
    const auto unsealed = ResultFor(
        unseal,
        SecureLegacyCommandDisposition::Replayed,
        LegacyFighterLevelSealUnsealedResult,
        22);
    checks->Require(
        registry.Resolve(unsealed) ==
                SecureOperationRegistryResult::Success &&
        registry.Snapshot().fighterExperienceProjectionCount == 2,
        "replayed unseal did not publish authoritative EXP projection");

    SecureFighterExperienceProjection first{};
    SecureFighterExperienceProjection second{};
    SecureFighterExperienceProjection none{};
    checks->Require(
        registry.TryTakeFighterExperienceProjection(&first) &&
        registry.TryTakeFighterExperienceProjection(&second) &&
        !registry.TryTakeFighterExperienceProjection(&none) &&
        first.maximumExperience == 0xFFFFFFFFU &&
        first.authoritativeRevision == 21 &&
        second.currentExperience == 12'345 &&
        second.maximumExperience == 117'174'640U &&
        second.authoritativeRevision == 22,
        "seal/unseal EXP projections were not retained in result order");

    const auto rejected = CreatePending(
        &registry, LegacyFighterLevelSealUnsealSubId);
    auto forgedProjection = ResultFor(
        rejected,
        SecureLegacyCommandDisposition::Rejected,
        LegacyFighterLevelSealInsufficientFundsResult,
        0);
    forgedProjection.hasFighterExperienceProjection = true;
    forgedProjection.currentExperience = 1;
    forgedProjection.maximumExperience = 2;
    checks->Require(
        registry.Resolve(forgedProjection) ==
                SecureOperationRegistryResult::InvalidPacket &&
        registry.Snapshot().pending == 1 &&
        registry.Snapshot().fighterExperienceProjectionCount == 0,
        "rejected Level Sealer result published an EXP projection");
}

} // namespace

int RunSecureFighterLevelSealRegistryTests() {
    Checks checks{};
    CheckRegistryIdentity(&checks);
    CheckActionBoundSettlement(&checks);
    CheckResultMatrixAndCodec(&checks);
    CheckProjectionAuthorizationAndOrdering(&checks);
    return checks.failures;
}
