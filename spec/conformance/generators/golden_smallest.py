"""golden-smallest.rawtiles — minimum-legal non-empty pack.

One tile at (z, x, y) = (0, 0, 0), tile_dim_px = 8 (64 bytes per tile),
WebMercator + Quadtree + XYZ axis, no extension sections. Total file size: 380 bytes.

This module is pure: it computes bytes and returns them. The orchestrator
(generate.py) is responsible for writing files and assembling the manifest.
"""

from __future__ import annotations

import hashlib
import struct
import zlib

# --- spec constants -----------------------------------------------------------

MAGIC = b"RAWT"                                   # § 4.1
FORMAT_VERSION_MAJOR = 1                          # § 4.2
FORMAT_VERSION_MINOR = 0

PIXEL_FORMAT_ABGR2222 = 1                         # § 8.1
PROJECTION_WEBMERCATOR = 1                        # § 8.2
ADDRESSING_QUADTREE = 1                           # § 8.3
AXIS_XYZ = 1                                      # § 8.4
COMPRESSION_NONE = 0                              # § 8.5

HEADER_SIZE = 292                                 # § 4 (offset 0, 292 bytes)
INDEX_ENTRY_SIZE = 20                             # § 5.1
CRC_SIZE = 4                                      # § 10
MERCATOR_POLE_UDEG = 85_051_129                   # § 4.9

# --- fixture-specific choices -------------------------------------------------

NAME = "golden-smallest"
TILE_DIM_PX = 8
TILE_BYTES = bytes([0xFF]) * (TILE_DIM_PX * TILE_DIM_PX)   # A=B=G=R=3 (opaque white)
BUILD_TIMESTAMP = 0                               # § 4.10 "no freshness info"
SUPERSEDES_UUID = bytes(16)                       # § 4.4 zero = supersedes nothing
PARENT_UUID = bytes(16)                           # § 4.5 reserved, must be zero in v1

# § 4.3 allows any non-zero opaque 16-byte value. Derive deterministically from
# the fixture name so regenerating produces byte-identical output.
PACK_UUID = hashlib.sha256(b"rawtiles-conformance:golden-smallest:v1").digest()[:16]


def build_pack() -> bytes:
    # Canonical bbox for Quadtree, single tile at (z=0, x=0, y=0), per § 4.9:
    #   lon_west_µ°(0, 0)  = (0·360_000_000 − 180_000_000) / 1 = −180_000_000
    #   lon_east_µ°(0, 0)  = lon_west_µ°(0, 1)                =  180_000_000
    #   lat_north_µ°(0, 0) = +85_051_129  (y == 0 special case)
    #   lat_south_µ°(0, 0) = −85_051_129  (y == 2^0 − 1 special case)
    bbox_min_lon, bbox_min_lat = -180_000_000, -MERCATOR_POLE_UDEG
    bbox_max_lon, bbox_max_lat = +180_000_000, +MERCATOR_POLE_UDEG

    tile_count = 1
    index_offset = HEADER_SIZE                                   # § 4.11 fixes this at 292
    tile_blob_start = index_offset + tile_count * INDEX_ENTRY_SIZE  # 312 (already 4-aligned)
    tile_offset = tile_blob_start                                # 312
    tile_length = len(TILE_BYTES)                                # 64 (already 4-aligned)
    extensions_offset = tile_offset + tile_length                # 376
    file_size = extensions_offset + CRC_SIZE                     # 380; § 4.13: no exts ⇒ ext_off == file_size − 4

    zoom_offsets = bytearray(24 * 8)
    struct.pack_into("<II", zoom_offsets, 0, index_offset, tile_count)   # zoom 0 only

    header = bytearray(HEADER_SIZE)
    struct.pack_into("<4sBB2x", header, 0,
                     MAGIC, FORMAT_VERSION_MAJOR, FORMAT_VERSION_MINOR)   # 0..8 incl. reserved_v1_0
    header[8:24]  = PACK_UUID
    header[24:40] = SUPERSEDES_UUID
    header[40:56] = PARENT_UUID
    struct.pack_into("<BBBBHBB", header, 56,
                     PIXEL_FORMAT_ABGR2222,
                     PROJECTION_WEBMERCATOR,
                     ADDRESSING_QUADTREE,
                     AXIS_XYZ,
                     TILE_DIM_PX,
                     0,    # zoom_min
                     0)    # zoom_max
    struct.pack_into("<iiii", header, 64,
                     bbox_min_lon, bbox_min_lat, bbox_max_lon, bbox_max_lat)
    struct.pack_into("<Q", header, 80, BUILD_TIMESTAMP)
    struct.pack_into("<II", header, 88, tile_count, index_offset)
    header[96:96 + 24 * 8] = bytes(zoom_offsets)
    struct.pack_into("<I", header, 288, extensions_offset)

    index_entry = struct.pack(
        "<BBBBIIII",
        0,                  # z
        COMPRESSION_NONE,
        0,                  # flags (§ 5.2: must be 0 in v1)
        0,                  # reserved (§ 5.2: must be 0)
        0,                  # x
        0,                  # y
        tile_offset,
        tile_length,
    )

    body = bytes(header) + index_entry + TILE_BYTES
    assert len(body) == file_size - CRC_SIZE, (len(body), file_size - CRC_SIZE)
    crc = zlib.crc32(body) & 0xFFFFFFFF                          # § 10 CRC-32/ISO-HDLC
    return body + struct.pack("<I", crc)


def build_hashes(pack: bytes) -> str:
    """Per-tile hash table per § 14.5: one line `<z> <x> <y> <sha256-hex>`."""
    tile_offset = HEADER_SIZE + INDEX_ENTRY_SIZE
    tile_length = TILE_DIM_PX * TILE_DIM_PX
    tile = pack[tile_offset:tile_offset + tile_length]
    digest = hashlib.sha256(tile).hexdigest()
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
            "Minimum-legal non-empty pack: 1 tile at (0,0,0), 8×8 px, "
            "WebMercator/Quadtree/XYZ, no extension sections."
        ),
        "spec_refs": ["§ 4.13", "§ 8.6", "§ 14.3"],
        "expected_outcome": "accept",
        "pack_sha256": hashlib.sha256(pack).hexdigest(),
        "hashes_path": f"golden/{NAME}.hashes",
        "hashes_sha256": hashlib.sha256(hashes.encode("utf-8")).hexdigest(),
    }
