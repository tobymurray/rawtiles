"""golden-orientation-mosaic.rawtiles — directional 4×4 tile mosaic.

A regular full grid at z = 2 (16 tiles, 32×32 px each) carrying intra-tile
orientation markers plus a position-encoded interior color per (x, y). The
fixture catches inter-tile placement bugs (x/y swap, row inversion, tile
mis-addressing) that `golden-orientation` cannot see, and `golden-grid`
records only via .hashes byte-equality rather than visually.

Each tile (regardless of (x, y)) carries the same intra-tile orientation
pattern, scaled from `golden-orientation`:

  - 4-px edge stripes — top RED, bottom BLUE, left GREEN, right YELLOW
    (paint order: top/bottom full-width first, then left/right in inner
    rows; so the four 4×4 frame corners are RED at the top, BLUE at the
    bottom).
  - 1-px corner dots overlaid at the four extreme corner pixels —
    NW BLACK, NE WHITE, SW MAGENTA, SE CYAN.

The 24×24 interior of each tile is filled with a position-encoded byte:

    byte(x, y) = 0xD0 + (y << 2) + x        # ∈ [0xD0, 0xDF]

The 0xDx range (A=3, B=1, varying G/R) is disjoint from the stripe and
corner-dot palette ({0xC0, 0xC3, 0xCC, 0xCF, 0xF0, 0xF3, 0xFC, 0xFF}), so
the 16 tile-id colors are visually distinct from the frame they sit inside.

In the composed 128×128 mosaic (under XYZ, row 0 = north):

  - The 16 interior colors march 0xD0..0xDF in row-major order: 0xD0 is
    the NW tile, 0xDF is the SE tile. Any vertical flip, transpose, or
    x/y swap rearranges that ramp visibly.
  - Every interior tile-tile seam shows an 8-px-thick paired stripe band:
    horizontal seams BLUE-over-RED (4 px each), vertical seams YELLOW-
    next-to-GREEN. A consumer that flips the mosaic gets RED-over-BLUE
    horizontal seams (visibly inverted).
  - Each tile's NW corner pixel is BLACK; in the composite, the 16 BLACK
    dots form a regular 4×4 lattice. Misplacement breaks the lattice.

Pack layout: 16 tiles at z = 2, WebMercator/Quadtree/XYZ, no extension
sections. Tile-index entries are sorted by (z, x, y) per § 5.2. Total file
size: 292 (header) + 16·20 (index) + 16·1024 (blob) + 4 (CRC) = 17000 bytes.
"""

from __future__ import annotations

import hashlib
import struct
import zlib

from . import golden_smallest as g

NAME = "golden-orientation-mosaic"
KIND = "golden"

TILE_DIM_PX = 32
ZOOM = 2
GRID_N = 1 << ZOOM                                            # 4 tiles per side
TILES_PER_PACK = GRID_N * GRID_N                              # 16
TILE_LENGTH = TILE_DIM_PX * TILE_DIM_PX                       # 1024

PACK_UUID = hashlib.sha256(b"rawtiles-conformance:golden-orientation-mosaic:v1").digest()[:16]


def _abgr2222(a: int, b: int, g_: int, r: int) -> int:
    return (a << 6) | (b << 4) | (g_ << 2) | r


# A=3 throughout (§ 9.1).
BLACK   = _abgr2222(3, 0, 0, 0)                               # 0xC0
WHITE   = _abgr2222(3, 3, 3, 3)                               # 0xFF
RED     = _abgr2222(3, 0, 0, 3)                               # 0xC3
GREEN   = _abgr2222(3, 0, 3, 0)                               # 0xCC
BLUE    = _abgr2222(3, 3, 0, 0)                               # 0xF0
YELLOW  = _abgr2222(3, 0, 3, 3)                               # 0xCF
MAGENTA = _abgr2222(3, 3, 0, 3)                               # 0xF3
CYAN    = _abgr2222(3, 3, 3, 0)                               # 0xFC

STRIPE_PX = 4


def _tile_id_byte(x: int, y: int) -> int:
    # 0xD0..0xDF — A=3, B=1, varying G/R. Disjoint from the stripe/corner
    # palette; row-major over the 4×4 grid so the composite shows a 16-step
    # color ramp in reading order.
    return 0xD0 | ((y << 2) | x)


