"""golden-zmax.rawtiles — single tile at z = 23 (max legal zoom).

A WebMercator/Quadtree/XYZ pack with one tile at (z=23, x=0, y=0). This
is the only v1 fixture exercising:

  - The maximum legal zoom (§ 4.8 + § 11 #10: zoom_max < 24, so 23 is
    the highest legal value).
  - The high-index zoom_offsets[24] slot (only `zoom_offsets[23]` is
    populated; slots 0..22 are (0, 0)). Pairs with golden-pyramid, which
    populates the low end of the directory.
  - The full § 4.9 Quadtree/WebMercator bbox derivation, including the
    non-canonical `lon_east_µ°` formula. Every other Quadtree fixture
    (golden-smallest, golden-grid, golden-pyramid, etc.) uses the
    full-world canonical endpoints because each touches both x = 0 and
    x = 2^z − 1; at z=23 with only x=0, `lon_east` actually exercises
    the i64 division + banker's rounding path.
  - The non-canonical `lat_south_µ°` formula via the
    `atan(sinh(π · (1 − 2y/2^z))) · (180_000_000 / π)` chain — the
    binary64 transcendental path the spec notes is libm-dependent
    (§ 14.1 deterministic-surface clause). The y=0 special case still
    applies to `lat_north`.

Tile (z=23, x=0, y=0) bbox derivation:

  lon_west_µ°(23, 0)   = −180_000_000           (x = 0 special case)
  lon_east_µ°(23, 0)   = round_half_even(
                            (1 · 360_000_000 − 180_000_000 · 2^23) / 2^23
                          )   evaluated in exact i64
                       = −179_999_957
  lat_north_µ°(23, 0)  = +85_051_129            (y = 0 special case)
  lat_south_µ°(23, 0)  = lat_north_µ°(23, 1)
                       = round_half_even(
                            atan(sinh(π · (1 − 2/2^23))) · (180_000_000/π)
                          )   evaluated in binary64
                       = + (computed at build time; libm-dependent
                              within the ≤ 1 µ° cross-implementation
                              tolerance documented in § 4.9)

Per § 4.9, `bbox` is the componentwise min/max over the four corner
latitudes / longitudes. For one tile that reduces to `(lon_west, lat_south,
lon_east, lat_north)`.

Pack layout (380 bytes): header (292) + 1 index entry (20) + tile blob
(64) + CRC (4) = 380. Tile fill: bytes encode (z, y, x) in the lower 6
bits with A=3, identical scheme to golden-pyramid but constant 0xC0 | 23
won't fit; instead each tile byte = 0xC7 (A=3, B=0, G=1, R=3 — a
recognizable distinct color value).
"""

from __future__ import annotations

import hashlib
import math
import struct
import zlib

from . import golden_smallest as g

NAME = "golden-zmax"
KIND = "golden"

TILE_DIM_PX = 8
TILE_LENGTH = TILE_DIM_PX * TILE_DIM_PX                       # 64
ZOOM = 23
TILE_X = 0
TILE_Y = 0

PACK_UUID = hashlib.sha256(b"rawtiles-conformance:golden-zmax:v1").digest()[:16]

# Recognizable tile fill: A=3, B=0, G=1, R=3 → 0xC7. Distinct from every
# other v1 fixture's fill (golden-smallest uses 0xFF, golden-grid uses
# 0xC0..0xCF, golden-pyramid uses 0xC0..0xEF, etc).
TILE_BYTES = bytes([0xC7]) * TILE_LENGTH


def _lon_west_udeg(z: int, x: int) -> int:
    """§ 4.9 Quadtree lon_west, evaluated in exact i64 with banker's rounding."""
    if x == 0:
        return -180_000_000
    pow2z = 1 << z
    numerator = x * 360_000_000 - 180_000_000 * pow2z
    # round_half_even: Python's built-in round() implements banker's rounding
    # but it operates on floats. For exact-i64 + banker's-rounding-on-
    # remainder, derive quotient and remainder separately.
    q, r = divmod(numerator, pow2z)
    if numerator < 0 and r != 0:
        # Python's divmod for negative dividends gives a non-negative r and a
        # quotient rounded toward -∞. Reinterpret as truncation + signed
        # remainder so the "halfway" test below is unambiguous.
        q += 1
        r -= pow2z
    # Now numerator = q * pow2z + r with r ∈ (-pow2z, pow2z) and sign(r) ==
    # sign(numerator) (or r == 0). Banker's rounding on the rational
    # remainder r / pow2z:
    twice_r = 2 * r
    if twice_r > pow2z or (twice_r == pow2z and q % 2 == 1):
        q += 1
    elif twice_r < -pow2z or (twice_r == -pow2z and q % 2 == -1):
        q -= 1
    return q


