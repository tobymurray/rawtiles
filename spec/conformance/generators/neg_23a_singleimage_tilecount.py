"""neg-23a-singleimage-tilecount.rawtiles — violates § 11 #23 (tile_count arm).

Targets the `tile_count == 1` conjunct of rule #23: a SingleImage pack
MUST have exactly one tile-index entry.

Custom 2-entry build in the shape of golden-singleimage-affn:
projection = LocalLinear, addressing = SingleImage, axis = XYZ, with the
existing AFFN section retained verbatim — but with `tile_count = 2` and
two index entries at (z=0, x=0, y=0) and (z=0, x=0, y=1). The two entries
are strictly ascending in (z, x, y) so § 11 #13's strict-ascending check
stays quiet; zoom_offsets[0] is set to (292, 2) so § 11 #17's directory
consistency stays quiet; the AFFN section is unchanged so rules #22, #34,
#35 stay quiet. Rule #23 fires because `tile_count == 1` is violated;
multiple #23 sub-conjuncts (`tile_count`, the lone-entry shape, the
`zoom_offsets[0].count == 1` requirement) technically all break, but
they're all the same rule.

Layout (520 bytes):
  - 0..292    header (zoom_min = zoom_max = 0, tile_count = 2,
              extensions_offset = 460)
  - 292..312  index entry 0: (z=0, x=0, y=0), offset 332, length 64
  - 312..332  index entry 1: (z=0, x=0, y=1), offset 396, length 64
  - 332..396  tile blob 0 (opaque white, 64 × 0xFF)
  - 396..460  tile blob 1 (opaque black, 64 × 0xC0)
  - 460..516  AFFN section (tag + length=48 + six finite-zero coefficients)
              identical bytes to golden-singleimage-affn's AFFN, just
              relocated
  - 516..520  CRC

Co-firing analysis:
  - rule #11 (bbox range/order): unchanged from golden-singleimage-affn's
    (-1M, -1M, +1M, +1M). Quiet.
  - rule #13 (sort order): two entries at (0,0,0) and (0,0,1) are
    strictly ascending. Quiet.
  - rule #14 (offset/length bounds): both entries' offsets 4-aligned,
    in [tile_blob_start, extensions_offset), length 64 fits. Quiet.
  - rule #15 (z in [zmin, zmax]): both z=0 in [0, 0]. Quiet.
  - rule #16 (length = tile_dim²): both lengths 64 = 8². Quiet.
  - rule #17 (zoom_offsets consistency): zoom_offsets[0] = (292, 2)
    matches the 2 entries at z=0. zoom_offsets[1..23] = (0, 0). Quiet.
  - rule #18 (extensions_offset): 460 = 332 + 64 + 64 = tile_blob_start
    + Σ padded_length. Quiet.
  - rule #22 (LocalLinear requires AFFN): AFFN present. Quiet.
  - rule #34/#35/#36 (AFFN): section unchanged, projection unchanged.
    Quiet.
"""

from __future__ import annotations

import hashlib
import struct
import zlib

from . import golden_singleimage_affn as _g
from . import golden_smallest as g

NAME = "neg-23a-singleimage-tilecount"
KIND = "negative"
DERIVED_FROM = "golden-singleimage-affn"
MUTATION = (
    "Built from scratch in the shape of golden-singleimage-affn but with "
    "tile_count = 2 and two tile-index entries at (z=0, x=0, y=0) and "
    "(z=0, x=0, y=1); zoom_offsets[0] = (292, 2) so rule #17 stays quiet; "
    "AFFN section retained verbatim at relocated offset 460. file_size 520."
)

TILE_DIM_PX = _g.TILE_DIM_PX                                  # 8
TILE_LENGTH = TILE_DIM_PX * TILE_DIM_PX                       # 64

# Distinct fills for the two tiles so a hex dump distinguishes them.
_TILE_0_BYTES = bytes([0xFF]) * TILE_LENGTH                   # opaque white
_TILE_1_BYTES = bytes([0xC0]) * TILE_LENGTH                   # opaque black

PACK_UUID = hashlib.sha256(b"rawtiles-conformance:neg-23a-singleimage-tilecount:v1").digest()[:16]


