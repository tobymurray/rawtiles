"""neg-22-locallinear-no-affn.rawtiles — violates § 11 #22.

Targets: "Reject `projection = LocalLinear` packs that do not contain an
`AFFN` extension" (§ 7.3 + § 11 #22).

Built from golden-singleimage-affn by stripping the 56-byte AFFN section.
The remaining pack carries `projection = LocalLinear`, `addressing =
SingleImage`, and NO extension sections — rule #22's exact failure mode.
Header is unchanged except for the recomputed CRC over the new (shorter)
body. file_size: 436 → 380. extensions_offset (376 in golden-singleimage-
affn) now equals `file_size − 4`, which § 4.13 requires for packs with no
extension sections, so rule #18 stays quiet.

This is a *reshape*-style negative (size changes) rather than a same-size
byte flip, so it can't use `_lib.mutate_and_recrc`; it rebuilds the body
explicitly and appends a fresh CRC.

Co-firing rules considered:
  - #18 (extensions_offset semantics): extensions_offset = 376 = file_size
    − 4 satisfies § 4.13 for zero-extension packs. Quiet.
  - #19 (extension framing): no sections to frame. Quiet.
  - #23 (SingleImage shape): zoom_offsets, entry, axis_convention all
    unchanged from golden-singleimage-affn, which satisfies #23. Quiet.
  - #24 (CRC): recomputed against the new body. Quiet.

Rule #22 is the lone violation.
"""

from __future__ import annotations

import hashlib
import struct
import zlib

from . import _lib, golden_singleimage_affn

NAME = "neg-22-locallinear-no-affn"
KIND = "negative"

# golden-singleimage-affn layout (see its module docstring):
#   - header at file bytes 0..292
#   - tile-index entry at 292..312
#   - tile blob at 312..376
#   - AFFN section at 376..432  ← stripped here
#   - CRC at 432..436            ← rebuilt below
_AFFN_SECTION_START = 376
_AFFN_SECTION_END = 432


def build_pack() -> bytes:
    base = golden_singleimage_affn.build_pack()
    # Keep header + index + tile blob; drop the AFFN section AND the existing
    # CRC. The new file's CRC is computed over the truncated body.
    body = base[:_AFFN_SECTION_START]
    crc = zlib.crc32(body) & 0xFFFFFFFF
    return body + struct.pack("<I", crc)


def manifest_entry(pack: bytes, hashes: str | None = None) -> dict:
    return _lib.negative_entry(
        name=NAME,
        description=(
            "Pack derived from golden-singleimage-affn by removing the AFFN "
            "extension section (56 bytes: tag+length+payload). The remaining "
            "pack still declares projection = LocalLinear but carries no AFFN, "
            "directly violating § 7.3's 'AFFN MUST appear when LocalLinear'. "
            "file_size 436 → 380; CRC recomputed."
        ),
        spec_refs=["§ 7.3"],
        rule_number="22",
        rule_summary=(
            "projection = LocalLinear packs MUST contain exactly one AFFN "
            "extension section (§ 7.3 + § 11 #22)"
        ),
        derived_from="golden-singleimage-affn",
        mutation=(
            "Removed bytes 376..432 (AFFN section: 4-byte tag + 4-byte length + "
            "48-byte payload); file_size 436 → 380; CRC recomputed over the "
            "new body."
        ),
        pack=pack,
    )
