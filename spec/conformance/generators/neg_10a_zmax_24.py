"""neg-10a-zmax-24.rawtiles — violates § 11 #10 (zoom_max bound).

Targets the first half of "Reject zoom_max ≥ 24 or zoom_min > zoom_max."
§ 4.8 fixes zoom_max < 24 because zoom_offsets[] is a 24-entry directory.

Mutation from golden-smallest: header[63] (zoom_max) 0 → 24. zoom_min stays
at 0, so the zoom_min > zoom_max half of #10 is not also tripped. The lone
tile-index entry has z = 0, which is within [zoom_min=0, zoom_max=24], so
§ 11 #15 is not tripped either. CRC recomputed.

Note: the inversion case (zoom_min > zoom_max) cannot be expressed as a
single-violation mutation of golden-smallest because the empty [zoom_min,
zoom_max] range would also violate § 11 #15 (entry z out of range).
neg-10b is therefore deferred until a metadata-only Quadtree golden base
(tile_count = 0) is available.
"""

from __future__ import annotations

from . import _lib


def _mutate(buf: bytearray) -> None:
    buf[63] = 24


FIXTURES = [
    _lib.mutate_style_negative(
        name="neg-10a-zmax-24",
        mutate=_mutate,
        description="Pack with zoom_max = 24 (§ 4.8 requires zoom_max < 24, the size of zoom_offsets[24]); CRC recomputed.",
        mutation="header[63] (zoom_max) 0 → 24; CRC recomputed.",
        spec_refs=["§ 4.8"],
        rule_number="10",
        rule_summary="zoom_max MUST be < 24 and zoom_min MUST be ≤ zoom_max (§ 4.8)",
    ),
]
