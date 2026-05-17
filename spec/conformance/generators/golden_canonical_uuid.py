"""golden-canonical-uuid.rawtiles — Appendix A `pack_uuid` derivation.

A 1-tile WebMercator/Quadtree/XYZ pack whose `pack_uuid` is derived via
the canonical Appendix A pipeline rather than the ad-hoc
`sha256("rawtiles-conformance:<name>:v1")[:16]` scheme every other v1
fixture uses. The pack itself is byte-equivalent in structure to
golden-smallest; only the UUID derivation differs.

Two things land here:

  1. The fixture's `pack_uuid` is computed from a logical-input descriptor
     (§ A.3) using JCS canonicalization (§ A.3) + UUIDv5 with the
     rawtiles namespace (§ A.1). Independent reproducibility-claiming
     writers given the same inputs MUST land on the same bytes.

  2. A self-test in this module reproduces § A.5's worked example
     end-to-end: the documented descriptor's canonical UTF-8 bytes must
     hash (SHA-1 over namespace ‖ bytes) to the documented intermediate
     `e91e34e73c2f329c85a0513a72dbefd4bdae8aa2`, and the UUIDv5 fixup
     must produce `e91e34e7-3c2f-529c-85a0-513a72dbefd4`. If your build
     fails this self-test, the generator's JCS path is broken — fix it
     here before consuming the fixture's bytes for anything.

The synthetic source kind (§ A.4) lets the fixture avoid a `content_hash`
field, sidestepping the writer-pipeline question that doesn't have a
clean answer in v1 conformance scope. The descriptor's other fields
mirror golden-smallest (1 tile at z=0, full-world bbox, ABGR2222,
WebMercator/Quadtree/XYZ, tile_dim_px = 8).
"""

from __future__ import annotations

import hashlib
import json
import struct
import uuid
import zlib

from . import golden_smallest as g

NAME = "golden-canonical-uuid"
KIND = "golden"

TILE_DIM_PX = g.TILE_DIM_PX
TILE_BYTES = g.TILE_BYTES                                     # opaque white, 64 bytes

_NAMESPACE = uuid.UUID("4e72f962-6632-4538-8e0a-7eab63350f3f")    # § A.1


