"""neg-25-index-offset-296.rawtiles — violates § 11 #25.

Targets: "Reject any pack where index_offset != 292 (§ 4.11)."

Mutation from golden-smallest: index_offset bumped 292 → 296. The 4-byte gap
between header end and the new tile-index location is filled with zeros, and
all cross-references (zoom_offsets[0].offset, the tile-index entry's offset,
extensions_offset) are updated so that NO other § 11 rule is violated.
CRC is recomputed over the new body so the pack would otherwise be valid.

A conforming reader MUST reject this pack on rule #25 (or earlier — readers
are not required to honor any specific ordering of § 11 checks, only that all
rejections fire before content is returned). Test passes on any rejection.

File size: 384 bytes (4 more than golden-smallest, due to the index shift).
"""

from __future__ import annotations

import hashlib
import struct
import zlib

from . import golden_smallest as g

NAME = "neg-25-index-offset-296"
KIND = "negative"
DERIVED_FROM = "golden-smallest"
MUTATION = (
    "index_offset 292 → 296; tile-index region shifted right by 4 zero bytes; "
    "zoom_offsets[0].offset, entry.offset, extensions_offset updated; CRC recomputed."
)


def build_pack() -> bytes:
    # Layout with shifted index — every internal cross-reference is consistent;
    # the ONLY violation is the index_offset field value itself.
    index_offset = 296                                               # ← the violation (§ 11 #25)
    tile_count = 1
    tile_blob_start = index_offset + tile_count * g.INDEX_ENTRY_SIZE  # 316 (already 4-aligned)
    tile_offset = tile_blob_start
    tile_length = len(g.TILE_BYTES)                                   # 64
    extensions_offset = tile_offset + tile_length                     # 380
    file_size = extensions_offset + g.CRC_SIZE                        # 384

    bbox = (-180_000_000, -g.MERCATOR_POLE_UDEG,
            +180_000_000, +g.MERCATOR_POLE_UDEG)

    zoom_offsets = bytearray(24 * 8)
    struct.pack_into("<II", zoom_offsets, 0, index_offset, tile_count)

    header = bytearray(g.HEADER_SIZE)
    struct.pack_into("<4sBB2x", header, 0,
                     g.MAGIC, g.FORMAT_VERSION_MAJOR, g.FORMAT_VERSION_MINOR)
    header[8:24]  = g.PACK_UUID
    header[24:40] = g.SUPERSEDES_UUID
    header[40:56] = g.PARENT_UUID
    struct.pack_into("<BBBBHBB", header, 56,
                     g.PIXEL_FORMAT_ABGR2222,
                     g.PROJECTION_WEBMERCATOR,
                     g.ADDRESSING_QUADTREE,
                     g.AXIS_XYZ,
                     g.TILE_DIM_PX,
                     0, 0)
    struct.pack_into("<iiii", header, 64, *bbox)
    struct.pack_into("<Q", header, 80, g.BUILD_TIMESTAMP)
    struct.pack_into("<II", header, 88, tile_count, index_offset)
    header[96:96 + 24 * 8] = bytes(zoom_offsets)
    struct.pack_into("<I", header, 288, extensions_offset)

    pre_index_padding = bytes(4)                                      # 292..296: 4 zero bytes

    index_entry = struct.pack(
        "<BBBBIIII",
        0, g.COMPRESSION_NONE, 0, 0,
        0, 0,
        tile_offset,
        tile_length,
    )

    body = bytes(header) + pre_index_padding + index_entry + g.TILE_BYTES
    assert len(body) == file_size - g.CRC_SIZE, (len(body), file_size - g.CRC_SIZE)
    crc = zlib.crc32(body) & 0xFFFFFFFF
    return body + struct.pack("<I", crc)


def build_hashes(pack: bytes) -> str:
    # Negative fixtures are not openable, so a .hashes table would never be
    # consumed. The orchestrator skips writing one for non-golden fixtures.
    raise NotImplementedError("negative fixtures have no .hashes table")


def manifest_entry(pack: bytes, hashes: str | None = None) -> dict:
    return {
        "name": NAME,
        "kind": "negative",
        "path": f"negative/{NAME}.rawtiles",
        "description": "Pack with index_offset = 296 instead of the v1.0-required 292.",
        "spec_refs": ["§ 4.11"],
        "expected_outcome": "reject",
        "pack_sha256": hashlib.sha256(pack).hexdigest(),
        "expected_reject_rule": {
            "rule_number": "25",
            "summary": "index_offset must equal 292 in v1.0",
        },
        "derived_from": DERIVED_FROM,
        "mutation": MUTATION,
    }
