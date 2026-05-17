"""neg-29b-duplicate-name-locale.rawtiles — violates § 11 #29 (NAME arm).

Targets the NAME-specific half of rule #29: "Reject any pack containing
two or more `NAME` sections sharing the same `bcp47_tag` value
(per § 7.4)."

Reshape from golden-names-multilocale: a duplicate of section 1
(`bcp47 = en`, 16 bytes) is inserted at file bytes 408..424, between the
original section 1 (392..408) and section 2 (originally at 408, now
shifted to 424..444). Section 3 also shifts forward by 16 bytes. The
duplicate is inserted in its canonical § 12.1 position (identical
payloads are tied; placing it immediately after the original keeps the
ordering monotonic on byte-comparisons), so § 12.1 ordering — which is a
writer requirement only, not a reader-rejection rule — would still hold
if it were reader-enforced.

The two `bcp47 = en` sections trip § 11 #29's NAME-uniqueness clause;
no other rule fires:
  - rule #19 (framing): inserted section is byte-identical to section 1,
    so its framing is valid; the file's total section bytes still sit
    contiguously inside [extensions_offset, file_size − 4).
  - rule #37: the duplicate's payload is valid by construction (it is a
    byte-copy of section 1's valid payload).
  - rule #18: extensions_offset stays at 376; tile_blob_start + Σ
    padded_length still equals 376.

Layout (472 bytes):
  - 0..376    header + index + tile blob (unchanged)
  - 376..392  Section 0 (tag_length=0 fallback)
  - 392..408  Section 1 (en)
  - 408..424  Section 1-DUP (en)        ← duplicate, inserted here
  - 424..444  Section 2 (zh), shifted +16
  - 444..468  Section 3 (en-US), shifted +16
  - 468..472  CRC (recomputed)
"""

from __future__ import annotations

import hashlib
import struct
import zlib

from . import golden_names_multilocale

NAME = "neg-29b-duplicate-name-locale"
KIND = "negative"
DERIVED_FROM = "golden-names-multilocale"
MUTATION = (
    "Inserted a byte-identical copy of section 1 (`bcp47 = en`, 16 bytes) at "
    "file offset 408, between the original section 1 and section 2. Sections "
    "2 and 3 shifted right by 16 bytes; file_size 456 → 472; CRC recomputed."
)

_INSERT_OFFSET = 408                                          # bytes 408..408+16
_SECTION_1_RANGE = (392, 408)                                 # source of the duplicate


def build_pack() -> bytes:
    base = golden_names_multilocale.build_pack()
    section_1_bytes = base[_SECTION_1_RANGE[0]:_SECTION_1_RANGE[1]]

    # Splice: header + sections 0..1 + DUP + sections 2..3 (everything that
    # was at byte 408 in the original up to but not including the CRC).
    body = (
        base[:_INSERT_OFFSET]
        + section_1_bytes
        + base[_INSERT_OFFSET:-4]                              # strip original CRC
    )

    crc = zlib.crc32(body) & 0xFFFFFFFF
    return body + struct.pack("<I", crc)


def manifest_entry(pack: bytes, hashes: str | None = None) -> dict:
    return {
        "name": NAME,
        "kind": "negative",
        "path": f"negative/{NAME}.rawtiles",
        "description": (
            "Pack derived from golden-names-multilocale by inserting a "
            "byte-identical copy of the `en` NAME section. Two NAME sections "
            "now share `bcp47 = en`, violating § 7.4's uniqueness rule for "
            "bcp47_tag values. Section 1's duplicate is placed immediately "
            "after the original (tied under § 12.1's byte-order sort, so "
            "ordering is locally consistent). file_size 456 → 472; CRC "
            "recomputed."
        ),
        "spec_refs": ["§ 7.4", "§ 11"],
        "expected_outcome": "reject",
        "pack_sha256": hashlib.sha256(pack).hexdigest(),
        "expected_reject_rule": {
            "rule_number": "29",
            "summary": (
                "any two NAME sections sharing the same bcp47_tag value MUST "
                "be rejected (§ 7.4 + § 11 #29)"
            ),
        },
        "derived_from": DERIVED_FROM,
        "mutation": MUTATION,
    }
