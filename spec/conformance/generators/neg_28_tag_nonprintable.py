"""neg-28-tag-nonprintable.rawtiles — violates § 11 #28.

Targets: "Reject any extension section whose tag bytes 2–4 contain any
byte outside printable ASCII (0x20–0x7E)" (§ 7.2 + § 11 #28).

Mutation from golden-attr: the ATTR section's tag is rewritten as
`a\\x01TR` — two bytes touched, with byte 1 (file offset 376) set to
`'a'` (0x61) and byte 2 (file offset 377) set to `0x01` (SOH, a C0
control character). The lower-case first byte dodges rule #20 (which
only applies when first byte is upper-case ASCII), and is still in
[A-Z, a-z] so rule #27 doesn't fire. Rule #21 (accept and ignore
unknown *lower-case* tags) is an accept rule and cannot keep a #28-
violating pack from being rejected: #28 applies to ALL sections
regardless of case, and a reject rule binds over an accept rule. The
rejection trigger is rule #28 alone.

CRC is recomputed; file size unchanged at 444 bytes.
"""

from __future__ import annotations

from . import _lib, golden_attr

NAME = "neg-28-tag-nonprintable"
KIND = "negative"


def _mutate(buf: bytearray) -> None:
    buf[376] = 0x61                                          # 'A' → 'a'
    buf[377] = 0x01                                          # 'T' → SOH (0x01)


def build_pack() -> bytes:
    return _lib.mutate_and_recrc(golden_attr.build_pack(), _mutate)


def manifest_entry(pack: bytes, hashes: str | None = None) -> dict:
    return _lib.negative_entry(
        name=NAME,
        description=(
            "Pack with the ATTR section's tag rewritten as `a\\x01TR`: byte 1 "
            "lower-cased to 'a' (dodges rule #20's upper-case-first scope) and "
            "byte 2 replaced with SOH (0x01), a C0 control character outside "
            "the [0x20, 0x7E] printable-ASCII range required for tag bytes 2–4. "
            "First byte 'a' is in [A-Z, a-z] so rule #27 also stays quiet. "
            "CRC recomputed."
        ),
        spec_refs=["§ 7.2"],
        rule_number="28",
        rule_summary=(
            "extension tag bytes 2–4 MUST be printable ASCII (0x20–0x7E); "
            "any other byte (control char, non-ASCII) MUST be rejected "
            "(§ 7.2 + § 11 #28)"
        ),
        derived_from="golden-attr",
        mutation=(
            "byte 376 (section tag byte 1) 0x41 ('A') → 0x61 ('a'); "
            "byte 377 (section tag byte 2) 0x54 ('T') → 0x01 (SOH); "
            "tag becomes `a\\x01TR`; CRC recomputed."
        ),
        pack=pack,
    )
