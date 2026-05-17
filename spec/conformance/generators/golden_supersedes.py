"""golden-supersedes.rawtiles — non-zero supersedes_uuid (§ 4.4).

Identical to golden-smallest except `supersedes_uuid` (header bytes 24..40)
is non-zero. § 4.4 reserves the all-zero value as the "supersedes nothing"
sentinel; a non-zero value names a UUID this pack is a refresh of, used
for chained-overrides distributions.

This is the only golden in the corpus with `supersedes_uuid ≠ 0`. The
value is derived deterministically from the pack name so regenerating
produces byte-identical output. Readers MUST treat the field as opaque
(no semantic check beyond zero/non-zero); this fixture pins the parse
path that handles a non-zero value without rejection.
"""

from __future__ import annotations

import hashlib
import struct
import zlib

from . import golden_smallest as g

NAME = "golden-supersedes"
KIND = "golden"

TILE_DIM_PX = g.TILE_DIM_PX
TILE_BYTES = g.TILE_BYTES

PACK_UUID = hashlib.sha256(b"rawtiles-conformance:golden-supersedes:v1").digest()[:16]
# Deterministic non-zero value distinct from PACK_UUID — derived from a
# different label so the two UUIDs differ in every byte with overwhelming
# probability, ruling out any reader that conflates the fields.
SUPERSEDES_UUID = hashlib.sha256(b"rawtiles-conformance:golden-supersedes:superseded").digest()[:16]
assert SUPERSEDES_UUID != bytes(16)
assert SUPERSEDES_UUID != PACK_UUID


def build_pack() -> bytes:
    bbox = (-180_000_000, -g.MERCATOR_POLE_UDEG, +180_000_000, +g.MERCATOR_POLE_UDEG)

    tile_count = 1
    index_offset = g.HEADER_SIZE                              # 292
    tile_blob_start = index_offset + tile_count * g.INDEX_ENTRY_SIZE   # 312
    tile_offset = tile_blob_start
    tile_length = len(TILE_BYTES)                             # 64
    extensions_offset = tile_offset + tile_length             # 376
    file_size = extensions_offset + g.CRC_SIZE                # 380

    zoom_offsets = bytearray(24 * 8)
    struct.pack_into("<II", zoom_offsets, 0, index_offset, tile_count)

    header = bytearray(g.HEADER_SIZE)
    struct.pack_into("<4sBB2x", header, 0,
                     g.MAGIC, g.FORMAT_VERSION_MAJOR, g.FORMAT_VERSION_MINOR)
    header[8:24]  = PACK_UUID
    header[24:40] = SUPERSEDES_UUID                           # ← non-zero (was all-zero)
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
            "1-tile pack identical to golden-smallest except "
            "`supersedes_uuid` (header bytes 24..40) is set to a non-zero "
            "deterministic UUID. The only v1 corpus fixture with "
            "supersedes_uuid != 0; pins the accept path for § 4.4's "
            "non-sentinel value."
        ),
        "spec_refs": ["§ 4.4"],
        "expected_outcome": "accept",
        "pack_sha256": hashlib.sha256(pack).hexdigest(),
        "hashes_path": f"golden/{NAME}.hashes",
        "hashes_sha256": hashlib.sha256(hashes.encode("utf-8")).hexdigest(),
    }
