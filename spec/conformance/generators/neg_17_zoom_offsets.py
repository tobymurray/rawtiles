"""neg-17 cluster — § 4.12 zoom_offsets directory consistency, rule #17.

Three sub-fixtures, each targeting one of rule #17's three sub-conditions
(per § 11 #17):

  - (a) count mismatch: `zoom_offsets[z].count` does not equal the actual
    count of tile-index entries at z.
  - (b) offset mismatch: `zoom_offsets[z].offset` does not equal the byte
    offset of the first index entry at z (when `count > 0`).
  - (c) offset non-zero when count == 0.

Each fixture is a 4-byte little-endian u32 write to one of the eight bytes
backing a `zoom_offsets[z]` pair (offset + count, each u32 LE). The base
is chosen per sub-fixture so the mutation is the lone violation:

  - (a) golden-smallest — has a populated zoom 0 to inflate the count for.
  - (b) golden-smallest — has a populated zoom 0 whose offset can be moved.
  - (c) golden-empty-quadtree — has every zoom_offsets[z] = (0, 0), so
    setting one offset non-zero while keeping count = 0 isolates the
    non-zero-on-empty sub-condition.

`zoom_offsets[24]` layout in the header (§ 4.12): 192 bytes total starting
at file offset 96; each entry is `(offset: u32, count: u32)` for 8 bytes,
indexed by zoom z. So zoom_offsets[z] occupies file bytes `96 + z*8` ..
`96 + z*8 + 8`, with `.offset` in the low 4 bytes and `.count` in the high
4 bytes.
"""

from __future__ import annotations

import struct

from . import _lib, golden_empty_quadtree, golden_smallest

_ZOOM_OFFSETS_BASE = 96                                # § 4.12: first byte of zoom_offsets[24]


def _zoom_offset_addr(z: int) -> int:
    """File offset of zoom_offsets[z].offset (u32 LE)."""
    return _ZOOM_OFFSETS_BASE + z * 8


def _zoom_count_addr(z: int) -> int:
    """File offset of zoom_offsets[z].count (u32 LE)."""
    return _zoom_offset_addr(z) + 4


# --- (a) count mismatch -------------------------------------------------------

def _mutate_count(buf: bytearray) -> None:
    # golden-smallest has zoom_offsets[0] = (292, 1) and one actual entry at z = 0.
    # Inflate count 1 → 2 so the directory claims two z = 0 entries but only
    # one exists in the tile index.
    struct.pack_into("<I", buf, _zoom_count_addr(0), 2)


# --- (b) offset mismatch ------------------------------------------------------

def _mutate_offset(buf: bytearray) -> None:
    # golden-smallest has zoom_offsets[0].offset = 292 (first byte of the
    # tile-index region). Shift to 296: the directory now claims the first
    # z = 0 entry starts at file byte 296, but the actual entry is still
    # at byte 292. count = 1 (unchanged) is consistent with the one entry
    # present, so only the offset sub-condition fires.
    struct.pack_into("<I", buf, _zoom_offset_addr(0), 296)


# --- (c) offset non-zero when count == 0 -------------------------------------

def _mutate_nonzero_empty(buf: bytearray) -> None:
    # golden-empty-quadtree has every zoom_offsets[z] = (0, 0). Set
    # zoom_offsets[0].offset to 292 while leaving count = 0. The directory
    # entry now has offset != 0 alongside count == 0, the third sub-clause
    # of rule #17.
    struct.pack_into("<I", buf, _zoom_offset_addr(0), 292)


_RULE_17_SUMMARY = (
    "zoom_offsets[z].count MUST equal the actual count of tile-index entries "
    "at zoom z; when count > 0, .offset MUST equal the byte offset of the first "
    "such entry; when count == 0, .offset MUST be 0 (§ 4.12 + § 11 #17)"
)


FIXTURES = [
    _lib.mutate_style_negative(
        name="neg-17a-count-mismatch",
        mutate=_mutate_count,
        description=(
            "Pack with zoom_offsets[0].count = 2 but only one actual tile-index "
            "entry at zoom 0; all other fields valid; CRC recomputed."
        ),
        mutation="header[100..104] (zoom_offsets[0].count, u32 LE) 1 → 2; CRC recomputed.",
        spec_refs=["§ 4.12"],
        rule_number="17",
        rule_summary=_RULE_17_SUMMARY,
        base_module=golden_smallest,
    ),
    _lib.mutate_style_negative(
        name="neg-17b-offset-mismatch",
        mutate=_mutate_offset,
        description=(
            "Pack with zoom_offsets[0].offset = 296 but the actual first (and only) "
            "z = 0 tile-index entry starts at byte 292; count = 1 stays consistent "
            "with the one entry present, isolating the offset sub-clause; CRC recomputed."
        ),
        mutation="header[96..100] (zoom_offsets[0].offset, u32 LE) 292 → 296; CRC recomputed.",
        spec_refs=["§ 4.12"],
        rule_number="17",
        rule_summary=_RULE_17_SUMMARY,
        base_module=golden_smallest,
    ),
    _lib.mutate_style_negative(
        name="neg-17c-offset-nonzero-empty",
        mutate=_mutate_nonzero_empty,
        description=(
            "Pack derived from golden-empty-quadtree (tile_count = 0) with "
            "zoom_offsets[0].offset = 292 alongside count = 0. Rule #17's "
            "third sub-clause requires offset = 0 when count = 0; CRC recomputed."
        ),
        mutation="header[96..100] (zoom_offsets[0].offset, u32 LE) 0 → 292; CRC recomputed.",
        spec_refs=["§ 4.12"],
        rule_number="17",
        rule_summary=_RULE_17_SUMMARY,
        derived_from="golden-empty-quadtree",
        base_module=golden_empty_quadtree,
    ),
]
