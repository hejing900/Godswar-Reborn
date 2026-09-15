#include "SecureWarehouseIdentityTests.h"

int RunSecureWarehouseParserTests();
int RunSecureWarehouseRegistryTests();
int RunOriginWarehousePageHostTests();

int RunSecureWarehouseIdentityTests() {
    return RunSecureWarehouseParserTests() +
        RunSecureWarehouseRegistryTests() +
        RunOriginWarehousePageHostTests();
}
