#include "SecureFighterLevelSealIdentityTests.h"

int RunSecureFighterLevelSealParserTests();
int RunSecureFighterLevelSealRegistryTests();

int RunSecureFighterLevelSealIdentityTests() {
    return RunSecureFighterLevelSealParserTests() +
        RunSecureFighterLevelSealRegistryTests();
}
