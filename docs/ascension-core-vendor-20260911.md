# Ascension Core vendor listing

The Bound Gold Vendor's Holy Suit tab sells item 9025, Ascension Core, for
50,000 B-Gold per unit. It follows Holy Box V as the final listing, with a
single-piece default quantity. Other item positions and prices are preserved.
The tab has 20 listings, within the native 45-slot capacity.

Purchased cores use the same bound identity, stack cap of 99 and Holy Suit
upgrade behavior as EXP-created cores. EXP conversion remains available.
There is no item-content revision, client asset change or schema migration.

Verification covers catalog order, price, currency, item-definition loadability,
real one- and two-core purchases, a 100-core purchase split into 99+1 stacks,
and consumption of purchased cores in a RuneSteel upgrade with duplicate
receipt replay. Evidence is under `artifacts/ascension-core-vendor-20260911/`.

Release build completed without warnings or errors. The vendor protocol check
and the PostgreSQL capital-shop suite passed with no failures or skips. The
existing Ascension Core artwork and Divinium native-container fix verify.

Deployed image:
`sha256:5c83f68cae11d0a1b35395622c24043337ae2979040be2e55b0c32f9d05be9d2`.
Tempest is healthy with zero restarts. Database publication, policies and owned
inventory match the stopped pre-deployment snapshot; stack isolation passes.
The previous image is retained as
`reborn-server:before-ascension-core-vendor-20260911`.
