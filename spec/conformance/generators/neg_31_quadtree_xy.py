"""neg-31 cluster — § 5.1 / § 11 #31 Quadtree (x, y) overflow.

Two sub-fixtures derived from golden-grid (z = 2, so legal (x, y) ∈ [0, 3]²).
Each mutates the *last* entry's `x` or `y` LSB from 3 → 4, putting that
coordinate one past the `2^z` limit.

The last entry (index 15) is chosen so the mutation does NOT violate the
strict-ascending (x, y) order of § 5.2: entry 14 has (3, 3) and entry 15
becomes (4, 3) or (3, 4), both of which are still > (3, 3) lex. Rule #13
stays quiet; rule #17 (count at z = 2 still 16) stays quiet; rule #14
(offsets) and #32 (placement) are untouched.

Tile-index entry layout (§ 5.1): per-entry x at bytes 4..8, y at bytes
8..12. golden-grid entry `i` starts at file offset 292 + i*20.
"""

from __future__ import annotations

from . import _lib, golden_grid

_ENTRY_15_BASE = 292 + 15 * 20                              # 592
_ENTRY_15_X_LSB = _ENTRY_15_BASE + 4                        # 596
_ENTRY_15_Y_LSB = _ENTRY_15_BASE + 8                        # 600


def _mutate_x_overflow(buf: bytearray) -> None:
    # Entry 15 was (z=2, x=3, y=3). Promote x to 4 (= 2^2). Entry stays
    # strictly greater than entry 14's (3, 3), so #13 doesn't fire.
    buf[_ENTRY_15_X_LSB] = 4                                # was 3


def _mutate_y_overflow(buf: bytearray) -> None:
    # Same idea on the y axis: entry 15 becomes (3, 4). (3, 4) > (3, 3),
    # so strict-ascending order is preserved and #13 stays quiet.
    buf[_ENTRY_15_Y_LSB] = 4                                # was 3


_RULE_31_SUMMARY = (
    "for tile_addressing_scheme = Quadtree, every tile-index entry MUST "
    "satisfy x < 2^z AND y < 2^z (§ 5.1 + § 11 #31)"
)


FIXTURES = [
    _lib.mutate_style_negative(
        name="neg-31a-x-overflow",
        mutate=_mutate_x_overflow,
        description=(
            "Pack derived from golden-grid with the last (entry 15) tile's "
            "x bumped 3 → 4 = 2^2. Strict (x, y) order vs entry 14's (3, 3) "
            "is preserved (4 > 3), so rule #13 stays quiet; CRC recomputed."
        ),
        mutation=f"file[{_ENTRY_15_X_LSB}] (entry 15 `x` LSB) 0x03 → 0x04; CRC recomputed.",
        spec_refs=["§ 5.1"],
        rule_number="31",
        rule_summary=_RULE_31_SUMMARY,
        derived_from="golden-grid",
        base_module=golden_grid,
    ),
    _lib.mutate_style_negative(
        name="neg-31b-y-overflow",
        mutate=_mutate_y_overflow,
        description=(
            "Pack derived from golden-grid with the last (entry 15) tile's "
            "y bumped 3 → 4 = 2^2. (3, 4) > (3, 3) keeps strict ordering "
            "intact; CRC recomputed."
        ),
        mutation=f"file[{_ENTRY_15_Y_LSB}] (entry 15 `y` LSB) 0x03 → 0x04; CRC recomputed.",
        spec_refs=["§ 5.1"],
        rule_number="31",
        rule_summary=_RULE_31_SUMMARY,
        derived_from="golden-grid",
        base_module=golden_grid,
    ),
]