def _lon_east_udeg(z: int, x: int) -> int:
    """§ 4.9: lon_east_µ°(z, x) = lon_west_µ°(z, x + 1), with x=2^z−1 special."""
    if x == (1 << z) - 1:
        return +180_000_000
    return _lon_west_udeg(z, x + 1)


# binary64 constants per § 4.9 ("π and 180_000_000/π are the binary64
# nearest-rounded values of those mathematical constants"). Python's math.pi
# is the binary64 representation of π; the quotient below is computed once
# and stored, matching the spec's "evaluated in IEEE-754 binary64" wording.
_PI = math.pi
_RAD_TO_UDEG = 180_000_000 / _PI


def _lat_north_udeg(z: int, y: int) -> int:
    """§ 4.9 Quadtree lat_north, in binary64 with strict rounding."""
    if y == 0:
        return +85_051_129
    arg = _PI * (1 - 2 * y / (1 << z))
    lat_udeg_float = math.atan(math.sinh(arg)) * _RAD_TO_UDEG
    # round() implements banker's rounding; for a float input round(x) yields
    # the nearest integer with half-to-even.
    return round(lat_udeg_float)


def _lat_south_udeg(z: int, y: int) -> int:
    if y == (1 << z) - 1:
        return -85_051_129
    return _lat_north_udeg(z, y + 1)


def build_pack() -> bytes:
    bbox = (
        _lon_west_udeg(ZOOM, TILE_X),
        _lat_south_udeg(ZOOM, TILE_Y),
        _lon_east_udeg(ZOOM, TILE_X),
        _lat_north_udeg(ZOOM, TILE_Y),
    )
    # Self-test: range and ordering invariants of rule #11.
    min_lon, min_lat, max_lon, max_lat = bbox
    assert -180_000_000 <= min_lon <= max_lon <= 180_000_000, bbox
    assert -90_000_000 <= min_lat <= max_lat <= 90_000_000, bbox
    # Expected values for (z=23, x=0, y=0) per § 4.9. lat_south uses the
    # libm-dependent atan/sinh path; only the i64 lon path is platform-
    # independent enough to assert exactly here.
    assert min_lon == -180_000_000, bbox
    assert max_lon == -179_999_957, bbox
    assert max_lat == +85_051_129, bbox
    # lat_south is binary64-dependent; just sanity-check the magnitude.
    assert 85_051_000 < min_lat < 85_051_129, bbox

    tile_count = 1
    index_offset = g.HEADER_SIZE                              # 292
    tile_blob_start = index_offset + tile_count * g.INDEX_ENTRY_SIZE  # 312
    tile_offset = tile_blob_start
    extensions_offset = tile_offset + TILE_LENGTH             # 376
    file_size = extensions_offset + g.CRC_SIZE                # 380

    # Only zoom_offsets[23] is populated; this is the only v1 fixture
    # exercising the high end of the 24-slot directory.
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
                     ZOOM,    # zoom_min = ZOOM (only zoom present)
                     ZOOM)    # zoom_max
    struct.pack_into("<iiii", header, 64, *bbox)
    struct.pack_into("<Q", header, 80, g.BUILD_TIMESTAMP)
    struct.pack_into("<II", header, 88, tile_count, index_offset)
    header[96:96 + 24 * 8] = bytes(zoom_offsets)
    struct.pack_into("<I", header, 288, extensions_offset)

    index_entry = struct.pack(
        "<BBBBIIII",
        ZOOM, g.COMPRESSION_NONE, 0, 0,
        TILE_X, TILE_Y,
        tile_offset, TILE_LENGTH,
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
        f"{ZOOM} {TILE_X} {TILE_Y} {digest}\n"
    )


def manifest_entry(pack: bytes, hashes: str) -> dict:
    return {
        "name": NAME,
        "kind": "golden",
        "path": f"golden/{NAME}.rawtiles",
        "description": (
            "1-tile WebMercator/Quadtree/XYZ pack at (z=23, x=0, y=0). The "
            "only v1 fixture exercising the maximum legal zoom (§ 11 #10), "
            "the high end of zoom_offsets[24] (only slot 23 populated), and "
            "the non-canonical § 4.9 bbox derivation: `lon_east` via exact-"
            "i64 division + banker's rounding, `lat_south` via the libm-"
            "dependent atan/sinh path noted in § 14.1's deterministic-surface "
            "clause. The y=0 / x=0 special cases still apply to `lat_north` "
            "and `lon_west`."
        ),
        "spec_refs": ["§ 4.8", "§ 4.9", "§ 4.12", "§ 14.1", "§ 14.3"],
        "expected_outcome": "accept",
        "pack_sha256": hashlib.sha256(pack).hexdigest(),
        "hashes_path": f"golden/{NAME}.hashes",
        "hashes_sha256": hashlib.sha256(hashes.encode("utf-8")).hexdigest(),
    }
