#include "OriginFighterExperienceHostTests.h"

#include "../src/OriginFighterExperienceHost.h"

#include <array>
#include <cstddef>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <limits>

namespace {

constexpr std::size_t PlayerCurrentExperienceOffset = 0x2B4;
constexpr std::size_t PlayerMaximumExperienceOffset = 0x47C;
constexpr std::size_t PlayerBytes =
    PlayerMaximumExperienceOffset + sizeof(std::uint32_t);
constexpr std::size_t LevelExperienceUpdateReturnOffset = 0xCE;

constexpr std::uint8_t LevelExperienceAccessorPrefix[]{
    0xA1, 0x28, 0x63, 0x57, 0x01, 0x85, 0xC0, 0x75,
    0x44, 0x6A, 0x20, 0xE8, 0xC3, 0xC5, 0x22, 0x00,
    0x83, 0xC4, 0x04, 0x85, 0xC0, 0x74, 0x2F,
};
constexpr std::uint8_t LevelExperienceUpdatePrefix[]{
    0x55, 0x8B, 0xEC, 0x83, 0xE4, 0xF8, 0x8B, 0x4A,
    0x0C, 0x83, 0xEC, 0x28, 0x85, 0xC9, 0x0F, 0x84,
    0xB7, 0x00, 0x00, 0x00, 0x85, 0xC0, 0x89, 0x44,
    0x24, 0x04, 0xDB, 0x44, 0x24, 0x04, 0x7D, 0x06,
    0xD8, 0x05, 0x00, 0x16, 0x96, 0x00,
};
constexpr std::uint8_t PersonalInfoAccessorPrefix[]{
    0x6A, 0xFF, 0x68, 0x7B, 0x11, 0x81, 0x00, 0x64,
    0xA1, 0x00, 0x00, 0x00, 0x00, 0x50, 0x83, 0xEC,
    0x08, 0x56, 0xA1, 0xB4, 0x79, 0x9C, 0x00, 0x33,
    0xC4,
};
constexpr std::uint8_t PersonalInfoRefreshPrefix[]{
    0x55, 0x8B, 0xEC, 0x83, 0xE4, 0xC0, 0x81, 0xEC,
    0x34, 0x03, 0x00, 0x00, 0xA1, 0xB4, 0x79, 0x9C,
    0x00, 0x33, 0xC4, 0x89, 0x84, 0x24, 0x30, 0x03,
    0x00, 0x00, 0x53, 0x56, 0x57, 0x68, 0x08, 0x02,
    0x00, 0x00,
};

int Failures = 0;

void Check(bool condition, const char* message) {
    if (condition) {
        return;
    }
    std::fprintf(stderr, "FAIL: %s\n", message);
    ++Failures;
}

struct RefreshEvidence {
    std::uint32_t currentExperience = 0;
    std::uint32_t maximumExperience = 0;
    int calls = 0;
    bool result = true;
};

bool CaptureRefresh(
    void* context,
    std::uint32_t currentExperience,
    std::uint32_t maximumExperience) noexcept {
    auto* evidence = static_cast<RefreshEvidence*>(context);
    if (evidence == nullptr) {
        return false;
    }
    evidence->currentExperience = currentExperience;
    evidence->maximumExperience = maximumExperience;
    ++evidence->calls;
    return evidence->result;
}

std::uint32_t ReadWord(
    const std::array<std::uint8_t, PlayerBytes>& player,
    std::size_t offset) {
    std::uint32_t value = 0;
    std::memcpy(&value, player.data() + offset, sizeof(value));
    return value;
}

bool HasOnlyExperienceFieldsChanged(
    const std::array<std::uint8_t, PlayerBytes>& player,
    std::uint8_t initial) {
    for (std::size_t index = 0; index < player.size(); ++index) {
        const bool currentField =
            index >= PlayerCurrentExperienceOffset &&
            index < PlayerCurrentExperienceOffset +
                sizeof(std::uint32_t);
        const bool maximumField =
            index >= PlayerMaximumExperienceOffset &&
            index < PlayerMaximumExperienceOffset +
                sizeof(std::uint32_t);
        if (!currentField && !maximumField && player[index] != initial) {
            return false;
        }
    }
    return true;
}

void RunProjectionChecks() {
    constexpr std::uint8_t Initial = 0xA5;
    constexpr std::uint32_t Current = 0xF5D0BF67;
    constexpr std::uint32_t Maximum =
        (std::numeric_limits<std::uint32_t>::max)();
    std::array<std::uint8_t, PlayerBytes> player{};
    player.fill(Initial);
    RefreshEvidence evidence;

    Check(
        godswar::network::origin_fighter_experience_host_detail::
            ApplyProjectionForTesting(
                player.data(),
                player.size(),
                Current,
                Maximum,
                &evidence,
                CaptureRefresh),
        "full-UInt32 fighter EXP projection was rejected");
    Check(
        ReadWord(player, PlayerCurrentExperienceOffset) == Current &&
            ReadWord(player, PlayerMaximumExperienceOffset) == Maximum,
        "fighter EXP projection did not update both native cache fields");
    Check(
        evidence.calls == 1 &&
            evidence.currentExperience == Current &&
            evidence.maximumExperience == Maximum,
        "fighter EXP projection did not invoke its UI refresh exactly once");
    Check(
        HasOnlyExperienceFieldsChanged(player, Initial),
        "fighter EXP projection changed unrelated player state");

    std::array<std::uint8_t, PlayerBytes> overThreshold{};
    overThreshold.fill(Initial);
    RefreshEvidence overThresholdEvidence;
    Check(
        godswar::network::origin_fighter_experience_host_detail::
            ApplyProjectionForTesting(
                overThreshold.data(),
                overThreshold.size(),
                4'000'000'000u,
                117'174'640u,
                &overThresholdEvidence,
                CaptureRefresh) &&
            overThresholdEvidence.calls == 1 &&
            ReadWord(
                overThreshold,
                PlayerCurrentExperienceOffset) == 4'000'000'000u &&
            ReadWord(
                overThreshold,
                PlayerMaximumExperienceOffset) == 117'174'640u,
        "stored EXP above an unsealed threshold was clamped or rejected");
}

void RunProjectionRejectionChecks() {
    constexpr std::uint8_t Initial = 0x5A;
    std::array<std::uint8_t, PlayerBytes> player{};
    player.fill(Initial);
    RefreshEvidence evidence;

    Check(
        !godswar::network::origin_fighter_experience_host_detail::
            ApplyProjectionForTesting(
                nullptr,
                player.size(),
                7,
                11,
                &evidence,
                CaptureRefresh),
        "null player was accepted for fighter EXP projection");
    Check(
        !godswar::network::origin_fighter_experience_host_detail::
            ApplyProjectionForTesting(
                player.data(),
                player.size() - 1,
                7,
                11,
                &evidence,
                CaptureRefresh),
        "undersized player state was accepted for fighter EXP projection");
    Check(
        !godswar::network::origin_fighter_experience_host_detail::
            ApplyProjectionForTesting(
                player.data(),
                player.size(),
                7,
                0,
                &evidence,
                CaptureRefresh),
        "zero fighter EXP denominator was accepted");
    Check(
        !godswar::network::origin_fighter_experience_host_detail::
            ApplyProjectionForTesting(
                player.data(),
                player.size(),
                7,
                11,
                &evidence,
                nullptr),
        "missing fighter EXP UI refresh was accepted");
    Check(
        evidence.calls == 0 &&
            HasOnlyExperienceFieldsChanged(player, Initial) &&
            ReadWord(player, PlayerCurrentExperienceOffset) ==
                0x5A5A5A5Au &&
            ReadWord(player, PlayerMaximumExperienceOffset) ==
                0x5A5A5A5Au,
        "rejected fighter EXP projection mutated native state");
}

void CopyNativeCode(
    std::array<std::uint8_t, 256>* levelUpdate,
    std::array<std::uint8_t, 64>* levelAccessor,
    std::array<std::uint8_t, 64>* personalAccessor,
    std::array<std::uint8_t, 64>* personalRefresh) {
    std::memcpy(
        levelAccessor->data(),
        LevelExperienceAccessorPrefix,
        sizeof(LevelExperienceAccessorPrefix));
    std::memcpy(
        levelUpdate->data(),
        LevelExperienceUpdatePrefix,
        sizeof(LevelExperienceUpdatePrefix));
    (*levelUpdate)[LevelExperienceUpdateReturnOffset] = 0xC2;
    (*levelUpdate)[LevelExperienceUpdateReturnOffset + 1] = 0x04;
    (*levelUpdate)[LevelExperienceUpdateReturnOffset + 2] = 0x00;
    std::memcpy(
        personalAccessor->data(),
        PersonalInfoAccessorPrefix,
        sizeof(PersonalInfoAccessorPrefix));
    std::memcpy(
        personalRefresh->data(),
        PersonalInfoRefreshPrefix,
        sizeof(PersonalInfoRefreshPrefix));
}

bool HasExpectedNativeCode(
    const std::array<std::uint8_t, 256>& levelUpdate,
    const std::array<std::uint8_t, 64>& levelAccessor,
    const std::array<std::uint8_t, 64>& personalAccessor,
    const std::array<std::uint8_t, 64>& personalRefresh) {
    return godswar::network::origin_fighter_experience_host_detail::
        HasExpectedNativeCodeForTesting(
            levelAccessor.data(),
            levelAccessor.size(),
            levelUpdate.data(),
            levelUpdate.size(),
            personalAccessor.data(),
            personalAccessor.size(),
            personalRefresh.data(),
            personalRefresh.size());
}

void RunNativeSignatureChecks() {
    std::array<std::uint8_t, 256> levelUpdate{};
    std::array<std::uint8_t, 64> levelAccessor{};
    std::array<std::uint8_t, 64> personalAccessor{};
    std::array<std::uint8_t, 64> personalRefresh{};
    CopyNativeCode(
        &levelUpdate,
        &levelAccessor,
        &personalAccessor,
        &personalRefresh);

    Check(
        HasExpectedNativeCode(
            levelUpdate,
            levelAccessor,
            personalAccessor,
            personalRefresh),
        "exact pinned Origin fighter EXP native code was rejected");

    levelUpdate[LevelExperienceUpdateReturnOffset + 1] = 0;
    Check(
        !HasExpectedNativeCode(
            levelUpdate,
            levelAccessor,
            personalAccessor,
            personalRefresh),
        "CLevelExp updater without ret-4 ABI was accepted");
    levelUpdate[LevelExperienceUpdateReturnOffset + 1] = 0x04;

    personalRefresh[6] ^= 0x01;
    Check(
        !HasExpectedNativeCode(
            levelUpdate,
            levelAccessor,
            personalAccessor,
            personalRefresh),
        "mismatched PersonalInfo refresh prologue was accepted");
    personalRefresh[6] ^= 0x01;

    Check(
        !godswar::network::origin_fighter_experience_host_detail::
            HasExpectedNativeCodeForTesting(
                levelAccessor.data(),
                levelAccessor.size(),
                levelUpdate.data(),
                LevelExperienceUpdateReturnOffset + 2,
                personalAccessor.data(),
                personalAccessor.size(),
                personalRefresh.data(),
                personalRefresh.size()),
        "truncated CLevelExp updater was accepted");
}

void RunUnsupportedHostCheck() {
    godswar::network::OriginFighterExperienceHost host;
    Check(
        !host.IsSupported(),
        "native test executable was accepted as a supported Origin host");
    Check(
        !host.Apply(73, 117'174'640u),
        "native test executable was accepted as the pinned Origin host");
}

} // namespace

int RunOriginFighterExperienceHostTests() {
    Failures = 0;
    RunProjectionChecks();
    RunProjectionRejectionChecks();
    RunNativeSignatureChecks();
    RunUnsupportedHostCheck();
    return Failures;
}
