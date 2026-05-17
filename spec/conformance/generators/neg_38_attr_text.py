"""neg-38[a-h] — § 11 #38 SRCD / ATTR text-rule violations (mutate-style).

§ 11 #38 (spec 0.3): "Reject any SRCD or ATTR section whose payload is not
valid UTF-8. Additionally reject any ATTR section whose payload (a) contains
any byte sequence decoding to U+0001–U+001F other than U+000A, to U+007F,
to U+0085, to U+2028, or to U+2029; (b) has declared length zero; or
(c) ends with byte 0x0A (trailing LF after the last string) (§ 7.3)."

All eight mutate-style fixtures here derive from golden-attr by mutating
bytes within the ATTR section's payload (file offsets 384..437) and/or
the section's length field (file offsets 380..384). Each fixture isolates
one failure mode; the others are valid.

  38a   SRCD bad UTF-8        — tag flipped to SRCD + payload byte → 0xFF   [#38(a)]
  38b   ATTR bad UTF-8        — payload byte → 0xFF                          [#38(a)]
  38c   ATTR CRLF             — byte immediately before the LF separator → 0x0D
  38d   ATTR bare CR          — non-adjacent-to-LF byte → 0x0D
  38e   ATTR C0 control       — non-LF byte → 0x07 (BEL)
  38f   ATTR NEL              — '©' trailer 0xA9 → 0x85; yields 0xC2 0x85 = U+0085
  38g   ATTR LS               — '© ' (3 bytes) → 0xE2 0x80 0xA8 = U+2028
  38h   ATTR trailing LF      — length 53 → 54 + first pad byte → 0x0A      [#38(c)]

The zero-length payload case (neg-38i) is a reshape-style fixture (file
shrinks) and lives in its own module.

ATTR payload layout in golden-attr (file offsets shown):

  384..399  "Example imagery " (ASCII, 16 bytes)
  400..401  0xC2 0xA9          (first '©')
  402..406  " 2026"            (ASCII, 5 bytes)
  407       0x0A               (separator LF)
  408..409  0xC2 0xA9          (second '©')
  410..436  " OpenStreetMap contributors" (ASCII, 27 bytes)
  437..440  0x00 0x00 0x00     (3 alignment pad bytes — repurposed by 38h)
"""

from __future__ import annotations

from . import _lib, golden_attr

_RULE_38_SUMMARY = (
    "SRCD and ATTR payloads MUST be valid UTF-8. ATTR additionally MUST "
    "(a) contain no C0 control codepoint other than LF, no DEL (U+007F), no "
    "NEL (U+0085), no LS (U+2028), and no PS (U+2029); (b) have non-zero "
    "declared length; (c) not end with byte 0x0A (no trailing LF after the "
    "last string) (§ 7.3 + § 11 #38)"
)

# ATTR section header occupies file offsets 376..384; payload begins at 384.
_PAYLOAD_START = 384


def _payload_byte(i: int) -> int:
    return _PAYLOAD_START + i


def _mut_srcd_bad_utf8(buf: bytearray) -> None:
    buf[376:380] = b"SRCD"
    buf[_payload_byte(16)] = 0xFF


def _mut_attr_bad_utf8(buf: bytearray) -> None:
    buf[_payload_byte(16)] = 0xFF


def _mut_attr_crlf(buf: bytearray) -> None:
    buf[_payload_byte(22)] = 0x0D


def _mut_attr_bare_cr(buf: bytearray) -> None:
    buf[_payload_byte(15)] = 0x0D


def _mut_attr_c0(buf: bytearray) -> None:
    buf[_payload_byte(15)] = 0x07


def _mut_attr_nel(buf: bytearray) -> None:
    buf[_payload_byte(17)] = 0x85


def _mut_attr_ls(buf: bytearray) -> None:
    # 3-byte UTF-8 of U+2028 = 0xE2 0x80 0xA8. Overwrite payload[16..19], which
    # was the first '©' (2 bytes) plus the following ASCII space.
    buf[_payload_byte(16)] = 0xE2
    buf[_payload_byte(17)] = 0x80
    buf[_payload_byte(18)] = 0xA8


def _mut_attr_trailing_lf(buf: bytearray) -> None:
    # Extend the declared payload by one byte (bumping length 53 → 54) and
    # promote the first alignment-pad byte to 0x0A. After mutation the section
    # ends at exactly the same file offset (8 header + 54 payload + 2 pad = 64),
    # so framing/CRC stay valid; only the new (c) clause of rule #38 fires.
    buf[380] = 54                                              # length LSB: 53 → 54
    buf[_payload_byte(53)] = 0x0A                              # was pad 0x00


_COMMON = dict(
    spec_refs=["§ 7.3"],
    rule_number="38",
    rule_summary=_RULE_38_SUMMARY,
    derived_from="golden-attr",
    base_module=golden_attr,
)


