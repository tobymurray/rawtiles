"""golden-png-to-pack-1tile.rawtiles — § 14.5 named PNG → pack fixture.

A 1-tile pack whose tile bytes are the § 14.4 ABGR2222 quantiser test
vector. Pack shape: 4×4 px tile (16 pixels = 16 bytes per tile, matching
the test vector's length exactly), WebMercator/Quadtree/XYZ, at (z=0,
x=0, y=0).

Scope. § 14.1 explicitly says the spec does NOT prescribe a PNG decode /
resample / alpha-handling pipeline — that pipeline is part of each
writer's documented deterministic surface (§ A.4). What the spec DOES
pin, byte-exactly, is the RGB888 → ABGR2222 quantiser of § 9.1.1, via
the test vector in § 14.4. This fixture therefore embeds § 14.4's 48-byte
RGB888 input as a Python constant, applies the canonical quantiser, and
asserts the result matches § 14.4's expected 16-byte output before any
byte goes on disk. The "PNG" in the fixture name refers to the upstream
pipeline a producing writer would invoke; the corpus consumer treats the
committed RGB888 input as the canonical post-decode output.

§ 9.1.1 quantiser. Each 8-bit channel maps to a 2-bit quantum via:

  Input range    Output quantum  Displayed level
  ────────────   ──────────────  ───────────────
   0 – 42              0              0
  43 – 127             1             85
  128 – 212            2            170
  213 – 255            3            255

The boundaries (42|43, 127|128, 212|213) are the midpoints between the
displayed levels (rounded toward the lower midpoint where ties occur).
Writers MUST produce byte-identical output across architectures, so the
mapping is implemented as a pure integer comparison chain.

A 1-tile pack at (z=0, x=0, y=0) gives the same canonical full-world
WebMercator bbox as golden-smallest. File size 332 bytes:
292 (header) + 20 (index) + 16 (tile) + 4 (CRC).
"""

from __future__ import annotations

import hashlib
import struct
import zlib

from . import golden_smallest as g

NAME = "golden-png-to-pack-1tile"
KIND = "golden"

TILE_DIM_PX = 4                                               # 16 pixels = § 14.4 vector length
TILE_LENGTH = TILE_DIM_PX * TILE_DIM_PX                       # 16

PACK_UUID = hashlib.sha256(b"rawtiles-conformance:golden-png-to-pack-1tile:v1").digest()[:16]


# § 14.4 ABGR2222 quantiser test vector: 16 input pixels as RGB888 (48 bytes).
# Pixels are in row-major order, left-to-right within each row.
_TEST_VECTOR_RGB888 = bytes([
    # row 0
    255,   0,   0,    0, 255,   0,    0,   0, 255,    255, 255, 255,
    # row 1
    128,   0,   0,    0, 128,   0,    0,   0, 128,    128, 128, 128,
    # row 2
     42,  42,  42,   43,  43,  43,   85,  85,  85,    127, 127, 127,
    # row 3
    170, 170, 170,  212, 212, 212,  213, 213, 213,    255, 128,   0,
])
assert len(_TEST_VECTOR_RGB888) == 48

# § 14.4 expected ABGR2222 output. The self-test below verifies our quantiser
# reproduces this byte-for-byte before any pack is emitted.
_TEST_VECTOR_ABGR2222 = bytes([
    0xC3, 0xCC, 0xF0, 0xFF,
    0xC2, 0xC8, 0xE0, 0xEA,
    0xC0, 0xD5, 0xD5, 0xD5,
    0xEA, 0xEA, 0xFF, 0xCB,
])
assert len(_TEST_VECTOR_ABGR2222) == 16


def _quantise_channel(c8: int) -> int:
    """§ 9.1.1 RGB888 → 2-bit quantum via integer-only midpoint thresholds."""
    if c8 <= 42:
        return 0
    if c8 <= 127:
        return 1
    if c8 <= 212:
        return 2
    return 3


def _quantise_rgb888_to_abgr2222(rgb888: bytes) -> bytes:
    """Apply § 9.1.1 to a flat RGB888 byte stream, producing one ABGR2222 byte
    per RGB triple. A=3 (opaque, § 9.1 v1 requirement) is set unconditionally."""
    assert len(rgb888) % 3 == 0
    out = bytearray(len(rgb888) // 3)
    for i, pixel_start in enumerate(range(0, len(rgb888), 3)):
        r = _quantise_channel(rgb888[pixel_start])
        g_ = _quantise_channel(rgb888[pixel_start + 1])
        b = _quantise_channel(rgb888[pixel_start + 2])
        out[i] = (3 << 6) | (b << 4) | (g_ << 2) | r
    return bytes(out)


# Self-test: our quantiser must reproduce § 14.4's expected output.
_computed_vector = _quantise_rgb888_to_abgr2222(_TEST_VECTOR_RGB888)
assert _computed_vector == _TEST_VECTOR_ABGR2222, (
    f"quantiser self-test failed: got {_computed_vector.hex()}, "
    f"expected {_TEST_VECTOR_ABGR2222.hex()}"
)

TILE_BYTES = _TEST_VECTOR_ABGR2222


def build_pack() -> bytes:
    bbox = (-180_000_000, -g.MERCATOR_POLE_UDEG, +180_000_000, +g.MERCATOR_POLE_UDEG)

    tile_count = 1
    index_offset = g.HEADER_SIZE                              # 292
    tile_blob_start = index_offset + tile_count * g.INDEX_ENTRY_SIZE  # 312
    tile_offset = tile_blob_start
    extensions_offset = tile_offset + TILE_LENGTH             # 328
    file_size = extensions_offset + g.CRC_SIZE                # 332

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

    body = bytes(header) + index_entry + TILE_BYTES
    assert len(body) == file_size - g.CRC_SIZE
    crc = zlib.crc32(body) & 0xFFFFFFFF
    return body + struct.pack("<I", crc)


def build_hashes(pack: bytes) -> str:
    tile_offset = g.HEADER_SIZE + g.INDEX_ENTRY_SIZE
    digest = hashlib.sha256(pack[tile_offset:tile_offset + TILE_LENGTH]).hexdigest()
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
            "1-tile WebMercator/Quadtree/XYZ pack whose 4×4 tile carries the "
            "§ 14.4 ABGR2222 quantiser test vector exactly: 16 pixels, "
            "16 bytes. The module embeds the § 14.4 RGB888 input + expected "
            "ABGR2222 output as Python constants and asserts the canonical "
            "§ 9.1.1 quantiser reproduces the expected output before any pack "
            "is emitted. The PNG-decode step is writer-implementation-specific "
            "per § 14.1 and is out of scope for the corpus; this fixture pins "
            "the deterministic post-decode RGB888 → ABGR2222 → pack path."
        ),
        "spec_refs": ["§ 9.1.1", "§ 14.3", "§ 14.4", "§ 14.5"],
        "expected_outcome": "accept",
        "pack_sha256": hashlib.sha256(pack).hexdigest(),
        "hashes_path": f"golden/{NAME}.hashes",
        "hashes_sha256": hashlib.sha256(hashes.encode("utf-8")).hexdigest(),
    }
