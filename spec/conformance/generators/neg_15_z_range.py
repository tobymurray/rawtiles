"""neg-15 cluster — § 4.8 / § 11 #15 entry-zoom out of declared range.

Two sub-fixtures targeting "Reject any tile-index entry with `z > zoom_max`
or `z < zoom_min`". Each is a coordinated multi-byte mutation on
golden-smallest so that rule #15 is the lone violation — naive single-byte
changes would also fire rule #17 (zoom_offsets directory inconsistency)
or rule #10 (zoom_min > zoom_max).

  - (a) z above zoom_max: entry's `z` 0 → 1 while migrating the
    zoom_offsets pointer from slot 0 to slot 1 (so the directory still
    correctly describes the actual entry placement at z = 1). The
    header's zoom_max stays at 0, so the entry's z = 1 > zoom_max = 0.
    Rule #15 fires; #17 (directory consistency) and #10 (range/order)
    stay quiet.

  - (b) z below zoom_min: leave the entry at z = 0 but bump
    zoom_min = zoom_max = 1 simultaneously (so #10's `zoom_min ≤ zoom_max`
    holds). The entry's z = 0 < zoom_min = 1. zoom_offsets[0] = (292, 1)
    remains consistent with the actual one entry at z = 0, so #17 stays
    quiet too.

Header field offsets used:
  - byte 62: `zoom_min` (u8)
  - byte 63: `zoom_max` (u8)
  - byte 292: entry 0's `z` (u8)
  - bytes 96..104:   zoom_offsets[0] = (offset u32 LE, count u32 LE)
  - bytes 104..112:  zoom_offsets[1] = (offset u32 LE, count u32 LE)
"""

from __future__ import annotations

import struct

from . import _lib, golden_smallest


# --- (a) entry.z > zoom_max --------------------------------------------------

def _mutate_z_above_zmax(buf: bytearray) -> None:
    # Promote the lone entry to z = 1 while leaving zoom_max = 0.
    buf[292] = 1                                            # entry 0's z: 0 → 1

    # Migrate the zoom_offsets pointer from slot 0 to slot 1 so the directory
    # is consistent with the actual entry's new zoom. Without this, rule #17
    # would also fire (count mismatch at both z=0 and z=1).
    struct.pack_into("<II", buf, 96, 0, 0)                  # zoom_offsets[0] = (0, 0)
    struct.pack_into("<II", buf, 104, 292, 1)               # zoom_offsets[1] = (292, 1)


# --- (b) entry.z < zoom_min --------------------------------------------------

def _mutate_z_below_zmin(buf: bytearray) -> None:
    # Bump both zoom_min and zoom_max to 1 in one stroke. The entry stays at
    # z = 0, so it now falls below zoom_min = 1. zoom_max also moves to 1 so
    # rule #10's `zoom_min ≤ zoom_max` holds.
    buf[62] = 1                                             # zoom_min: 0 → 1
    buf[63] = 1                                             # zoom_max: 0 → 1


FIXTURES = [
    _lib.mutate_style_negative(
        name="neg-15a-z-above-zmax",
        mutate=_mutate_z_above_zmax,
        description=(
            "Pack derived from golden-smallest with entry 0 promoted to z = 1 "
            "and zoom_offsets migrated from slot 0 to slot 1 to match. Header "
            "zoom_max stays at 0, so the entry's z = 1 > zoom_max = 0 trips "
            "rule #15. The coordinated zoom_offsets shift keeps rule #17 "
            "(directory consistency) quiet; CRC recomputed."
        ),
        mutation=(
            "file[292] (entry 0 `z`) 0 → 1; file[96..104] (zoom_offsets[0]) "
            "(292, 1) → (0, 0); file[104..112] (zoom_offsets[1]) (0, 0) → "
            "(292, 1); CRC recomputed."
        ),
        spec_refs=["§ 4.8"],
        rule_number="15",
        rule_summary="entry z MUST satisfy zoom_min ≤ z ≤ zoom_max (§ 4.8 + § 11 #15)",
        base_module=golden_smallest,
    ),
    _lib.mutate_style_negative(
        name="neg-15b-z-below-zmin",
        mutate=_mutate_z_below_zmin,
        description=(
            "Pack derived from golden-smallest by bumping both zoom_min and "
            "zoom_max to 1 while leaving entry 0 at z = 0. Entry's z = 0 < "
            "zoom_min = 1 trips rule #15. zoom_max also moves to 1 so #10 "
            "(zoom_min ≤ zoom_max) stays quiet; zoom_offsets[0] = (292, 1) "
            "still consistent with the entry at z = 0, so #17 also quiet. "
            "CRC recomputed."
        ),
        mutation=(
            "header[62] (zoom_min) 0 → 1 and header[63] (zoom_max) 0 → 1; "
            "entry 0's z stays at 0; CRC recomputed."
        ),
        spec_refs=["§ 4.8"],
        rule_number="15",
        rule_summary="entry z MUST satisfy zoom_min ≤ z ≤ zoom_max (§ 4.8 + § 11 #15)",
        base_module=golden_smallest,
    ),
]
