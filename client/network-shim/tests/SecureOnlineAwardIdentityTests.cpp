#include "SecureOnlineAwardIdentityTests.h"

#include "../src/SecureLegacyCommandIdentity.h"
#include "../src/SecureOnlineAwardCommandIdentity.h"
#include "../src/SecurePendingOperationRegistry.h"

#include <cstdint>
#include <cstdio>
#include <cstring>

namespace {

using namespace godswar::network;

inline constexpr std::size_t LoginPacketBytes =
    4 + SecurePrincipalFingerprintBytes;

struct Checks final {
    int failures = 0;

    void Require(bool condition, const char* message) {
        if (!condition) {
            std::fprintf(stderr, "FAIL: %s\n", message);
            ++failures;
        }
    }
};

void Write16(std::uint8_t* destination, std::uint16_t value) {
    destination[0] = static_cast<std::uint8_t>(value);
    destination[1] = static_cast<std::uint8_t>(value >> 8U);
}

void Write32(std::uint8_t* destination, std::uint32_t value) {
    for (std::size_t index = 0; index < 4; ++index) {
        destination[index] = static_cast<std::uint8_t>(
            value >> (index * 8U));
    }
}

void BuildOnlineAwardPacket(
    std::uint8_t* packet,
    std::uint32_t npcId = LegacyAthensOnlineAwardNpc) {
    std::memset(packet, 0xFF, LegacyOnlineAwardActionPacketBytes);
    Write16(packet, LegacyOnlineAwardActionPacketBytes);
    Write16(packet + 2, LegacyNpcFunctionActionOpcode);
    Write32(packet + 4, npcId);
    Write32(packet + 8, LegacyOnlineAwardDialog);
    Write32(packet + 12, LegacyOnlineAwardDialog);
    Write32(
        packet + 16,
        static_cast<std::uint32_t>(LegacyOnlineAwardInitialSubId));
}

void BuildLoginPacket(std::uint8_t* packet) {
    std::memset(packet, 0, LoginPacketBytes);
    Write16(packet, static_cast<std::uint16_t>(LoginPacketBytes));
    Write16(packet + 2, LegacyLoginGameServerOpcode);
    for (std::size_t index = 0;
         index < SecurePrincipalFingerprintBytes;
         ++index) {
        packet[4 + index] = static_cast<std::uint8_t>(80 + index);
    }
}

struct Hooks final {
    std::uint8_t randomSeed = 1;
    std::uint64_t now = 170'000;
};

bool Random(
    void* context,
    void* destination,
    std::size_t destinationBytes) noexcept {
    auto* hooks = static_cast<Hooks*>(context);
    auto* output = static_cast<std::uint8_t*>(destination);
    if (hooks == nullptr || output == nullptr) {
        return false;
    }
    for (std::size_t index = 0; index < destinationBytes; ++index) {
        output[index] = static_cast<std::uint8_t>(
            hooks->randomSeed + index);
    }
    ++hooks->randomSeed;
    return true;
}

bool Clock(
    void* context,
    std::uint64_t* unixMilliseconds) noexcept {
    if (context == nullptr || unixMilliseconds == nullptr) {
        return false;
    }
    *unixMilliseconds = static_cast<Hooks*>(context)->now;
    return true;
}

bool Establish(SecurePendingOperationRegistry* registry) {
    std::uint8_t login[LoginPacketBytes]{};
    BuildLoginPacket(login);
    LegacyPacketDescriptor descriptor{};
    return registry != nullptr &&
        registry->DescribePacket(
            login, sizeof(login), &descriptor) ==
            SecureOperationRegistryResult::Success &&
        !descriptor.hasOperation &&
        registry->SetCharacter(930) ==
            SecureOperationRegistryResult::Success;
}

SecureOperationRegistryResult Describe(
    SecurePendingOperationRegistry* registry,
    std::uint8_t* packet,
    LegacyPacketDescriptor* descriptor) {
    return registry->DescribePacket(
        packet,
        LegacyOnlineAwardActionPacketBytes,
        descriptor);
}

bool SameOperation(
    const LegacyPacketDescriptor& first,
    const LegacyPacketDescriptor& second) {
    return first.hasOperation && second.hasOperation &&
        std::memcmp(
            first.operation.operationId,
            second.operation.operationId,
            sizeof(first.operation.operationId)) == 0;
}

SecureLegacyCommandResult ResultFor(
    const LegacyPacketDescriptor& descriptor,
    SecureLegacyCommandDisposition disposition,
    std::uint32_t code,
    std::uint64_t revision) {
    SecureLegacyCommandResult result{};
    result.disposition = disposition;
    result.commandFamily = SecureLegacyCommandFamily::OnlineAward;
    result.resultCode = code;
    result.inventoryRevision = revision;
    std::memcpy(
        result.operationId,
        descriptor.operation.operationId,
        sizeof(result.operationId));
    return result;
}

void CheckExactParser(Checks* checks) {
    std::uint8_t packet[LegacyOnlineAwardActionPacketBytes]{};
    LegacyOnlineAwardCommand command{};
    BuildOnlineAwardPacket(packet, LegacyAthensOnlineAwardNpc);
    checks->Require(
        TryReadLegacyOnlineAwardCommand(
            packet, sizeof(packet), &command) &&
        command.npcId == LegacyAthensOnlineAwardNpc,
        "Athens Online Award claim did not parse");
    BuildOnlineAwardPacket(packet, LegacySpartaOnlineAwardNpc);
    checks->Require(
        TryReadLegacyOnlineAwardCommand(
            packet, sizeof(packet), &command) &&
        command.npcId == LegacySpartaOnlineAwardNpc,
        "Sparta Online Award claim did not parse");

    for (std::size_t index = 0;
         index < LegacyOnlineAwardArgumentCount;
         ++index) {
        Write32(
            packet + 20 + index * 4,
            static_cast<std::uint32_t>(
                0xA5010000U + index * 0x101U));
    }
    checks->Require(
        TryReadLegacyOnlineAwardCommand(
            packet, sizeof(packet), &command) &&
        command.npcId == LegacySpartaOnlineAwardNpc,
        "Online Award rejected unused native argument scratch values");
}

void CheckFailClosedParser(Checks* checks) {
    std::uint8_t packet[LegacyOnlineAwardActionPacketBytes + 1]{};
    BuildOnlineAwardPacket(packet);
    checks->Require(
        ClassifyLegacyOnlineAwardPacket(
            packet,
            LegacyOnlineAwardActionPacketBytes - 1,
            nullptr) == LegacyOnlineAwardPacketKind::InvalidMutation &&
        ClassifyLegacyOnlineAwardPacket(
            packet,
            LegacyOnlineAwardActionPacketBytes + 1,
            nullptr) == LegacyOnlineAwardPacketKind::InvalidMutation,
        "Online Award accepted a non-92-byte recognized request");

    BuildOnlineAwardPacket(packet);
    Write32(packet + 12, LegacyOnlineAwardDialog + 1);
    checks->Require(
        ClassifyLegacyOnlineAwardPacket(
            packet, LegacyOnlineAwardActionPacketBytes, nullptr) ==
            LegacyOnlineAwardPacketKind::InvalidMutation,
        "Online Award accepted a changed duplicate dialog");
    BuildOnlineAwardPacket(packet);
    Write32(packet + 16, 0);
    checks->Require(
        ClassifyLegacyOnlineAwardPacket(
            packet, LegacyOnlineAwardActionPacketBytes, nullptr) ==
            LegacyOnlineAwardPacketKind::InvalidMutation,
        "Online Award accepted a non-initial sub-id");
    BuildOnlineAwardPacket(packet, 5000);
    checks->Require(
        ClassifyLegacyOnlineAwardPacket(
            packet, LegacyOnlineAwardActionPacketBytes, nullptr) ==
            LegacyOnlineAwardPacketKind::Unrelated,
        "another NPC was mistaken for Online Award");
    BuildOnlineAwardPacket(packet, 5131);
    checks->Require(
        ClassifyLegacyOnlineAwardPacket(
            packet, LegacyOnlineAwardActionPacketBytes, nullptr) ==
            LegacyOnlineAwardPacketKind::Unrelated,
        "stale Sparta interaction 5131 was accepted as Online Award");
    BuildOnlineAwardPacket(packet);
    Write16(packet + 2, LegacyNpcFunctionActionOpcode - 1);
    checks->Require(
        ClassifyLegacyOnlineAwardPacket(
            packet, LegacyOnlineAwardActionPacketBytes, nullptr) ==
            LegacyOnlineAwardPacketKind::Unrelated &&
        ClassifyLegacyOnlineAwardPacket(nullptr, 0, nullptr) ==
            LegacyOnlineAwardPacketKind::Unrelated,
        "Online Award unrelated/null parser contract changed");
}

void CheckRegistryIdentity(Checks* checks) {
    Hooks hooks{};
    SecurePendingOperationRegistry registry(
        &hooks, Random, &hooks, Clock);
    std::uint8_t packet[LegacyOnlineAwardActionPacketBytes]{};
    BuildOnlineAwardPacket(packet);
    LegacyPacketDescriptor first{};
    checks->Require(
        Describe(&registry, packet, &first) ==
            SecureOperationRegistryResult::NoPrincipal,
        "Online Award mutation did not require a principal");

    std::uint8_t login[LoginPacketBytes]{};
    BuildLoginPacket(login);
    checks->Require(
        registry.DescribePacket(login, sizeof(login), &first) ==
                SecureOperationRegistryResult::Success &&
        Describe(&registry, packet, &first) ==
                SecureOperationRegistryResult::NoCharacter &&
        registry.SetCharacter(930) ==
                SecureOperationRegistryResult::Success,
        "Online Award mutation did not require a character");

    BuildOnlineAwardPacket(packet, LegacyAthensOnlineAwardNpc);
    LegacyPacketDescriptor retry{};
    LegacyPacketDescriptor otherCity{};
    checks->Require(
        Describe(&registry, packet, &first) ==
                SecureOperationRegistryResult::Success &&
        Describe(&registry, packet, &retry) ==
                SecureOperationRegistryResult::Success &&
        first.hasOperation && SameOperation(first, retry),
        "Online Award retry did not retain one UUID");
    for (std::size_t index = 0;
         index < LegacyOnlineAwardArgumentCount;
         ++index) {
        Write32(
            packet + 20 + index * 4,
            static_cast<std::uint32_t>(index * 73U + 11U));
    }
    LegacyPacketDescriptor staleArguments{};
    checks->Require(
        Describe(&registry, packet, &staleArguments) ==
                SecureOperationRegistryResult::Success &&
        SameOperation(first, staleArguments) &&
        registry.Snapshot().pending == 1,
        "unused Online Award argument scratch changed the retry UUID");
    BuildOnlineAwardPacket(packet, LegacySpartaOnlineAwardNpc);
    checks->Require(
        Describe(&registry, packet, &otherCity) ==
                SecureOperationRegistryResult::Success &&
        SameOperation(first, otherCity) &&
        registry.Snapshot().pending == 1,
        "city transfer changed character-scoped Online Award identity");
}

LegacyPacketDescriptor CreatePending(
    SecurePendingOperationRegistry* registry) {
    std::uint8_t packet[LegacyOnlineAwardActionPacketBytes]{};
    BuildOnlineAwardPacket(packet);
    LegacyPacketDescriptor descriptor{};
    if (Describe(registry, packet, &descriptor) !=
            SecureOperationRegistryResult::Success ||
        !descriptor.hasOperation) {
        descriptor = LegacyPacketDescriptor{};
    }
    return descriptor;
}

void CheckResultMatrix(Checks* checks) {
    Hooks hooks{};
    SecurePendingOperationRegistry registry(
        &hooks, Random, &hooks, Clock);
    checks->Require(Establish(&registry),
        "Online Award result setup failed");
    auto descriptor = CreatePending(&registry);
    checks->Require(descriptor.hasOperation,
        "Online Award result setup created no operation");

    auto wrongFamily = ResultFor(
        descriptor,
        SecureLegacyCommandDisposition::Applied,
        0,
        1);
    wrongFamily.commandFamily =
        SecureLegacyCommandFamily::HolyStoneDrill;
    checks->Require(
        registry.Resolve(wrongFamily) ==
                SecureOperationRegistryResult::FamilyConflict &&
        registry.Snapshot().pending == 1,
        "Online Award accepted another result family");

    const SecureLegacyCommandResult invalidResults[]{
        ResultFor(descriptor,
            SecureLegacyCommandDisposition::Applied, 999, 1),
        ResultFor(descriptor,
            SecureLegacyCommandDisposition::Rejected,
            LegacyOnlineAwardSuccessResult, 0),
        ResultFor(descriptor,
            SecureLegacyCommandDisposition::Replayed,
            LegacyOnlineAwardSuccessResult, 0),
        ResultFor(descriptor,
            SecureLegacyCommandDisposition::Applied,
            LegacyOnlineAwardAlreadyResult, 1),
        ResultFor(descriptor,
            SecureLegacyCommandDisposition::Conflict,
            LegacyOnlineAwardBagFullResult, 0),
        ResultFor(descriptor,
            SecureLegacyCommandDisposition::Applied,
            LegacyOnlineAwardUnavailableResult, 1),
    };
    for (const auto& invalid : invalidResults) {
        checks->Require(
            registry.Resolve(invalid) ==
                    SecureOperationRegistryResult::InvalidPacket &&
            registry.Snapshot().pending == 1,
            "invalid Online Award result retired the pending UUID");
    }

    const auto success = ResultFor(
        descriptor,
        SecureLegacyCommandDisposition::Applied,
        LegacyOnlineAwardSuccessResult,
        1);
    checks->Require(
        registry.Resolve(success) ==
                SecureOperationRegistryResult::Success &&
        registry.Resolve(success) ==
                SecureOperationRegistryResult::Success,
        "applied Online Award success did not settle idempotently");

    struct ValidResult final {
        SecureLegacyCommandDisposition disposition;
        std::uint32_t code;
        std::uint64_t revision;
    };
    const ValidResult valid[]{
        {SecureLegacyCommandDisposition::Replayed,
            LegacyOnlineAwardSuccessResult, 2},
        {SecureLegacyCommandDisposition::Rejected,
            LegacyOnlineAwardAlreadyResult, 0},
        {SecureLegacyCommandDisposition::Rejected,
            LegacyOnlineAwardBagFullResult, 0},
        {SecureLegacyCommandDisposition::Rejected,
            LegacyOnlineAwardUnavailableResult, 0},
        {SecureLegacyCommandDisposition::Conflict,
            LegacyOnlineAwardUnavailableResult, 0},
    };
    for (const auto& expected : valid) {
        descriptor = CreatePending(&registry);
        const auto result = ResultFor(
            descriptor,
            expected.disposition,
            expected.code,
            expected.revision);
        checks->Require(
            descriptor.hasOperation &&
            registry.Resolve(result) ==
                SecureOperationRegistryResult::Success,
            "valid Online Award terminal result did not settle");
    }
    checks->Require(
        registry.Snapshot().pending == 0 &&
        registry.Snapshot().resolved == 6,
        "Online Award result matrix left inconsistent registry evidence");
}

void CheckResultCodec(Checks* checks) {
    checks->Require(
        static_cast<std::uint16_t>(
            SecureLegacyCommandFamily::OnlineAward) == 57,
        "Online Award secure family no longer matches the server");
    SecureLegacyCommandResult input{};
    input.disposition = SecureLegacyCommandDisposition::Applied;
    input.commandFamily = SecureLegacyCommandFamily::OnlineAward;
    input.resultCode = LegacyOnlineAwardSuccessResult;
    input.inventoryRevision = 11;
    for (std::size_t index = 0;
         index < sizeof(input.operationId);
         ++index) {
        input.operationId[index] =
            static_cast<std::uint8_t>(index + 1);
    }
    std::uint8_t encoded[SecureLegacyCommandResultPayloadBytes]{};
    SecureLegacyCommandResult decoded{};
    checks->Require(
        TryEncodeSecureLegacyCommandResult(
            input, encoded, sizeof(encoded)) &&
        TryDecodeSecureLegacyCommandResult(
            encoded, sizeof(encoded), &decoded) &&
        decoded.commandFamily ==
            SecureLegacyCommandFamily::OnlineAward &&
        decoded.resultCode == LegacyOnlineAwardSuccessResult &&
        decoded.inventoryRevision == 11 &&
        std::memcmp(
            decoded.operationId,
            input.operationId,
            sizeof(input.operationId)) == 0,
        "Online Award family 57 result did not round-trip");
}

} // namespace

int RunSecureOnlineAwardIdentityTests() {
    Checks checks{};
    CheckExactParser(&checks);
    CheckFailClosedParser(&checks);
    CheckRegistryIdentity(&checks);
    CheckResultMatrix(&checks);
    CheckResultCodec(&checks);
    return checks.failures;
}
