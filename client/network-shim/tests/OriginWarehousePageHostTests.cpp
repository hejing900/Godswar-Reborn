#include "SecureWarehouseTestSupport.h"
#include "../src/OriginWarehousePageHost.h"
#include "../src/OriginWarehousePageUi.h"

#include <initializer_list>

namespace {

using namespace warehouse_test;

class FakePageUi final : public WarehousePageUi {
public:
    bool available = true;
    bool dragging = false;
    int page = 0;
    int clearedChunks = 0;
    int emptyPages = 0;

    bool IsAvailable() noexcept override { return available; }
    bool ReadSelectedPage(int* selected) noexcept override {
        *selected = page;
        return true;
    }
    bool SelectPage(int selected) noexcept override {
        page = selected;
        return true;
    }
    bool ClearStorageChunk(int firstSlot, int slotCount) noexcept override {
        if (firstSlot != 36 || slotCount != 4) {
            return false;
        }
        ++clearedChunks;
        return true;
    }
    bool ShowEmptyStoragePage() noexcept override {
        ++emptyPages;
        return true;
    }
    bool IsDragActive() noexcept override { return dragging; }
};

void ObserveOpen(OriginWarehousePageHost* host, std::uint32_t npcId,
                 std::uint16_t opcode = 10068) {
    std::uint8_t packet[8]{};
    Write16(packet, sizeof(packet));
    Write16(packet + 2, opcode);
    Write32(packet + 4, npcId);
    host->ObserveClientPacket(packet, sizeof(packet));
}

void ObserveSnapshot(OriginWarehousePageHost* host, int page) {
    // Native message prefix is a vtable pointer, followed by a real 24B header.
    std::uint8_t message[sizeof(void*) + 24]{};
    auto* packet = message + sizeof(void*);
    Write16(packet, 24);
    Write16(packet + 2, 10034);
    Write32(packet + 8, 0x57485090U + static_cast<std::uint32_t>(page));
    Write16(packet + 12, 40);
    packet[14] = 6;
    host->ObserveServerMessage(message);
}

bool IsPageRequest(const std::uint8_t* packet, int size,
                   std::uint32_t npcId, int page) {
    std::uint8_t expected[12]{};
    Write16(expected, 12);
    Write16(expected + 2, 10068);
    Write32(expected + 4, npcId);
    Write32(expected + 8, static_cast<std::uint32_t>(page));
    return size == static_cast<int>(sizeof(expected)) &&
        std::memcmp(packet, expected, sizeof(expected)) == 0;
}

void CheckEndpoint(Checks* checks, std::uint32_t npcId) {
    FakePageUi ui;
    OriginWarehousePageHost host(ui);
    std::uint8_t request[12]{};
    int requestBytes = 0;
    ObserveOpen(&host, npcId);
    ObserveSnapshot(&host, 0);
    checks->Require(
        !host.TryBuildPageRequest(request, sizeof(request), &requestBytes) &&
        ui.clearedChunks == 1,
        "warehouse initial snapshot did not establish native page context");

    ui.page = 8;
    checks->Require(
        host.TryBuildPageRequest(request, sizeof(request), &requestBytes) &&
        IsPageRequest(request, requestBytes, npcId, 8),
        "warehouse ninth-tab request lost its NPC identity or logical page");
    host.CompletePageRequestSend(false);
    checks->Require(
        host.TryBuildPageRequest(request, sizeof(request), &requestBytes) &&
        IsPageRequest(request, requestBytes, npcId, 8),
        "warehouse failed page send could not be retried");
    host.CompletePageRequestSend(true);
    checks->Require(
        !host.TryBuildPageRequest(request, sizeof(request), &requestBytes),
        "warehouse pending page was resent before a snapshot arrived");

    ObserveSnapshot(&host, 8);
    ui.page = 0; // Stock snapshot processing selects the first physical tab.
    checks->Require(
        !host.TryBuildPageRequest(request, sizeof(request), &requestBytes) &&
        ui.page == 8 && ui.clearedChunks == 2,
        "warehouse snapshot did not restore the selected logical tab");

    std::uint8_t transfer[20]{};
    std::uint8_t rewritten[20]{};
    LegacyWarehouseTransferCommand command{};
    BuildTransferPacket(transfer, 39, 2, 5, 1);
    checks->Require(
        host.TryRewriteClientPacket(transfer, sizeof(transfer),
                                    rewritten, sizeof(rewritten)) &&
        ClassifyLegacyWarehouseTransferPacket(
            rewritten, sizeof(rewritten), &command) ==
                LegacyWarehousePacketKind::Transfer &&
        command.warehouseSlot == 359 && command.kitBagSlot == 53,
        "warehouse endpoint deposit bypassed logical-page translation");

    ui.dragging = true;
    ui.page = 2;
    checks->Require(
        host.TryBuildPageRequest(request, sizeof(request), &requestBytes) &&
        IsPageRequest(request, requestBytes, npcId, 2),
        "warehouse drag did not request its destination page");
    BuildTransferPacket(transfer, 5, 9, -1, 0, 0, 1);
    checks->Require(
        host.TryRewriteClientPacket(transfer, sizeof(transfer),
                                    rewritten, sizeof(rewritten)) &&
        ClassifyLegacyWarehouseTransferPacket(
            rewritten, sizeof(rewritten), &command) ==
                LegacyWarehousePacketKind::Transfer &&
        command.warehouseSlot == 325 &&
        command.destinationWarehouseSlot == 89,
        "warehouse drag lost distinct source and destination logical pages");

    for (const std::uint32_t manager : {5273U, 5131U}) {
        ObserveOpen(&host, manager, 10067);
        checks->Require(host.TryRewriteClientPacket(
            transfer, sizeof(transfer), rewritten, sizeof(rewritten)),
            "related warehouse manager discarded warehouse context");
    }
    ObserveOpen(&host, 5197, 10067);
    checks->Require(
        !host.TryBuildPageRequest(request, sizeof(request), &requestBytes) &&
        !host.TryRewriteClientPacket(transfer, sizeof(transfer),
                                     rewritten, sizeof(rewritten)),
        "unrelated NPC retained warehouse page/transfer context");
}

void CheckRejectedContexts(Checks* checks) {
    for (const std::uint32_t npcId : {0U, 5201U, 5197U}) {
        FakePageUi ui;
        OriginWarehousePageHost host(ui);
        ObserveOpen(&host, npcId);
        ObserveSnapshot(&host, 0);
        ui.page = 8;
        std::uint8_t request[12]{};
        int requestBytes = 0;
        checks->Require(
            !host.TryBuildPageRequest(request, sizeof(request), &requestBytes) &&
            ui.clearedChunks == 0,
            "unknown NPC established warehouse page context");
    }
    FakePageUi ui;
    ui.available = false;
    OriginWarehousePageHost host(ui);
    ObserveOpen(&host, 5202);
    ObserveSnapshot(&host, 0);
    ui.available = true;
    ui.page = 8;
    std::uint8_t request[12]{};
    int requestBytes = 0;
    checks->Require(
        !host.TryBuildPageRequest(request, sizeof(request), &requestBytes) &&
        ui.clearedChunks == 0,
        "disabled warehouse UI accepted or later resurrected NPC context");
}

} // namespace

int RunOriginWarehousePageHostTests() {
    Checks checks;
    // Independent wire identities: capitals and captured Duel Arena Akou.
    for (const std::uint32_t npcId : {5164U, 47750U, 5202U}) {
        CheckEndpoint(&checks, npcId);
    }
    CheckRejectedContexts(&checks);
    return checks.failures;
}
