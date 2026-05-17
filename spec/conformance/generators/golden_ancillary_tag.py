"""golden-ancillary-tag.rawtiles — accept path for § 11 #21.

Targets: "Accept and MAY ignore any unknown extension tag whose first byte
is lower-case ASCII" (§ 7.2 + § 11 #21).

Identical to golden-smallest except for a single extension section with
tag `xnot` (lower-case 4-char tag, not a v1 reserved tag) and a 4-byte
ASCII payload `test`. The payload is exactly 4 bytes so the section's
total framed length is 8 + 4 = 12 (already 4-aligned, no pad). The pack
exercises:

  - § 11 #21 accept path: an unknown lower-case tag MUST NOT cause
    rejection; readers MAY ignore the section.
  - § 7.1 framing: the section sits at `extensions_offset`, its bytes lie
    entirely in `[extensions_offset, file_size − 4)`, and there are no
    stranded bytes before the CRC footer.

This is the v1.0 companion to golden-minor-1, which exercises the minor-
version accept path without any unknown tag. Splitting the two accept
paths into separate fixtures keeps each rule's anchor independent.

Tag choice — `xnot`:
  - First byte 'x' (0x78) is lower-case ASCII, in [A-Z, a-z].
  - Bytes 2–4 'not' (0x6E 0x6F 0x74) are all printable ASCII.
  - Not among the v1 reserved set {NAME, SRCD, ATTR, AFFN}.
"""

from __future__ import annotations

import hashlib
import struct
import zlib

from . import golden_smallest as g

NAME = "golden-ancillary-tag"
KIND = "golden"

TILE_DIM_PX = g.TILE_DIM_PX
TILE_BYTES = g.TILE_BYTES

PACK_UUID = hashlib.sha256(b"rawtiles-conformance:golden-ancillary-tag:v1").digest()[:16]

_TAG = b"xnot"
_PAYLOAD = b"test"
_PAYLOAD_LEN = len(_PAYLOAD)                                  # 4
_PAD_LEN = (-_PAYLOAD_LEN) % 4                                # 0 (already 4-aligned)
_SECTION_LEN = 8 + _PAYLOAD_LEN + _PAD_LEN                    # 12


def _ancillary_section() -> bytes:
    return _TAG + struct.pack("<I", _PAYLOAD_LEN) + _PAYLOAD + bytes(_PAD_LEN)


def build_pack() -> bytes:
    bbox = (-180_000_000, -g.MERCATOR_POLE_UDEG, +180_000_000, +g.MERCATOR_POLE_UDEG)

    tile_count = 1
    index_offset = g.HEADER_SIZE                              # 292
    tile_blob_start = index_offset + tile_count * g.INDEX_ENTRY_SIZE   # 312
    tile_offset = tile_blob_start
    tile_length = len(TILE_BYTES)                             # 64
    extensions_offset = tile_offset + tile_length             # 376
    section = _ancillary_section()
    file_size = extensions_offset + len(section) + g.CRC_SIZE  # 376 + 12 + 4 = 392

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

    body = bytes(header) + index_entry + TILE_BYTES + section
    assert len(body) == file_size - g.CRC_SIZE
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
            "1-tile pack identical to golden-smallest except for one extension "
            "section with the unknown lower-case tag `xnot` and a 4-byte ASCII "
            "payload `test`. Pins the § 11 #21 accept path: readers MUST accept "
            "and MAY ignore unknown lower-case-first tags. File size 392 bytes."
        ),
        "spec_refs": ["§ 7.2"],
        "expected_outcome": "accept",
        "pack_sha256": hashlib.sha256(pack).hexdigest(),
        "hashes_path": f"golden/{NAME}.hashes",
        "hashes_sha256": hashlib.sha256(hashes.encode("utf-8")).hexdigest(),
    }
