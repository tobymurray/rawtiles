"""golden-grid.rawtiles — § 14.3 "largest single-zoom layout".

A regular full grid at z = 2: 16 tiles at (z=2, x∈[0,3], y∈[0,3]), full
WebMercator world coverage. 8×8 px per tile (64 bytes), 16 tiles in the
blob, total file size 1640 bytes.

This is the first multi-tile fixture in the corpus. It exercises:

  - Multi-entry tile index sorted ascending by (z, x, y) per § 5.2.
  - zoom_offsets[24] with a non-trivial count (zoom_offsets[2] = (292, 16);
    zoom_offsets[0..1, 3..23] = (0, 0)).
  - Multi-row .hashes file per § 14.5, distinguishing 16 tiles that a
    reader's lookup MUST return individually.
  - Canonical bbox derivation per § 4.9 with multiple tiles contributing.

Each tile is filled with a single distinct byte: `0xC0 | ((y << 3) | x)`.
The 0xC0 mask keeps alpha = 3 (opaque, per § 9.1); the low 6 bits encode
(y, x) so all 16 tiles have distinct fill values, and therefore distinct
SHA-256 digests in the .hashes table — a reader returning the wrong tile
for any lookup will fail the § 14.5 check.
"""

from __future__ import annotations

import hashlib
import struct
import zlib

from . import golden_smallest as g

NAME = "golden-grid"
KIND = "golden"

TILE_DIM_PX = 8
ZOOM = 2
GRID_N = 1 << ZOOM                           # 4 tiles per side
TILES_PER_PACK = GRID_N * GRID_N             # 16
TILE_LENGTH = TILE_DIM_PX * TILE_DIM_PX      # 64 bytes per tile

PACK_UUID = hashlib.sha256(b"rawtiles-conformance:golden-grid:v1").digest()[:16]


def _tile_fill(x: int, y: int) -> int:
    # A = 3 (top 2 bits = 11 → 0xC0 mask). Low 6 bits encode (y, x): unique
    # per (x, y) for x, y ∈ [0, 3], so each tile has a distinct fill byte
    # and therefore a distinct SHA-256.
    return 0xC0 | ((y << 3) | x)


def _tile_bytes(x: int, y: int) -> bytes:
    return bytes([_tile_fill(x, y)]) * TILE_LENGTH


def _coords_sorted():
    """Yield (z, x, y) in § 5.2 ascending order: z non-decreasing across
    entries; within each z, (x, y) strictly ascending lexicographically."""
    z = ZOOM
    for x in range(GRID_N):
        for y in range(GRID_N):
            yield (z, x, y)


def build_pack() -> bytes:
    # Canonical bbox for a full grid at z = ZOOM covers the whole WebMercator
    # world; the formulas of § 4.9 collapse to the same special-case endpoints
    # used by golden-smallest at z = 0.
    bbox = (-180_000_000, -g.MERCATOR_POLE_UDEG, +180_000_000, +g.MERCATOR_POLE_UDEG)

    tile_count = TILES_PER_PACK
    index_offset = g.HEADER_SIZE                                       # 292
    tile_blob_start = index_offset + tile_count * g.INDEX_ENTRY_SIZE   # 612
    extensions_offset = tile_blob_start + tile_count * TILE_LENGTH     # 1636
    file_size = extensions_offset + g.CRC_SIZE                          # 1640

    zoom_offsets = bytearray(24 * 8)
    struct.pack_into("<II", zoom_offsets, ZOOM * 8, index_offset, tile_count)

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
                     ZOOM,   # zoom_min = actual minimum z in tile-index
                     ZOOM)   # zoom_max = actual maximum z in tile-index
    struct.pack_into("<iiii", header, 64, *bbox)
    struct.pack_into("<Q", header, 80, g.BUILD_TIMESTAMP)
    struct.pack_into("<II", header, 88, tile_count, index_offset)
    header[96:96 + 24 * 8] = bytes(zoom_offsets)
    struct.pack_into("<I", header, 288, extensions_offset)

    index_buf = bytearray()
    for i, (z, x, y) in enumerate(_coords_sorted()):
        entry_offset = tile_blob_start + i * TILE_LENGTH
        index_buf.extend(struct.pack(
            "<BBBBIIII",
            z, g.COMPRESSION_NONE, 0, 0,
            x, y,
            entry_offset, TILE_LENGTH,
        ))

    blob_buf = bytearray()
    for (_z, x, y) in _coords_sorted():
        blob_buf.extend(_tile_bytes(x, y))

    body = bytes(header) + bytes(index_buf) + bytes(blob_buf)
    assert len(body) == file_size - g.CRC_SIZE, (len(body), file_size - g.CRC_SIZE)
    crc = zlib.crc32(body) & 0xFFFFFFFF
    return body + struct.pack("<I", crc)


def build_hashes(pack: bytes) -> str:
    lines = [
        "# rawtiles per-tile hash table, § 14.5",
        "# format: <z> <x> <y> <sha256-hex>",
    ]
    tile_blob_start = g.HEADER_SIZE + TILES_PER_PACK * g.INDEX_ENTRY_SIZE
    for i, (z, x, y) in enumerate(_coords_sorted()):
        off = tile_blob_start + i * TILE_LENGTH
        tile = pack[off:off + TILE_LENGTH]
        digest = hashlib.sha256(tile).hexdigest()
        lines.append(f"{z} {x} {y} {digest}")
    return "\n".join(lines) + "\n"


def manifest_entry(pack: bytes, hashes: str) -> dict:
    return {
        "name": NAME,
        "kind": "golden",
        "path": f"golden/{NAME}.rawtiles",
        "description": (
            f"Regular {GRID_N}×{GRID_N} grid at z={ZOOM} "
            f"({TILES_PER_PACK} tiles, {TILE_DIM_PX}×{TILE_DIM_PX} px each), "
            "full WebMercator world coverage; no extension sections."
        ),
        "spec_refs": ["§ 4.12", "§ 5.2", "§ 14.3", "§ 14.5"],
        "expected_outcome": "accept",
        "pack_sha256": hashlib.sha256(pack).hexdigest(),
        "hashes_path": f"golden/{NAME}.hashes",
        "hashes_sha256": hashlib.sha256(hashes.encode("utf-8")).hexdigest(),
    }
