"""golden-orientation.rawtiles — directional test tile.

A 256×256 single-tile pack whose pixel pattern makes any orientation-pipeline
bug (vertical flip, transpose, axis swap) instantly visible to a renderer.
The byte layout exercises:

  - § 6.2 row-major byte order with row 0 = northernmost under XYZ.
  - § 8.4 XYZ axis convention (Y increases southward).
  - § 9.1 ABGR2222 quantum encoding for the eight saturated palette corners.

The tile is a Mondrian-style frame around a grey interior, with four
asymmetric corner dots inset into the interior. Every region is one of the
nine A=3 ABGR2222 byte values listed below. A consumer that decodes XYZ
backwards (or transposes rows/columns) renders a visibly wrong image; a
consumer that decodes ABGR2222 with the wrong channel order paints the
wrong color into otherwise-correct regions. The two failure modes are
distinguishable by eye.

Pixel regions (rows × cols, 0-indexed; row 0 = north, col 0 = west):

  Edge stripes (16 px thick), painted in this order so the four 16×16
  corners of the frame end up RED (top wins) or BLUE (bottom wins):
    rows   0..15,   cols   0..255 → RED      (top stripe)
    rows 240..255,  cols   0..255 → BLUE     (bottom stripe)
    rows  16..239,  cols   0..15  → GREEN    (left stripe)
    rows  16..239,  cols 240..255 → YELLOW   (right stripe)

  Interior fill:
    rows  16..239,  cols  16..239 → GREY     (mid-level on each channel)

  Corner dots (8×8, inset 8 px from the frame; disambiguate the four
  frame corners which only carry two distinct colors):
    rows  24..31,   cols  24..31  → BLACK    (NW)
    rows  24..31,   cols 224..231 → WHITE    (NE)
    rows 224..231,  cols  24..31  → MAGENTA  (SW)
    rows 224..231,  cols 224..231 → CYAN     (SE)

ABGR2222 palette (one byte per pixel; bit 7..0 = AABBGGRR; A=3 throughout):

    BLACK   = 0xC0   (A=3, B=0, G=0, R=0)
    WHITE   = 0xFF   (A=3, B=3, G=3, R=3)
    RED     = 0xC3   (A=3, B=0, G=0, R=3)
    GREEN   = 0xCC   (A=3, B=0, G=3, R=0)
    BLUE    = 0xF0   (A=3, B=3, G=0, R=0)
    YELLOW  = 0xCF   (A=3, B=0, G=3, R=3)
    MAGENTA = 0xF3   (A=3, B=3, G=0, R=3)
    CYAN    = 0xFC   (A=3, B=3, G=3, R=0)
    GREY    = 0xD5   (A=3, B=1, G=1, R=1)

Pack layout: 1 tile at (z, x, y) = (0, 0, 0), WebMercator/Quadtree/XYZ, no
extension sections. Total file size: 292 + 20 + 65536 + 4 = 65852 bytes.
"""

from __future__ import annotations

import hashlib
import struct
import zlib

from . import golden_smallest as g

NAME = "golden-orientation"
KIND = "golden"

TILE_DIM_PX = 256
TILE_LENGTH = TILE_DIM_PX * TILE_DIM_PX                       # 65536

PACK_UUID = hashlib.sha256(b"rawtiles-conformance:golden-orientation:v1").digest()[:16]


def _abgr2222(a: int, b: int, g_: int, r: int) -> int:
    return (a << 6) | (b << 4) | (g_ << 2) | r


# A=3 throughout (§ 9.1 v1 opacity requirement).
BLACK   = _abgr2222(3, 0, 0, 0)
WHITE   = _abgr2222(3, 3, 3, 3)
RED     = _abgr2222(3, 0, 0, 3)
GREEN   = _abgr2222(3, 0, 3, 0)
BLUE    = _abgr2222(3, 3, 0, 0)
YELLOW  = _abgr2222(3, 0, 3, 3)
MAGENTA = _abgr2222(3, 3, 0, 3)
CYAN    = _abgr2222(3, 3, 3, 0)
GREY    = _abgr2222(3, 1, 1, 1)

STRIPE_PX = 16
DOT_PX = 8
DOT_INSET = STRIPE_PX + 8                                     # 24


