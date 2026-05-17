"""neg-36-affn-with-webmercator.rawtiles — violates § 11 #36.

Targets: "Reject any pack with `projection ≠ LocalLinear` that contains
an AFFN section" (§ 7.3 + § 11 #36).

Custom build: golden-smallest's shape (WebMercator/Quadtree/XYZ) with a
valid 48-byte AFFN extension section appended. The AFFN payload itself
is well-formed (six finite f64 zeros for a degenerate-but-finite affine
map), so rules #34 (length = 48) and #35 (coefficients finite) stay
quiet. The pack still has `projection = WebMercator (1)` and `addressing
= Quadtree (1)`, a legal § 8.6 pair on its own — so rule #8 stays quiet.
The lone violation is hosting an AFFN section without LocalLinear.

The AFFN coefficients are emitted as positive-zero binary64 bit patterns
(`0x0000000000000000`). § 7.3 forbids negative-zero on disk but accepts
positive-zero; though the coefficients describe a degenerate affine map
(every coordinate maps to (0, 0)), the section is structurally valid.

Layout (436 bytes):
  - 0..292    header (WebMercator/Quadtree/XYZ; bbox = canonical full-world)
  - 292..312  tile-index entry (z=x=y=0)
  - 312..376  tile blob (64 bytes opaque white, same as golden-smallest)
  - 376..432  AFFN section (4-byte tag + 4-byte length + 48-byte payload;
              48 already 4-aligned so no trailing pad)
  - 432..436  CRC
extensions_offset = 376; file_size = 436.
"""

from __future__ import annotations

import hashlib
import struct
import zlib

from . import golden_smallest as g

NAME = "neg-36-affn-with-webmercator"
KIND = "negative"

PACK_UUID = hashlib.sha256(b"rawtiles-conformance:neg-36-affn-with-webmercator:v1").digest()[:16]

_AFFN_TAG = b"AFFN"
_AFFN_LENGTH = 48                                             # § 11 #34: MUST be 48
_AFFN_PAYLOAD = struct.pack("<6d", 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)   # six finite zeros
assert len(_AFFN_PAYLOAD) == _AFFN_LENGTH
# Guard against -0.0 ever creeping in (§ 7.3 forbids it on disk).
assert b"\x00\x00\x00\x00\x00\x00\x00\x80" not in _AFFN_PAYLOAD, "AFFN payload contains -0.0"


def build_pack() -> bytes:
    bbox = (-180_000_000, -g.MERCATOR_POLE_UDEG, +180_000_000, +g.MERCATOR_POLE_UDEG)

    tile_count = 1
    index_offset = g.HEADER_SIZE                              # 292
    tile_blob_start = index_offset + tile_count * g.INDEX_ENTRY_SIZE  # 312
    tile_offset = tile_blob_start
    tile_length = len(g.TILE_BYTES)                           # 64
    extensions_offset = tile_offset + tile_length             # 376
    affn_section = _AFFN_TAG + struct.pack("<I", _AFFN_LENGTH) + _AFFN_PAYLOAD
    assert len(affn_section) == 8 + _AFFN_LENGTH              # 56 (already 4-aligned)
    file_size = extensions_offset + len(affn_section) + g.CRC_SIZE  # 440

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
                     g.PROJECTION_WEBMERCATOR,                # ← WebMercator (not LocalLinear)
                     g.ADDRESSING_QUADTREE,
                     g.AXIS_XYZ,
                     g.TILE_DIM_PX,
                     0, 0)
    struct.pack_into("<iiii", header, 64, *bbox)
    struct.pack_into("<Q", header, 80, g.BUILD_TIMESTAMP)
    struct.pack_into("<II", header, 88, tile_count, index_offset)
    header[96:96 + 24 * 8] = bytes(zoom_offsets)
    struct.pack_into("<I", header, 288, extensions_offset)

    index_entry = struct.pack(
        "<BBBBIIII",
        0, g.COMPRESSION_NONE, 0, 0,
        0, 0, tile_offset, tile_length,
    )

    body = bytes(header) + index_entry + g.TILE_BYTES + affn_section
    assert len(body) == file_size - g.CRC_SIZE
    crc = zlib.crc32(body) & 0xFFFFFFFF
    return body + struct.pack("<I", crc)


def manifest_entry(pack: bytes, hashes: str | None = None) -> dict:
    return {
        "name": NAME,
        "kind": "negative",
        "path": f"negative/{NAME}.rawtiles",
        "description": (
            "WebMercator/Quadtree pack with a valid 48-byte AFFN extension "
            "section (six finite zero coefficients). AFFN must only appear "
            "when projection = LocalLinear (§ 7.3); its presence here trips "
            "rule #36. Rules #34 (length = 48), #35 (coefs finite), and #8 "
            "(legal proj×scheme pair) all stay quiet. file_size 440."
        ),
        "spec_refs": ["§ 7.3"],
        "expected_outcome": "reject",
        "pack_sha256": hashlib.sha256(pack).hexdigest(),
        "expected_reject_rule": {
            "rule_number": "36",
            "summary": "AFFN MUST NOT appear in packs whose projection is not LocalLinear (§ 7.3 + § 11 #36)",
        },
        "derived_from": "golden-smallest",
        "mutation": (
            "Built from scratch in the shape of golden-smallest "
            "(WebMercator/Quadtree/XYZ, 1 tile at 0,0,0) with a valid AFFN "
            "section appended at extensions_offset = 376 (tag + length=48 + "
            "six finite zero f64 coefficients). file_size 380 → 436."
        ),
    }
