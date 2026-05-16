"""neg-19c-stranded-bytes — § 11 #19 stranded bytes between last section and CRC.

Pack derived from golden-attr by inserting 4 zero bytes between the ATTR
section's padded end (file offset 440) and the CRC footer. file_size grows
from 444 to 448; the ATTR section still ends at offset 440 but file_size − 4
is now 444, so the rule "end of final section's complete extent MUST equal
file_size − 4" is violated by exactly 4 stranded bytes.

The stranded bytes are all-zero so this fixture isolates the stranded-bytes
sub-clause cleanly: rule #19's pad-byte sub-clause (b) doesn't fire because
the section's own pad bytes are unchanged, and the section-bounds sub-clause
doesn't fire because the section still lies within [extensions_offset,
file_size − 4).
"""

from __future__ import annotations

import hashlib
import struct
import zlib

from . import golden_attr

NAME = "neg-19c-stranded-bytes"
KIND = "negative"
DERIVED_FROM = "golden-attr"
MUTATION = (
    "Inserted 4 zero bytes between the ATTR section's padded end (byte 440) and the "
    "CRC footer; file_size 444 → 448; CRC recomputed over the new body."
)


def build_pack() -> bytes:
    base = golden_attr.build_pack()
    body = base[:-4] + bytes(4)             # original body + 4 stranded zero bytes
    crc = zlib.crc32(body) & 0xFFFFFFFF
    return body + struct.pack("<I", crc)


def build_hashes(pack: bytes) -> str:
    raise NotImplementedError("negative fixtures have no .hashes table")


def manifest_entry(pack: bytes, hashes: str | None = None) -> dict:
    return {
        "name": NAME,
        "kind": "negative",
        "path": f"negative/{NAME}.rawtiles",
        "description": (
            "Pack derived from golden-attr by inserting 4 zero bytes between the ATTR "
            "section's padded end and the CRC footer. The ATTR section is structurally "
            "intact; the violation is the 4 stranded bytes between the section and the "
            "(now-relocated) CRC footer. file_size 444 → 448; CRC recomputed."
        ),
        "spec_refs": ["§ 7.1"],
        "expected_outcome": "reject",
        "pack_sha256": hashlib.sha256(pack).hexdigest(),
        "expected_reject_rule": {
            "rule_number": "19",
            "summary": (
                "extension section's extent (tag + length + payload + alignment pad) "
                "MUST lie within [extensions_offset, file_size − 4); pad bytes MUST "
                "be 0x00; no stranded bytes may exist between the last section and "
                "the CRC footer (§ 7.1)"
            ),
        },
        "derived_from": DERIVED_FROM,
        "mutation": MUTATION,
    }
