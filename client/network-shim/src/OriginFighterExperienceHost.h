#pragma once

#include <cstddef>
#include <cstdint>

namespace godswar::network {

class OriginFighterExperienceHost final {
public:
    bool IsSupported() const noexcept;
    bool Apply(
        std::uint32_t currentExperience,
        std::uint32_t maximumExperience) noexcept;
};

namespace origin_fighter_experience_host_detail {

using UiRefreshInvoker = bool (*)(
    void* context,
    std::uint32_t currentExperience,
    std::uint32_t maximumExperience) noexcept;

bool ApplyProjectionForTesting(
    void* player,
    std::size_t playerBytes,
    std::uint32_t currentExperience,
    std::uint32_t maximumExperience,
    void* context,
    UiRefreshInvoker refresh) noexcept;

bool HasExpectedNativeCodeForTesting(
    const void* levelExperienceAccessor,
    std::size_t levelExperienceAccessorBytes,
    const void* levelExperienceUpdate,
    std::size_t levelExperienceUpdateBytes,
    const void* personalInfoAccessor,
    std::size_t personalInfoAccessorBytes,
    const void* personalInfoRefresh,
    std::size_t personalInfoRefreshBytes) noexcept;

} // namespace origin_fighter_experience_host_detail

} // namespace godswar::network
