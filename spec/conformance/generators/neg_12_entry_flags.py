"""neg-12[a,b] — § 11 #12 tile-index entry flags / reserved bytes.

Targets: "Reject any tile-index entry with non-zero flags or non-zero
reserved (§ 5.2)." Two fixtures, both single-byte mutations of the lone
tile-index entry in golden-smallest.

Tile-index entry 0 starts at file offset 292 in golden-smallest (the
index_offset). Within the 20-byte entry layout (§ 5.1):

  entry[0] = z              → file[292]
  entry[1] = compression    → file[293]
  entry[2] = flags          → file[294]   ← neg-12a target
  entry[3] = reserved       → file[295]   ← neg-12b target
  entry[4..8]  = x
  entry[8..12] = y
  ...
"""

from __future__ import annotations

from . import _lib

_RULE_12_SUMMARY = (
    "tile-index entry flags (byte 2) and reserved (byte 3) MUST be 0 in v1 (§ 5.2)"
)


def _mut_flags(buf: bytearray) -> None:
    buf[294] = 1


def _mut_reserved(buf: bytearray) -> None:
    buf[295] = 1


FIXTURES = [
    _lib.mutate_style_negative(
        name="neg-12a-flags-nonzero",
        mutate=_mut_flags,
        description="Pack whose lone tile-index entry has flags = 1; v1 requires flags = 0; CRC recomputed.",
        mutation="file[294] (tile-index entry 0 byte 2, flags) 0 → 1; CRC recomputed.",
        spec_refs=["§ 5.2"],
        rule_number="12",
        rule_summary=_RULE_12_SUMMARY,
    ),
    _lib.mutate_style_negative(
        name="neg-12b-reserved-nonzero",
        mutate=_mut_reserved,
        description="Pack whose lone tile-index entry has reserved = 1; v1 requires reserved = 0; CRC recomputed.",
        mutation="file[295] (tile-index entry 0 byte 3, reserved) 0 → 1; CRC recomputed.",
        spec_refs=["§ 5.2"],
        rule_number="12",
        rule_summary=_RULE_12_SUMMARY,
    ),
]
