"""neg-18 cluster — § 4.13 / § 11 #18 extensions_offset rules.

§ 11 #18 imposes four conditions on the header's `extensions_offset` field:

  (a) MUST be 4-byte aligned
  (b) extensions_offset ≤ file_size − 4
  (c) extensions_offset ≥ tile_blob_start
  (d) extensions_offset == tile_blob_start + Σ padded_length(i)
                          for i ∈ [0, tile_count)

Four sub-fixtures, each mutating golden-smallest's `extensions_offset`
u32 LE at file bytes 288..292.

Co-firing analysis. golden-smallest's expected extensions_offset is
exactly 376 (= 312 + 64). Any deviation breaks (d), so sub-fixtures
(a), (b), (c) inherently co-fire with (d). Isolating (a/b/c) from (d)
would require also changing the tile blob layout (a reshape this
cluster intentionally avoids). Sub-fixture (d) is the only cleanly-
isolated value: pick an aligned offset inside [tile_blob_start,
file_size − 4] that isn't 376.

Header layout (§ 4):
  - byte 88..92:  tile_count (u32 LE) = 1
  - byte 288..292: extensions_offset (u32 LE)

golden-smallest reference points:
  - tile_blob_start = 312
  - file_size = 380, so file_size − 4 = 376
  - Σ padded_length = 64
  - canonical extensions_offset = 376
"""

from __future__ import annotations

import struct

from . import _lib, golden_smallest

_EXT_OFFSET_ADDR = 288                                        # extensions_offset field


def _mutate_misaligned(buf: bytearray) -> None:
    # 376 → 377: 1 byte past the aligned/canonical/file-size-bound value.
    # Trips (a) misalignment; also (b) since 377 > 376; also (d).
    struct.pack_into("<I", buf, _EXT_OFFSET_ADDR, 377)


def _mutate_past_crc(buf: bytearray) -> None:
    # 376 → 380: aligned (380 % 4 = 0), but 380 > file_size − 4 = 376.
    # Trips (b); also (d).
    struct.pack_into("<I", buf, _EXT_OFFSET_ADDR, 380)


def _mutate_below_blob(buf: bytearray) -> None:
    # 376 → 308: aligned, in [0, file_size − 4], but 308 < tile_blob_start = 312.
    # Trips (c); also (d).
    struct.pack_into("<I", buf, _EXT_OFFSET_ADDR, 308)


def _mutate_wrong_sum(buf: bytearray) -> None:
    # 376 → 372: aligned, ≥ tile_blob_start, ≤ file_size − 4, but ≠
    # expected sum (372 ≠ 312 + 64 = 376). Only (d) fires.
    struct.pack_into("<I", buf, _EXT_OFFSET_ADDR, 372)


_RULE_18_SUMMARY = (
    "extensions_offset MUST be 4-aligned, ≤ file_size − 4, ≥ "
    "tile_blob_start, AND equal tile_blob_start + Σ padded_length(i) over "
    "every tile-index entry (§ 4.13 + § 11 #18)"
)


FIXTURES = [
    _lib.mutate_style_negative(
        name="neg-18a-extoff-misaligned",
        mutate=_mutate_misaligned,
        description=(
            "Pack with extensions_offset 376 → 377 (not 4-aligned). Sub-"
            "clause (a) fires; (b) and (d) also fire since 377 > 376 and "
            "377 ≠ 376 = expected sum. Any of the three rejections "
            "satisfies the test. CRC recomputed."
        ),
        mutation=f"file[{_EXT_OFFSET_ADDR}..{_EXT_OFFSET_ADDR+4}] (extensions_offset, u32 LE) 376 → 377; CRC recomputed.",
        spec_refs=["§ 4.13"],
        rule_number="18",
        rule_summary=_RULE_18_SUMMARY,
        base_module=golden_smallest,
    ),
    _lib.mutate_style_negative(
        name="neg-18b-extoff-past-crc",
        mutate=_mutate_past_crc,
        description=(
            "Pack with extensions_offset 376 → 380 (aligned, but past "
            "file_size − 4 = 376). Sub-clause (b) fires; (d) also fires "
            "since 380 ≠ expected. CRC recomputed."
        ),
        mutation=f"file[{_EXT_OFFSET_ADDR}..{_EXT_OFFSET_ADDR+4}] (extensions_offset, u32 LE) 376 → 380; CRC recomputed.",
        spec_refs=["§ 4.13"],
        rule_number="18",
        rule_summary=_RULE_18_SUMMARY,
        base_module=golden_smallest,
    ),
    _lib.mutate_style_negative(
        name="neg-18c-extoff-below-blob",
        mutate=_mutate_below_blob,
        description=(
            "Pack with extensions_offset 376 → 308 (aligned and ≤ file_size − 4, "
            "but below tile_blob_start = 312). Sub-clause (c) fires; (d) "
            "also fires since 308 ≠ expected. CRC recomputed."
        ),
        mutation=f"file[{_EXT_OFFSET_ADDR}..{_EXT_OFFSET_ADDR+4}] (extensions_offset, u32 LE) 376 → 308; CRC recomputed.",
        spec_refs=["§ 4.13"],
        rule_number="18",
        rule_summary=_RULE_18_SUMMARY,
        base_module=golden_smallest,
    ),
    _lib.mutate_style_negative(
        name="neg-18d-extoff-wrong-sum",
        mutate=_mutate_wrong_sum,
        description=(
            "Pack with extensions_offset 376 → 372: aligned, "
            "≥ tile_blob_start = 312, ≤ file_size − 4 = 376, but "
            "372 ≠ tile_blob_start + Σ padded_length = 312 + 64 = 376. "
            "Sub-clauses (a), (b), (c) all stay quiet; only (d) fires. "
            "The only fixture in this cluster that isolates a single "
            "sub-clause of rule #18. CRC recomputed."
        ),
        mutation=f"file[{_EXT_OFFSET_ADDR}..{_EXT_OFFSET_ADDR+4}] (extensions_offset, u32 LE) 376 → 372; CRC recomputed.",
        spec_refs=["§ 4.13"],
        rule_number="18",
        rule_summary=_RULE_18_SUMMARY,
        base_module=golden_smallest,
    ),
]
