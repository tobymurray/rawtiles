"""neg-32 cluster — § 12 #8 / § 11 #32 per-tile placement (gap / overlap).

§ 11 #32: "For each tile-index entry i, reject the pack if
`offset(i) ≠ tile_blob_start + Σ padded_length(j) for j < i`."
The rule pins the layout tiles must take in the blob: consecutive,
4-aligned, no gaps and no overlaps.

Two sub-fixtures derived from golden-grid (16 tiles at z=2, each 64 bytes,
all `padded_length = 64`):

  - (a) gap: entry 1's `offset` is bumped 676 → 680, leaving a 4-byte gap
    between tile 0's end (byte 676) and tile 1's declared start (byte 680).
    Subsequent entries are untouched, so entry 1's offset alone is
    inconsistent with the expected position. The 4 stranded bytes at
    676..680 are inside the tile blob (not the extension section) so
    rule #19c doesn't fire.

  - (b) overlap: entry 1's `offset` is decremented 676 → 672, declaring
    tile 1's start 4 bytes BEFORE tile 0's end. The two tiles' declared
    ranges overlap by 4 bytes.

In both cases, entry 1's `length` is unchanged at 64. Bounds checks
(#14a/b/c/d) all hold:
  - alignment: 680 and 672 are both 4-aligned (#14a quiet);
  - offset > tile_blob_start = 612 (#14b quiet);
  - offset + length = 744 or 736 ≤ extensions_offset = 1636 (#14c, #14d quiet).

Tile-index entry 1's `offset` field is the u32 LE at file bytes 324..328
(entry 1 starts at byte 312; the offset field sits at byte 12 of the
20-byte entry per § 5.1).
"""

from __future__ import annotations

import struct

from . import _lib, golden_grid

_ENTRY_1_OFFSET_ADDR = 292 + 1 * 20 + 12                       # 324


def _mutate_gap(buf: bytearray) -> None:
    # Tile 1 claims to start 4 bytes later than the contiguous-pack expectation.
    struct.pack_into("<I", buf, _ENTRY_1_OFFSET_ADDR, 680)     # was 676


def _mutate_overlap(buf: bytearray) -> None:
    # Tile 1 claims to start 4 bytes BEFORE tile 0 finishes (672 = 676 − 4).
    struct.pack_into("<I", buf, _ENTRY_1_OFFSET_ADDR, 672)     # was 676


_RULE_32_SUMMARY = (
    "for each tile-index entry i, offset(i) MUST equal tile_blob_start + "
    "Σ padded_length(j) for j < i; tiles MUST sit consecutively in the "
    "blob with no gap and no overlap (§ 12 #8 + § 11 #32)"
)


FIXTURES = [
    _lib.mutate_style_negative(
        name="neg-32a-tile-gap",
        mutate=_mutate_gap,
        description=(
            "Pack derived from golden-grid with entry 1's `offset` field "
            "bumped 676 → 680, leaving a 4-byte gap between tile 0 (612..676) "
            "and tile 1 (now 680..744). Subsequent entries' offsets are "
            "untouched, so entry 1 alone is misplaced. CRC recomputed."
        ),
        mutation=f"file[{_ENTRY_1_OFFSET_ADDR}..{_ENTRY_1_OFFSET_ADDR+4}] (entry 1 `offset`, u32 LE) 676 → 680; CRC recomputed.",
        spec_refs=["§ 12.1"],
        rule_number="32",
        rule_summary=_RULE_32_SUMMARY,
        derived_from="golden-grid",
        base_module=golden_grid,
    ),
    _lib.mutate_style_negative(
        name="neg-32b-tile-overlap",
        mutate=_mutate_overlap,
        description=(
            "Pack derived from golden-grid with entry 1's `offset` field "
            "decremented 676 → 672, so tile 1's declared range (672..736) "
            "overlaps tile 0 (612..676) by 4 bytes. CRC recomputed."
        ),
        mutation=f"file[{_ENTRY_1_OFFSET_ADDR}..{_ENTRY_1_OFFSET_ADDR+4}] (entry 1 `offset`, u32 LE) 676 → 672; CRC recomputed.",
        spec_refs=["§ 12.1"],
        rule_number="32",
        rule_summary=_RULE_32_SUMMARY,
        derived_from="golden-grid",
        base_module=golden_grid,
    ),
]
