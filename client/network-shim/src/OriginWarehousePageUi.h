#pragma once

namespace godswar::network {

// Keeps the page protocol independent of executable addresses and UI memory.
class WarehousePageUi {
public:
    virtual ~WarehousePageUi() = default;
    virtual bool IsAvailable() noexcept = 0;
    virtual bool ReadSelectedPage(int* page) noexcept = 0;
    virtual bool SelectPage(int page) noexcept = 0;
    virtual bool ClearStorageChunk(int firstSlot, int slotCount) noexcept = 0;
    virtual bool ShowEmptyStoragePage() noexcept = 0;
    virtual bool IsDragActive() noexcept = 0;
};

WarehousePageUi& GetOriginWarehousePageUi() noexcept;

} // namespace godswar::network
