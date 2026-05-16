"""neg-29a-duplicate-uppercase — § 11 #29 duplicate upper-case extension tag.

Pack derived from golden-attr by appending a second ATTR section. § 7.3 forbids
two upper-case tags of the same name in a single pack (except NAME, which has
its own bcp47-keyed uniqueness rule).

Both ATTR sections are individually well-formed: the first is byte-identical
to golden-attr's ATTR (53-byte payload + 3 pad bytes = 64 section bytes); the
second carries a short valid attribution ("Other source", 12 ASCII bytes, no
trailing pad needed). The lone violation is the duplicate tag.

Layout:
  - Header (292 bytes)
  - Index entry (20 bytes, 1 tile at (0,0,0))
  - Tile blob (64 bytes)
  - ATTR section #1 (376..440, 64 bytes — unchanged from golden-attr)
  - ATTR section #2 (440..460, 20 bytes — tag + length=12 + 12 payload bytes)
  - CRC (460..464)
  - File size: 464 bytes
"""

from __future__ import annotations

import hashlib
import struct
import zlib

from . import golden_attr

NAME = "neg-29a-duplicate-uppercase"
KIND = "negative"
DERIVED_FROM = "golden-attr"
_SECOND_PAYLOAD = b"Other source"          # 12 bytes, already 4-aligned with the 8-byte header
MUTATION = (
    "Appended a second ATTR section with payload 'Other source' (12 bytes) directly "
    "after the existing ATTR section; file_size 444 → 464; CRC recomputed."
)


def _second_attr_section() -> bytes:
    assert len(_SECOND_PAYLOAD) % 4 == 0, "second payload must be 4-aligned (no pad)"
    return b"ATTR" + struct.pack("<I", len(_SECOND_PAYLOAD)) + _SECOND_PAYLOAD


def build_pack() -> bytes:
    base = golden_attr.build_pack()
    body = base[:-4] + _second_attr_section()
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
            "Pack derived from golden-attr by appending a second ATTR section "
            "(payload 'Other source', 12 bytes, 4-aligned). Both sections are "
            "individually well-formed; the violation is the duplicate upper-case "
            "tag. file_size 444 → 464; CRC recomputed."
        ),
        "spec_refs": ["§ 7.3", "§ 11"],
        "expected_outcome": "reject",
        "pack_sha256": hashlib.sha256(pack).hexdigest(),
        "expected_reject_rule": {
            "rule_number": "29",
            "summary": (
                "each upper-case (SDK-reserved) extension tag MUST appear at most "
                "once per pack, except NAME (which has its own bcp47_tag-based "
                "uniqueness rule per § 7.4)"
            ),
        },
        "derived_from": DERIVED_FROM,
        "mutation": MUTATION,
    }
