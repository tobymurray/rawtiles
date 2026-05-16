"""neg-20-unknown-uppercase-tag.rawtiles — violates § 11 #20.

Targets: "Reject any pack containing an unknown extension tag whose first
byte is upper-case ASCII (A–Z)" (§ 7.2 + § 11 #20).

Mutation from golden-attr: the ATTR section's 4-byte tag at file offset
376..380 is replaced with `XYZQ` — four uppercase ASCII letters, none of
which match a v1 SDK-reserved tag (NAME, SRCD, ATTR, AFFN). Section
length, payload, padding, and offsets are unchanged, so framing rules
(#19), the legacy ATTR text-content rule (#38, scoped to ATTR/SRCD
specifically), and length/alignment rules don't fire. The rejection
trigger is rule #20 alone.

CRC is recomputed; file size unchanged at 444 bytes.
"""

from __future__ import annotations

from . import _lib, golden_attr

NAME = "neg-20-unknown-uppercase-tag"
KIND = "negative"


def _mutate(buf: bytearray) -> None:
    buf[376:380] = b"XYZQ"                                   # was b"ATTR"


def build_pack() -> bytes:
    return _lib.mutate_and_recrc(golden_attr.build_pack(), _mutate)


def manifest_entry(pack: bytes, hashes: str | None = None) -> dict:
    return _lib.negative_entry(
        name=NAME,
        description=(
            "Pack with the ATTR section's tag renamed to `XYZQ` — an unknown "
            "4-byte uppercase ASCII tag, not among v1's SDK-reserved set "
            "{NAME, SRCD, ATTR, AFFN}. Framing/length/padding all valid; "
            "CRC recomputed."
        ),
        spec_refs=["§ 7.2"],
        rule_number="20",
        rule_summary=(
            "unknown extension tag whose first byte is upper-case ASCII "
            "(A–Z) MUST be rejected (§ 7.2 + § 11 #20)"
        ),
        derived_from="golden-attr",
        mutation="bytes 376..380 (section tag) `ATTR` → `XYZQ`; CRC recomputed.",
        pack=pack,
    )
