"""neg-23e-singleimage-zoomoffsets-leak.rawtiles — § 11 #23 (zoom_offsets arm).

Targets the "every `zoom_offsets[z]` for z ∈ [1, 23] is (0, 0)" conjunct
of rule #23: a SingleImage pack MUST have empty (zero) directory entries
at every zoom above 0.

Mutation from golden-singleimage-affn: `zoom_offsets[1].offset` (the u32
LE at file bytes 104..108) is set to a non-zero value (292), violating
rule #23's all-zero requirement for z ∈ [1, 23]. `zoom_offsets[1].count`
stays at 0, so the section count remains 0 at zoom 1.

Co-firing with rule #17 (zoom_offsets directory consistency) is
unavoidable: § 11 #17's third sub-clause requires `.offset == 0` whenever
`.count == 0`, and rule #23 in turn requires the entire slot to be
`(0, 0)`. Any non-zero value at `zoom_offsets[1..23]` that doesn't add a
real entry at that zoom necessarily violates both. Adding a real entry
would in turn break rule #23 in a different way (tile_count > 1, lone-
entry shape). Co-firing is documented; test passes on any rejection.

Sister fixture neg-17c-offset-nonzero-empty already covers rule #17(c)
in isolation against a Quadtree base; this fixture's primary signal is
rule #23.
"""

from __future__ import annotations

import struct

from . import _lib, golden_singleimage_affn

# zoom_offsets[1] starts at file byte 96 + 1 * 8 = 104. Its `.offset` field
# is the first u32 LE (bytes 104..108); `.count` is at bytes 108..112.
_ZOOM_OFFSETS_1_OFFSET_ADDR = 104


def _mutate(buf: bytearray) -> None:
    # Any non-zero value works; 292 is a meaningful target (the byte
    # offset of zoom_offsets[0]'s entry) but as a u32 it has no effect on
    # the pack's tile lookup because zoom_offsets[1].count stays 0 and
    # § 5.3 #2 returns absent without consulting .offset.
    struct.pack_into("<I", buf, _ZOOM_OFFSETS_1_OFFSET_ADDR, 292)


FIXTURES = [
    _lib.mutate_style_negative(
        name="neg-23e-singleimage-zoomoffsets-leak",
        mutate=_mutate,
        description=(
            "SingleImage pack with zoom_offsets[1].offset set to 292 while "
            "zoom_offsets[1].count stays 0. Violates rule #23's `every "
            "zoom_offsets[z ∈ [1, 23]] is (0, 0)` conjunct. Rule #17(c) "
            "(offset MUST be 0 when count == 0) inherently co-fires; the "
            "same-base mutation can't isolate from #17 because any non-zero "
            "value at z ∈ [1, 23] that doesn't add a real entry breaks both. "
            "CRC recomputed."
        ),
        mutation=(
            f"file[{_ZOOM_OFFSETS_1_OFFSET_ADDR}..{_ZOOM_OFFSETS_1_OFFSET_ADDR+4}] "
            "(zoom_offsets[1].offset, u32 LE) 0 → 292; CRC recomputed."
        ),
        spec_refs=["§ 4.12", "§ 8.6"],
        rule_number="23",
        rule_summary=(
            "SingleImage packs MUST satisfy ALL of: tile_count == 1; the "
            "lone entry is (z=0, x=0, y=0); zoom_min == zoom_max == 0; "
            "tile_axis_convention == 1; zoom_offsets[0] == (index_offset, 1); "
            "every zoom_offsets[z ∈ [1, 23]] == (0, 0) (§ 8.6 + § 11 #23)"
        ),
        derived_from="golden-singleimage-affn",
        base_module=golden_singleimage_affn,
    ),
]
