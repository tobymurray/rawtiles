"""neg-08 cluster — § 8.6 / § 11 #8 illegal projection × addressing pairs.

§ 8.6 fixes two legal pairs for v1: (WebMercator, Quadtree) and
(LocalLinear, SingleImage). The other two combinations
(WebMercator, SingleImage) and (LocalLinear, Quadtree) MUST be rejected
even though each enum byte is individually valid (so rule #7 stays quiet).

Each sub-fixture is a single-byte mutation chosen so that no other rule
fires under it:

  - (a) (WebMercator, SingleImage): base golden-smallest already
    coincidentally satisfies every SingleImage shape condition (1 tile at
    0,0,0; zoom_min = zoom_max = 0; axis = 1; zoom_offsets[0] = (292, 1)
    with all other slots zero). Switching `tile_addressing_scheme` from 1
    (Quadtree) to 2 (SingleImage) therefore yields a structurally valid
    SingleImage pack — except it declares projection = WebMercator,
    breaking § 8.6's pair table. Rule #23 (SingleImage shape) stays quiet
    because golden-smallest's shape already complies.

  - (b) (LocalLinear, Quadtree): base golden-singleimage-affn has
    projection = LocalLinear and addressing = SingleImage with an AFFN
    section, satisfying rule #22 (AFFN required for LocalLinear). Flipping
    addressing 2 → 1 (Quadtree) breaks the pair. AFFN with LocalLinear
    still satisfies rule #36; AFFN format unchanged so #34, #35 stay quiet;
    zoom_offsets[0] = (292, 1) and the lone entry at (z=0, x=0, y=0)
    remain consistent for Quadtree's 1-tile layout.
"""

from __future__ import annotations

from . import _lib, golden_singleimage_affn, golden_smallest


def _mutate_webmerc_singleimage(buf: bytearray) -> None:
    # Quadtree (1) → SingleImage (2). projection stays at WebMercator (1).
    buf[58] = 2


def _mutate_locallinear_quadtree(buf: bytearray) -> None:
    # SingleImage (2) → Quadtree (1). projection stays at LocalLinear (3).
    buf[58] = 1


_RULE_8_SUMMARY = (
    "the (projection, tile_addressing_scheme) pair MUST be one of the two "
    "legal v1 combinations in § 8.6: (WebMercator, Quadtree) or "
    "(LocalLinear, SingleImage); any other pairing MUST be rejected "
    "(§ 8.6 + § 11 #8)"
)


FIXTURES = [
    _lib.mutate_style_negative(
        name="neg-08a-webmerc-singleimage",
        mutate=_mutate_webmerc_singleimage,
        description=(
            "Pack derived from golden-smallest with tile_addressing_scheme "
            "switched 1 (Quadtree) → 2 (SingleImage) while projection stays at "
            "1 (WebMercator). golden-smallest already satisfies every "
            "SingleImage shape condition, so rule #23 stays quiet; the only "
            "violation is § 8.6's legal-pair constraint. CRC recomputed."
        ),
        mutation="header[58] (tile_addressing_scheme) 1 (Quadtree) → 2 (SingleImage); CRC recomputed.",
        spec_refs=["§ 8.6"],
        rule_number="8",
        rule_summary=_RULE_8_SUMMARY,
        base_module=golden_smallest,
    ),
    _lib.mutate_style_negative(
        name="neg-08b-locallinear-quadtree",
        mutate=_mutate_locallinear_quadtree,
        description=(
            "Pack derived from golden-singleimage-affn with "
            "tile_addressing_scheme switched 2 (SingleImage) → 1 (Quadtree) "
            "while projection stays at 3 (LocalLinear). The AFFN section "
            "remains valid (rule #22, #34, #35 stay quiet); zoom_offsets and "
            "the lone entry stay consistent for Quadtree's 1-tile layout; "
            "rule #23 no longer applies. The pair is the lone violation. "
            "CRC recomputed."
        ),
        mutation="header[58] (tile_addressing_scheme) 2 (SingleImage) → 1 (Quadtree); CRC recomputed.",
        spec_refs=["§ 8.6"],
        rule_number="8",
        rule_summary=_RULE_8_SUMMARY,
        derived_from="golden-singleimage-affn",
        base_module=golden_singleimage_affn,
    ),
]