def _canonical_descriptor_bytes(descriptor: dict) -> bytes:
    """JCS-canonicalize a descriptor object to UTF-8 bytes (§ A.3).

    For the all-ASCII-keys, integers-and-simple-strings descriptors v1
    uses, this reduces to: keys sorted by codepoint, no whitespace, ints
    rendered as decimal, UTF-8 encoded. `ensure_ascii=False` is required
    so non-ASCII string values pass through as UTF-8 bytes rather than
    `\\uXXXX` escapes.
    """
    return json.dumps(
        descriptor, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def _derive_pack_uuid(descriptor: dict) -> bytes:
    """UUIDv5 over (namespace bytes ‖ canonical descriptor bytes), § A.2."""
    canonical = _canonical_descriptor_bytes(descriptor)
    return uuid.uuid5(_NAMESPACE, canonical.decode("utf-8")).bytes


def _self_test_worked_example() -> None:
    """Reproduce § A.5 byte-for-byte; called at import time."""
    worked_example = {
        "affn": None,
        "bbox": [-180_000_000, -85_000_000, 180_000_000, 85_000_000],
        "format_version": [1, 0],
        "pixel_format": 1,
        "projection": 1,
        "quantiser_version": 1,
        "sources": [{
            "auth_kinds": [],
            "content_hash": "0" * 64,
            "kind": "url",
            "template": "https://tile.openstreetmap.org/{z}/{x}/{y}.png",
            "zoom_max": 12,
            "zoom_min": 6,
        }],
        "style_hash": None,
        "tile_addressing_scheme": 1,
        "tile_axis_convention": 1,
        "tile_dim_px": 128,
        "zoom_range": [6, 12],
    }
    canonical = _canonical_descriptor_bytes(worked_example)
    sha1_hex = hashlib.sha1(_NAMESPACE.bytes + canonical).hexdigest()
    assert sha1_hex == "e91e34e73c2f329c85a0513a72dbefd4bdae8aa2", sha1_hex
    derived = uuid.uuid5(_NAMESPACE, canonical.decode("utf-8"))
    assert str(derived) == "e91e34e7-3c2f-529c-85a0-513a72dbefd4", str(derived)


_self_test_worked_example()


# Descriptor for the fixture itself: minimal 1-tile WebMercator/Quadtree pack
# with one synthetic source. Synthetic is the only kind that doesn't carry a
# content_hash (§ A.4), so the descriptor doesn't depend on the writer's
# pipeline byte output.
DESCRIPTOR = {
    "affn": None,
    "bbox": [-180_000_000, -g.MERCATOR_POLE_UDEG, 180_000_000, +g.MERCATOR_POLE_UDEG],
    "format_version": [1, 0],
    "pixel_format": 1,
    "projection": 1,
    "quantiser_version": 1,
    "sources": [{"fixture_version": 1, "kind": "synthetic"}],
    "style_hash": None,
    "tile_addressing_scheme": 1,
    "tile_axis_convention": 1,
    "tile_dim_px": TILE_DIM_PX,
    "zoom_range": [0, 0],
}

PACK_UUID = _derive_pack_uuid(DESCRIPTOR)
assert PACK_UUID != bytes(16), "derived pack_uuid MUST be non-zero (§ 4.3)"


def build_pack() -> bytes:
    bbox = (-180_000_000, -g.MERCATOR_POLE_UDEG, +180_000_000, +g.MERCATOR_POLE_UDEG)

    tile_count = 1
    index_offset = g.HEADER_SIZE                              # 292
    tile_blob_start = index_offset + tile_count * g.INDEX_ENTRY_SIZE  # 312
    tile_offset = tile_blob_start
    tile_length = len(TILE_BYTES)                             # 64
    extensions_offset = tile_offset + tile_length             # 376
    file_size = extensions_offset + g.CRC_SIZE                # 380

    zoom_offsets = bytearray(24 * 8)
    struct.pack_into("<II", zoom_offsets, 0, index_offset, tile_count)

    header = bytearray(g.HEADER_SIZE)
    struct.pack_into("<4sBB2x", header, 0,
                     g.MAGIC, g.FORMAT_VERSION_MAJOR, g.FORMAT_VERSION_MINOR)
    header[8:24]  = PACK_UUID                                 # ← Appendix-A-derived
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
        0, 0, tile_offset, tile_length,
    )

    body = bytes(header) + index_entry + TILE_BYTES
    assert len(body) == file_size - g.CRC_SIZE
    crc = zlib.crc32(body) & 0xFFFFFFFF
    return body + struct.pack("<I", crc)


def build_hashes(pack: bytes) -> str:
    tile_offset = g.HEADER_SIZE + g.INDEX_ENTRY_SIZE
    tile_length = len(TILE_BYTES)
    digest = hashlib.sha256(pack[tile_offset:tile_offset + tile_length]).hexdigest()
    return (
        "# rawtiles per-tile hash table, § 14.5\n"
        "# format: <z> <x> <y> <sha256-hex>\n"
        f"0 0 0 {digest}\n"
    )


def manifest_entry(pack: bytes, hashes: str) -> dict:
    derived_uuid_str = str(uuid.UUID(bytes=PACK_UUID))
    return {
        "name": NAME,
        "kind": "golden",
        "path": f"golden/{NAME}.rawtiles",
        "description": (
            "1-tile WebMercator/Quadtree/XYZ pack identical in shape to "
            "golden-smallest, except `pack_uuid` is derived via the "
            "Appendix A canonical pipeline (UUIDv5 over the rawtiles "
            f"namespace + JCS-canonicalized descriptor): {derived_uuid_str}. "
            "Module self-tests reproduce § A.5's worked example end-to-end "
            "(intermediate SHA-1 and final UUID must match the spec) before "
            "any byte is emitted; a build failure means the JCS pipeline is "
            "broken. The descriptor's lone source is `synthetic` "
            "(fixture_version=1), which skips the writer-pipeline content_hash."
        ),
        "spec_refs": ["§ 4.3", "§ A.1", "§ A.2", "§ A.3", "§ A.4", "§ A.5"],
        "expected_outcome": "accept",
        "pack_sha256": hashlib.sha256(pack).hexdigest(),
        "hashes_path": f"golden/{NAME}.hashes",
        "hashes_sha256": hashlib.sha256(hashes.encode("utf-8")).hexdigest(),
    }
