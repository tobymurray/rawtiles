"""golden-png-to-pack-5tiles.rawtiles — § 14.5 multi-tile PNG → pack fixture.

A 5-tile pack covering z=0..1 (1 + 4 = 5 tiles, full coverage at each
zoom), WebMercator/Quadtree/XYZ, 4×4 px per tile. Each tile carries a
distinct RGB888 input that the canonical § 9.1.1 quantiser maps to
ABGR2222 byte content, so the .hashes table contains 5 distinct
SHA-256 digests — exercising the multi-tile quantiser path that the
1-tile fixture cannot.

Per-tile RGB888 inputs (4×4 = 16 pixels each):

  - (z=0, x=0, y=0): the § 14.4 test vector (the documented 48-byte
    input ↔ 16-byte output reference pair). Pins the quantiser against
    the spec's published values.
  - (z=1, x=0, y=0): solid red       (255,   0,   0) → quantises to 0xC3
  - (z=1, x=0, y=1): solid green     (  0, 255,   0) → 0xCC
  - (z=1, x=1, y=0): solid blue      (  0,   0, 255) → 0xF0
  - (z=1, x=1, y=1): solid white     (255, 255, 255) → 0xFF

The four z=1 tiles are uniform-color so each tile's content reduces to
a single byte; distinct fills give distinct .hashes. The z=0 tile
recycles the § 14.4 test vector verbatim, sharing the 1-tile fixture's
quantiser self-test.

§ 14.1 note. The PNG decode step is writer-implementation-specific and
out of scope for this corpus. This fixture commits the post-decode
RGB888 inputs and the canonical-quantiser ABGR2222 outputs; the upstream
PNG → RGB888 pipeline is a producing writer's responsibility.

Layout (476 bytes):
  - 0..292    header (zoom_min = 0, zoom_max = 1)
  - 292..312  index entry 0 (z=0, x=0, y=0)
  - 312..332  index entry 1 (z=1, x=0, y=0)
  - 332..352  index entry 2 (z=1, x=0, y=1)
  - 352..372  index entry 3 (z=1, x=1, y=0)
  - 372..392  index entry 4 (z=1, x=1, y=1)
  - 392..408  tile blob: 5 × 16-byte tiles, contiguous, no per-tile pad
  - 472..476  CRC
extensions_offset = 472.

zoom_offsets[0] = (292, 1); zoom_offsets[1] = (312, 4); 2..23 = (0, 0).
"""

from __future__ import annotations

import hashlib
import struct
import zlib

from . import golden_png_to_pack_1tile as _g1
from . import golden_smallest as g

NAME = "golden-png-to-pack-5tiles"
KIND = "golden"

TILE_DIM_PX = 4
TILE_LENGTH = TILE_DIM_PX * TILE_DIM_PX                       # 16

PACK_UUID = hashlib.sha256(b"rawtiles-conformance:golden-png-to-pack-5tiles:v1").digest()[:16]


def _rgb888_solid(r: int, g_: int, b: int) -> bytes:
    return bytes([r, g_, b]) * (TILE_DIM_PX * TILE_DIM_PX)


# Per-tile RGB888 inputs (16 pixels × 3 bytes = 48 bytes each).
_INPUTS_RGB888 = {
    (0, 0, 0): _g1._TEST_VECTOR_RGB888,                       # § 14.4 reference
    (1, 0, 0): _rgb888_solid(255,   0,   0),                  # red
    (1, 0, 1): _rgb888_solid(  0, 255,   0),                  # green
    (1, 1, 0): _rgb888_solid(  0,   0, 255),                  # blue
    (1, 1, 1): _rgb888_solid(255, 255, 255),                  # white
}


def _coords_sorted():
    """§ 5.2 ascending (z, x, y)."""
    yield (0, 0, 0)
    for x in range(2):
        for y in range(2):
            yield (1, x, y)


# Build per-tile ABGR2222 bytes via the canonical quantiser (reused from
# the 1-tile fixture so the quantiser self-test exercises this fixture too).
_TILE_BYTES = {
    coord: _g1._quantise_rgb888_to_abgr2222(_INPUTS_RGB888[coord])
    for coord in _INPUTS_RGB888
}

# Self-test: each z=1 tile is uniform-color, so quantised bytes are 16 copies
# of the expected single-pixel byte.
assert _TILE_BYTES[(1, 0, 0)] == bytes([0xC3]) * 16
assert _TILE_BYTES[(1, 0, 1)] == bytes([0xCC]) * 16
assert _TILE_BYTES[(1, 1, 0)] == bytes([0xF0]) * 16
assert _TILE_BYTES[(1, 1, 1)] == bytes([0xFF]) * 16


def build_pack() -> bytes:
    # z=0 (0, 0) alone covers the full world; bbox collapses to canonical
    # full-world endpoints (same as golden-grid at z=2 etc.).
    bbox = (-180_000_000, -g.MERCATOR_POLE_UDEG, +180_000_000, +g.MERCATOR_POLE_UDEG)

    coords = list(_coords_sorted())
    tile_count = len(coords)                                  # 5

    index_offset = g.HEADER_SIZE                              # 292
    tile_blob_start = index_offset + tile_count * g.INDEX_ENTRY_SIZE  # 392
    extensions_offset = tile_blob_start + tile_count * TILE_LENGTH    # 472
    file_size = extensions_offset + g.CRC_SIZE                # 476

    zoom_offsets = bytearray(24 * 8)
    struct.pack_into("<II", zoom_offsets, 0 * 8, index_offset, 1)     # zoom 0
    struct.pack_into("<II", zoom_offsets, 1 * 8, index_offset + 20, 4)  # zoom 1

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
                     0, 1)     # zoom_min, zoom_max
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
    for coord in coords:
        blob_buf.extend(_TILE_BYTES[coord])

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
            "5-tile WebMercator/Quadtree/XYZ pack at z=0..1 (1 + 4 tiles, "
            "4×4 px each). The z=0 tile uses § 14.4's RGB888 test vector; "
            "the four z=1 tiles are solid red/green/blue/white. All tiles "
            "are quantised via § 9.1.1 from RGB888 inputs embedded in the "
            "generator module. Pairs with golden-png-to-pack-1tile to "
            "exercise the multi-tile quantiser path. File size 476 bytes."
        ),
        "spec_refs": ["§ 9.1.1", "§ 14.3", "§ 14.4", "§ 14.5"],
        "expected_outcome": "accept",
        "pack_sha256": hashlib.sha256(pack).hexdigest(),
        "hashes_path": f"golden/{NAME}.hashes",
        "hashes_sha256": hashlib.sha256(hashes.encode("utf-8")).hexdigest(),
    }
