"""golden-pyramid.rawtiles — § 14.5 named "multi-zoom" fixture.

A WebMercator/Quadtree/XYZ pack carrying a full pyramid for zooms 0..2:
1 tile at z=0, 4 tiles at z=1, 16 tiles at z=2 — 21 tiles total. The
fixture exercises:

  - § 5.2 multi-zoom tile-index ordering (z non-decreasing across all
    entries; within each z, (x, y) strictly ascending lexicographically).
  - § 4.12 zoom_offsets directory with three populated slots
    (`zoom_offsets[0..2]`) AND 21 unpopulated slots (`zoom_offsets[3..23]
    = (0, 0)`). This is the only v1 fixture exercising more than one
    populated slot.
  - § 5.3 multi-level binary search: a reader looking up `(z, x, y)` MUST
    enter `zoom_offsets[z]` first, then binary-search within the
    `count`-entry sub-range. golden-pyramid pins this path with three
    populated zooms whose sub-ranges differ in size (1, 4, 16).
  - § 14.5 multi-row .hashes table with 21 distinct entries.

Tile fill: `byte = 0xC0 | (z << 4) | (y << 2) | x`. A=3 (opaque, § 9.1).
Bits 4..5 carry z (range [0, 2]), bits 2..3 carry y (range [0, 3]), and
bits 0..1 carry x (range [0, 3]). The encoding is injective on the
21-element (z, x, y) set, so every tile has a distinct fill byte and
therefore a distinct SHA-256 in the .hashes file. The full set of fill
bytes spans 0xC0..0xEF (with gaps at z=0 and z=1 levels where (x, y)
don't fill the 4×4 range).

bbox per § 4.9: z=0 tile (0, 0, 0) alone covers the full WebMercator
world; higher-z tiles are subsets. Canonical full-world endpoints apply.

Pack layout: 292 (header) + 21·20 (index) + 21·64 (blob) + 4 (CRC)
= 292 + 420 + 1344 + 4 = 2060 bytes. extensions_offset = 2056.
"""

from __future__ import annotations

import hashlib
import struct
import zlib

from . import golden_smallest as g

NAME = "golden-pyramid"
KIND = "golden"

TILE_DIM_PX = 8
TILE_LENGTH = TILE_DIM_PX * TILE_DIM_PX                       # 64
ZOOM_MIN = 0
ZOOM_MAX = 2

PACK_UUID = hashlib.sha256(b"rawtiles-conformance:golden-pyramid:v1").digest()[:16]


def _coords_sorted():
    """Yield (z, x, y) in § 5.2 ascending order (z outer, then (x, y) lex)."""
    for z in range(ZOOM_MIN, ZOOM_MAX + 1):
        n = 1 << z
        for x in range(n):
            for y in range(n):
                yield (z, x, y)


def _tile_fill(z: int, x: int, y: int) -> int:
    # A=3 (top 2 bits, 0xC0 mask). Lower 6 bits pack (z, y, x) so every
    # (z, x, y) triple in {0..3, 0..3, 0..3} yields a distinct byte.
    return 0xC0 | (z << 4) | (y << 2) | x


def _tile_bytes(z: int, x: int, y: int) -> bytes:
    return bytes([_tile_fill(z, x, y)]) * TILE_LENGTH


def build_pack() -> bytes:
    # Canonical full-world bbox: z=0 tile (0, 0, 0) anchors it; higher-z
    # tiles are subsets that don't expand the union.
    bbox = (-180_000_000, -g.MERCATOR_POLE_UDEG, +180_000_000, +g.MERCATOR_POLE_UDEG)

    coords = list(_coords_sorted())
    tile_count = len(coords)                                  # 1 + 4 + 16 = 21

    index_offset = g.HEADER_SIZE                              # 292
    tile_blob_start = index_offset + tile_count * g.INDEX_ENTRY_SIZE  # 712
    extensions_offset = tile_blob_start + tile_count * TILE_LENGTH    # 2056
    file_size = extensions_offset + g.CRC_SIZE                 # 2060

    # Build zoom_offsets[24] with three populated slots. Walk the sorted
    # coord list once, recording the byte offset and count for each z.
    zoom_offsets = bytearray(24 * 8)
    running_byte = index_offset
    for z in range(ZOOM_MIN, ZOOM_MAX + 1):
        count_at_z = (1 << z) ** 2
        struct.pack_into("<II", zoom_offsets, z * 8, running_byte, count_at_z)
        running_byte += count_at_z * g.INDEX_ENTRY_SIZE
    # zoom_offsets[ZOOM_MAX+1 .. 23] stay zeroed.

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
                     ZOOM_MIN,
                     ZOOM_MAX)
    struct.pack_into("<iiii", header, 64, *bbox)
    struct.pack_into("<Q", header, 80, g.BUILD_TIMESTAMP)
    struct.pack_into("<II", header, 88, tile_count, index_offset)
    header[96:96 + 24 * 8] = bytes(zoom_offsets)
    struct.pack_into("<I", header, 288, extensions_offset)

    index_buf = bytearray()
    for i, (z, x, y) in enumerate(coords):
        entry_offset = tile_blob_start + i * TILE_LENGTH
        index_buf.extend(struct.pack(
            "<BBBBIIII",
            z, g.COMPRESSION_NONE, 0, 0,
            x, y, entry_offset, TILE_LENGTH,
        ))

    blob_buf = bytearray()
    for (z, x, y) in coords:
        blob_buf.extend(_tile_bytes(z, x, y))

    body = bytes(header) + bytes(index_buf) + bytes(blob_buf)
    assert len(body) == file_size - g.CRC_SIZE
    crc = zlib.crc32(body) & 0xFFFFFFFF
    return body + struct.pack("<I", crc)


def build_hashes(pack: bytes) -> str:
    lines = [
        "# rawtiles per-tile hash table, § 14.5",
        "# format: <z> <x> <y> <sha256-hex>",
    ]
    coords = list(_coords_sorted())
    tile_blob_start = g.HEADER_SIZE + len(coords) * g.INDEX_ENTRY_SIZE
    for i, (z, x, y) in enumerate(coords):
        off = tile_blob_start + i * TILE_LENGTH
        digest = hashlib.sha256(pack[off:off + TILE_LENGTH]).hexdigest()
        lines.append(f"{z} {x} {y} {digest}")
    return "\n".join(lines) + "\n"


def manifest_entry(pack: bytes, hashes: str) -> dict:
    return {
        "name": NAME,
        "kind": "golden",
        "path": f"golden/{NAME}.rawtiles",
        "description": (
            "Full pyramid for zooms 0..2: 1 + 4 + 16 = 21 tiles at 8×8 px each, "
            "WebMercator/Quadtree/XYZ, no extension sections. Exercises § 5.2 "
            "multi-zoom tile-index ordering, § 4.12 zoom_offsets with three "
            "populated slots, § 5.3 multi-level binary search, and § 14.5 "
            "multi-row .hashes table."
        ),
        "spec_refs": ["§ 4.12", "§ 5.2", "§ 5.3", "§ 14.3", "§ 14.5"],
        "expected_outcome": "accept",
        "pack_sha256": hashlib.sha256(pack).hexdigest(),
        "hashes_path": f"golden/{NAME}.hashes",
        "hashes_sha256": hashlib.sha256(hashes.encode("utf-8")).hexdigest(),
    }
