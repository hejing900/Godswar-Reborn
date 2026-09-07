#include "SecurePendingOperationRegistry.h"

namespace godswar::network {

bool SecurePendingOperationRegistry::
TryTakeFighterExperienceProjection(
    SecureFighterExperienceProjection* projection) noexcept {
    if (projection == nullptr) {
        return false;
    }
    *projection = SecureFighterExperienceProjection{};
    AcquireSRWLockExclusive(&lock_);
    if (fighterExperienceProjectionCount_ == 0) {
        ReleaseSRWLockExclusive(&lock_);
        return false;
    }
    *projection = fighterExperienceProjections_[
        fighterExperienceProjectionHead_];
    fighterExperienceProjections_[
        fighterExperienceProjectionHead_] =
            SecureFighterExperienceProjection{};
    fighterExperienceProjectionHead_ =
        (fighterExperienceProjectionHead_ + 1) %
            SecureFighterExperienceProjectionCapacity;
    --fighterExperienceProjectionCount_;
    ReleaseSRWLockExclusive(&lock_);
    return true;
}

bool SecurePendingOperationRegistry::
CanPublishFighterExperienceProjection() const noexcept {
    return fighterExperienceProjectionCount_ <
        SecureFighterExperienceProjectionCapacity;
}

void SecurePendingOperationRegistry::
PublishFighterExperienceProjection(
    const SecureLegacyCommandResult& result) noexcept {
    const std::size_t index =
        (fighterExperienceProjectionHead_ +
         fighterExperienceProjectionCount_) %
            SecureFighterExperienceProjectionCapacity;
    fighterExperienceProjections_[index] = {
        result.currentExperience,
        result.maximumExperience,
        result.inventoryRevision};
    ++fighterExperienceProjectionCount_;
}

void SecurePendingOperationRegistry::
ClearFighterExperienceProjections() noexcept {
    SecureZeroMemory(
        fighterExperienceProjections_,
        sizeof(fighterExperienceProjections_));
    fighterExperienceProjectionHead_ = 0;
    fighterExperienceProjectionCount_ = 0;
}

} // namespace godswar::network