def build_pack() -> bytes:
    # bbox from golden-singleimage-affn's AFFN-derived coordinates (2°×2°
    # at origin). Within rule #11 range and min ≤ max.
    bbox = (-1_000_000, -1_000_000, +1_000_000, +1_000_000)

    tile_count = 2
    index_offset = g.HEADER_SIZE                              # 292
    tile_blob_start = index_offset + tile_count * g.INDEX_ENTRY_SIZE  # 332
    tile_0_offset = tile_blob_start                           # 332
    tile_1_offset = tile_0_offset + TILE_LENGTH               # 396
    extensions_offset = tile_blob_start + tile_count * TILE_LENGTH    # 460
    affn_section = _g._affn_section()                         # reuse golden-singleimage-affn's bytes
    file_size = extensions_offset + len(affn_section) + g.CRC_SIZE    # 520

    zoom_offsets = bytearray(24 * 8)
    struct.pack_into("<II", zoom_offsets, 0, index_offset, tile_count)  # (292, 2)

    header = bytearray(g.HEADER_SIZE)
    struct.pack_into("<4sBB2x", header, 0,
                     g.MAGIC, g.FORMAT_VERSION_MAJOR, g.FORMAT_VERSION_MINOR)
    header[8:24]  = PACK_UUID
    header[24:40] = g.SUPERSEDES_UUID
    header[40:56] = g.PARENT_UUID
    struct.pack_into("<BBBBHBB", header, 56,
                     g.PIXEL_FORMAT_ABGR2222,
                     _g.PROJECTION_LOCALLINEAR,
                     _g.ADDRESSING_SINGLEIMAGE,
                     g.AXIS_XYZ,
                     TILE_DIM_PX,
                     0, 0)                                    # zoom_min, zoom_max
    struct.pack_into("<iiii", header, 64, *bbox)
    struct.pack_into("<Q", header, 80, g.BUILD_TIMESTAMP)
    struct.pack_into("<II", header, 88, tile_count, index_offset)
    header[96:96 + 24 * 8] = bytes(zoom_offsets)
    struct.pack_into("<I", header, 288, extensions_offset)

    entry_0 = struct.pack(
        "<BBBBIIII",
        0, g.COMPRESSION_NONE, 0, 0,
        0, 0, tile_0_offset, TILE_LENGTH,
    )
    entry_1 = struct.pack(
        "<BBBBIIII",
        0, g.COMPRESSION_NONE, 0, 0,
        0, 1, tile_1_offset, TILE_LENGTH,
    )

    body = (
        bytes(header)
        + entry_0
        + entry_1
        + _TILE_0_BYTES
        + _TILE_1_BYTES
        + affn_section
    )
    assert len(body) == file_size - g.CRC_SIZE, (len(body), file_size - g.CRC_SIZE)
    crc = zlib.crc32(body) & 0xFFFFFFFF
    return body + struct.pack("<I", crc)


def manifest_entry(pack: bytes, hashes: str | None = None) -> dict:
    return {
        "name": NAME,
        "kind": "negative",
        "path": f"negative/{NAME}.rawtiles",
        "description": (
            "Custom 2-entry SingleImage pack: shape of golden-singleimage-affn "
            "with tile_count = 2, two entries at (0,0,0) and (0,0,1), and "
            "zoom_offsets[0] = (292, 2). Rule #23's `tile_count == 1` arm "
            "fires; rules #13/#14/#17/#18/#22/#34/#35/#36 all stay quiet."
        ),
        "spec_refs": ["§ 8.6"],
        "expected_outcome": "reject",
        "pack_sha256": hashlib.sha256(pack).hexdigest(),
        "expected_reject_rule": {
            "rule_number": "23",
            "summary": (
                "SingleImage packs MUST satisfy ALL of: tile_count == 1; the "
                "lone entry is (z=0, x=0, y=0); zoom_min == zoom_max == 0; "
                "tile_axis_convention == 1; zoom_offsets[0] == (index_offset, "
                "1); every zoom_offsets[z ∈ [1, 23]] == (0, 0) (§ 8.6 + § 11 "
                "#23)"
            ),
        },
        "derived_from": DERIVED_FROM,
        "mutation": MUTATION,
    }
