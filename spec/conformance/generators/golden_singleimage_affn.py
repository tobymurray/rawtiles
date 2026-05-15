"""golden-singleimage-affn.rawtiles — (LocalLinear, SingleImage) with AFFN.

The only path in v1 that exercises § 7.3 AFFN encoding and § 4.9
LocalLinear bbox derivation. Per § 8.6, `(LocalLinear, SingleImage)` is
one of the two legal projection × addressing pairs; AFFN is mandatory
for LocalLinear.

Layout:
  - 1 tile at (z, x, y) = (0, 0, 0), tile_dim_px = 8 (64-byte tile)
  - One AFFN extension section (48-byte payload)
  - No SRCD / ATTR / NAME
  - File size: 436 bytes

AFFN coefficients are chosen for binary64 exactness: every entry is
either zero, ±1, or ±0.25 (= 2^-2), so the AFFN→corner→bbox arithmetic
of § 4.9 produces byte-identical output on any conforming binary64
implementation. The chosen matrix places an 8 × 8 image over the
2° × 2° square centered on (0, 0):

  AFFN = (a, b, c, d, e, f) = (0.25, 0, -1, 0, -0.25, 1)
    lon(u, v) = 0.25·u + 0·v + (-1)
    lat(u, v) = 0·u + (-0.25)·v + 1

Corner geographic mapping:
  (u=0, v=0) → (-1°, +1°)    top-left
  (u=8, v=0) → (+1°, +1°)    top-right
  (u=0, v=8) → (-1°, -1°)    bottom-left
  (u=8, v=8) → (+1°, -1°)    bottom-right

So bbox = (-1_000_000, -1_000_000, +1_000_000, +1_000_000) µ°.

Tile pixels: pixel(u, v) = 0xC0 | ((v << 3) | u). Top 2 bits = 11
(opaque, § 9.1). Low 6 bits encode (v, u) so all 64 pixels have
distinct byte values — useful for any reader that wants to spot-check
its decoder against known pixel positions, in addition to the § 14.5
whole-tile hash.
"""

from __future__ import annotations

import hashlib
import struct
import zlib

from . import golden_smallest as g

NAME = "golden-singleimage-affn"
KIND = "golden"

TILE_DIM_PX = 8
AFFN_COEFFS = (0.25, 0.0, -1.0, 0.0, -0.25, 1.0)   # (a, b, c, d, e, f)

PACK_UUID = hashlib.sha256(b"rawtiles-conformance:golden-singleimage-affn:v1").digest()[:16]

# Per § 4.6 / § 8.2 / § 8.3 / § 8.4
PROJECTION_LOCALLINEAR = 3
ADDRESSING_SINGLEIMAGE = 2

# § 7.1: AFFN section framing
_AFFN_TAG = b"AFFN"
_AFFN_PAYLOAD_LENGTH = 48                          # 6 × 8 bytes (f64 LE)
_AFFN_SECTION_LENGTH = 8 + _AFFN_PAYLOAD_LENGTH    # tag + length header + payload; 48 already 4-aligned


def _tile_bytes() -> bytes:
    # pixel(u, v) = 0xC0 | ((v << 3) | u) → 64 distinct values for u, v ∈ [0, 7]
    out = bytearray(TILE_DIM_PX * TILE_DIM_PX)
    for v in range(TILE_DIM_PX):
        for u in range(TILE_DIM_PX):
            out[v * TILE_DIM_PX + u] = 0xC0 | ((v << 3) | u)
    return bytes(out)


def _compute_bbox_from_affn(a: float, b: float, c: float, d: float, e: float, f: float,
                             w: int, h: int) -> tuple[int, int, int, int]:
    """Apply § 4.9 LocalLinear bbox derivation: tight i32-µ° bbox over the
    four image corners. Binary64 strict, integer microdegree conversion via
    round-half-even (Python's built-in round() implements banker's rounding)."""
    corners = [(0, 0), (w, 0), (0, h), (w, h)]
    lons_udeg: list[int] = []
    lats_udeg: list[int] = []
    for u, v in corners:
        lon = a * u + b * v + c
        lat = d * u + e * v + f
        lons_udeg.append(round(lon * 1_000_000))
        lats_udeg.append(round(lat * 1_000_000))
    return (min(lons_udeg), min(lats_udeg), max(lons_udeg), max(lats_udeg))


