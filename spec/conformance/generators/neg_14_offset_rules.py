"""neg-14 cluster — § 11 #14 tile-index entry offset/length rules.

§ 11 #14 lists four sub-clauses evaluated in order — (a) alignment,
(b) below blob start, (c) past extensions_offset, (d) length overrun —
and rejection on any fires. All four sub-fixtures mutate golden-smallest's
lone tile-index entry's `offset` (u32 LE at file bytes 304..308) or its
combination with `length`.

Co-firing with rule #32 (per-tile placement equality) is unavoidable for
all four: rule #32 requires `offset(0) == tile_blob_start`, so any change
to entry 0's offset also breaks #32. Strict readers honoring rule #14's
"evaluated in order" should fire the targeted #14 sub-clause first, but
test passes on any rejection (cf. neg-25's note). The manifest documents
the primary rule per fixture.

Tile-index entry layout (§ 5.1, 20 bytes starting at file byte 292):
  - byte 0..3:   z, compression, flags, reserved
  - byte 4..8:   x (u32 LE)
  - byte 8..12:  y (u32 LE)
  - byte 12..16: offset (u32 LE)      ← file bytes 304..308
  - byte 16..20: length (u32 LE)      ← file bytes 308..312

golden-smallest reference points:
  - tile_blob_start = 312
  - extensions_offset = 376
  - tile length = 64
"""

from __future__ import annotations

import struct

from . import _lib, golden_smallest

_OFFSET_ADDR = 304                                            # entry 0's `offset` field


# --- (a) offset not 4-aligned -------------------------------------------------

def _mutate_misaligned(buf: bytearray) -> None:
    # 312 → 313: still inside the blob region (312..376) and unsigned-greater
    # than tile_blob_start, but 313 % 4 == 1. Rule #14a fires first.
    struct.pack_into("<I", buf, _OFFSET_ADDR, 313)


# --- (b) offset < tile_blob_start --------------------------------------------

def _mutate_below_blob(buf: bytearray) -> None:
    # 312 → 288: aligned (288 % 4 == 0), below tile_blob_start = 312 (rule
    # #14b fires), and length 64 ≤ extensions_offset − 288 = 88 (so #14d
    # stays quiet).
    struct.pack_into("<I", buf, _OFFSET_ADDR, 288)


# --- (c) offset >= extensions_offset ------------------------------------------

def _mutate_past_ext(buf: bytearray) -> None:
    # 312 → 376: equals extensions_offset. Rule #14c fires. (#14d would also
    # fire — 64 > 376 − 376 = 0 — but #14c is checked first per § 11 #14's
    # "evaluated in order" clause.)
    struct.pack_into("<I", buf, _OFFSET_ADDR, 376)


# --- (d) length > extensions_offset − offset ----------------------------------

def _mutate_length_overrun(buf: bytearray) -> None:
    # Move offset forward to 316 while leaving length = 64. Aligned (#14a
    # quiet), above tile_blob_start (#14b quiet), below extensions_offset
    # (#14c quiet). 64 > 376 − 316 = 60 → rule #14d fires. Length = 64
    # still equals tile_dim_px² so rule #16 also stays quiet.
    struct.pack_into("<I", buf, _OFFSET_ADDR, 316)


_RULE_14_SUMMARY = (
    "for each tile-index entry, evaluated in order: (a) offset MUST be "
    "4-aligned; (b) offset ≥ tile_blob_start; (c) offset < extensions_offset; "
    "(d) length ≤ extensions_offset − offset (§ 11 #14)"
)


FIXTURES = [
    _lib.mutate_style_negative(
        name="neg-14a-offset-misaligned",
        mutate=_mutate_misaligned,
        description=(
            "Pack with entry 0's `offset` set to 313 (not 4-aligned). Rule "
            "#14a fires first per § 11 #14's evaluation order. Rule #32 "
            "(per-tile placement) also fires; either rejection satisfies the "
            "test. CRC recomputed."
        ),
        mutation=f"file[{_OFFSET_ADDR}..{_OFFSET_ADDR+4}] (entry 0 `offset`, u32 LE) 312 → 313; CRC recomputed.",
        spec_refs=["§ 5.1"],
        rule_number="14",
        rule_summary=_RULE_14_SUMMARY,
        base_module=golden_smallest,
    ),
    _lib.mutate_style_negative(
        name="neg-14b-offset-below-blob",
        mutate=_mutate_below_blob,
        description=(
            "Pack with entry 0's `offset` set to 288 (inside the header, "
            "below tile_blob_start = 312). Rule #14b fires; #14a quiet "
            "(288 is 4-aligned), #14d quiet (64 ≤ 376 − 288). Rule #32 "
            "also fires. CRC recomputed."
        ),
        mutation=f"file[{_OFFSET_ADDR}..{_OFFSET_ADDR+4}] (entry 0 `offset`, u32 LE) 312 → 288; CRC recomputed.",
        spec_refs=["§ 5.1"],
        rule_number="14",
        rule_summary=_RULE_14_SUMMARY,
        base_module=golden_smallest,
    ),
    _lib.mutate_style_negative(
        name="neg-14c-offset-past-ext",
        mutate=_mutate_past_ext,
        description=(
            "Pack with entry 0's `offset` set to 376 (= extensions_offset). "
            "Rule #14c fires first per the evaluation order; #14d would also "
            "fire (64 > 0) but the spec orders (c) before (d). Rule #32 "
            "also fires. CRC recomputed."
        ),
        mutation=f"file[{_OFFSET_ADDR}..{_OFFSET_ADDR+4}] (entry 0 `offset`, u32 LE) 312 → 376; CRC recomputed.",
        spec_refs=["§ 5.1"],
        rule_number="14",
        rule_summary=_RULE_14_SUMMARY,
        base_module=golden_smallest,
    ),
    _lib.mutate_style_negative(
        name="neg-14d-length-overrun",
        mutate=_mutate_length_overrun,
        description=(
            "Pack with entry 0's `offset` bumped 312 → 316 while length "
            "stays at 64. 316 is aligned and within bounds, so #14a/b/c "
            "stay quiet; 64 > 376 − 316 = 60 fires #14d. Length still "
            "equals tile_dim_px² so #16 stays quiet. Rule #32 also fires. "
            "CRC recomputed."
        ),
        mutation=f"file[{_OFFSET_ADDR}..{_OFFSET_ADDR+4}] (entry 0 `offset`, u32 LE) 312 → 316; CRC recomputed.",
        spec_refs=["§ 5.1"],
        rule_number="14",
        rule_summary=_RULE_14_SUMMARY,
        base_module=golden_smallest,
    ),
]
