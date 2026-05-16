"""neg-19[a,b] — § 11 #19 extension-framing violations (mutate-style).

§ 11 #19 has three sub-clauses; (a) and (b) here are single-field mutations
of golden-attr. The stranded-bytes sub-clause lives in neg_19c_stranded.py
(reshape-style: file_size grows).

  19a   section-overruns       — length field bumped past the section-bounds limit
  19b   section-padding-nonzero — first alignment-pad byte set to 0xFF

The base is golden-attr (444-byte pack, single ATTR section at offsets 376..440):

  tag    (376..380) = "ATTR"
  length (380..384) = 53     (max legal = 56 = (file_size − 4) − section_start − 8)
  payload(384..437)
  pad    (437..440) = 0x00 × 3
  crc    (440..444)
"""

from __future__ import annotations

import struct

from . import _lib, golden_attr

_RULE_19_SUMMARY = (
    "extension section's extent (tag + length + payload + alignment pad) MUST lie "
    "within [extensions_offset, file_size − 4); pad bytes MUST be 0x00; no stranded "
    "bytes may exist between the last section and the CRC footer (§ 7.1)"
)


def _mut_section_overruns(buf: bytearray) -> None:
    # Bump length 53 → 60. The strict overflow-safe upper bound is
    #   length ≤ (file_size − 4) − section_start − 8 = 440 − 376 − 8 = 56.
    # Setting length=60 violates that bound and pushes the section's declared
    # extent past file_size − 4. No payload bytes are touched.
    struct.pack_into("<I", buf, 380, 60)


def _mut_pad_nonzero(buf: bytearray) -> None:
    # First of the section's 3 alignment-pad bytes 0x00 → 0xFF.
    buf[437] = 0xFF


FIXTURES = [
    _lib.mutate_style_negative(
        name="neg-19a-section-overruns",
        mutate=_mut_section_overruns,
        description=(
            "Pack with ATTR section's length field bumped 53 → 60; the section's "
            "declared extent now exceeds file_size − 4. All other bytes unchanged; "
            "CRC recomputed."
        ),
        mutation="bytes 380..384 (ATTR length field) 53 → 60; CRC recomputed.",
        spec_refs=["§ 7.1"],
        rule_number="19",
        rule_summary=_RULE_19_SUMMARY,
        derived_from="golden-attr",
        base_module=golden_attr,
    ),
    _lib.mutate_style_negative(
        name="neg-19b-section-padding-nonzero",
        mutate=_mut_pad_nonzero,
        description=(
            "Pack with the ATTR section's first alignment-pad byte set to 0xFF "
            "(was 0x00). Payload and length unchanged; CRC recomputed."
        ),
        mutation="byte 437 (first of ATTR's 3 pad bytes) 0x00 → 0xFF; CRC recomputed.",
        spec_refs=["§ 7.1"],
        rule_number="19",
        rule_summary=_RULE_19_SUMMARY,
        derived_from="golden-attr",
        base_module=golden_attr,
    ),
]
