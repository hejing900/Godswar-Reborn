#include "OriginFighterExperienceHost.h"

#include <Windows.h>

#include <cstddef>
#include <cstdint>
#include <cstring>

namespace {

constexpr std::uintptr_t OriginImageBase = 0x00400000;
constexpr DWORD OriginTimestamp = 0x52AA79CA;
constexpr DWORD OriginImageSize = 0x011DE000;
constexpr DWORD OriginEntryPointRva = 0x003BF68D;

constexpr std::uintptr_t LocalPlayerSingletonRva = 0x01175EAC;
constexpr std::uintptr_t LevelExperienceAccessorRva = 0x0018B6A0;
constexpr std::uintptr_t LevelExperienceUpdateRva = 0x0018B900;
constexpr std::uintptr_t PersonalInfoAccessorRva = 0x001B5470;
constexpr std::uintptr_t PersonalInfoRefreshRva = 0x001B54E0;
constexpr std::size_t PlayerCurrentExperienceOffset = 0x2B4;
constexpr std::size_t PlayerMaximumExperienceOffset = 0x47C;
constexpr std::size_t LevelExperienceObjectBytes = 0x20;
constexpr std::size_t PersonalInfoObjectBytes = 0x184;
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
constexpr std::uint8_t LevelExperienceUpdateReturn[]{
    0xC2, 0x04, 0x00,
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

enum class RequiredProtection {
    Readable,
    Writable,
    Executable,
};

bool HasReadableProtection(DWORD protection) noexcept {
    if ((protection & (PAGE_GUARD | PAGE_NOACCESS)) != 0) {
        return false;
    }
    switch (protection & 0xFF) {
        case PAGE_READONLY:
        case PAGE_READWRITE:
        case PAGE_WRITECOPY:
        case PAGE_EXECUTE:
        case PAGE_EXECUTE_READ:
        case PAGE_EXECUTE_READWRITE:
        case PAGE_EXECUTE_WRITECOPY:
            return true;
        default:
            return false;
    }
}

bool HasWritableProtection(DWORD protection) noexcept {
    if ((protection & (PAGE_GUARD | PAGE_NOACCESS)) != 0) {
        return false;
    }
    switch (protection & 0xFF) {
        case PAGE_READWRITE:
        case PAGE_WRITECOPY:
        case PAGE_EXECUTE_READWRITE:
        case PAGE_EXECUTE_WRITECOPY:
            return true;
        default:
            return false;
    }
}

bool HasExecutableProtection(DWORD protection) noexcept {
    if ((protection & (PAGE_GUARD | PAGE_NOACCESS)) != 0) {
        return false;
    }
    switch (protection & 0xFF) {
        case PAGE_EXECUTE:
        case PAGE_EXECUTE_READ:
        case PAGE_EXECUTE_READWRITE:
        case PAGE_EXECUTE_WRITECOPY:
            return true;
        default:
            return false;
    }
}

bool IsRangeAccessible(
    const void* address,
    std::size_t bytes,
    RequiredProtection required) noexcept {
    if (address == nullptr || bytes == 0) {
        return false;
    }

    MEMORY_BASIC_INFORMATION memory{};
    if (VirtualQuery(address, &memory, sizeof(memory)) == 0 ||
        memory.State != MEM_COMMIT) {
        return false;
    }

    const auto start = reinterpret_cast<std::uintptr_t>(address);
    const auto regionStart =
        reinterpret_cast<std::uintptr_t>(memory.BaseAddress);
    const auto regionEnd = regionStart + memory.RegionSize;
    if (regionEnd < regionStart ||
        start < regionStart ||
        start > regionEnd ||
        bytes > regionEnd - start) {
        return false;
    }

    switch (required) {
        case RequiredProtection::Readable:
            return HasReadableProtection(memory.Protect);
        case RequiredProtection::Writable:
            return HasWritableProtection(memory.Protect);
        case RequiredProtection::Executable:
            return HasExecutableProtection(memory.Protect);
        default:
            return false;
    }
}

bool HasSupportedPeIdentity(const std::uint8_t* image) noexcept {
    if (reinterpret_cast<std::uintptr_t>(image) != OriginImageBase ||
        !IsRangeAccessible(
            image,
            sizeof(IMAGE_DOS_HEADER),
            RequiredProtection::Readable)) {
        return false;
    }

    __try {
        const auto* dos =
            reinterpret_cast<const IMAGE_DOS_HEADER*>(image);
        if (dos->e_magic != IMAGE_DOS_SIGNATURE ||
            dos->e_lfanew < static_cast<LONG>(sizeof(*dos))) {
            return false;
        }
        const auto* nt = reinterpret_cast<const IMAGE_NT_HEADERS32*>(
            image + dos->e_lfanew);
        return IsRangeAccessible(
                   nt,
                   sizeof(*nt),
                   RequiredProtection::Readable) &&
            nt->Signature == IMAGE_NT_SIGNATURE &&
            nt->FileHeader.Machine == IMAGE_FILE_MACHINE_I386 &&
            nt->FileHeader.TimeDateStamp == OriginTimestamp &&
            nt->OptionalHeader.Magic == IMAGE_NT_OPTIONAL_HDR32_MAGIC &&
            nt->OptionalHeader.ImageBase == OriginImageBase &&
            nt->OptionalHeader.SizeOfImage == OriginImageSize &&
            nt->OptionalHeader.AddressOfEntryPoint == OriginEntryPointRva;
    }
    __except (EXCEPTION_EXECUTE_HANDLER) {
        return false;
    }
}

bool HasPrefix(
    const void* bytes,
    std::size_t byteCount,
    const std::uint8_t* expected,
    std::size_t expectedBytes) noexcept {
    return bytes != nullptr &&
        expected != nullptr &&
        byteCount >= expectedBytes &&
        std::memcmp(bytes, expected, expectedBytes) == 0;
}

struct NativeRefreshContext {
    void* levelExperience = nullptr;
    void* levelExperienceUpdate = nullptr;
    void* personalInfo = nullptr;
    void* personalInfoRefresh = nullptr;
};

#if defined(_M_IX86)
__declspec(naked) void InvokeNativeLevelExperienceUpdate(
    void*,
    std::uint32_t,
    std::uint32_t,
    void*) noexcept {
    __asm {
        mov edx, dword ptr [esp + 4]
        mov eax, dword ptr [esp + 8]
        mov ecx, dword ptr [esp + 12]
        push ecx
        mov ecx, dword ptr [esp + 20]
        call ecx
        ret
    }
}

bool InvokeNativeRefresh(
    void* context,
    std::uint32_t currentExperience,
    std::uint32_t maximumExperience) noexcept {
    auto* native = static_cast<NativeRefreshContext*>(context);
    if (native == nullptr ||
        native->levelExperience == nullptr ||
        native->levelExperienceUpdate == nullptr ||
        native->personalInfo == nullptr ||
        native->personalInfoRefresh == nullptr) {
        return false;
    }

    __try {
        using PersonalInfoRefresh = void (__thiscall*)(void*);
        const auto refreshPersonalInfo =
            reinterpret_cast<PersonalInfoRefresh>(
                native->personalInfoRefresh);
        refreshPersonalInfo(native->personalInfo);
        InvokeNativeLevelExperienceUpdate(
            native->levelExperience,
            currentExperience,
            maximumExperience,
            native->levelExperienceUpdate);
        return true;
    }
    __except (EXCEPTION_EXECUTE_HANDLER) {
        return false;
    }
}
#endif

bool HasSupportedRuntimeImage(std::uint8_t* image) noexcept {
    constexpr std::size_t LevelUpdateRequiredBytes =
        LevelExperienceUpdateReturnOffset +
        sizeof(LevelExperienceUpdateReturn);
    if (!HasSupportedPeIdentity(image)) {
        return false;
    }

    auto* levelAccessor = image + LevelExperienceAccessorRva;
    auto* levelUpdate = image + LevelExperienceUpdateRva;
    auto* personalAccessor = image + PersonalInfoAccessorRva;
    auto* personalRefresh = image + PersonalInfoRefreshRva;
    return IsRangeAccessible(
               levelAccessor,
               sizeof(LevelExperienceAccessorPrefix),
               RequiredProtection::Executable) &&
        IsRangeAccessible(
            levelUpdate,
            LevelUpdateRequiredBytes,
            RequiredProtection::Executable) &&
        IsRangeAccessible(
            personalAccessor,
            sizeof(PersonalInfoAccessorPrefix),
            RequiredProtection::Executable) &&
        IsRangeAccessible(
            personalRefresh,
            sizeof(PersonalInfoRefreshPrefix),
            RequiredProtection::Executable) &&
        godswar::network::origin_fighter_experience_host_detail::
            HasExpectedNativeCodeForTesting(
                levelAccessor,
                sizeof(LevelExperienceAccessorPrefix),
                levelUpdate,
                LevelUpdateRequiredBytes,
                personalAccessor,
                sizeof(PersonalInfoAccessorPrefix),
                personalRefresh,
                sizeof(PersonalInfoRefreshPrefix));
}

} // namespace

namespace godswar::network {
namespace origin_fighter_experience_host_detail {

bool ApplyProjectionForTesting(
    void* player,
    std::size_t playerBytes,
    std::uint32_t currentExperience,
    std::uint32_t maximumExperience,
    void* context,
    UiRefreshInvoker refresh) noexcept {
    if (player == nullptr ||
        playerBytes < PlayerMaximumExperienceOffset +
            sizeof(maximumExperience) ||
        maximumExperience == 0 ||
        refresh == nullptr) {
        return false;
    }

    auto* bytes = static_cast<std::uint8_t*>(player);
    std::memcpy(
        bytes + PlayerCurrentExperienceOffset,
        &currentExperience,
        sizeof(currentExperience));
    std::memcpy(
        bytes + PlayerMaximumExperienceOffset,
        &maximumExperience,
        sizeof(maximumExperience));
    return refresh(
        context,
        currentExperience,
        maximumExperience);
}

bool HasExpectedNativeCodeForTesting(
    const void* levelExperienceAccessor,
    std::size_t levelExperienceAccessorBytes,
    const void* levelExperienceUpdate,
    std::size_t levelExperienceUpdateBytes,
    const void* personalInfoAccessor,
    std::size_t personalInfoAccessorBytes,
    const void* personalInfoRefresh,
    std::size_t personalInfoRefreshBytes) noexcept {
    if (!HasPrefix(
            levelExperienceAccessor,
            levelExperienceAccessorBytes,
            LevelExperienceAccessorPrefix,
            sizeof(LevelExperienceAccessorPrefix)) ||
        !HasPrefix(
            levelExperienceUpdate,
            levelExperienceUpdateBytes,
            LevelExperienceUpdatePrefix,
            sizeof(LevelExperienceUpdatePrefix)) ||
        !HasPrefix(
            personalInfoAccessor,
            personalInfoAccessorBytes,
            PersonalInfoAccessorPrefix,
            sizeof(PersonalInfoAccessorPrefix)) ||
        !HasPrefix(
            personalInfoRefresh,
            personalInfoRefreshBytes,
            PersonalInfoRefreshPrefix,
            sizeof(PersonalInfoRefreshPrefix)) ||
        levelExperienceUpdateBytes <
            LevelExperienceUpdateReturnOffset +
                sizeof(LevelExperienceUpdateReturn)) {
        return false;
    }

    const auto* levelUpdate =
        static_cast<const std::uint8_t*>(levelExperienceUpdate);
    return std::memcmp(
               levelUpdate + LevelExperienceUpdateReturnOffset,
               LevelExperienceUpdateReturn,
               sizeof(LevelExperienceUpdateReturn)) == 0;
}

} // namespace origin_fighter_experience_host_detail

bool OriginFighterExperienceHost::IsSupported() const noexcept {
#if !defined(_M_IX86)
    return false;
#else
    const auto module = GetModuleHandleW(nullptr);
    return module != nullptr && HasSupportedRuntimeImage(
        reinterpret_cast<std::uint8_t*>(module));
#endif
}

bool OriginFighterExperienceHost::Apply(
    std::uint32_t currentExperience,
    std::uint32_t maximumExperience) noexcept {
#if !defined(_M_IX86)
    static_cast<void>(currentExperience);
    static_cast<void>(maximumExperience);
    return false;
#else
    if (maximumExperience == 0) {
        return false;
    }

    const auto module = GetModuleHandleW(nullptr);
    auto* image = reinterpret_cast<std::uint8_t*>(module);
    if (module == nullptr || !HasSupportedRuntimeImage(image)) {
        return false;
    }

    auto* playerSlot = reinterpret_cast<void**>(
        image + LocalPlayerSingletonRva);
    if (!IsRangeAccessible(
            playerSlot,
            sizeof(*playerSlot),
            RequiredProtection::Readable)) {
        return false;
    }

    void* player = nullptr;
    __try {
        player = *playerSlot;
    }
    __except (EXCEPTION_EXECUTE_HANDLER) {
        return false;
    }
    if (player == nullptr) {
        return false;
    }

    auto* playerBytes = static_cast<std::uint8_t*>(player);
    if (!IsRangeAccessible(
            playerBytes + PlayerCurrentExperienceOffset,
            sizeof(currentExperience),
            RequiredProtection::Writable) ||
        !IsRangeAccessible(
            playerBytes + PlayerMaximumExperienceOffset,
            sizeof(maximumExperience),
            RequiredProtection::Writable)) {
        return false;
    }

    using NativeAccessor = void* (__cdecl*)();
    const auto getLevelExperience =
        reinterpret_cast<NativeAccessor>(
            image + LevelExperienceAccessorRva);
    const auto getPersonalInfo =
        reinterpret_cast<NativeAccessor>(
            image + PersonalInfoAccessorRva);
    NativeRefreshContext native{};
    __try {
        native.levelExperience = getLevelExperience();
        native.personalInfo = getPersonalInfo();
    }
    __except (EXCEPTION_EXECUTE_HANDLER) {
        return false;
    }
    if (!IsRangeAccessible(
            native.levelExperience,
            LevelExperienceObjectBytes,
            RequiredProtection::Readable) ||
        !IsRangeAccessible(
            native.personalInfo,
            PersonalInfoObjectBytes,
            RequiredProtection::Readable)) {
        return false;
    }

    native.levelExperienceUpdate =
        image + LevelExperienceUpdateRva;
    native.personalInfoRefresh = image + PersonalInfoRefreshRva;
    __try {
        return origin_fighter_experience_host_detail::
            ApplyProjectionForTesting(
                player,
                PlayerMaximumExperienceOffset +
                    sizeof(maximumExperience),
                currentExperience,
                maximumExperience,
                &native,
                InvokeNativeRefresh);
    }
    __except (EXCEPTION_EXECUTE_HANDLER) {
        return false;
    }
#endif
}

} // namespace godswar::network