FIXTURES = [
    _lib.mutate_style_negative(
        name="neg-38a-srcd-bad-utf8",
        mutate=_mut_srcd_bad_utf8,
        description=(
            "Pack with golden-attr's ATTR section re-tagged 'SRCD' and the lead byte "
            "0xC2 of the first '©' codepoint set to 0xFF, making the SRCD payload "
            "invalid UTF-8; CRC recomputed."
        ),
        mutation=(
            "bytes 376..380 (section tag) 'ATTR' → 'SRCD'; byte 400 (payload[16], "
            "lead byte of first '©') 0xC2 → 0xFF; CRC recomputed."
        ),
        **_COMMON,
    ),
    _lib.mutate_style_negative(
        name="neg-38b-attr-bad-utf8",
        mutate=_mut_attr_bad_utf8,
        description=(
            "Pack with the lead byte 0xC2 of the first '©' codepoint in ATTR's payload "
            "set to 0xFF, making the payload invalid UTF-8; CRC recomputed."
        ),
        mutation="byte 400 (payload[16], lead byte of first '©') 0xC2 → 0xFF; CRC recomputed.",
        **_COMMON,
    ),
    _lib.mutate_style_negative(
        name="neg-38c-attr-crlf",
        mutate=_mut_attr_crlf,
        description=(
            "Pack with ATTR payload's '6' (last byte of '2026', immediately preceding "
            "the LF separator) set to CR, producing a CRLF line break; CRC recomputed."
        ),
        mutation="byte 406 (payload[22], '6' before the LF separator) 0x36 → 0x0D; CRC recomputed.",
        **_COMMON,
    ),
    _lib.mutate_style_negative(
        name="neg-38d-attr-bare-cr",
        mutate=_mut_attr_bare_cr,
        description=(
            "Pack with an ATTR payload space byte (not adjacent to the LF separator) "
            "set to CR, producing a bare CR; CRC recomputed."
        ),
        mutation="byte 399 (payload[15], space before first '©') 0x20 → 0x0D; CRC recomputed.",
        **_COMMON,
    ),
    _lib.mutate_style_negative(
        name="neg-38e-attr-c0-control",
        mutate=_mut_attr_c0,
        description=(
            "Pack with an ATTR payload space byte set to BEL (0x07), a C0 control "
            "codepoint other than LF; CRC recomputed."
        ),
        mutation="byte 399 (payload[15], space before first '©') 0x20 → 0x07 (BEL); CRC recomputed.",
        **_COMMON,
    ),
    _lib.mutate_style_negative(
        name="neg-38f-attr-nel",
        mutate=_mut_attr_nel,
        description=(
            "Pack with the trailing byte 0xA9 of the first '©' set to 0x85, yielding "
            "0xC2 0x85 (U+0085, NEL) in ATTR's payload; CRC recomputed."
        ),
        mutation=(
            "byte 401 (payload[17], trailer of first '©') 0xA9 → 0x85; combined with "
            "the unchanged lead 0xC2 this encodes U+0085 (NEL); CRC recomputed."
        ),
        **_COMMON,
    ),
    _lib.mutate_style_negative(
        name="neg-38g-attr-ls",
        mutate=_mut_attr_ls,
        description=(
            "Pack with bytes 0xC2 0xA9 0x20 (first '©' plus the following space) in "
            "ATTR's payload replaced by 0xE2 0x80 0xA8 (U+2028, LINE SEPARATOR); "
            "CRC recomputed."
        ),
        mutation=(
            "bytes 400..403 (payload[16..19], first '©' UTF-8 plus the following space) "
            "0xC2 0xA9 0x20 → 0xE2 0x80 0xA8 (U+2028); CRC recomputed."
        ),
        **_COMMON,
    ),
    _lib.mutate_style_negative(
        name="neg-38h-attr-trailing-lf",
        mutate=_mut_attr_trailing_lf,
        description=(
            "Pack with the ATTR section's declared payload length bumped 53 → 54 "
            "and the first alignment-pad byte (file 437) promoted to 0x0A. The "
            "now-54-byte payload ends with LF, violating § 11 #38(c) "
            "(no trailing LF after the last string). The 2 remaining pad bytes "
            "stay 0x00, so § 11 #19's pad-zero rule stays quiet; total framed "
            "size (8 + 54 + 2 = 64) and section/CRC offsets are unchanged. "
            "CRC recomputed."
        ),
        mutation=(
            "byte 380 (ATTR length field LSB) 0x35 → 0x36 (53 → 54); byte 437 "
            "(first alignment-pad byte, now repurposed as the last payload byte) "
            "0x00 → 0x0A; CRC recomputed."
        ),
        **_COMMON,
    ),
]
