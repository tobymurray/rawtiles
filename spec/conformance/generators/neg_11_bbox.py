"""neg-11[a-d] — § 11 #11 bbox out-of-range or inverted.

Spec § 11 #11:
  "Reject bbox values outside the integer-microdegree ranges of § 4.9:
   min_lon and max_lon outside [−180_000_000, 180_000_000], or
   min_lat and max_lat outside [−90_000_000, 90_000_000].
   Reject min_lon > max_lon or min_lat > max_lat."

Two distinct failure modes share the rule:
  - Range overflow (a, b): bump one coordinate just past the absolute limit.
  - Inversion (c, d): swap min and max so one strictly exceeds the other,
    with both values still in range so the *only* violation is inversion.

bbox layout in the header (§ 4.9):
  64..68  min_lon (i32 LE)
  68..72  min_lat (i32 LE)
  72..76  max_lon (i32 LE)
  76..80  max_lat (i32 LE)
"""

from __future__ import annotations

import struct

from . import _lib

_RULE_11_SUMMARY = (
    "bbox values MUST lie within [-180M, +180M] µ° (lon) / [-90M, +90M] µ° (lat) "
    "and satisfy min ≤ max (§ 4.9)"
)


def _mut_lon_overflow(buf: bytearray) -> None:
    struct.pack_into("<i", buf, 72, 180_000_001)        # max_lon


def _mut_lat_overflow(buf: bytearray) -> None:
    struct.pack_into("<i", buf, 68, -90_000_001)        # min_lat


def _mut_lon_inverted(buf: bytearray) -> None:
    struct.pack_into("<i", buf, 64, 180_000_000)        # min_lon: -180M → +180M
    struct.pack_into("<i", buf, 72, -180_000_000)       # max_lon: +180M → -180M


def _mut_lat_inverted(buf: bytearray) -> None:
    struct.pack_into("<i", buf, 68, 85_051_129)         # min_lat: -85_051_129 → +85_051_129
    struct.pack_into("<i", buf, 76, -85_051_129)        # max_lat: +85_051_129 → -85_051_129


FIXTURES = [
    _lib.mutate_style_negative(
        name="neg-11a-lon-overflow",
        mutate=_mut_lon_overflow,
        description="Pack with bbox.max_lon = +180_000_001, one µ° past the +180_000_000 limit; CRC recomputed.",
        mutation="header[72..76] (bbox.max_lon) 180_000_000 → 180_000_001 (out of [-180M, +180M] µ° range); CRC recomputed.",
        spec_refs=["§ 4.9"],
        rule_number="11",
        rule_summary=_RULE_11_SUMMARY,
    ),
    _lib.mutate_style_negative(
        name="neg-11b-lat-overflow",
        mutate=_mut_lat_overflow,
        description="Pack with bbox.min_lat = -90_000_001, one µ° past the -90_000_000 limit; CRC recomputed.",
        mutation="header[68..72] (bbox.min_lat) -85_051_129 → -90_000_001 (out of [-90M, +90M] µ° range); CRC recomputed.",
        spec_refs=["§ 4.9"],
        rule_number="11",
        rule_summary=_RULE_11_SUMMARY,
    ),
    _lib.mutate_style_negative(
        name="neg-11c-lon-inverted",
        mutate=_mut_lon_inverted,
        description="Pack with bbox lon endpoints swapped (min_lon > max_lon); both values still in range, so inversion is the lone violation; CRC recomputed.",
        mutation="header[64..68] (bbox.min_lon) and header[72..76] (bbox.max_lon) swapped: min_lon -180_000_000 → +180_000_000, max_lon +180_000_000 → -180_000_000; CRC recomputed.",
        spec_refs=["§ 4.9"],
        rule_number="11",
        rule_summary=_RULE_11_SUMMARY,
    ),
    _lib.mutate_style_negative(
        name="neg-11d-lat-inverted",
        mutate=_mut_lat_inverted,
        description="Pack with bbox lat endpoints swapped (min_lat > max_lat); both values still in range, so inversion is the lone violation; CRC recomputed.",
        mutation="header[68..72] (bbox.min_lat) and header[76..80] (bbox.max_lat) swapped: min_lat -85_051_129 → +85_051_129, max_lat +85_051_129 → -85_051_129; CRC recomputed.",
        spec_refs=["§ 4.9"],
        rule_number="11",
        rule_summary=_RULE_11_SUMMARY,
    ),
]
