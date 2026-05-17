"""neg-35 cluster — § 7.3 AFFN finiteness, rule #35.

Two sub-fixtures derived from golden-singleimage-affn. Each replaces one
of the six IEEE-754 binary64 AFFN coefficients with a non-finite bit
pattern:

  - (a) quiet NaN (0x7FF8_0000_0000_0000 LE).
  - (b) +∞ (0x7FF0_0000_0000_0000 LE).

The AFFN section's tag, length field (48), payload byte length, and
section padding are all unchanged — only the eight bytes of one
coefficient move. The projection stays at LocalLinear, so rule #36
(AFFN with non-LocalLinear) doesn't fire; the section size is preserved,
so rules #19 (framing) and #34 (length = 48) stay quiet. The header's
bbox is unchanged and remains within § 4.9's i32-µ° range, so rule #11
doesn't fire either. The rejection trigger is rule #35 alone.

AFFN section layout in golden-singleimage-affn (file size 436):
  - tag 'AFFN' at bytes 376..380
  - length field 48 at bytes 380..384
  - six f64 coefficients (a, b, c, d, e, f) at bytes 384..432:
      a=384..392, b=392..400, c=400..408, d=408..416, e=416..424, f=424..432
  - CRC footer at bytes 432..436

The mutated coefficient is `f` (file bytes 424..432) — the y-offset of
the affine map. Replacing the last coefficient minimises overlap with
the header's bbox (which is statically embedded and won't be recomputed
by a reader), making the violation strictly local to AFFN finiteness.
"""

from __future__ import annotations

from . import _lib, golden_singleimage_affn

_AFFN_F_OFFSET = 424                                     # bytes 424..432 = coef[5] (`f`)

_QNAN_BYTES = b"\x00\x00\x00\x00\x00\x00\xf8\x7f"        # 0x7FF8_0000_0000_0000 LE
_POS_INF_BYTES = b"\x00\x00\x00\x00\x00\x00\xf0\x7f"     # 0x7FF0_0000_0000_0000 LE


def _mutate_nan(buf: bytearray) -> None:
    buf[_AFFN_F_OFFSET:_AFFN_F_OFFSET + 8] = _QNAN_BYTES


def _mutate_inf(buf: bytearray) -> None:
    buf[_AFFN_F_OFFSET:_AFFN_F_OFFSET + 8] = _POS_INF_BYTES


_RULE_35_SUMMARY = (
    "all six AFFN coefficients MUST be finite IEEE-754 binary64 values "
    "(no NaN, no ±∞); readers MUST reject violations (§ 7.3 + § 11 #35)"
)


FIXTURES = [
    _lib.mutate_style_negative(
        name="neg-35a-affn-nan",
        mutate=_mutate_nan,
        description=(
            "Pack with AFFN coefficient `f` (the y-offset) overwritten with the "
            "8-byte LE encoding of a quiet NaN (0x7FF8_0000_0000_0000). Section "
            "framing, length field, projection, and bbox are all unchanged; "
            "CRC recomputed."
        ),
        mutation=(
            "bytes 424..432 (AFFN payload coef[5] `f`, IEEE-754 binary64 LE) "
            "1.0 → 0x7FF8_0000_0000_0000 (quiet NaN); CRC recomputed."
        ),
        spec_refs=["§ 7.3"],
        rule_number="35",
        rule_summary=_RULE_35_SUMMARY,
        derived_from="golden-singleimage-affn",
        base_module=golden_singleimage_affn,
    ),
    _lib.mutate_style_negative(
        name="neg-35b-affn-inf",
        mutate=_mutate_inf,
        description=(
            "Pack with AFFN coefficient `f` overwritten with the 8-byte LE "
            "encoding of +∞ (0x7FF0_0000_0000_0000). Section framing, length "
            "field, projection, and bbox are all unchanged; CRC recomputed."
        ),
        mutation=(
            "bytes 424..432 (AFFN payload coef[5] `f`, IEEE-754 binary64 LE) "
            "1.0 → 0x7FF0_0000_0000_0000 (+∞); CRC recomputed."
        ),
        spec_refs=["§ 7.3"],
        rule_number="35",
        rule_summary=_RULE_35_SUMMARY,
        derived_from="golden-singleimage-affn",
        base_module=golden_singleimage_affn,
    ),
]
