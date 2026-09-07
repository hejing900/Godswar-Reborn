#include "OriginWarehousePageUi.h"
#include "OriginWarehousePageHost.h"

namespace godswar::network {
namespace {

class OriginWarehousePageUi final : public WarehousePageUi {
public:
    bool IsAvailable() noexcept override {
        return warehouse_page_host_detail::EnsureRuntimePatched();
    }
    bool ReadSelectedPage(int* page) noexcept override {
        return warehouse_page_host_detail::TryReadSelectedPage(page);
    }
    bool SelectPage(int page) noexcept override {
        return warehouse_page_host_detail::TrySelectPage(page);
    }
    bool ClearStorageChunk(int firstSlot, int slotCount) noexcept override {
        return warehouse_page_host_detail::TryClearProjectedStorageChunk(
            firstSlot, slotCount);
    }
    bool ShowEmptyStoragePage() noexcept override {
        return warehouse_page_host_detail::TryShowEmptyProjectedStoragePage();
    }
    bool IsDragActive() noexcept override {
        return warehouse_page_host_detail::IsWarehouseDragActive();
    }
};

} // namespace

WarehousePageUi& GetOriginWarehousePageUi() noexcept {
    static OriginWarehousePageUi ui;
    return ui;
}

} // namespace godswar::network
