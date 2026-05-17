"""golden-minor-1.rawtiles — accept path for § 11 #4.

Targets: "Accept packs with `format_version_minor > 0`, applying §§ 7.2
and 8 to any extension tags or enum values they contain" (§ 11 #4).

Identical to golden-smallest except `format_version_minor` is `1` instead
of `0`. No new extension tags or enum values — those are exercised by
golden-ancillary-tag. This fixture's sole job is to pin the minor-version
accept path: a strict v1.0 reader that rejects (1, 1) packs is
non-conforming.

The 1-tile blob byte and tile_index entry are byte-identical to
golden-smallest, so the .hashes file is also identical.
"""

from __future__ import annotations

import hashlib
import struct
import zlib

from . import golden_smallest as g

NAME = "golden-minor-1"
KIND = "golden"

TILE_DIM_PX = g.TILE_DIM_PX
TILE_BYTES = g.TILE_BYTES                                    # opaque white, 64 bytes

PACK_UUID = hashlib.sha256(b"rawtiles-conformance:golden-minor-1:v1").digest()[:16]


def build_pack() -> bytes:
    # Same canonical bbox as golden-smallest (full-world, single tile at 0,0,0).
    bbox = (-180_000_000, -g.MERCATOR_POLE_UDEG, +180_000_000, +g.MERCATOR_POLE_UDEG)

    tile_count = 1
    index_offset = g.HEADER_SIZE                              # 292
    tile_blob_start = index_offset + tile_count * g.INDEX_ENTRY_SIZE  # 312
    tile_offset = tile_blob_start
    tile_length = len(TILE_BYTES)                             # 64
    extensions_offset = tile_offset + tile_length             # 376
    file_size = extensions_offset + g.CRC_SIZE                # 380

    zoom_offsets = bytearray(24 * 8)
    struct.pack_into("<II", zoom_offsets, 0, index_offset, tile_count)

    header = bytearray(g.HEADER_SIZE)
    struct.pack_into("<4sBB2x", header, 0,
                     g.MAGIC,
                     g.FORMAT_VERSION_MAJOR,                  # 1
                     1)                                       # ← minor version: 1 (was 0)
    header[8:24]  = PACK_UUID
    header[24:40] = g.SUPERSEDES_UUID
    header[40:56] = g.PARENT_UUID
    struct.pack_into("<BBBBHBB", header, 56,
                     g.PIXEL_FORMAT_ABGR2222,
                     g.PROJECTION_WEBMERCATOR,
                     g.ADDRESSING_QUADTREE,
                     g.AXIS_XYZ,
                     TILE_DIM_PX,
                     0,    # zoom_min
                     0)    # zoom_max
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

    body = bytes(header) + index_entry + TILE_BYTES
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
            "Minimum-legal pack identical to golden-smallest except "
            "`format_version_minor = 1`. Pins the § 11 #4 accept path: "
            "readers MUST accept (1, x) packs for any minor x, applying "
            "§§ 7.2 and 8 to whatever the pack contains."
        ),
        "spec_refs": ["§ 4.2", "§ 14.3"],
        "expected_outcome": "accept",
        "pack_sha256": hashlib.sha256(pack).hexdigest(),
        "hashes_path": f"golden/{NAME}.hashes",
        "hashes_sha256": hashlib.sha256(hashes.encode("utf-8")).hexdigest(),
    }
