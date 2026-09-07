#pragma once

#include <cstdint>

namespace godswar::network {

// TestWarehouseEndpointParity.ps1 checks these against the server's accepted
// endpoints. Script aliases never replace the NPC's wire interaction identity.
inline constexpr std::uint32_t AthensWarehouseNpcId = 5164;
inline constexpr std::uint32_t SpartaWarehouseNpcId = 47750;
inline constexpr std::uint32_t DuelArenaWarehouseNpcId = 5202;
inline constexpr std::uint32_t AthensManagerNpcId = 5273;
inline constexpr std::uint32_t SpartaManagerNpcId = 5131;

inline constexpr std::uint32_t WarehouseNpcIds[] = {
    AthensWarehouseNpcId, SpartaWarehouseNpcId, DuelArenaWarehouseNpcId
};
inline constexpr std::uint32_t WarehouseManagerNpcIds[] = {
    AthensManagerNpcId, SpartaManagerNpcId
};

inline bool IsWarehouseNpc(std::uint32_t npcId) noexcept {
    for (const auto candidate : WarehouseNpcIds) {
        if (candidate == npcId) {
            return true;
        }
    }
    return false;
}

inline bool IsRelatedWarehouseManager(std::uint32_t npcId) noexcept {
    for (const auto candidate : WarehouseManagerNpcIds) {
        if (candidate == npcId) {
            return true;
        }
    }
    return false;
}

} // namespace godswar::network