def _affn_section() -> bytes:
    payload = struct.pack("<6d", *AFFN_COEFFS)
    # Guard against -0.0 ever creeping in (§ 7.3 forbids it on disk).
    assert b"\x00\x00\x00\x00\x00\x00\x00\x80" not in payload, "AFFN contains -0.0"
    header = _AFFN_TAG + struct.pack("<I", _AFFN_PAYLOAD_LENGTH)
    return header + payload


def build_pack() -> bytes:
    bbox = _compute_bbox_from_affn(*AFFN_COEFFS, TILE_DIM_PX, TILE_DIM_PX)
    # Sanity-check the computation against hand-derived expected bbox; this
    # is a self-test of the generator's AFFN→bbox formula, not a runtime
    # property of the pack.
    assert bbox == (-1_000_000, -1_000_000, +1_000_000, +1_000_000), bbox

    tile_count = 1
    index_offset = g.HEADER_SIZE                                       # 292
    tile_blob_start = index_offset + tile_count * g.INDEX_ENTRY_SIZE   # 312
    tile_length = TILE_DIM_PX * TILE_DIM_PX                            # 64 (already 4-aligned)
    tile_offset = tile_blob_start
    extensions_offset = tile_offset + tile_length                       # 376
    affn_section = _affn_section()
    file_size = extensions_offset + len(affn_section) + g.CRC_SIZE     # 376 + 56 + 4 = 436

    zoom_offsets = bytearray(24 * 8)
    struct.pack_into("<II", zoom_offsets, 0, index_offset, tile_count)  # zoom 0 only

    header = bytearray(g.HEADER_SIZE)
    struct.pack_into("<4sBB2x", header, 0,
                     g.MAGIC, g.FORMAT_VERSION_MAJOR, g.FORMAT_VERSION_MINOR)
    header[8:24]  = PACK_UUID
    header[24:40] = g.SUPERSEDES_UUID
    header[40:56] = g.PARENT_UUID
    struct.pack_into("<BBBBHBB", header, 56,
                     g.PIXEL_FORMAT_ABGR2222,
                     PROJECTION_LOCALLINEAR,
                     ADDRESSING_SINGLEIMAGE,
                     g.AXIS_XYZ,           # § 8.4: writers MUST emit 1 for SingleImage
                     TILE_DIM_PX,
                     0,                    # zoom_min — § 8.6 MUST be 0 for SingleImage
                     0)                    # zoom_max — § 8.6 MUST be 0 for SingleImage
    struct.pack_into("<iiii", header, 64, *bbox)
    struct.pack_into("<Q", header, 80, g.BUILD_TIMESTAMP)
    struct.pack_into("<II", header, 88, tile_count, index_offset)
    header[96:96 + 24 * 8] = bytes(zoom_offsets)
    struct.pack_into("<I", header, 288, extensions_offset)

    index_entry = struct.pack(
        "<BBBBIIII",
        0, g.COMPRESSION_NONE, 0, 0,
        0, 0,                              # x, y — § 8.6 MUST be 0 for SingleImage
        tile_offset,
        tile_length,
    )

    body = bytes(header) + index_entry + _tile_bytes() + affn_section
    assert len(body) == file_size - g.CRC_SIZE, (len(body), file_size - g.CRC_SIZE)
    crc = zlib.crc32(body) & 0xFFFFFFFF
    return body + struct.pack("<I", crc)


def build_hashes(pack: bytes) -> str:
    tile_offset = g.HEADER_SIZE + g.INDEX_ENTRY_SIZE                   # 312
    tile_length = TILE_DIM_PX * TILE_DIM_PX                            # 64
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
            "(LocalLinear, SingleImage) pack with 1 tile at (0,0,0), 8×8 px, "
            "AFFN extension placing the image over the 2°×2° square at origin. "
            "The only v1 path that exercises § 7.3 AFFN encoding and § 4.9 "
            "LocalLinear bbox derivation."
        ),
        "spec_refs": ["§ 4.9", "§ 7.3", "§ 8.6", "§ 14.3"],
        "expected_outcome": "accept",
        "pack_sha256": hashlib.sha256(pack).hexdigest(),
        "hashes_path": f"golden/{NAME}.hashes",
        "hashes_sha256": hashlib.sha256(hashes.encode("utf-8")).hexdigest(),
    }
