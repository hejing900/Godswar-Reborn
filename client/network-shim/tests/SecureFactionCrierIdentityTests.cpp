#include "SecureFactionCrierIdentityTests.h"

int RunSecureFactionCrierParserTests();
int RunSecureFactionCrierRegistryTests();

int RunSecureFactionCrierIdentityTests() {
    return RunSecureFactionCrierParserTests() +
        RunSecureFactionCrierRegistryTests();
}
