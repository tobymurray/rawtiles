"""golden-names-multilocale.rawtiles — § 7.4 + § 12.1 multi-locale NAME ordering.

A 1-tile WebMercator pack carrying four `NAME` sections (the only v1
extension tag that admits multiple instances per § 7.3 Cardinality). The
fixture pins the canonical ordering rule of § 12.1: NAME sections are
sorted by ascending unsigned-byte order of their *raw length-prefixed
payloads*, NOT by alphabetical order on the BCP-47 tag.

The four locales are chosen to illustrate the "zh vs en-US byte-order
trap" called out in § 12.1: a writer that sorts by BCP-47 string would
put `en-US` before `zh` ('e' < 'z' alphabetically), but the byte-order
rule puts `zh` (length 2) before `en-US` (length 5) because the
`tag_length` byte at payload offset 0 dominates the comparison.

Sections (in canonical order):

  - Section 0: `tag_length = 0` (unlocalized fallback)         name="Tiles"
    Per § 7.4, a pack with multiple NAME sections SHOULD carry exactly
    one such fallback. Payload begins `\\x00…`, sorting first.
  - Section 1: `bcp47_tag = "en"` (length 2)                   name="Tiles"
    Payload begins `\\x02en…`. Among length-2 tags, alphabetical on
    the tag bytes themselves.
  - Section 2: `bcp47_tag = "zh"` (length 2)                   name="瓦片"
    Payload begins `\\x02zh…`. CJK name verifies the § 7.3 NFC + UTF-8
    requirement on `name`. 'z' > 'e' but both length 2, so `zh` sorts
    after `en`.
  - Section 3: `bcp47_tag = "en-US"` (length 5)                name="Tiles (US)"
    Payload begins `\\x05en-US…`. The length byte dominates: even
    though 'en-US' < 'zh' alphabetically, the length-5 sections sort
    AFTER all length-2 sections.

Byte-order verification (first 1-2 payload bytes):
    `\\x00` < `\\x02e` < `\\x02z` < `\\x05e`
so the canonical order is 0, 1, 2, 3.

The fixture is the base for negative fixtures targeting NAME-specific
rules: framing (§ 11 #26), duplicate-locale (§ 11 #29), and per-payload
UTF-8 / BCP-47 conformance (§ 11 #37).

Pack layout (456 bytes):
  - 0..292    header
  - 292..312  tile-index entry (z=x=y=0)
  - 312..376  tile blob (64 bytes, opaque white)
  - 376..392  Section 0: NAME with tag_length=0 (8 header + 6 payload + 2 pad)
  - 392..408  Section 1: NAME with bcp47="en" (8 + 8 + 0)
  - 408..428  Section 2: NAME with bcp47="zh" (8 + 9 + 3 pad)
  - 428..452  Section 3: NAME with bcp47="en-US" (8 + 16 + 0)
  - 452..456  CRC
extensions_offset = 376; file_size = 456.
"""

from __future__ import annotations

import hashlib
import struct
import unicodedata
import zlib

from . import golden_smallest as g

NAME = "golden-names-multilocale"
KIND = "golden"

TILE_DIM_PX = g.TILE_DIM_PX
TILE_BYTES = g.TILE_BYTES

PACK_UUID = hashlib.sha256(b"rawtiles-conformance:golden-names-multilocale:v1").digest()[:16]

# Sections in canonical § 12.1 byte-order. Each entry is (bcp47_tag_bytes, name_str).
# Empty bcp47_tag means tag_length = 0 (the unlocalized fallback).
_SECTIONS = [
    (b"",       "Tiles"),
    (b"en",     "Tiles"),
    (b"zh",     "瓦片"),
    (b"en-US",  "Tiles (US)"),
]


def _name_payload(bcp47_tag: bytes, name: str) -> bytes:
    """§ 7.4 NAME payload layout: tag_length (u8) + bcp47_tag + name (UTF-8)."""
    assert unicodedata.is_normalized("NFC", name), f"name {name!r} must be NFC (§ 7.3)"
    name_bytes = name.encode("utf-8")
    assert len(bcp47_tag) <= 255
    return bytes([len(bcp47_tag)]) + bcp47_tag + name_bytes


def _name_section(bcp47_tag: bytes, name: str) -> bytes:
    payload = _name_payload(bcp47_tag, name)
    header = b"NAME" + struct.pack("<I", len(payload))
    pad = (-len(payload)) % 4
    return header + payload + bytes(pad)


