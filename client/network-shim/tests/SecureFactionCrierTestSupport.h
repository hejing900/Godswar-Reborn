#pragma once

#include "../src/SecureFactionCrierCommandIdentity.h"
#include "../src/SecureLegacyCommandIdentity.h"
#include "../src/SecurePendingOperationRegistry.h"

#include <cstdint>
#include <cstdio>
#include <cstring>

namespace faction_crier_test {

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

inline void Write16(
    std::uint8_t* destination,
    std::uint16_t value) {
    destination[0] = static_cast<std::uint8_t>(value);
    destination[1] = static_cast<std::uint8_t>(value >> 8U);
}

inline void Write32(
    std::uint8_t* destination,
    std::uint32_t value) {
    for (std::size_t index = 0; index < 4; ++index) {
        destination[index] = static_cast<std::uint8_t>(
            value >> (index * 8U));
    }
}

inline void BuildFactionCrierPacket(
    std::uint8_t* packet,
    std::int32_t rootSubId,
    std::uint32_t npcId = LegacyPublishedSpartaFactionCrierNpc) {
    std::memset(packet, 0xFF, LegacyFactionCrierActionPacketBytes);
    Write16(packet, LegacyFactionCrierActionPacketBytes);
    Write16(packet + 2, LegacyNpcFunctionActionOpcode);
    Write32(packet + 4, npcId);
    Write32(packet + 8, LegacyFactionCrierDialog);
    Write32(packet + 12, LegacyFactionCrierDialog);
    Write32(packet + 16, static_cast<std::uint32_t>(rootSubId));
}

inline void SetArgument(
    std::uint8_t* packet,
    std::size_t argumentIndex,
    std::int32_t value) {
    Write32(
        packet + 20 + argumentIndex * 4,
        static_cast<std::uint32_t>(value));
}

inline void BuildLoginPacket(
    std::uint8_t principalSeed,
    std::uint8_t* packet) {
    std::memset(packet, 0, LoginPacketBytes);
    Write16(packet, static_cast<std::uint16_t>(LoginPacketBytes));
    Write16(packet + 2, LegacyLoginGameServerOpcode);
    for (std::size_t index = 0;
         index < SecurePrincipalFingerprintBytes;
         ++index) {
        packet[4 + index] = static_cast<std::uint8_t>(
            principalSeed + index);
    }
}

struct Hooks final {
    std::uint8_t randomSeed = 1;
    std::uint64_t now = 150'000;
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
    for (std::size_t index = 0;
         index < destinationBytes;
         ++index) {
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

inline bool Establish(
    SecurePendingOperationRegistry* registry,
    std::uint8_t principalSeed = 80,
    int characterId = 930) {
    std::uint8_t login[LoginPacketBytes]{};
    BuildLoginPacket(principalSeed, login);
    LegacyPacketDescriptor descriptor{};
    return registry != nullptr &&
        registry->DescribePacket(
            login, sizeof(login), &descriptor) ==
            SecureOperationRegistryResult::Success &&
        !descriptor.hasOperation &&
        registry->SetCharacter(characterId) ==
            SecureOperationRegistryResult::Success;
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

inline SecureLegacyCommandResult ResultFor(
    const LegacyPacketDescriptor& descriptor,
    SecureLegacyCommandDisposition disposition =
        SecureLegacyCommandDisposition::Applied) {
    SecureLegacyCommandResult result{};
    result.disposition = disposition;
    result.commandFamily = SecureLegacyCommandFamily::FactionCrier;
    result.inventoryRevision =
        disposition == SecureLegacyCommandDisposition::Applied ? 1 : 0;
    std::memcpy(
        result.operationId,
        descriptor.operation.operationId,
        sizeof(result.operationId));
    return result;
}

} // namespace faction_crier_test
