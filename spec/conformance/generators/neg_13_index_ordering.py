"""neg-13 cluster — § 5.2 / § 11 #13 tile-index ordering.

Two sub-fixtures derived from golden-grid (16 entries at z = 2, sorted
ascending by (z, x, y)). Each swaps a single u32 LE byte inside two of
the 20-byte index entries to break the strict-within-zoom ordering:

  - (b) within-zoom (x, y) not strictly ascending: entry 0 and entry 1
    swap their `y` values, yielding the (x, y) sequence
    `(0,1), (0,0), (0,2), (0,3), (1,0), ...`. Strict lex order broken
    between the first two entries.
  - (c) duplicate (z, x, y): entry 1's `y` is set equal to entry 0's,
    yielding two adjacent entries both at `(2, 0, 0)`.

The z-non-monotone sub-case (#13's other half) needs a multi-zoom base
that v1 doesn't yet ship (a `golden-pyramid` fixture would unblock it);
it is intentionally absent until that base exists.

Tile-index entry layout (§ 5.1, 20 bytes per entry):
  - byte 0: z (u8)
  - byte 1: compression (u8)
  - byte 2: flags (u8)
  - byte 3: reserved (u8)
  - bytes 4..8:   x (u32 LE)
  - bytes 8..12:  y (u32 LE)
  - bytes 12..16: offset (u32 LE)
  - bytes 16..20: length (u32 LE)

In golden-grid, the index region starts at file offset 292 (§ 4.11)
with 16 entries. Entry `i` occupies file bytes `292 + i*20 .. 292 + i*20 + 20`.
"""

from __future__ import annotations

from . import _lib, golden_grid

_INDEX_BASE = 292                                          # § 4.11
_ENTRY_SIZE = 20                                           # § 5.1


def _entry_y_addr(i: int) -> int:
    """File offset of entry i's `y` field (u32 LE, 4 bytes)."""
    return _INDEX_BASE + i * _ENTRY_SIZE + 8


# --- (b) within-zoom (x, y) not strictly ascending ---------------------------

def _mutate_swap_y_01(buf: bytearray) -> None:
    # Entry 0 in golden-grid is (z=2, x=0, y=0); entry 1 is (z=2, x=0, y=1).
    # Swap their y LSBs (each y fits in one byte for z=2, since y ∈ [0, 3]):
    a, b = _entry_y_addr(0), _entry_y_addr(1)
    buf[a], buf[b] = buf[b], buf[a]                        # 0x00↔0x01 — symmetric


# --- (c) duplicate (z, x, y) -------------------------------------------------

def _mutate_dup_zxy_01(buf: bytearray) -> None:
    # Set entry 1's y LSB to 0 so it matches entry 0's (z=2, x=0, y=0).
    buf[_entry_y_addr(1)] = 0x00                           # was 0x01


_RULE_13_SUMMARY = (
    "tile-index entries MUST be sorted ascending by (z, x, y): z "
    "non-decreasing across all entries; within each zoom, (x, y) strictly "
    "ascending lexicographically (forbids duplicate triples and underpins "
    "§ 5.3's binary search) (§ 11 #13)"
)


FIXTURES = [
    _lib.mutate_style_negative(
        name="neg-13b-xy-not-strict",
        mutate=_mutate_swap_y_01,
        description=(
            "Pack derived from golden-grid by swapping entry 0's and entry 1's "
            "`y` LSBs, yielding the (x, y) sequence `(0,1), (0,0), (0,2), ...`. "
            "(0,1) > (0,0) breaks strict ascending between adjacent entries. "
            "Offsets and counts are unchanged so rules #14, #17, and #32 stay "
            "quiet; CRC recomputed."
        ),
        mutation=(
            "file[300] (entry 0 `y` LSB) 0x00 → 0x01 and file[320] (entry 1 `y` "
            "LSB) 0x01 → 0x00 (atomic swap); CRC recomputed."
        ),
        spec_refs=["§ 5.2"],
        rule_number="13",
        rule_summary=_RULE_13_SUMMARY,
        derived_from="golden-grid",
        base_module=golden_grid,
    ),
    _lib.mutate_style_negative(
        name="neg-13c-duplicate-zxy",
        mutate=_mutate_dup_zxy_01,
        description=(
            "Pack derived from golden-grid by setting entry 1's `y` LSB to 0, "
            "so entries 0 and 1 are both `(z=2, x=0, y=0)`. Duplicate (z, x, y) "
            "violates the *strict* part of strict-ascending; CRC recomputed."
        ),
        mutation="file[320] (entry 1 `y` LSB) 0x01 → 0x00; CRC recomputed.",
        spec_refs=["§ 5.2"],
        rule_number="13",
        rule_summary=_RULE_13_SUMMARY,
        derived_from="golden-grid",
        base_module=golden_grid,
    ),
]
