# Title bracket color correction — 13 September 2026

The previous display-bracket patch formatted colored names as `[|cffCOLORName|cFFFFFFFF]`. This placed the opening bracket before the title color and the closing bracket after the white reset. Both brackets now belong to the title's existing color span: `|cffCOLOR[Name]|cFFFFFFFF`. The raw title catalogue remains bracket-free, so the character title list still shows plain names with their existing colors.

The display wrapper calls the original bounded formatter and rotates the two brackets inside a complete color span. It preserves the return length, stack, nonvolatile registers, input title string, terminating NUL and output length. Ordinary names retain stock formatting. The existing width helper again detects markup at the first byte and excludes the same 20 formatting bytes from visible width.

The wrapper occupies the verified, retired 128-byte character-speed cave; its old hook must be disabled and native boundaries must match. The title installer rejects foreign references, occupied or partial cave states and unknown executable layouts. The character-speed maintenance tool recognizes only the complete coupled title patch and preserves it through its own operations; six partial-state checks and the old speed migration remain covered.

An independent Unicorn x86 audit executes the actual wrapper and stock format adapter, substituting only the CRT bounded-format primitive. The previous executable fails the bracket-color assertion. The planned correction passes all 192 title rows across both installed locales, including 28 colored rows and 576 inherited-color cases. Every bracket and title glyph has the intended color, and the reset does not leak into following text. This is native instruction and color-markup validation, not an interactive rendering observation.

Validation passed: 9 title patch fixtures, 12 palette fixtures, the historical Medusa patch fixture, 2,004 character-display regression assertions, and the focused shared-cave preservation/rejection checks. Forward-title, Medusa, character-speed and palette installed readbacks also passed. The independent x86/glyph-color audit passed again against the installed executable.

The transaction changed only `C:\Godswar Origin\Origin.exe`; both name catalogues and both description catalogues remained byte-identical. Installed SHA256: `42C8BA150871FF07C325A742CF84F09468CD8EA1F24B747B1C32D791D809A4D6`. Verified backup manifest: `C:\Godswar Origin\backups\title-display-brackets\20260912-230724-06a71aadb5154a259d3581e3895c7e07\manifest.json`.

Evidence: `artifacts/wonderland-title-bracket-colors-20260913`. The client was independently confirmed closed before installation. Reopen it to load the corrected formatter; no server restart was required or performed.