# Self-tests: tile-id bytes are unique AND disjoint from stripe/corner palette.
_PALETTE = {BLACK, WHITE, RED, GREEN, BLUE, YELLOW, MAGENTA, CYAN}
_IDS = {_tile_id_byte(x, y) for x in range(GRID_N) for y in range(GRID_N)}
assert len(_IDS) == TILES_PER_PACK, "tile-id encoding is not injective"
assert _IDS.isdisjoint(_PALETTE), "tile-id range overlaps stripe/corner palette"


def _build_tile_bytes(x: int, y: int) -> bytes:
    n = TILE_DIM_PX
    buf = bytearray([_tile_id_byte(x, y)]) * (n * n)

    def fill(r0: int, r1: int, c0: int, c1: int, color: int) -> None:
        for r in range(r0, r1 + 1):
            base = r * n
            for c in range(c0, c1 + 1):
                buf[base + c] = color

    # Edge stripes — same order as golden-orientation so frame-corner colors
    # match (top wins over left/right; bottom wins over left/right).
    fill(0,             STRIPE_PX - 1,     0,             n - 1,        RED)
    fill(n - STRIPE_PX, n - 1,             0,             n - 1,        BLUE)
    fill(STRIPE_PX,     n - STRIPE_PX - 1, 0,             STRIPE_PX - 1, GREEN)
    fill(STRIPE_PX,     n - STRIPE_PX - 1, n - STRIPE_PX, n - 1,         YELLOW)

    # 1-px corner dots overlaid at the extreme corners.
    buf[0 * n + 0]                       = BLACK             # NW
    buf[0 * n + (n - 1)]                 = WHITE             # NE
    buf[(n - 1) * n + 0]                 = MAGENTA           # SW
    buf[(n - 1) * n + (n - 1)]           = CYAN              # SE

    return bytes(buf)


def _coords_sorted():
    # § 5.2: ascending (z, x, y); within z, (x, y) lexicographic.
    for x in range(GRID_N):
        for y in range(GRID_N):
            yield (ZOOM, x, y)


def build_pack() -> bytes:
    # Full WebMercator world at z = 2 collapses to the same canonical
    # endpoints as a single tile at (0, 0, 0) (§ 4.9 special cases).
    bbox = (-180_000_000, -g.MERCATOR_POLE_UDEG, +180_000_000, +g.MERCATOR_POLE_UDEG)

    tile_count = TILES_PER_PACK
    index_offset = g.HEADER_SIZE                                            # 292
    tile_blob_start = index_offset + tile_count * g.INDEX_ENTRY_SIZE        # 612
    extensions_offset = tile_blob_start + tile_count * TILE_LENGTH          # 16996
    file_size = extensions_offset + g.CRC_SIZE                              # 17000

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
                     ZOOM,  # zoom_min = actual minimum z
                     ZOOM)  # zoom_max = actual maximum z
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
        blob_buf.extend(_build_tile_bytes(x, y))

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
            f"{GRID_N}×{GRID_N} mosaic at z={ZOOM} ({TILES_PER_PACK} tiles, "
            f"{TILE_DIM_PX}×{TILE_DIM_PX} px each), full WebMercator world "
            "coverage. Each tile carries the same RED/BLUE/GREEN/YELLOW "
            "4-px edge stripes + BLACK/WHITE/MAGENTA/CYAN 1-px corner dots "
            "as golden-orientation, plus a 24×24 interior fill whose byte "
            "encodes (x, y) as 0xD0 + (y << 2) + x. In the composed "
            f"{GRID_N * TILE_DIM_PX}×{GRID_N * TILE_DIM_PX} mosaic the 16 "
            "interior bytes march 0xD0..0xDF in row-major order; tile-tile "
            "seams show paired BLUE/RED (horizontal) and YELLOW/GREEN "
            "(vertical) bands. Exercises § 5.2 multi-entry tile-index "
            "ordering, § 6.2 row-major byte order, § 8.4 XYZ axis (tile "
            "and pixel), and § 9.1 ABGR2222 encoding; complements "
            "golden-orientation (intra-tile) with inter-tile placement."
        ),
        "spec_refs": ["§ 4.12", "§ 5.2", "§ 6.2", "§ 8.4", "§ 9.1", "§ 14.3", "§ 14.5"],
        "expected_outcome": "accept",
        "pack_sha256": hashlib.sha256(pack).hexdigest(),
        "hashes_path": f"golden/{NAME}.hashes",
        "hashes_sha256": hashlib.sha256(hashes.encode("utf-8")).hexdigest(),
    }
