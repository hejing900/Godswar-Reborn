#include "RawFighterLevelSealProjectionBridgeTests.h"

#include "../src/NetClientProxy.h"
#include "../src/RawFighterLevelSealProjectionBridge.h"
#include "../src/SecureLegacyCommandIdentity.h"

#include <array>
#include <cstddef>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <limits>

namespace {

using godswar::network::LegacyAthensFighterLevelSealNpc;
using godswar::network::LegacyFighterLevelSealActionPacketBytes;
using godswar::network::LegacyFighterLevelSealDialog;
using godswar::network::LegacyFighterLevelSealInsufficientFundsResult;
using godswar::network::LegacyFighterLevelSealSealSubId;
using godswar::network::LegacyFighterLevelSealSealedResult;
using godswar::network::LegacyFighterLevelSealUnsealSubId;
using godswar::network::LegacyFighterLevelSealUnsealedResult;
using godswar::network::LegacyNpcFunctionActionOpcode;
using godswar::network::RawFighterExperienceProjection;
using godswar::network::RawFighterLevelSealFailureResponseBytes;
using godswar::network::RawFighterLevelSealObservation;
using godswar::network::RawFighterLevelSealPreparedSend;
using godswar::network::RawFighterLevelSealProjectionBridge;
using godswar::network::RawFighterLevelSealRequestLifetimeMilliseconds;
using godswar::network::RawFighterLevelSealRequestTokenPrefix;
using godswar::network::RawFighterLevelSealResponseMarker;
using godswar::network::RawFighterLevelSealSuccessResponseBytes;

constexpr std::uint16_t NpcFunctionActionResponseOpcode = 10070;
constexpr std::uint32_t UInt32Max =
    (std::numeric_limits<std::uint32_t>::max)();
static_assert(RawFighterLevelSealResponseMarker == 0x31505852U);

int Failures = 0;

void Check(bool condition, const char* message) {
    if (condition) {
        return;
    }
    std::fprintf(stderr, "FAIL: %s\n", message);
    ++Failures;
}

std::uint16_t Read16(const std::uint8_t* bytes) {
    return static_cast<std::uint16_t>(
        bytes[0] |
        (static_cast<std::uint16_t>(bytes[1]) << 8U));
}

std::uint32_t Read32(const std::uint8_t* bytes) {
    return bytes[0] |
        (static_cast<std::uint32_t>(bytes[1]) << 8U) |
        (static_cast<std::uint32_t>(bytes[2]) << 16U) |
        (static_cast<std::uint32_t>(bytes[3]) << 24U);
}

void Write16(std::uint8_t* bytes, std::uint16_t value) {
    bytes[0] = static_cast<std::uint8_t>(value);
    bytes[1] = static_cast<std::uint8_t>(value >> 8U);
}

void Write32(std::uint8_t* bytes, std::uint32_t value) {
    bytes[0] = static_cast<std::uint8_t>(value);
    bytes[1] = static_cast<std::uint8_t>(value >> 8U);
    bytes[2] = static_cast<std::uint8_t>(value >> 16U);
    bytes[3] = static_cast<std::uint8_t>(value >> 24U);
}

struct Dependencies final {
    std::uint32_t random = 0x00123456U;
    std::uint64_t now = 10'000;
    bool randomSucceeds = true;
    bool clockSucceeds = true;
};

bool ReadRandom(void* context, std::uint32_t* random) noexcept {
    auto* dependencies = static_cast<Dependencies*>(context);
    if (dependencies == nullptr || random == nullptr ||
        !dependencies->randomSucceeds) {
        return false;
    }
    *random = dependencies->random++;
    return true;
}

bool ReadClock(void* context, std::uint64_t* now) noexcept {
    const auto* dependencies = static_cast<const Dependencies*>(context);
    if (dependencies == nullptr || now == nullptr ||
        !dependencies->clockSucceeds) {
        return false;
    }
    *now = dependencies->now;
    return true;
}

using Request = std::array<
    std::uint8_t,
    LegacyFighterLevelSealActionPacketBytes>;

Request BuildRequest(
    std::int32_t actionSubId,
    std::uint32_t npcId = LegacyAthensFighterLevelSealNpc) {
    Request packet{};
    Write16(packet.data(), static_cast<std::uint16_t>(packet.size()));
    Write16(packet.data() + 2, LegacyNpcFunctionActionOpcode);
    Write32(packet.data() + 4, npcId);
    Write32(
        packet.data() + 8,
        static_cast<std::uint32_t>(LegacyFighterLevelSealDialog));
    Write32(
        packet.data() + 12,
        static_cast<std::uint32_t>(LegacyFighterLevelSealDialog));
    Write32(packet.data() + 16, static_cast<std::uint32_t>(actionSubId));
    for (std::size_t offset = 20; offset < packet.size(); offset += 4) {
        Write32(packet.data() + offset, 0xFFFFFFFFU);
    }
    return packet;
}

std::array<std::uint8_t, RawFighterLevelSealSuccessResponseBytes>
BuildResponse(
    std::uint16_t packetBytes,
    std::uint32_t npcId,
    std::uint32_t result,
    std::uint32_t token,
    std::uint32_t current = 0,
    std::uint32_t maximum = 0) {
    std::array<
        std::uint8_t,
        RawFighterLevelSealSuccessResponseBytes> packet{};
    Write16(packet.data(), packetBytes);
    Write16(packet.data() + 2, NpcFunctionActionResponseOpcode);
    Write32(packet.data() + 4, npcId);
    Write32(
        packet.data() + 8,
        static_cast<std::uint32_t>(LegacyFighterLevelSealDialog));
    Write32(packet.data() + 12, result);
    if (packetBytes >= RawFighterLevelSealFailureResponseBytes) {
        Write32(packet.data() + 16, RawFighterLevelSealResponseMarker);
        Write32(packet.data() + 20, token);
    }
    if (packetBytes >= RawFighterLevelSealSuccessResponseBytes) {
        Write32(packet.data() + 24, current);
        Write32(packet.data() + 28, maximum);
    }
    return packet;
}

RawFighterLevelSealPreparedSend PrepareAndComplete(
    RawFighterLevelSealProjectionBridge* bridge,
    std::int32_t action,
    std::uint32_t npcId,
    Request* rewritten,
    bool sent = true) {
    const auto request = BuildRequest(action, npcId);
    RawFighterLevelSealPreparedSend prepared{};
    if (!bridge->TryPrepareClientPacket(
            request.data(),
            static_cast<int>(request.size()),
            rewritten->data(),
            rewritten->size(),
            &prepared)) {
        return RawFighterLevelSealPreparedSend{};
    }
    bridge->CompleteClientSend(prepared, sent);
    return prepared;
}

bool IsTrailerCleared(
    const std::array<
        std::uint8_t,
        RawFighterLevelSealSuccessResponseBytes>& response,
    std::size_t packetBytes) {
    for (std::size_t index = 16; index < packetBytes; ++index) {
        if (response[index] != 0) {
            return false;
        }
    }
    return true;
}

void RunRequestRewriteChecks() {
    Dependencies dependencies{};
    RawFighterLevelSealProjectionBridge bridge(
        &dependencies, ReadRandom, ReadClock);
    const auto request = BuildRequest(LegacyFighterLevelSealSealSubId);
    Request rewritten{};
    RawFighterLevelSealPreparedSend prepared{};
    Check(
        bridge.TryPrepareClientPacket(
            request.data(),
            static_cast<int>(request.size()),
            rewritten.data(),
            rewritten.size(),
            &prepared),
        "request: canonical rejected");
    const auto expectedToken =
        RawFighterLevelSealRequestTokenPrefix | 0x00123456U;
    Check(
        prepared.prepared && prepared.token == expectedToken &&
            Read32(rewritten.data() + 12) == expectedToken,
        "request: token offset/value");
    bool onlyTokenChanged = true;
    for (std::size_t index = 0; index < request.size(); ++index) {
        if (index >= 12 && index < 16) {
            continue;
        }
        onlyTokenChanged = onlyTokenChanged &&
            request[index] == rewritten[index];
    }
    Check(
        onlyTokenChanged,
        "request: field changed");

    RawFighterLevelSealPreparedSend unrelated{};
    auto navigation = BuildRequest(101);
    Check(
        !bridge.TryPrepareClientPacket(
            navigation.data(),
            static_cast<int>(navigation.size()),
            rewritten.data(),
            rewritten.size(),
            &unrelated),
        "request: navigation rewritten");
}

void RunRawEligibilityChecks() {
    godswar::network::NativeClientSnapshot client{};
    client.registered = true;
    client.state = godswar::network::NativeClientState::Connected;
    client.decision = godswar::network::ClientRouteDecision::PassThrough;
    Check(
        godswar::network::net_client_proxy_detail::
            IsRawFighterProjectionEligible(
                godswar::network::SecureClientRuntimeState::Disabled,
                client,
                true),
        "eligibility: disabled rejected");
    Check(
        !godswar::network::net_client_proxy_detail::
            IsRawFighterProjectionEligible(
                godswar::network::
                    SecureClientRuntimeState::SecureRequiredReady,
                client,
                true),
        "eligibility: secure accepted");
    Check(
        !godswar::network::net_client_proxy_detail::
            IsRawFighterProjectionEligible(
                godswar::network::SecureClientRuntimeState::FailedClosed,
                client,
                true),
        "eligibility: failure accepted");
    Check(
        !godswar::network::net_client_proxy_detail::
            IsRawFighterProjectionEligible(
                godswar::network::SecureClientRuntimeState::Disabled,
                client,
                false),
        "eligibility: unsupported host");
    client.state = godswar::network::NativeClientState::HostReady;
    Check(
        !godswar::network::net_client_proxy_detail::
            IsRawFighterProjectionEligible(
                godswar::network::SecureClientRuntimeState::Disabled,
                client,
                true),
        "eligibility: disconnected");
}

void RunSuccessChecks() {
    Dependencies dependencies{};
    RawFighterLevelSealProjectionBridge bridge(
        &dependencies, ReadRandom, ReadClock);
    Request rewritten{};
    const auto seal = PrepareAndComplete(
        &bridge,
        LegacyFighterLevelSealSealSubId,
        LegacyAthensFighterLevelSealNpc,
        &rewritten);
    auto response = BuildResponse(
        RawFighterLevelSealSuccessResponseBytes,
        seal.npcId,
        LegacyFighterLevelSealSealedResult,
        seal.token,
        4'000'000'000U,
        UInt32Max);
    Check(
        bridge.ObserveServerPacket(
            response.data(),
            RawFighterLevelSealSuccessResponseBytes) ==
            RawFighterLevelSealObservation::ProjectionQueued,
        "seal: projection not queued");
    Check(
        Read16(response.data()) == 16 &&
            IsTrailerCleared(
                response,
                RawFighterLevelSealSuccessResponseBytes),
        "seal: response not normalized");
    RawFighterExperienceProjection projection{};
    Check(
        bridge.TryTakeProjection(&projection) &&
            projection.currentExperience == 4'000'000'000U &&
            projection.maximumExperience == UInt32Max,
        "seal: projection values changed");

    const auto unseal = PrepareAndComplete(
        &bridge,
        LegacyFighterLevelSealUnsealSubId,
        LegacyAthensFighterLevelSealNpc,
        &rewritten);
    response = BuildResponse(
        RawFighterLevelSealSuccessResponseBytes,
        unseal.npcId,
        LegacyFighterLevelSealUnsealedResult,
        unseal.token,
        4'000'000'000U,
        117'174'640U);
    Check(
        bridge.ObserveServerPacket(
            response.data(),
            RawFighterLevelSealSuccessResponseBytes) ==
            RawFighterLevelSealObservation::ProjectionQueued &&
        bridge.TryTakeProjection(&projection) &&
            projection.currentExperience > projection.maximumExperience,
        "unseal: current above max rejected");
}

void RunTerminalAndCorrelationChecks() {
    Dependencies dependencies{};
    RawFighterLevelSealProjectionBridge bridge(
        &dependencies, ReadRandom, ReadClock);
    Request rewritten{};
    const auto unseal = PrepareAndComplete(
        &bridge,
        LegacyFighterLevelSealUnsealSubId,
        LegacyAthensFighterLevelSealNpc,
        &rewritten);
    auto failure = BuildResponse(
        RawFighterLevelSealFailureResponseBytes,
        unseal.npcId,
        LegacyFighterLevelSealInsufficientFundsResult,
        unseal.token);
    Check(
        bridge.ObserveServerPacket(
            failure.data(),
            RawFighterLevelSealFailureResponseBytes) ==
            RawFighterLevelSealObservation::Normalized &&
            Read16(failure.data()) == 16 &&
            IsTrailerCleared(
                failure,
                RawFighterLevelSealFailureResponseBytes),
        "failure: not normalized");
    RawFighterExperienceProjection projection{};
    Check(
        !bridge.TryTakeProjection(&projection),
        "failure: projection published");

    const auto seal = PrepareAndComplete(
        &bridge,
        LegacyFighterLevelSealSealSubId,
        LegacyAthensFighterLevelSealNpc,
        &rewritten);
    auto stale = BuildResponse(
        RawFighterLevelSealSuccessResponseBytes,
        seal.npcId,
        LegacyFighterLevelSealSealedResult,
        seal.token + 1,
        9,
        UInt32Max);
    Check(
        bridge.ObserveServerPacket(
            stale.data(),
            RawFighterLevelSealSuccessResponseBytes) ==
            RawFighterLevelSealObservation::Normalized &&
            Read16(stale.data()) == 16 &&
            !bridge.TryTakeProjection(&projection),
        "correlation: stale accepted");

    auto valid = BuildResponse(
        RawFighterLevelSealSuccessResponseBytes,
        seal.npcId,
        LegacyFighterLevelSealSealedResult,
        seal.token,
        9,
        UInt32Max);
    Check(
        bridge.ObserveServerPacket(
            valid.data(),
            RawFighterLevelSealSuccessResponseBytes) ==
            RawFighterLevelSealObservation::ProjectionQueued,
        "correlation: live consumed");
}

void RunLegacyAndExpiryChecks() {
    Dependencies dependencies{};
    RawFighterLevelSealProjectionBridge bridge(
        &dependencies, ReadRandom, ReadClock);
    Request rewritten{};
    const auto seal = PrepareAndComplete(
        &bridge,
        LegacyFighterLevelSealSealSubId,
        LegacyAthensFighterLevelSealNpc,
        &rewritten);
    auto legacy = BuildResponse(
        16,
        seal.npcId,
        LegacyFighterLevelSealSealedResult,
        0);
    Check(
        bridge.ObserveServerPacket(legacy.data(), 16) ==
            RawFighterLevelSealObservation::LegacyTerminal &&
            Read16(legacy.data()) == 16,
        "legacy: response changed");

    auto lateExtension = BuildResponse(
        RawFighterLevelSealSuccessResponseBytes,
        seal.npcId,
        LegacyFighterLevelSealSealedResult,
        seal.token,
        7,
        UInt32Max);
    RawFighterExperienceProjection projection{};
    Check(
        bridge.ObserveServerPacket(
            lateExtension.data(),
            RawFighterLevelSealSuccessResponseBytes) ==
            RawFighterLevelSealObservation::Normalized &&
            !bridge.TryTakeProjection(&projection),
        "legacy: token retained");

    const auto expiring = PrepareAndComplete(
        &bridge,
        LegacyFighterLevelSealUnsealSubId,
        LegacyAthensFighterLevelSealNpc,
        &rewritten);
    dependencies.now +=
        RawFighterLevelSealRequestLifetimeMilliseconds + 1;
    auto expired = BuildResponse(
        RawFighterLevelSealSuccessResponseBytes,
        expiring.npcId,
        LegacyFighterLevelSealUnsealedResult,
        expiring.token,
        1,
        117'174'640U);
    Check(
        bridge.ObserveServerPacket(
            expired.data(),
            RawFighterLevelSealSuccessResponseBytes) ==
            RawFighterLevelSealObservation::Normalized &&
            !bridge.TryTakeProjection(&projection),
        "expiry: projection published");
}

void RunRejectionAndResetChecks() {
    Dependencies dependencies{};
    RawFighterLevelSealProjectionBridge bridge(
        &dependencies, ReadRandom, ReadClock);
    Request rewritten{};
    const auto seal = PrepareAndComplete(
        &bridge,
        LegacyFighterLevelSealSealSubId,
        LegacyAthensFighterLevelSealNpc,
        &rewritten,
        false);
    auto response = BuildResponse(
        RawFighterLevelSealSuccessResponseBytes,
        seal.npcId,
        LegacyFighterLevelSealSealedResult,
        seal.token,
        1,
        UInt32Max);
    RawFighterExperienceProjection projection{};
    Check(
        bridge.ObserveServerPacket(
            response.data(),
            RawFighterLevelSealSuccessResponseBytes) ==
            RawFighterLevelSealObservation::Normalized &&
            !bridge.TryTakeProjection(&projection),
        "send failure: token armed");

    const auto clockFailure = PrepareAndComplete(
        &bridge,
        LegacyFighterLevelSealUnsealSubId,
        LegacyAthensFighterLevelSealNpc,
        &rewritten);
    dependencies.clockSucceeds = false;
    response = BuildResponse(
        RawFighterLevelSealSuccessResponseBytes,
        clockFailure.npcId,
        LegacyFighterLevelSealUnsealedResult,
        clockFailure.token,
        1,
        117'174'640U);
    Check(
        bridge.ObserveServerPacket(
            response.data(),
            RawFighterLevelSealSuccessResponseBytes) ==
            RawFighterLevelSealObservation::Normalized &&
            Read16(response.data()) == 16 &&
            IsTrailerCleared(
                response,
                RawFighterLevelSealSuccessResponseBytes) &&
            !bridge.TryTakeProjection(&projection),
        "clock: extension accepted");
    dependencies.clockSucceeds = true;
    bridge.Reset();

    const auto live = PrepareAndComplete(
        &bridge,
        LegacyFighterLevelSealSealSubId,
        LegacyAthensFighterLevelSealNpc,
        &rewritten);
    bridge.Reset();
    response = BuildResponse(
        RawFighterLevelSealSuccessResponseBytes,
        live.npcId,
        LegacyFighterLevelSealSealedResult,
        live.token,
        1,
        UInt32Max);
    Check(
        bridge.ObserveServerPacket(
            response.data(),
            RawFighterLevelSealSuccessResponseBytes) ==
            RawFighterLevelSealObservation::Normalized &&
            !bridge.TryTakeProjection(&projection),
        "reset: token retained");

    const auto wrongMaximum = PrepareAndComplete(
        &bridge,
        LegacyFighterLevelSealSealSubId,
        LegacyAthensFighterLevelSealNpc,
        &rewritten);
    response = BuildResponse(
        RawFighterLevelSealSuccessResponseBytes,
        wrongMaximum.npcId,
        LegacyFighterLevelSealSealedResult,
        wrongMaximum.token,
        1,
        117'174'640U);
    Check(
        bridge.ObserveServerPacket(
            response.data(),
            RawFighterLevelSealSuccessResponseBytes) ==
            RawFighterLevelSealObservation::Normalized &&
            !bridge.TryTakeProjection(&projection),
        "seal: invalid maximum accepted");

    std::array<std::uint8_t, 16> unrelated{};
    Write16(unrelated.data(), 16);
    Write16(unrelated.data() + 2, 10038);
    const auto before = unrelated;
    Check(
        bridge.ObserveServerPacket(
            unrelated.data(), unrelated.size()) ==
            RawFighterLevelSealObservation::Unrelated &&
            unrelated == before,
        "unrelated: packet changed");
}

} // namespace

int RunRawFighterLevelSealProjectionBridgeTests() {
    Failures = 0;
    RunRequestRewriteChecks();
    RunRawEligibilityChecks();
    RunSuccessChecks();
    RunTerminalAndCorrelationChecks();
    RunLegacyAndExpiryChecks();
    RunRejectionAndResetChecks();
    return Failures;
}
