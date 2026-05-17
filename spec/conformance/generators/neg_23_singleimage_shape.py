"""neg-23 cluster — § 8.6 / § 11 #23 SingleImage shape violations.

Rule #23 is a conjunctive requirement on SingleImage packs: tile_count == 1
AND lone entry is (z=0, x=0, y=0) AND zoom_min == zoom_max == 0 AND
tile_axis_convention == 1 AND zoom_offsets[0] == (index_offset, 1) AND
zoom_offsets[z ∈ [1, 23]] == (0, 0). Violating any conjunct rejects the
pack.

Three sub-fixtures, each derived from golden-singleimage-affn with a
single-byte mutation that breaks one conjunct without disturbing the
others:

  - (b) lone entry (z, x, y) ≠ (0, 0, 0): entry.y LSB 0 → 1.
  - (c) header zoom_max ≠ 0: zoom_max 0 → 5 (zoom_min stays at 0 so #10
    stays quiet; zoom_offsets remain consistent because all zooms above 0
    legitimately have count = 0).
  - (d) tile_axis_convention ≠ 1: axis 1 (XYZ) → 2 (TMS). TMS is a known
    enum (§ 8.4) so rule #7 doesn't fire; § 12 #19 and § 11 #23 require
    SingleImage packs to emit/accept only `1`.

Sub-cases (a) tile_count = 2 and (e) leaking zoom_offsets[z ∈ [1, 23]]
entangle with other rules:
  - (a) needs a second tile-index entry, which by § 5.2's strict-ascending
    rule would also force #13 to fire. Deferred until a reshape-style
    builder is available.
  - (e) any leak into zoom_offsets[z ≥ 1] also makes that slot
    inconsistent with the 0 entries at that zoom, firing rule #17.
    Deferred for the same reason.

golden-singleimage-affn key file offsets used:
  - byte 59:  tile_axis_convention (u8)
  - byte 63:  zoom_max (u8)
  - byte 300: entry 0's y LSB (low byte of u32 LE)
"""

from __future__ import annotations

from . import _lib, golden_singleimage_affn


def _mutate_entry_nonzero(buf: bytearray) -> None:
    # Entry 0's (z=0, x=0, y=0) → (0, 0, 1). The SingleImage spec mandates
    # the lone entry sits at (0, 0, 0) regardless of how the rest of the
    # pack looks.
    buf[300] = 1                                              # entry.y LSB: 0 → 1


def _mutate_zoom_max(buf: bytearray) -> None:
    # zoom_max 0 → 5. zoom_min stays at 0, so rule #10's zmin ≤ zmax
    # (0 ≤ 5 < 24) holds. The actual entry is still at z = 0, in range
    # [0, 5], so rule #15 stays quiet. zoom_offsets[1..5] remain (0, 0)
    # consistent with 0 entries at those zooms, so rule #17 stays quiet.
    buf[63] = 5                                               # zoom_max: 0 → 5


def _mutate_axis_tms(buf: bytearray) -> None:
    # tile_axis_convention 1 (XYZ) → 2 (TMS). § 8.4 lists 2 as valid for
    # Quadtree but § 11 #23 requires SingleImage packs to use XYZ. Rule #7
    # (reserved enum) doesn't apply since 2 is a known value.
    buf[59] = 2                                               # tile_axis_convention: 1 → 2


_RULE_23_SUMMARY = (
    "SingleImage packs MUST satisfy ALL of: tile_count == 1; the lone "
    "entry is (z=0, x=0, y=0); zoom_min == zoom_max == 0; "
    "tile_axis_convention == 1; zoom_offsets[0] == (index_offset, 1); "
    "every zoom_offsets[z ∈ [1, 23]] == (0, 0) (§ 8.6 + § 11 #23)"
)


FIXTURES = [
    _lib.mutate_style_negative(
        name="neg-23b-singleimage-entry-nonzero",
        mutate=_mutate_entry_nonzero,
        description=(
            "SingleImage pack with the lone entry at (z=0, x=0, y=1) instead "
            "of (0, 0, 0). Header/zoom_offsets unchanged; CRC recomputed."
        ),
        mutation="file[300] (entry 0 `y` LSB) 0x00 → 0x01; CRC recomputed.",
        spec_refs=["§ 8.6"],
        rule_number="23",
        rule_summary=_RULE_23_SUMMARY,
        derived_from="golden-singleimage-affn",
        base_module=golden_singleimage_affn,
    ),
    _lib.mutate_style_negative(
        name="neg-23c-singleimage-zmax-nonzero",
        mutate=_mutate_zoom_max,
        description=(
            "SingleImage pack with header.zoom_max bumped 0 → 5. zoom_min "
            "stays at 0 (so rule #10 stays quiet); the lone entry remains at "
            "z = 0 within [0, 5] (so rule #15 stays quiet); zoom_offsets "
            "remain consistent (so rule #17 stays quiet). CRC recomputed."
        ),
        mutation="header[63] (zoom_max) 0 → 5; CRC recomputed.",
        spec_refs=["§ 8.6"],
        rule_number="23",
        rule_summary=_RULE_23_SUMMARY,
        derived_from="golden-singleimage-affn",
        base_module=golden_singleimage_affn,
    ),
    _lib.mutate_style_negative(
        name="neg-23d-singleimage-axis-tms",
        mutate=_mutate_axis_tms,
        description=(
            "SingleImage pack with tile_axis_convention set to 2 (TMS) "
            "instead of the SingleImage-required 1 (XYZ). 2 is a known enum "
            "value (§ 8.4 lists it for Quadtree), so rule #7 stays quiet; "
            "rule #23 is the lone violation. CRC recomputed."
        ),
        mutation="header[59] (tile_axis_convention) 1 (XYZ) → 2 (TMS); CRC recomputed.",
        spec_refs=["§ 8.4", "§ 8.6"],
        rule_number="23",
        rule_summary=_RULE_23_SUMMARY,
        derived_from="golden-singleimage-affn",
        base_module=golden_singleimage_affn,
    ),
]
