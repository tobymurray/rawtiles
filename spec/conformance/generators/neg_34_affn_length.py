"""neg-34-affn-length.rawtiles — violates § 11 #34.

Targets: "Reject any AFFN section whose `length` field is not 48"
(§ 7.3 + § 11 #34).

Built from golden-singleimage-affn by dropping the last coefficient (`f`,
the y-offset) and updating the AFFN section's length field from 48 to 40.
The shorter payload is still 4-aligned (40 % 4 = 0) so no padding is
required. file_size shrinks by 8 bytes (436 → 428); CRC is recomputed
over the new body.

Reshape-style build — same-size mutation can't isolate rule #34 alone:
keeping the file at 436 bytes while declaring length=40 would leave 8
stranded bytes between the section's declared end and the CRC, firing
rule #19c too. Truncating the file matches the declared section size
and keeps rule #34 as the lone violation.

Rules to consider:
  - #19 (section framing): section now spans bytes 376..424 (tag 4 +
    length 4 + payload 40 + pad 0), and the CRC sits at 424..428 =
    file_size − 4. No stranded bytes. Quiet.
  - #22 (LocalLinear requires AFFN): the AFFN section is still present
    (just shorter). Quiet.
  - #35 (coefficients must be finite): only 5 of the original 6
    coefficients survive in the on-disk payload; readers checking #34
    first reject before attempting to decode the truncated payload.
  - #36 (AFFN with non-LocalLinear): projection still LocalLinear. Quiet.

Layout (428 bytes):
  - 0..292    header (unchanged from golden-singleimage-affn)
  - 292..312  tile-index entry (unchanged)
  - 312..376  tile blob (unchanged)
  - 376..380  AFFN tag (unchanged)
  - 380..384  length = 40 (was 48)
  - 384..424  5 f64 coefficients (a, b, c, d, e); `f` dropped
  - 424..428  CRC (recomputed)
"""

from __future__ import annotations

import hashlib
import struct
import zlib

from . import _lib, golden_singleimage_affn

NAME = "neg-34-affn-length"
KIND = "negative"

_BAD_LENGTH = 40                                              # 48 ≠ 40
_AFFN_SECTION_PAYLOAD_DROP = 8                                # drop last f64 coefficient


def build_pack() -> bytes:
    base = golden_singleimage_affn.build_pack()

    # Slice golden-singleimage-affn into the parts we keep and rebuild
    # the AFFN section with a shorter length field + truncated payload.
    pre_affn = base[:376]                                     # header + index + tile
    # Original AFFN payload occupies bytes 384..432 (48 bytes); keep the
    # first 40 bytes (5 coefficients) and drop the last 8 bytes (coef `f`).
    affn_payload_truncated = base[384:432 - _AFFN_SECTION_PAYLOAD_DROP]
    assert len(affn_payload_truncated) == _BAD_LENGTH

    affn_section = b"AFFN" + struct.pack("<I", _BAD_LENGTH) + affn_payload_truncated
    assert len(affn_section) == 8 + _BAD_LENGTH               # 48 bytes total (already 4-aligned)

    body = pre_affn + affn_section
    crc = zlib.crc32(body) & 0xFFFFFFFF
    return body + struct.pack("<I", crc)


def manifest_entry(pack: bytes, hashes: str | None = None) -> dict:
    return {
        "name": NAME,
        "kind": "negative",
        "path": f"negative/{NAME}.rawtiles",
        "description": (
            "Pack derived from golden-singleimage-affn by dropping the last "
            "AFFN coefficient and updating the section's length field 48 → "
            "40. Section framing and CRC remain consistent (file truncated to "
            "match), so rule #19 stays quiet and rule #34 is the lone "
            "violation. file_size 436 → 428."
        ),
        "spec_refs": ["§ 7.3"],
        "expected_outcome": "reject",
        "pack_sha256": hashlib.sha256(pack).hexdigest(),
        "expected_reject_rule": {
            "rule_number": "34",
            "summary": "AFFN section's length field MUST be 48 (§ 7.3 + § 11 #34)",
        },
        "derived_from": "golden-singleimage-affn",
        "mutation": (
            "AFFN length field (file[380..384]) 48 → 40; AFFN payload "
            "(file[384..432]) truncated from 48 to 40 bytes (drops coef `f`); "
            "file_size 436 → 428; CRC recomputed over the new body."
        ),
    }
