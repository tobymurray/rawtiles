"""golden-tms.rawtiles — TMS axis convention branch (§ 8.4).

Identical to golden-smallest except `tile_axis_convention = 2` (TMS).
This is the only v1 fixture exercising the TMS branch of § 4.9
(WebMercator bbox derivation: y' = 2^z − 1 − y before applying the XYZ
formulas) and § 6.2 (tile blob row order: first row is southernmost
under TMS, northernmost under XYZ).

The single tile at (z=0, x=0, y=0) makes the y'-substitution a no-op
(y' = 2^0 − 1 − 0 = 0), so the canonical bbox matches golden-smallest's
full-world endpoints. The fixture's value is in pinning the parse path
for `tile_axis_convention = 2`, not in differentiating the bbox; a
reader that wrongly rejects TMS at the header byte fails the accept
path before bbox enters the picture.

A separate multi-tile TMS fixture would be needed to make the
y'-substitution numerically meaningful — out of scope here.
"""

from __future__ import annotations

import hashlib
import struct
import zlib

from . import golden_smallest as g

NAME = "golden-tms"
KIND = "golden"

TILE_DIM_PX = g.TILE_DIM_PX
TILE_BYTES = g.TILE_BYTES
AXIS_TMS = 2                                                  # § 8.4

PACK_UUID = hashlib.sha256(b"rawtiles-conformance:golden-tms:v1").digest()[:16]


def build_pack() -> bytes:
    # Single tile at (0, 0, 0) — the TMS y'-substitution is a no-op at z=0,
    # so bbox matches golden-smallest's canonical full-world endpoints.
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
                     g.MAGIC, g.FORMAT_VERSION_MAJOR, g.FORMAT_VERSION_MINOR)
    header[8:24]  = PACK_UUID
    header[24:40] = g.SUPERSEDES_UUID
    header[40:56] = g.PARENT_UUID
    struct.pack_into("<BBBBHBB", header, 56,
                     g.PIXEL_FORMAT_ABGR2222,
                     g.PROJECTION_WEBMERCATOR,
                     g.ADDRESSING_QUADTREE,
                     AXIS_TMS,                                # ← 2 (was 1 = XYZ)
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
            "`tile_axis_convention = 2` (TMS). The only v1 fixture exercising "
            "the TMS branch of § 4.9 (WebMercator y'-substitution) and § 6.2 "
            "(tile row order: first row southernmost). Single-tile at z=0 "
            "makes the y'-substitution a no-op, so the canonical bbox matches "
            "the XYZ baseline; the fixture pins the header-parse accept path."
        ),
        "spec_refs": ["§ 6.2", "§ 8.4"],
        "expected_outcome": "accept",
        "pack_sha256": hashlib.sha256(pack).hexdigest(),
        "hashes_path": f"golden/{NAME}.hashes",
        "hashes_sha256": hashlib.sha256(hashes.encode("utf-8")).hexdigest(),
    }
