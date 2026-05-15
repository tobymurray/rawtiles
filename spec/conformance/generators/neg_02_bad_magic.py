"""neg-02-bad-magic.rawtiles — violates § 11 #2.

Targets: "Reject any pack whose first 4 bytes are not ASCII RAWT (§ 4.1)."

Mutation from golden-smallest: header[0] zeroed (`RAWT` → `\\x00AWT`).
CRC is recomputed over the mutated body so no other § 11 rule fires.
Total file size unchanged at 380 bytes.

The minimal-mutation approach works directly here because no other field
depends on the magic bytes — unlike neg-25-index-offset-296, there is no
cross-reference to update.
"""

from __future__ import annotations

import hashlib
import struct
import zlib

from . import golden_smallest as g

NAME = "neg-02-bad-magic"
KIND = "negative"
DERIVED_FROM = "golden-smallest"
MUTATION = r"header[0] zeroed (magic RAWT → \x00AWT); CRC recomputed."

BAD_MAGIC = b"\x00AWT"


def build_pack() -> bytes:
    base = bytearray(g.build_pack())
    base[0:4] = BAD_MAGIC
    body = bytes(base[:-g.CRC_SIZE])
    crc = zlib.crc32(body) & 0xFFFFFFFF
    return body + struct.pack("<I", crc)


def manifest_entry(pack: bytes, hashes: str | None = None) -> dict:
    return {
        "name": NAME,
        "kind": "negative",
        "path": f"negative/{NAME}.rawtiles",
        "description": r"Pack with first byte zeroed (\x00AWT); all other fields valid; CRC recomputed.",
        "spec_refs": ["§ 4.1"],
        "expected_outcome": "reject",
        "pack_sha256": hashlib.sha256(pack).hexdigest(),
        "expected_reject_rule": {
            "rule_number": "2",
            "summary": "first 4 bytes MUST be ASCII \"RAWT\" (0x52 0x41 0x57 0x54)",
        },
        "derived_from": DERIVED_FROM,
        "mutation": MUTATION,
    }
