"""neg-26a-name-payload-empty.rawtiles — violates § 11 #26 (length < 1 arm).

Targets the first sub-clause of rule #26: "Reject any NAME section whose
section payload length is less than 1 (no byte available for the
mandatory `tag_length`)."

Reshape from golden-names-multilocale: the last NAME section (section 3,
`bcp47 = en-US`) is truncated to a zero-length payload. The section's
on-disk header still says `NAME` but its `length` field is now 0, so
there is no byte from which to read the mandatory `tag_length`. file_size
shrinks by 16 bytes (the section's original payload, no pad to drop).
CRC is recomputed over the new body.

Reshape is mandatory: a same-size mutation that sets section 3's length
field to 0 in place would leave 16 stranded bytes (the orphaned payload)
between the truncated section and the next-section / CRC region,
which would itself violate rule #19c (no stranded bytes between the last
section and the CRC footer).

Co-firing analysis:
  - rule #19 (section framing + stranded bytes): the truncated section
    spans bytes 428..436 (tag + length, no payload, no pad); CRC
    immediately follows at 436..440 = file_size − 4. No stranded
    bytes. Quiet.
  - rule #29 (duplicate NAME locale): section 3 now has zero payload,
    so its bcp47_tag is unreadable. Rule #26 fires before any
    bcp47-uniqueness check has a defined input. Quiet.
  - rule #37 (NAME UTF-8 / BCP-47): no payload to validate. Quiet.

Layout (440 bytes):
  - 0..376    header + index + tile blob (unchanged)
  - 376..392  Section 0 (tag_length=0 fallback)
  - 392..408  Section 1 (en)
  - 408..428  Section 2 (zh)
  - 428..432  Section 3 tag = "NAME"
  - 432..436  Section 3 length = 0   ← violation
  - 436..440  CRC
"""

from __future__ import annotations

import hashlib
import struct
import zlib

from . import golden_names_multilocale

NAME = "neg-26a-name-payload-empty"
KIND = "negative"
DERIVED_FROM = "golden-names-multilocale"
MUTATION = (
    "Truncated golden-names-multilocale's section 3 (`bcp47=en-US`) to a "
    "zero-length payload: section length field 16 → 0; section payload (16 "
    "bytes) and CRC dropped; new CRC appended. file_size 456 → 440."
)

_SECTION_3_START = 428                                        # bytes 428..452 in the golden
_SECTION_3_HEADER_END = 436                                   # tag (4) + length (4)


def build_pack() -> bytes:
    base = golden_names_multilocale.build_pack()

    # Keep everything up through section 3's header (8 bytes); rewrite the
    # length field to 0; drop the rest of section 3 and the original CRC.
    body = bytearray(base[:_SECTION_3_HEADER_END])
    struct.pack_into("<I", body, _SECTION_3_START + 4, 0)     # length 16 → 0

    crc = zlib.crc32(bytes(body)) & 0xFFFFFFFF
    return bytes(body) + struct.pack("<I", crc)


def manifest_entry(pack: bytes, hashes: str | None = None) -> dict:
    return {
        "name": NAME,
        "kind": "negative",
        "path": f"negative/{NAME}.rawtiles",
        "description": (
            "Pack derived from golden-names-multilocale by truncating "
            "section 3's payload to 0 bytes and the file accordingly. The "
            "section's `length` field is 0, so no byte is available for the "
            "mandatory `tag_length` per § 7.4. file_size 456 → 440; CRC "
            "recomputed."
        ),
        "spec_refs": ["§ 7.4"],
        "expected_outcome": "reject",
        "pack_sha256": hashlib.sha256(pack).hexdigest(),
        "expected_reject_rule": {
            "rule_number": "26",
            "summary": (
                "NAME section payload length MUST be ≥ 1 (one byte for "
                "`tag_length`); additionally `1 + tag_length` MUST be ≤ "
                "payload length (§ 7.4 + § 11 #26)"
            ),
        },
        "derived_from": DERIVED_FROM,
        "mutation": MUTATION,
    }
