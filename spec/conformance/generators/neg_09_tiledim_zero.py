"""neg-09-tiledim-zero.rawtiles — violates § 11 #9.

Targets: "Reject tile_dim_px == 0 (§ 4.7)."

Mutation: header[60..62] (tile_dim_px) → 0.

Derived from golden-empty-quadtree, NOT golden-smallest, because applying
this mutation to golden-smallest would also violate § 11 #16 (the lone
tile-index entry's length = 64 wouldn't equal tile_dim² = 0). The
metadata-only base has no tile-index entries, so #16 cannot fire and the
mutation isolates cleanly to #9.

CRC recomputed; total file size unchanged at 296 bytes.
"""

from __future__ import annotations

import struct

from . import _lib, golden_empty_quadtree


def _mutate(buf: bytearray) -> None:
    struct.pack_into("<H", buf, 60, 0)


FIXTURES = [
    _lib.mutate_style_negative(
        name="neg-09-tiledim-zero",
        mutate=_mutate,
        description="Pack with tile_dim_px = 0; § 4.7 requires non-zero. Built on the metadata-only base so § 11 #16 (length = tile_dim²) cannot also fire. CRC recomputed.",
        mutation="header[60..62] (tile_dim_px, u16 LE) 8 → 0; CRC recomputed.",
        spec_refs=["§ 4.7"],
        rule_number="9",
        rule_summary="tile_dim_px MUST be non-zero (§ 4.7)",
        base_module=golden_empty_quadtree,
    ),
]
