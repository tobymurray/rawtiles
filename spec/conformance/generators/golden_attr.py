"""golden-attr.rawtiles — § 14.3 ATTR multi-source ordering + extension framing.

A 1-tile WebMercator pack carrying a single ATTR extension section. The fixture
exercises three otherwise-uncovered spec surfaces:

  - § 7.1 extension framing: section header (tag + u32 length), payload, and
    trailing alignment padding. The ATTR payload is 53 bytes — chosen
    deliberately so `(8 + 53) mod 4 = 1` and the section must carry 3 zero
    padding bytes to reach the next 4-byte boundary (which here also equals
    `file_size − 4`, the CRC footer, per § 7.1).
  - § 7.3 ATTR payload rules: LF-separated strings (single 0x0A), no trailing
    LF, NFC-normalised, free of the forbidden C0 / DEL / NEL / LS / PS
    codepoints.
  - § 12.1 / Appendix A.4 ATTR string ordering. The pack's notional sources
    are one `image`-kind source and one `url`-kind source. Per § A.4 the sort
    key is `(zoom_min, zoom_max, kind, identity)`; the `image` source's
    `zoom_max = 0` sorts ahead of the `url` source's `zoom_max = 5`, so the
    image attribution appears first in the LF-joined payload.

The negative corpus that targets ATTR/SRCD text rules (neg-19, neg-29a,
neg-38a–i) is built by mutating this golden — a payload large enough to
host realistic byte flips while still being the minimum size that exercises
non-zero alignment padding.

Layout:
  - 1 tile at (0, 0, 0), tile_dim_px = 8 (64-byte tile)
  - One ATTR section: 4 (tag) + 4 (length header) + 53 (payload) + 3 (pad) = 64 bytes
  - File size: 444 bytes
"""

from __future__ import annotations

import hashlib
import struct
import unicodedata
import zlib

from . import golden_smallest as g

NAME = "golden-attr"
KIND = "golden"

TILE_DIM_PX = 8
TILE_BYTES = bytes([0xFF]) * (TILE_DIM_PX * TILE_DIM_PX)   # opaque white

PACK_UUID = hashlib.sha256(b"rawtiles-conformance:golden-attr:v1").digest()[:16]

# Notional sources (§ A.4), in canonical sort order:
#   1. image  kind, zoom_min=0, zoom_max=0 → "Example imagery © 2026"
#   2. url    kind, zoom_min=0, zoom_max=5 → "© OpenStreetMap contributors"
# Sort key `(zoom_min, zoom_max, kind, identity)`: (0,0,image,...) < (0,5,url,...).
_ATTR_LINES = (
    "Example imagery © 2026",
    "© OpenStreetMap contributors",
)
ATTR_PAYLOAD = "\n".join(_ATTR_LINES).encode("utf-8")

# Self-tests on the payload — generator-side, not runtime properties of the pack.
assert unicodedata.is_normalized("NFC", "\n".join(_ATTR_LINES)), "ATTR text must be NFC (§ 7.3)"
assert len(ATTR_PAYLOAD) == 53, len(ATTR_PAYLOAD)
assert ATTR_PAYLOAD[-1] != 0x0A, "no trailing LF (§ 7.3 ATTR rules)"
assert b"\r" not in ATTR_PAYLOAD, "no CR (§ 7.3 ATTR rules)"

_ATTR_TAG = b"ATTR"
_ATTR_PAYLOAD_LENGTH = len(ATTR_PAYLOAD)                                  # 53
_ATTR_PAD_LENGTH = (-_ATTR_PAYLOAD_LENGTH) % 4                            # 3
_ATTR_SECTION_LENGTH = 8 + _ATTR_PAYLOAD_LENGTH + _ATTR_PAD_LENGTH        # 64


def _attr_section() -> bytes:
    header = _ATTR_TAG + struct.pack("<I", _ATTR_PAYLOAD_LENGTH)
    return header + ATTR_PAYLOAD + bytes(_ATTR_PAD_LENGTH)


def build_pack() -> bytes:
    # Same canonical full-world bbox as golden-smallest (1 tile at (0,0,0), § 4.9).
    bbox = (-180_000_000, -g.MERCATOR_POLE_UDEG, +180_000_000, +g.MERCATOR_POLE_UDEG)

    tile_count = 1
    index_offset = g.HEADER_SIZE                                          # 292
    tile_blob_start = index_offset + tile_count * g.INDEX_ENTRY_SIZE      # 312
    tile_length = len(TILE_BYTES)                                         # 64
    tile_offset = tile_blob_start                                         # 312
    extensions_offset = tile_offset + tile_length                         # 376
    attr_section = _attr_section()
    file_size = extensions_offset + len(attr_section) + g.CRC_SIZE        # 444

    zoom_offsets = bytearray(24 * 8)
    struct.pack_into("<II", zoom_offsets, 0, index_offset, tile_count)    # zoom 0 only

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
        0, 0,                                                              # x, y
        tile_offset,
        tile_length,
    )

    body = bytes(header) + index_entry + TILE_BYTES + attr_section
    assert len(body) == file_size - g.CRC_SIZE, (len(body), file_size - g.CRC_SIZE)
    crc = zlib.crc32(body) & 0xFFFFFFFF
    return body + struct.pack("<I", crc)


def build_hashes(pack: bytes) -> str:
    tile_offset = g.HEADER_SIZE + g.INDEX_ENTRY_SIZE                       # 312
    tile_length = len(TILE_BYTES)                                          # 64
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
            "1-tile WebMercator pack with a single ATTR extension section "
            "(53-byte payload + 3 pad bytes) exercising § 7.1 extension framing, "
            "§ 7.3 ATTR payload rules, and § 12.1 / A.4 multi-source string "
            "ordering (image-kind source attributed before url-kind source per "
            "the (zoom_min, zoom_max, kind, identity) sort key)."
        ),
        "spec_refs": ["§ 7.1", "§ 7.3", "§ 12.1", "§ A.4", "§ 14.3", "§ 14.5"],
        "expected_outcome": "accept",
        "pack_sha256": hashlib.sha256(pack).hexdigest(),
        "hashes_path": f"golden/{NAME}.hashes",
        "hashes_sha256": hashlib.sha256(hashes.encode("utf-8")).hexdigest(),
    }
