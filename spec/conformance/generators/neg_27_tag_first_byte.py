"""neg-27-tag-digit-first.rawtiles — violates § 11 #27.

Targets: "Reject any extension section whose tag's first byte is outside
[A-Z, a-z] (digits, punctuation, control chars, non-ASCII, etc.)"
(§ 7.2 + § 11 #27).

Mutation from golden-attr: the ATTR section's tag's first byte (file
offset 376) is replaced with `'1'` (0x31), yielding the 4-byte tag
`1TTR`. Bytes 2–4 remain `TTR` — all printable ASCII, so rule #28 does
not fire. The tag's first byte is a digit (outside [A-Z, a-z]), so rule
#20 (unknown *upper-case* first byte) doesn't apply either. The
rejection trigger is rule #27 alone.

CRC is recomputed; file size unchanged at 444 bytes.
"""

from __future__ import annotations

from . import _lib, golden_attr

NAME = "neg-27-tag-digit-first"
KIND = "negative"


def _mutate(buf: bytearray) -> None:
    buf[376] = 0x31                                          # 'A' → '1'


def build_pack() -> bytes:
    return _lib.mutate_and_recrc(golden_attr.build_pack(), _mutate)


def manifest_entry(pack: bytes, hashes: str | None = None) -> dict:
    return _lib.negative_entry(
        name=NAME,
        description=(
            "Pack with the ATTR section's tag's first byte set to '1' (0x31), "
            "yielding the tag `1TTR`. Bytes 2–4 are still printable ASCII so "
            "rule #28 doesn't fire; the digit first byte is outside [A-Z, a-z] "
            "so rule #20 (unknown uppercase) doesn't apply. CRC recomputed."
        ),
        spec_refs=["§ 7.2"],
        rule_number="27",
        rule_summary=(
            "extension tag's first byte MUST be in [A-Z, a-z]; any other "
            "byte (digit, punctuation, control char, non-ASCII) MUST be "
            "rejected (§ 7.2 + § 11 #27)"
        ),
        derived_from="golden-attr",
        mutation="byte 376 (section tag byte 1) 0x41 ('A') → 0x31 ('1'); tag becomes `1TTR`; CRC recomputed.",
        pack=pack,
    )
