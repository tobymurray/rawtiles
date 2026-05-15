"""neg-24-crc-flipped.rawtiles — violates § 11 #24.

Targets: "Verify the CRC-32 footer per § 10 and reject the pack on mismatch."

This is the one rule the `_lib.mutate_and_recrc` helper can't cover — the
helper recomputes the CRC, which is exactly the failure mode we want to
exercise. The fixture is the golden-smallest bytes with the lowest-order
bit of the u32 CRC footer flipped (footer u32 XOR'd with 0x0000_0001).
The footer is little-endian, so flipping bit 0 of the u32 flips bit 0 of
file byte `file_size - 4`.

Body bytes (everything before the footer) are byte-identical to the golden,
so no structural § 11 rule fires — only the CRC mismatch does. Total file
size unchanged at 380 bytes.
"""

from __future__ import annotations

from . import _lib, golden_smallest as g

NAME = "neg-24-crc-flipped"
KIND = "negative"


def build_pack() -> bytes:
    base = bytearray(g.build_pack())
    base[-4] ^= 0x01   # u32 LE: byte 0 is the LSB; XOR with 0x0000_0001
    return bytes(base)


def manifest_entry(pack: bytes, hashes: str | None = None) -> dict:
    return _lib.negative_entry(
        name=NAME,
        description="Pack with footer u32 XOR'd with 0x0000_0001 (LSB of CRC flipped). Body bytes identical to golden-smallest.",
        spec_refs=["§ 10"],
        rule_number="24",
        rule_summary="CRC-32/ISO-HDLC footer MUST match a fresh computation over bytes [0, file_size − 4) (§ 10)",
        derived_from="golden-smallest",
        mutation="file[-4] (CRC footer byte 0, LSB) XOR 0x01; body bytes unchanged.",
        pack=pack,
    )
