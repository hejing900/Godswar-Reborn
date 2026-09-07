#pragma once

#include "../src/SecureFighterLevelSealCommandIdentity.h"
#include "../src/SecureLegacyCommandIdentity.h"
#include "../src/SecurePendingOperationRegistry.h"

#include <cstdint>
#include <cstdio>
#include <cstring>

namespace fighter_level_seal_test {

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

inline void Write16(std::uint8_t* destination, std::uint16_t value) {
    destination[0] = static_cast<std::uint8_t>(value);
    destination[1] = static_cast<std::uint8_t>(value >> 8U);
}

inline void Write32(std::uint8_t* destination, std::uint32_t value) {
    for (std::size_t index = 0; index < 4; ++index) {
        destination[index] = static_cast<std::uint8_t>(
            value >> (index * 8U));
    }
}

inline void BuildFighterLevelSealPacket(
    std::uint8_t* packet,
    std::int32_t subId,
    std::uint32_t npcId = LegacySpartaFighterLevelSealNpc) {
    std::memset(
        packet,
        0xFF,
        LegacyFighterLevelSealActionPacketBytes);
    Write16(packet, LegacyFighterLevelSealActionPacketBytes);
    Write16(packet + 2, LegacyNpcFunctionActionOpcode);
    Write32(packet + 4, npcId);
    Write32(packet + 8, LegacyFighterLevelSealDialog);
    Write32(packet + 12, LegacyFighterLevelSealDialog);
    Write32(packet + 16, static_cast<std::uint32_t>(subId));
}

inline void SetArgument(
    std::uint8_t* packet,
    std::size_t index,
    std::int32_t value) {
    Write32(
        packet + 20 + index * 4,
        static_cast<std::uint32_t>(value));
}

inline void BuildLoginPacket(std::uint8_t* packet) {
    std::memset(packet, 0, LoginPacketBytes);
    Write16(packet, static_cast<std::uint16_t>(LoginPacketBytes));
    Write16(packet + 2, LegacyLoginGameServerOpcode);
    for (std::size_t index = 0;
         index < SecurePrincipalFingerprintBytes;
         ++index) {
        packet[4 + index] = static_cast<std::uint8_t>(30 + index);
    }
}

struct Hooks final {
    std::uint8_t randomSeed = 1;
    std::uint64_t now = 310'000;
};

inline bool Random(
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

inline bool Clock(
    void* context,
    std::uint64_t* unixMilliseconds) noexcept {
    if (context == nullptr || unixMilliseconds == nullptr) {
        return false;
    }
    *unixMilliseconds = static_cast<Hooks*>(context)->now;
    return true;
}

inline bool Establish(SecurePendingOperationRegistry* registry) {
    std::uint8_t login[LoginPacketBytes]{};
    BuildLoginPacket(login);
    LegacyPacketDescriptor descriptor{};
    return registry != nullptr &&
        registry->DescribePacket(
            login, sizeof(login), &descriptor) ==
            SecureOperationRegistryResult::Success &&
        registry->SetCharacter(930) ==
            SecureOperationRegistryResult::Success;
}

inline SecureOperationRegistryResult Describe(
    SecurePendingOperationRegistry* registry,
    std::uint8_t* packet,
    LegacyPacketDescriptor* descriptor) {
    return registry->DescribePacket(
        packet,
        LegacyFighterLevelSealActionPacketBytes,
        descriptor);
}

inline bool SameOperation(
    const LegacyPacketDescriptor& first,
    const LegacyPacketDescriptor& second) {
    return first.hasOperation && second.hasOperation &&
        std::memcmp(
            first.operation.operationId,
            second.operation.operationId,
            sizeof(first.operation.operationId)) == 0;
}

inline LegacyPacketDescriptor CreatePending(
    SecurePendingOperationRegistry* registry,
    std::int32_t actionSubId) {
    std::uint8_t packet[LegacyFighterLevelSealActionPacketBytes]{};
    BuildFighterLevelSealPacket(packet, actionSubId);
    LegacyPacketDescriptor descriptor{};
    if (Describe(registry, packet, &descriptor) !=
            SecureOperationRegistryResult::Success ||
        !descriptor.hasOperation) {
        return LegacyPacketDescriptor{};
    }
    return descriptor;
}

inline SecureLegacyCommandResult ResultFor(
    const LegacyPacketDescriptor& descriptor,
    SecureLegacyCommandDisposition disposition,
    std::uint32_t resultCode,
    std::uint64_t revision) {
    SecureLegacyCommandResult result{};
    result.disposition = disposition;
    result.commandFamily =
        SecureLegacyCommandFamily::FighterLevelSeal;
    result.resultCode = resultCode;
    result.inventoryRevision = revision;
    if ((disposition ==
                SecureLegacyCommandDisposition::Applied ||
            disposition ==
                SecureLegacyCommandDisposition::Replayed) &&
        (resultCode == LegacyFighterLevelSealSealedResult ||
         resultCode == LegacyFighterLevelSealUnsealedResult)) {
        result.hasFighterExperienceProjection = true;
        result.currentExperience = 12'345;
        result.maximumExperience =
            resultCode == LegacyFighterLevelSealSealedResult
                ? 0xFFFFFFFFU
                : 117'174'640U;
    }
    std::memcpy(
        result.operationId,
        descriptor.operation.operationId,
        sizeof(result.operationId));
    return result;
}

} // namespace fighter_level_seal_test
