"""neg-13a-z-non-monotone.rawtiles — violates § 11 #13 (z-non-decreasing arm).

Targets the z-monotonicity half of rule #13: "Reject the pack if entries
are not sorted ascending by (z, x, y): z non-decreasing across all entries."

A custom 3-entry pack with one tile per zoom at (z, 0, 0) for z ∈ {2, 1, 0}
laid out in *physical* order (entry 0 is z=2, entry 1 is z=1, entry 2 is
z=0). Z values across the index sequence are 2, 1, 0 — strictly decreasing,
violating "z non-decreasing". The (x, y) strict-ascending sub-rule is
trivially satisfied because each zoom has exactly one entry (no within-zoom
ordering to check).

Sister fixtures `neg-13b` and `neg-13c` cover the within-zoom (x, y) arm
of rule #13. Together the three pin all distinct sub-violations of #13.

Critically, `zoom_offsets[z]` is populated to *correctly* point at each
entry's byte offset (with count = 1), so rule #17 (directory consistency)
stays quiet:

  - entry 0 (z=2) at byte 292 → zoom_offsets[2] = (292, 1)
  - entry 1 (z=1) at byte 312 → zoom_offsets[1] = (312, 1)
  - entry 2 (z=0) at byte 332 → zoom_offsets[0] = (332, 1)
  - zoom_offsets[3..23] all = (0, 0)

Each zoom holding exactly one entry means the "entries at zoom z are
contiguous in the index" implicit assumption of § 5.3's binary search is
trivially satisfied (a singleton is contiguous). Rule #13 is the lone
violation.

Header zoom_min = 0, zoom_max = 2 — all entries' z values fall in [0, 2],
so rule #15 stays quiet. Quadtree (x, y) = (0, 0) at every zoom satisfies
rule #31 (x, y < 2^z) trivially.

bbox: tile (z=0, 0, 0) covers the full WebMercator world; higher-z tiles
are subsets. Canonical full-world endpoints, same as golden-smallest /
golden-grid / golden-pyramid.

Pack size: 292 (header) + 3·20 (index) + 3·64 (blob) + 4 (CRC) = 548.
"""

from __future__ import annotations

import hashlib
import struct
import zlib

from . import golden_smallest as g

NAME = "neg-13a-z-non-monotone"
KIND = "negative"
DERIVED_FROM = "golden-pyramid"
MUTATION = (
    "Built from scratch in the shape of a 3-entry pack with one tile per "
    "zoom ∈ {0, 1, 2}. Entries written in physical order z = [2, 1, 0] so "
    "the (z) sequence across the index is strictly decreasing — violating "
    "rule #13's `z non-decreasing` arm. zoom_offsets[0..2] each point at "
    "their respective entry's byte offset with count = 1, so rule #17 "
    "stays quiet; tile_blob_start, entry offsets, and extensions_offset "
    "are sequential 4-aligned so rules #14, #32, #18 stay quiet."
)

PACK_UUID = hashlib.sha256(b"rawtiles-conformance:neg-13a-z-non-monotone:v1").digest()[:16]

TILE_DIM_PX = 8
TILE_LENGTH = TILE_DIM_PX * TILE_DIM_PX                       # 64

# Index region: 3 entries × 20 bytes = 60 bytes, at file bytes 292..352.
_ENTRY0_OFFSET = 292                                          # z = 2 entry
_ENTRY1_OFFSET = 312                                          # z = 1 entry
_ENTRY2_OFFSET = 332                                          # z = 0 entry
_TILE_BLOB_START = 352
_EXTENSIONS_OFFSET = _TILE_BLOB_START + 3 * TILE_LENGTH       # 544


def _tile_bytes(z: int) -> bytes:
    # A=3 (opaque, § 9.1). Lower 6 bits encode z so each tile has a distinct
    # fill byte. Negative fixtures don't ship .hashes, but distinct bytes make
    # a hex-dump of the file easier to read.
    return bytes([0xC0 | (z << 4)]) * TILE_LENGTH


def build_pack() -> bytes:
    bbox = (-180_000_000, -g.MERCATOR_POLE_UDEG, +180_000_000, +g.MERCATOR_POLE_UDEG)

    tile_count = 3
    index_offset = g.HEADER_SIZE                              # 292
    extensions_offset = _EXTENSIONS_OFFSET                    # 544
    file_size = extensions_offset + g.CRC_SIZE                # 548

    # Each zoom has exactly one entry. Build zoom_offsets to correctly point
    # at each entry's byte offset so rule #17 stays quiet despite the
    # physical-order z sequence violating rule #13.
    zoom_offsets = bytearray(24 * 8)
    struct.pack_into("<II", zoom_offsets, 0 * 8, _ENTRY2_OFFSET, 1)   # zoom 0
    struct.pack_into("<II", zoom_offsets, 1 * 8, _ENTRY1_OFFSET, 1)   # zoom 1
    struct.pack_into("<II", zoom_offsets, 2 * 8, _ENTRY0_OFFSET, 1)   # zoom 2
    # zoom_offsets[3..23] stay zeroed.

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
                     2)    # zoom_max
    struct.pack_into("<iiii", header, 64, *bbox)
    struct.pack_into("<Q", header, 80, g.BUILD_TIMESTAMP)
    struct.pack_into("<II", header, 88, tile_count, index_offset)
    header[96:96 + 24 * 8] = bytes(zoom_offsets)
    struct.pack_into("<I", header, 288, extensions_offset)

    # Tile blob holds one tile per entry, in physical order matching the
    # index. Entry 0 (z=2) → first tile at byte 352; entry 1 (z=1) → second
    # tile at byte 416; entry 2 (z=0) → third tile at byte 480.
    index_buf = bytearray()
    for i, z in enumerate([2, 1, 0]):
        index_buf.extend(struct.pack(
            "<BBBBIIII",
            z, g.COMPRESSION_NONE, 0, 0,
            0, 0,                                              # x, y
            _TILE_BLOB_START + i * TILE_LENGTH,
            TILE_LENGTH,
        ))

    blob_buf = bytearray()
    for z in [2, 1, 0]:
        blob_buf.extend(_tile_bytes(z))

    body = bytes(header) + bytes(index_buf) + bytes(blob_buf)
    assert len(body) == file_size - g.CRC_SIZE, (len(body), file_size - g.CRC_SIZE)
    crc = zlib.crc32(body) & 0xFFFFFFFF
    return body + struct.pack("<I", crc)


def manifest_entry(pack: bytes, hashes: str | None = None) -> dict:
    return {
        "name": NAME,
        "kind": "negative",
        "path": f"negative/{NAME}.rawtiles",
        "description": (
            "Custom 3-entry pack with one tile per zoom (z ∈ {0, 1, 2}) "
            "written in physical order z = [2, 1, 0]. The z sequence across "
            "the index is strictly decreasing, violating rule #13's "
            "z-non-decreasing arm. zoom_offsets correctly target each entry "
            "with count = 1 so directory-consistency (rule #17) stays quiet."
        ),
        "spec_refs": ["§ 5.2"],
        "expected_outcome": "reject",
        "pack_sha256": hashlib.sha256(pack).hexdigest(),
        "expected_reject_rule": {
            "rule_number": "13",
            "summary": (
                "tile-index entries MUST be sorted ascending by (z, x, y): z "
                "non-decreasing across all entries; within each zoom, (x, y) "
                "strictly ascending lexicographically (§ 11 #13)"
            ),
        },
        "derived_from": DERIVED_FROM,
        "mutation": MUTATION,
    }
