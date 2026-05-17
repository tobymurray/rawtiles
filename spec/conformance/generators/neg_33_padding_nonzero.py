"""neg-33-padding-nonzero.rawtiles — violates § 11 #33.

Targets: "Reject the pack if any per-tile alignment padding byte in the
tile blob (§ 6.1) is non-zero."

Custom build: a 1-tile pack with `tile_dim_px = 3`. Tile length = 9 bytes
(`pixel_format = ABGR2222`, `length = tile_dim_px² = 9`, satisfying rule
#16). Since 9 is not a multiple of 4, the next 4-aligned position is 12
bytes after the tile start — so 3 padding bytes follow the tile to align
`extensions_offset`. One of those pad bytes is set to 0xFF, the lone
violation.

This is the only v1 fixture exercising a non-4-aligned tile length, and
therefore the only fixture in which `padded_length(i) > length(i)`. Every
other corpus pack uses `tile_dim_px = 8` (length 64, already aligned).

Layout (328 bytes):
  - 0..292    header (WebMercator/Quadtree/XYZ; tile_dim_px = 3)
  - 292..312  tile-index entry (z=x=y=0, offset=312, length=9)
  - 312..321  tile bytes (9 × 0xFF — opaque white)
  - 321..324  per-tile alignment padding (3 bytes; § 6.1)
              byte 321 = 0xFF   ← rule #33 violation
              bytes 322..324 = 0x00
  - 324..328  CRC
extensions_offset = 324 = 312 + padded_length(9) = 312 + 12.

The non-zero pad byte is the lone violation. Rules to consider:
  - #16 (length = tile_dim²): 9 = 3 × 3. Quiet.
  - #14 (offset/length bounds): offset 312 = tile_blob_start; length 9 <
    extensions_offset − offset = 12. Quiet.
  - #18 (extensions_offset = tile_blob_start + Σ padded_length): 312 + 12
    = 324 = extensions_offset. Quiet.
  - #19 (extension framing): no extension sections. Quiet.
"""

from __future__ import annotations

import hashlib
import struct
import zlib

from . import golden_smallest as g

NAME = "neg-33-padding-nonzero"
KIND = "negative"
DERIVED_FROM = "golden-smallest"
MUTATION = (
    "Built from scratch in the shape of golden-smallest but with "
    "tile_dim_px = 3 (so tile length = 9 is not 4-aligned and 3 padding "
    "bytes follow the tile in the blob). The first per-tile pad byte at "
    "file offset 321 is set to 0xFF; the other 2 pad bytes remain 0x00. "
    "file_size 328; CRC fresh."
)

TILE_DIM_PX = 3
TILE_LENGTH = TILE_DIM_PX * TILE_DIM_PX                       # 9
PAD_LENGTH = (-TILE_LENGTH) % 4                               # 3

PACK_UUID = hashlib.sha256(b"rawtiles-conformance:neg-33-padding-nonzero:v1").digest()[:16]

TILE_BYTES = bytes([0xFF]) * TILE_LENGTH                      # opaque white (§ 9.1)


def build_pack() -> bytes:
    bbox = (-180_000_000, -g.MERCATOR_POLE_UDEG, +180_000_000, +g.MERCATOR_POLE_UDEG)

    tile_count = 1
    index_offset = g.HEADER_SIZE                              # 292
    tile_blob_start = index_offset + tile_count * g.INDEX_ENTRY_SIZE  # 312
    tile_offset = tile_blob_start
    extensions_offset = tile_offset + TILE_LENGTH + PAD_LENGTH         # 324
    file_size = extensions_offset + g.CRC_SIZE                # 328

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
        0, 0, tile_offset, TILE_LENGTH,
    )

    # Per-tile alignment padding: first byte 0xFF (the violation), rest 0x00.
    padding = bytes([0xFF]) + bytes(PAD_LENGTH - 1)

    body = bytes(header) + index_entry + TILE_BYTES + padding
    assert len(body) == file_size - g.CRC_SIZE
    crc = zlib.crc32(body) & 0xFFFFFFFF
    return body + struct.pack("<I", crc)


def manifest_entry(pack: bytes, hashes: str | None = None) -> dict:
    return {
        "name": NAME,
        "kind": "negative",
        "path": f"negative/{NAME}.rawtiles",
        "description": (
            "1-tile Quadtree pack with tile_dim_px = 3 (length = 9, requiring "
            "3 per-tile pad bytes to 4-align extensions_offset). The first "
            "pad byte at file offset 321 is set to 0xFF, violating § 6.1's "
            "zero-fill requirement. file_size 328."
        ),
        "spec_refs": ["§ 6.1"],
        "expected_outcome": "reject",
        "pack_sha256": hashlib.sha256(pack).hexdigest(),
        "expected_reject_rule": {
            "rule_number": "33",
            "summary": (
                "per-tile alignment padding bytes in the tile blob MUST be 0x00 "
                "(§ 6.1 + § 11 #33)"
            ),
        },
        "derived_from": DERIVED_FROM,
        "mutation": MUTATION,
    }