def _verify_canonical_order():
    """Self-check: the section list is already in § 12.1 byte-order."""
    payloads = [_name_payload(tag, name) for tag, name in _SECTIONS]
    sorted_payloads = sorted(payloads)
    assert payloads == sorted_payloads, "section list is not in canonical byte-order"


_verify_canonical_order()


def build_pack() -> bytes:
    bbox = (-180_000_000, -g.MERCATOR_POLE_UDEG, +180_000_000, +g.MERCATOR_POLE_UDEG)

    tile_count = 1
    index_offset = g.HEADER_SIZE                              # 292
    tile_blob_start = index_offset + tile_count * g.INDEX_ENTRY_SIZE  # 312
    tile_offset = tile_blob_start
    tile_length = len(TILE_BYTES)                             # 64
    extensions_offset = tile_offset + tile_length             # 376

    sections = b"".join(_name_section(tag, name) for tag, name in _SECTIONS)
    file_size = extensions_offset + len(sections) + g.CRC_SIZE

    zoom_offsets = bytearray(24 * 8)
    struct.pack_into("<II", zoom_offsets, 0, index_offset, tile_count)

    header = bytearray(g.HEADER_SIZE)
    struct.pack_into("<4sBB2x", header, 0,
                     g.MAGIC, g.FORMAT_VERSION_MAJOR, g.FORMAT_VERSION_MINOR)
    header[8:24]  = PACK_UUID
    header[24:40] = g.SUPERSEDES_UUID
    header[40:56] = g.PARENT_UUID
    struct.pack_into("<BBBBHBB", header, 56,
                     g.PIXEL_FORMAT_ABGR2222,
                     g.PROJECTION_WEBMERCATOR,
                     g.ADDRESSING_QUADTREE,
                     g.AXIS_XYZ,
                     TILE_DIM_PX,
                     0, 0)
    struct.pack_into("<iiii", header, 64, *bbox)
    struct.pack_into("<Q", header, 80, g.BUILD_TIMESTAMP)
    struct.pack_into("<II", header, 88, tile_count, index_offset)
    header[96:96 + 24 * 8] = bytes(zoom_offsets)
    struct.pack_into("<I", header, 288, extensions_offset)

    index_entry = struct.pack(
        "<BBBBIIII",
        0, g.COMPRESSION_NONE, 0, 0,
        0, 0, tile_offset, tile_length,
    )

    body = bytes(header) + index_entry + TILE_BYTES + sections
    assert len(body) == file_size - g.CRC_SIZE, (len(body), file_size - g.CRC_SIZE)
    crc = zlib.crc32(body) & 0xFFFFFFFF
    return body + struct.pack("<I", crc)


def build_hashes(pack: bytes) -> str:
    tile_offset = g.HEADER_SIZE + g.INDEX_ENTRY_SIZE
    tile_length = len(TILE_BYTES)
    digest = hashlib.sha256(pack[tile_offset:tile_offset + tile_length]).hexdigest()
    return (
        "# rawtiles per-tile hash table, § 14.5\n"
        "# format: <z> <x> <y> <sha256-hex>\n"
        f"0 0 0 {digest}\n"
    )


def manifest_entry(pack: bytes, hashes: str) -> dict:
    return {
        "name": NAME,
        "kind": "golden",
        "path": f"golden/{NAME}.rawtiles",
        "description": (
            "1-tile WebMercator pack with four NAME sections (tag_length=0 "
            "fallback, `en`, `zh`, `en-US`) in canonical § 12.1 byte-order. "
            "Pins the `zh` vs `en-US` byte-order trap: a writer that sorts "
            "by BCP-47 string would put `en-US` before `zh`, but the byte-"
            "order rule puts `zh` (length 2) before `en-US` (length 5) "
            "because the tag_length byte at payload offset 0 dominates. "
            "Exercises § 7.4 NAME payload layout, § 7.3 NFC text rules, "
            "and § 12.1 multi-instance section ordering. File size 456 bytes."
        ),
        "spec_refs": ["§ 7.3", "§ 7.4", "§ 12.1", "§ 14.5"],
        "expected_outcome": "accept",
        "pack_sha256": hashlib.sha256(pack).hexdigest(),
        "hashes_path": f"golden/{NAME}.hashes",
        "hashes_sha256": hashlib.sha256(hashes.encode("utf-8")).hexdigest(),
    }