def _build_tile_bytes() -> bytes:
    n = TILE_DIM_PX
    buf = bytearray([GREY]) * (n * n)

    def fill(r0: int, r1: int, c0: int, c1: int, color: int) -> None:
        # Inclusive bounds, row-major (§ 6.2): row r occupies [r*n, r*n+n).
        for r in range(r0, r1 + 1):
            base = r * n
            for c in range(c0, c1 + 1):
                buf[base + c] = color

    # Edge stripes. Paint top/bottom full-width first, then left/right in the
    # remaining inner rows — corners of the frame inherit top/bottom color.
    fill(0,             STRIPE_PX - 1,  0,             n - 1,        RED)     # top
    fill(n - STRIPE_PX, n - 1,          0,             n - 1,        BLUE)    # bottom
    fill(STRIPE_PX,     n - STRIPE_PX - 1, 0,          STRIPE_PX - 1, GREEN)  # left
    fill(STRIPE_PX,     n - STRIPE_PX - 1, n - STRIPE_PX, n - 1,      YELLOW) # right

    # Corner dots inside the interior; coordinates documented in module docstring.
    d_lo, d_hi = DOT_INSET, DOT_INSET + DOT_PX - 1
    far_lo, far_hi = n - 1 - d_hi, n - 1 - d_lo
    fill(d_lo,   d_hi,   d_lo,   d_hi,   BLACK)               # NW
    fill(d_lo,   d_hi,   far_lo, far_hi, WHITE)               # NE
    fill(far_lo, far_hi, d_lo,   d_hi,   MAGENTA)             # SW
    fill(far_lo, far_hi, far_lo, far_hi, CYAN)                # SE

    return bytes(buf)


def build_pack() -> bytes:
    # Single tile at (0, 0, 0): canonical full-world WebMercator bbox per § 4.9
    # (same special-case endpoints as golden-smallest).
    bbox = (-180_000_000, -g.MERCATOR_POLE_UDEG, +180_000_000, +g.MERCATOR_POLE_UDEG)

    tile_bytes = _build_tile_bytes()
    assert len(tile_bytes) == TILE_LENGTH

    tile_count = 1
    index_offset = g.HEADER_SIZE                                            # 292
    tile_blob_start = index_offset + tile_count * g.INDEX_ENTRY_SIZE        # 312
    tile_offset = tile_blob_start
    extensions_offset = tile_offset + TILE_LENGTH                           # 65848
    file_size = extensions_offset + g.CRC_SIZE                              # 65852

    zoom_offsets = bytearray(24 * 8)
    struct.pack_into("<II", zoom_offsets, 0, index_offset, tile_count)      # zoom 0 only

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
        0, 0,                                                                # x, y
        tile_offset,
        TILE_LENGTH,
    )

    body = bytes(header) + index_entry + tile_bytes
    assert len(body) == file_size - g.CRC_SIZE, (len(body), file_size - g.CRC_SIZE)
    crc = zlib.crc32(body) & 0xFFFFFFFF
    return body + struct.pack("<I", crc)


def build_hashes(pack: bytes) -> str:
    tile_offset = g.HEADER_SIZE + g.INDEX_ENTRY_SIZE                        # 312
    tile = pack[tile_offset:tile_offset + TILE_LENGTH]
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
            "1-tile WebMercator pack, 256×256 px, carrying a directional test "
            "pattern: RED/BLUE/GREEN/YELLOW 16-px edge stripes (top/bottom/"
            "left/right under XYZ), GREY interior, and 8×8 BLACK/WHITE/MAGENTA/"
            "CYAN corner dots (NW/NE/SW/SE) inset 8 px from the frame. The "
            "asymmetric pattern makes any vertical flip, transpose, or "
            "ABGR2222 channel-order bug visible by eye when the tile is "
            "rendered. Exercises § 6.2 row-major byte order, § 8.4 XYZ axis "
            "convention, and § 9.1 ABGR2222 saturated-palette encoding."
        ),
        "spec_refs": ["§ 6.2", "§ 8.4", "§ 9.1", "§ 14.3", "§ 14.5"],
        "expected_outcome": "accept",
        "pack_sha256": hashlib.sha256(pack).hexdigest(),
        "hashes_path": f"golden/{NAME}.hashes",
        "hashes_sha256": hashlib.sha256(hashes.encode("utf-8")).hexdigest(),
    }
