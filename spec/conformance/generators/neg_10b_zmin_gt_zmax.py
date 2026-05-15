"""neg-10b-zmin-gt-zmax.rawtiles — violates § 11 #10 (zmin > zmax half).

Targets the second half of "Reject zoom_max ≥ 24 or zoom_min > zoom_max."

Mutation: header[62] (zoom_min) 0 → 1, with header[63] (zoom_max) left
at 0. The resulting zoom_min = 1 > zoom_max = 0 violates § 11 #10.

Derived from golden-empty-quadtree, NOT golden-smallest, because the
inverted range [zmin=1, zmax=0] is empty, so any tile-index entry's z
would also violate § 11 #15 (z out of [zmin, zmax]). The metadata-only
base has no entries, so #15 cannot fire and the mutation isolates to
#10. The § 4.8 writer obligation "for tile_count == 0 packs, both
fields MUST be 0" is a writer-side rule and is not separately
enforced in § 11.

CRC recomputed; total file size unchanged at 296 bytes.
"""

from __future__ import annotations

from . import _lib, golden_empty_quadtree


def _mutate(buf: bytearray) -> None:
    buf[62] = 1


FIXTURES = [
    _lib.mutate_style_negative(
        name="neg-10b-zmin-gt-zmax",
        mutate=_mutate,
        description="Pack with zoom_min = 1 and zoom_max = 0 (inverted). Built on the metadata-only base so § 11 #15 (entry z out of [zmin, zmax]) cannot also fire. CRC recomputed.",
        mutation="header[62] (zoom_min) 0 → 1; header[63] (zoom_max) stays at 0; CRC recomputed.",
        spec_refs=["§ 4.8"],
        rule_number="10",
        rule_summary="zoom_max MUST be < 24 and zoom_min MUST be ≤ zoom_max (§ 4.8)",
        base_module=golden_empty_quadtree,
    ),
]
