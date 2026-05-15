"""neg-03-major-2.rawtiles — violates § 11 #3.

Targets: "Reject any pack whose format_version_major != 1."

Mutation from golden-smallest: header[4] flipped from 1 to 2.
CRC is recomputed over the mutated body so no other § 11 rule fires.
Total file size unchanged at 380 bytes.
"""

from __future__ import annotations

from . import _lib, golden_smallest as g

NAME = "neg-03-major-2"
KIND = "negative"


def _mutate(buf: bytearray) -> None:
    buf[4] = 2


def build_pack() -> bytes:
    return _lib.mutate_and_recrc(g.build_pack(), _mutate)


def manifest_entry(pack: bytes, hashes: str | None = None) -> dict:
    return _lib.negative_entry(
        name=NAME,
        description="Pack with format_version_major = 2; all other fields valid; CRC recomputed.",
        spec_refs=["§ 4.2"],
        rule_number="3",
        rule_summary="format_version_major MUST be 1 in v1",
        derived_from="golden-smallest",
        mutation="header[4] (format_version_major) 1 → 2; CRC recomputed.",
        pack=pack,
    )
