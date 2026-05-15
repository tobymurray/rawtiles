"""neg-02-bad-magic.rawtiles — violates § 11 #2.

Targets: "Reject any pack whose first 4 bytes are not ASCII RAWT (§ 4.1)."

Mutation from golden-smallest: header[0] zeroed (`RAWT` → `\\x00AWT`).
CRC is recomputed over the mutated body so no other § 11 rule fires.
Total file size unchanged at 380 bytes.
"""

from __future__ import annotations

from . import _lib, golden_smallest as g

NAME = "neg-02-bad-magic"
KIND = "negative"


def _mutate(buf: bytearray) -> None:
    buf[0:4] = b"\x00AWT"


def build_pack() -> bytes:
    return _lib.mutate_and_recrc(g.build_pack(), _mutate)


def manifest_entry(pack: bytes, hashes: str | None = None) -> dict:
    return _lib.negative_entry(
        name=NAME,
        description=r"Pack with first byte zeroed (\x00AWT); all other fields valid; CRC recomputed.",
        spec_refs=["§ 4.1"],
        rule_number="2",
        rule_summary="first 4 bytes MUST be ASCII \"RAWT\" (0x52 0x41 0x57 0x54)",
        derived_from="golden-smallest",
        mutation=r"header[0] zeroed (magic RAWT → \x00AWT); CRC recomputed.",
        pack=pack,
    )
