"""golden-empty-quadtree.rawtiles — § 8.6 metadata-only Quadtree pack.

The smallest legal Quadtree pack: tile_count = 0, no tile blob, no extension
sections. Just a 292-byte header and a 4-byte CRC footer. Total file size:
296 bytes.

This is the metadata-only path readers MUST accept per § 8.6:

    "tile_count MAY be 0 (a metadata-only pack carrying only extension
    sections). When tile_count == 0 every zoom_offsets[z] MUST be (0, 0)
    (§ 4.12), the tile blob is empty, and extensions_offset == 292.
    Readers MUST accept such packs and report no tiles available rather
    than treat the pack as malformed."

Beyond exercising the accept path, this fixture is the base for two
negative fixtures (neg-09, neg-10b) that target single rules which
would entangle with entry-side rules (#15, #16) if applied to
golden-smallest. Putting them on a metadata-only base lets the
mutation isolate to its targeted rule.

Canonical bbox per § 4.9 for tile_count = 0 Quadtree: (0, 0, 0, 0).
Canonical zoom_min / zoom_max per § 4.8 for tile_count = 0: both 0.
extensions_offset per § 4.13 for tile_count = 0: equals 292.
"""

from __future__ import annotations

import hashlib
import struct
import zlib

from . import golden_smallest as g

NAME = "golden-empty-quadtree"
KIND = "golden"

TILE_DIM_PX = 8                          # § 4.7: non-zero; any value, no tiles to size

PACK_UUID = hashlib.sha256(b"rawtiles-conformance:golden-empty-quadtree:v1").digest()[:16]


def build_pack() -> bytes:
    tile_count = 0
    index_offset = g.HEADER_SIZE                                 # 292
    extensions_offset = index_offset                              # 292 per § 4.13
    file_size = extensions_offset + g.CRC_SIZE                    # 296

    zoom_offsets = bytes(24 * 8)                                  # all-zero per § 4.12

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
                     0,   # zoom_min
                     0)   # zoom_max
    # bbox = (0, 0, 0, 0) per § 4.9 canonical for tile_count == 0
    struct.pack_into("<iiii", header, 64, 0, 0, 0, 0)
    struct.pack_into("<Q", header, 80, g.BUILD_TIMESTAMP)
    struct.pack_into("<II", header, 88, tile_count, index_offset)
    header[96:96 + 24 * 8] = zoom_offsets
    struct.pack_into("<I", header, 288, extensions_offset)

    body = bytes(header)
    assert len(body) == file_size - g.CRC_SIZE
    crc = zlib.crc32(body) & 0xFFFFFFFF
    return body + struct.pack("<I", crc)


def build_hashes(pack: bytes) -> str:
    # § 14.5 hash table — empty data section since the pack has no tiles.
    # Header comments document the pack so the file is human-meaningful.
    return (
        "# rawtiles per-tile hash table, § 14.5\n"
        "# format: <z> <x> <y> <sha256-hex>\n"
        "# (no tiles in this pack — tile_count == 0, metadata-only)\n"
    )


def manifest_entry(pack: bytes, hashes: str) -> dict:
    return {
        "name": NAME,
        "kind": "golden",
        "path": f"golden/{NAME}.rawtiles",
        "description": (
            "Metadata-only Quadtree pack (§ 8.6): tile_count = 0, no tile blob, "
            "no extension sections. The smallest legal Quadtree pack at 296 bytes."
        ),
        "spec_refs": ["§ 4.13", "§ 8.6", "§ 14.3"],
        "expected_outcome": "accept",
        "pack_sha256": hashlib.sha256(pack).hexdigest(),
        "hashes_path": f"golden/{NAME}.hashes",
        "hashes_sha256": hashlib.sha256(hashes.encode("utf-8")).hexdigest(),
    }
