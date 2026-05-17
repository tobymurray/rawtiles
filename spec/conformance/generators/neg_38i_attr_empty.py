"""neg-38i-attr-empty.rawtiles — violates § 11 #38(b) (spec 0.3).

Targets the new zero-length-payload sub-clause of rule #38 added in spec
0.3: "Reject any ATTR section whose payload (b) has declared length zero."

Reshape from golden-attr: the ATTR section's declared length is set to 0
and its 53-byte payload + 3 pad bytes are stripped from the file, so the
section's framed extent ends at byte 384 (immediately after the 8-byte
header) with no stranded bytes before the CRC footer at 384..388. file_size
shrinks 444 → 388. CRC recomputed.

The reshape is required: a same-size mutation that sets length=0 in place
would leave the 56 original payload+pad bytes stranded between the
truncated section's declared end and the CRC, firing rule #19c
(stranded bytes) in addition to #38(b). Truncating the file matches the
declared section size and keeps #38(b) as the lone violation.

Co-firing analysis:
  - rule #19 (framing): section now spans bytes 376..384 (tag + length, no
    payload, no pad). CRC at 384..388 = file_size − 4. No stranded bytes,
    no non-zero pad. Quiet.
  - rule #38(a) (forbidden codepoints) / #38(c) (trailing LF): zero-byte
    payload has no bytes to inspect. Quiet.
  - rule #18 (extensions_offset): unchanged at 376 = tile_blob_start +
    Σ padded_length = 312 + 64 = 376. Quiet.

Layout (388 bytes):
  - 0..292    header (unchanged from golden-attr)
  - 292..312  tile-index entry (unchanged)
  - 312..376  tile blob (unchanged)
  - 376..380  ATTR tag (unchanged)
  - 380..384  length = 0       ← rule #38(b) violation
  - 384..388  CRC (recomputed)
"""

from __future__ import annotations

import hashlib
import struct
import zlib

from . import golden_attr

NAME = "neg-38i-attr-empty"
KIND = "negative"
DERIVED_FROM = "golden-attr"
MUTATION = (
    "ATTR section length field 53 → 0; the section's 53-byte payload and "
    "3 pad bytes are dropped from the file; original CRC dropped and a "
    "new CRC appended. file_size 444 → 388."
)

_ATTR_HEADER_END = 376 + 8                                    # tag + length = 384


def build_pack() -> bytes:
    base = golden_attr.build_pack()
    body = bytearray(base[:_ATTR_HEADER_END])
    struct.pack_into("<I", body, 380, 0)                      # length 53 → 0

    crc = zlib.crc32(bytes(body)) & 0xFFFFFFFF
    return bytes(body) + struct.pack("<I", crc)


def manifest_entry(pack: bytes, hashes: str | None = None) -> dict:
    return {
        "name": NAME,
        "kind": "negative",
        "path": f"negative/{NAME}.rawtiles",
        "description": (
            "Pack derived from golden-attr by truncating the ATTR section's "
            "payload to zero bytes and the file accordingly. The section's "
            "declared length field is 0; § 11 #38(b) (spec 0.3) requires "
            "non-zero ATTR payload length. file_size 444 → 388; CRC recomputed."
        ),
        "spec_refs": ["§ 7.3"],
        "expected_outcome": "reject",
        "pack_sha256": hashlib.sha256(pack).hexdigest(),
        "expected_reject_rule": {
            "rule_number": "38",
            "summary": (
                "SRCD and ATTR payloads MUST be valid UTF-8. ATTR additionally "
                "MUST (a) contain no C0 control codepoint other than LF, no "
                "DEL (U+007F), no NEL (U+0085), no LS (U+2028), and no PS "
                "(U+2029); (b) have non-zero declared length; (c) not end "
                "with byte 0x0A (no trailing LF after the last string) "
                "(§ 7.3 + § 11 #38)"
            ),
        },
        "derived_from": DERIVED_FROM,
        "mutation": MUTATION,
    }
