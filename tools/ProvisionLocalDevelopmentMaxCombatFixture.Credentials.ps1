Set-StrictMode -Version Latest

function Get-MaxFixtureTest25StockClientVerifier {
    # The stock client's 140-byte login sends lowercase MD5(password) as ASCII.
    # Keep the typed fixture password test25; protect that wire credential with
    # the same PBKDF2-SHA256 v1 policy (600,000 iterations, 16-byte salt, 32-byte key).
    # This fixed local-fixture verifier is shared by provisioning and Status.
    return 'gws$pbkdf2-sha256$v1$600000$' +
        '3EIgjUktl5sFyy2YYK3ynQ==$' +
        'cYxS8TWbhyiYxFT4c9QMaCOMp5sBiNCNFCHQ4iRBGww='
}
