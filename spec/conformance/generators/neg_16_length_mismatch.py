"""neg-16-length-mismatch.rawtiles — violates § 11 #16.

Targets: for `pixel_format = ABGR2222`, `compression = None`, every entry's
`length` MUST equal `tile_dim_px × tile_dim_px`.

Mutation from golden-smallest: the lone tile-index entry's `length` u32 LE
at file offset 308 is decremented from 64 → 63. The tile blob is untouched
(64 bytes at offset 312), and the entry's `offset` is unchanged. The
mutation isolates rule #16:

  - rule #14d (`length > extensions_offset − offset`): 63 ≤ 64, holds.
  - rule #18 (`extensions_offset == tile_blob_start + Σ padded_length(i)`):
    `padded_length(63) = 64`, sum stays 64, equation still holds.
  - rule #32 (per-tile placement): only one entry, no neighbor to misalign.
  - rule #33 (per-tile padding non-zero): the trailing byte (file[375]) is
    still `0xFF`, but it's no longer covered by the entry's declared
    length, so #33 doesn't apply (#33 is about pad bytes within the blob
    between entries, not bytes outside any entry's declared range). The
    rejection trigger is the format-mismatched length itself.

CRC is recomputed; file size unchanged at 380 bytes.
"""

from __future__ import annotations

from . import _lib, golden_smallest as g

NAME = "neg-16-length-mismatch"
KIND = "negative"


def _mutate(buf: bytearray) -> None:
    # Tile-index entry layout: z(1) compression(1) flags(1) reserved(1)
    # x(4) y(4) offset(4) length(4). The `length` u32 LE starts at byte
    # 16 of the 20-byte entry, i.e., file offset 292 + 16 = 308.
    buf[308] = 63                                            # was 64 (0x40 → 0x3F)


def build_pack() -> bytes:
    return _lib.mutate_and_recrc(g.build_pack(), _mutate)


def manifest_entry(pack: bytes, hashes: str | None = None) -> dict:
    return _lib.negative_entry(
        name=NAME,
        description=(
            "Pack with the lone tile-index entry's `length` field decremented "
            "64 → 63. For ABGR2222/None the format-implied tile size is "
            "tile_dim_px² = 64, so the entry's declared length no longer "
            "matches. All other fields valid; CRC recomputed."
        ),
        spec_refs=["§ 5.2", "§ 6.2"],
        rule_number="16",
        rule_summary=(
            "tile-index entry `length` MUST equal tile_dim_px² for v1's only "
            "pixel/compression pair (ABGR2222 / None) per § 11 #16"
        ),
        derived_from="golden-smallest",
        mutation="file[308] (tile-index entry 0 `length` LSB) 0x40 → 0x3F (length 64 → 63); CRC recomputed.",
        pack=pack,
    )
