#include "SecureFactionCrierCommandIdentity.h"

#include "SecureLegacyCommandIdentity.h"

namespace godswar::network {
namespace {

std::uint16_t ReadUInt16Little(
    const std::uint8_t* source) noexcept {
    return static_cast<std::uint16_t>(
        source[0] |
        (static_cast<std::uint16_t>(source[1]) << 8U));
}

std::uint32_t ReadUInt32Little(
    const std::uint8_t* source) noexcept {
    return source[0] |
        (static_cast<std::uint32_t>(source[1]) << 8U) |
        (static_cast<std::uint32_t>(source[2]) << 16U) |
        (static_cast<std::uint32_t>(source[3]) << 24U);
}

bool IsFactionCrierNpc(std::uint32_t npcId) noexcept {
    return npcId == LegacyAthensFactionCrierNpc ||
        npcId == LegacyPublishedSpartaFactionCrierNpc ||
        npcId == LegacySourceSpartaFactionCrierNpc;
}

bool HasExactPath(
    const std::int32_t* arguments,
    const std::int32_t* path,
    std::size_t pathCount) noexcept {
    if (arguments == nullptr ||
        pathCount > LegacyFactionCrierArgumentCount) {
        return false;
    }
    for (std::size_t index = 0;
         index < LegacyFactionCrierArgumentCount;
         ++index) {
        const auto expected = index < pathCount
            ? path[index]
            : -1;
        if (arguments[index] != expected) {
            return false;
        }
    }
    return true;
}

bool HasNoArguments(const std::int32_t* arguments) noexcept {
    return HasExactPath(arguments, nullptr, 0);
}

bool IsExactNavigation(
    std::int32_t rootSubId,
    const std::int32_t* arguments) noexcept {
    if (rootSubId == -1 && HasNoArguments(arguments)) {
        return true;
    }
    if ((rootSubId == 2 || rootSubId == 3 || rootSubId == 4) &&
        HasNoArguments(arguments)) {
        return true;
    }
    if (rootSubId != 2) {
        return false;
    }

    const std::int32_t one[]{10};
    const std::int32_t many[]{20};
    const std::int32_t odd[]{20, 107};
    const std::int32_t even[]{20, 108};
    const std::int32_t all[]{20, 109};
    return HasExactPath(arguments, one, 1) ||
        HasExactPath(arguments, many, 1) ||
        HasExactPath(arguments, odd, 2) ||
        HasExactPath(arguments, even, 2) ||
        HasExactPath(arguments, all, 2);
}

bool TryDecodeItemCoordinate(
    std::int32_t coordinate,
    int* kitBagSlot) noexcept {
    if (coordinate < 0 || kitBagSlot == nullptr) {
        return false;
    }
    const auto page = coordinate / 100;
    const auto pageSlot = coordinate % 100;
    if (page < 0 || page >= LegacyFactionCrierBagPageCount ||
        pageSlot < 0 ||
        pageSlot >= LegacyFactionCrierBagSlotsPerPage) {
        return false;
    }
    *kitBagSlot = static_cast<int>(
        page * LegacyFactionCrierBagSlotsPerPage + pageSlot);
    return true;
}

bool HasRenewalShape(
    const std::int32_t* arguments) noexcept {
    if (arguments == nullptr ||
        arguments[0] < 41 || arguments[0] > 46) {
        return false;
    }
    for (std::size_t index = 0;
         index < LegacyFactionCrierArgumentCount;
         ++index) {
        const bool allowed = index == 0 ||
            index == LegacyFactionCrierItemArgument ||
            (index >= LegacyFactionCrierFirstScratchArgument &&
                index <= LegacyFactionCrierLastScratchArgument);
        if (!allowed && arguments[index] != -1) {
            return false;
        }
    }
    return true;
}

bool TryReadOffer(
    LegacyFactionCrierNameplateSet set,
    std::int32_t actionSubId,
    LegacyFactionCrierRewardKind* reward,
    LegacyFactionCrierCurrency* currency,
    int* multiplier) noexcept {
    if (reward == nullptr || currency == nullptr ||
        multiplier == nullptr) {
        return false;
    }
    if (set == LegacyFactionCrierNameplateSet::AllSix) {
        *reward = LegacyFactionCrierRewardKind::
            ExperienceAndTalentPoints;
        switch (actionSubId) {
            case 130:
                *currency = LegacyFactionCrierCurrency::Silver;
                *multiplier = 12;
                return true;
            case 131:
                *currency = LegacyFactionCrierCurrency::BindingGold;
                *multiplier = 18;
                return true;
            case 132:
                *currency = LegacyFactionCrierCurrency::Gold;
                *multiplier = 18;
                return true;
            case 133:
                *currency = LegacyFactionCrierCurrency::BindingGold;
                *multiplier = 24;
                return true;
            case 134:
                *currency = LegacyFactionCrierCurrency::Gold;
                *multiplier = 24;
                return true;
            default:
                return false;
        }
    }

    const int firstSubId =
        set == LegacyFactionCrierNameplateSet::OddTriple
        ? 110
        : set == LegacyFactionCrierNameplateSet::EvenTriple
            ? 120
            : -1;
    const int option = actionSubId - firstSubId;
    if (firstSubId < 0 || option < 0 || option > 9) {
        return false;
    }
    *reward = option % 2 == 0
        ? LegacyFactionCrierRewardKind::Experience
        : LegacyFactionCrierRewardKind::TalentPoints;
    switch (option / 2) {
        case 0:
            *currency = LegacyFactionCrierCurrency::Silver;
            *multiplier = 6;
            return true;
        case 1:
            *currency = LegacyFactionCrierCurrency::BindingGold;
            *multiplier = 9;
            return true;
        case 2:
            *currency = LegacyFactionCrierCurrency::Gold;
            *multiplier = 9;
            return true;
        case 3:
            *currency = LegacyFactionCrierCurrency::BindingGold;
            *multiplier = 12;
            return true;
        case 4:
            *currency = LegacyFactionCrierCurrency::Gold;
            *multiplier = 12;
            return true;
        default:
            return false;
    }
}

bool TryReadMutation(
    std::uint32_t npcId,
    std::int32_t rootSubId,
    const std::int32_t* arguments,
    LegacyFactionCrierCommand* command) noexcept {
    LegacyFactionCrierCommand parsed{};
    parsed.npcId = npcId;

    if (rootSubId == 1 && HasNoArguments(arguments)) {
        parsed.operation = LegacyFactionCrierOperation::DailyClaim;
        parsed.actionSubId = 1;
        if (command != nullptr) {
            *command = parsed;
        }
        return true;
    }

    if (rootSubId == 3 &&
        arguments[0] >= 31 && arguments[0] <= 36) {
        const std::int32_t path[]{arguments[0]};
        if (HasExactPath(arguments, path, 1)) {
            parsed.operation =
                LegacyFactionCrierOperation::WeeklyReclaim;
            parsed.actionSubId = arguments[0];
            parsed.nameplateOrdinal = arguments[0] - 30;
            parsed.paymentCurrency = LegacyFactionCrierCurrency::Gold;
            if (command != nullptr) {
                *command = parsed;
            }
            return true;
        }
    }

    if (rootSubId == 4 && HasRenewalShape(arguments)) {
        int sourceKitBagSlot = -1;
        if (TryDecodeItemCoordinate(
                arguments[LegacyFactionCrierItemArgument],
                &sourceKitBagSlot)) {
            parsed.operation =
                LegacyFactionCrierOperation::RenewNameplate;
            parsed.actionSubId = arguments[0];
            parsed.nameplateOrdinal = arguments[0] - 40;
            parsed.paymentCurrency = LegacyFactionCrierCurrency::Gold;
            parsed.sourceKitBagSlot = sourceKitBagSlot;
            if (command != nullptr) {
                *command = parsed;
            }
            return true;
        }
    }

    if (rootSubId == 2 && arguments[0] == 10 &&
        arguments[1] >= 101 && arguments[1] <= 106) {
        const std::int32_t path[]{10, arguments[1]};
        if (HasExactPath(arguments, path, 2)) {
            parsed.operation =
                LegacyFactionCrierOperation::TurnInNameplates;
            parsed.actionSubId = arguments[1];
            parsed.nameplateOrdinal = arguments[1] - 100;
            parsed.nameplateSet = LegacyFactionCrierNameplateSet::Single;
            parsed.rewardKind = LegacyFactionCrierRewardKind::Experience;
            parsed.rewardMultiplier = 1;
            if (command != nullptr) {
                *command = parsed;
            }
            return true;
        }
    }

    if (rootSubId != 2 || arguments[0] != 20) {
        return false;
    }
    const auto set = arguments[1] == 107
        ? LegacyFactionCrierNameplateSet::OddTriple
        : arguments[1] == 108
            ? LegacyFactionCrierNameplateSet::EvenTriple
            : arguments[1] == 109
                ? LegacyFactionCrierNameplateSet::AllSix
                : LegacyFactionCrierNameplateSet::None;
    const std::int32_t path[]{20, arguments[1], arguments[2]};
    LegacyFactionCrierRewardKind reward{};
    LegacyFactionCrierCurrency currency{};
    int multiplier = 0;
    if (set == LegacyFactionCrierNameplateSet::None ||
        !HasExactPath(arguments, path, 3) ||
        !TryReadOffer(
            set,
            arguments[2],
            &reward,
            &currency,
            &multiplier)) {
        return false;
    }

    parsed.operation = LegacyFactionCrierOperation::TurnInNameplates;
    parsed.actionSubId = arguments[2];
    parsed.nameplateSet = set;
    parsed.rewardKind = reward;
    parsed.paymentCurrency = currency;
    parsed.rewardMultiplier = multiplier;
    if (command != nullptr) {
        *command = parsed;
    }
    return true;
}

} // namespace

LegacyFactionCrierPacketKind ClassifyLegacyFactionCrierPacket(
    const void* packet,
    std::size_t packetBytes,
    LegacyFactionCrierCommand* command) noexcept {
    if (packet == nullptr || packetBytes < 12) {
        return LegacyFactionCrierPacketKind::Unrelated;
    }

    const auto* bytes = static_cast<const std::uint8_t*>(packet);
    const auto opcode = ReadUInt16Little(bytes + 2);
    const auto npcId = ReadUInt32Little(bytes + 4);
    const auto dialog = static_cast<std::int32_t>(
        ReadUInt32Little(bytes + 8));
    if (opcode != LegacyNpcFunctionActionOpcode ||
        !IsFactionCrierNpc(npcId) ||
        dialog != LegacyFactionCrierDialog) {
        return LegacyFactionCrierPacketKind::Unrelated;
    }

    std::uint16_t parsedOpcode = 0;
    if (packetBytes != LegacyFactionCrierActionPacketBytes ||
        !TryReadLegacyPacketHeader(
            packet, packetBytes, &parsedOpcode) ||
        parsedOpcode != LegacyNpcFunctionActionOpcode) {
        return LegacyFactionCrierPacketKind::InvalidMutation;
    }

    const auto duplicateDialog = static_cast<std::int32_t>(
        ReadUInt32Little(bytes + 12));
    const auto rootSubId = static_cast<std::int32_t>(
        ReadUInt32Little(bytes + 16));
    if (duplicateDialog != LegacyFactionCrierDialog) {
        return LegacyFactionCrierPacketKind::InvalidMutation;
    }

    std::int32_t arguments[LegacyFactionCrierArgumentCount]{};
    for (std::size_t index = 0;
         index < LegacyFactionCrierArgumentCount;
         ++index) {
        arguments[index] = static_cast<std::int32_t>(
            ReadUInt32Little(bytes + 20 + index * 4));
    }

    if (TryReadMutation(npcId, rootSubId, arguments, command)) {
        return LegacyFactionCrierPacketKind::Commit;
    }
    if (IsExactNavigation(rootSubId, arguments) ||
        (rootSubId == 4 &&
            HasRenewalShape(arguments) &&
            arguments[LegacyFactionCrierItemArgument] == -1)) {
        return LegacyFactionCrierPacketKind::Navigation;
    }

    if (rootSubId == 1 || rootSubId == 2 ||
        rootSubId == 3 || rootSubId == 4) {
        return LegacyFactionCrierPacketKind::InvalidMutation;
    }
    return LegacyFactionCrierPacketKind::Unrelated;
}

bool TryReadLegacyFactionCrierCommand(
    const void* packet,
    std::size_t packetBytes,
    LegacyFactionCrierCommand* command) noexcept {
    return command != nullptr &&
        ClassifyLegacyFactionCrierPacket(
            packet, packetBytes, command) ==
            LegacyFactionCrierPacketKind::Commit;
}

} // namespace godswar::network
