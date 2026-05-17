"""neg-26b-name-tag-overruns.rawtiles — violates § 11 #26 (tag overrun arm).

Targets the second sub-clause of rule #26: "Reject any NAME section
where `1 + tag_length > section payload length`".

Mutation from golden-names-multilocale: section 1's `tag_length` byte
(payload offset 0, file byte 400) is bumped 2 → 8. Section 1's payload is
8 bytes total, so `1 + 8 = 9 > 8` — the declared bcp47_tag spans more
bytes than the payload contains. A strict reader rejects on rule #26
before any byte interpretation of the would-be bcp47_tag.

Single-byte mutation; same file size; CRC recomputed. Co-firing rules:
  - rule #37 (BCP-47 conformance): the over-declared bcp47_tag would
    span payload bytes [1..9] but only [1..8] exist, so the rule has no
    well-defined input. Rule #26 fires first. Quiet under strict ordering.
  - rule #29: bcp47_tag uniqueness check has no defined input here either.
    Quiet under strict ordering.
"""

from __future__ import annotations

from . import _lib, golden_names_multilocale

_SECTION_1_TAG_LENGTH_ADDR = 400                              # payload byte 0 of section 1


def _mutate(buf: bytearray) -> None:
    buf[_SECTION_1_TAG_LENGTH_ADDR] = 8                       # was 2


FIXTURES = [
    _lib.mutate_style_negative(
        name="neg-26b-name-tag-overruns",
        mutate=_mutate,
        description=(
            "Pack with section 1's `tag_length` byte (file offset 400) bumped "
            "2 → 8. Payload length is 8, so `1 + tag_length = 9 > 8` — the "
            "declared bcp47_tag exceeds the payload's bounds. CRC recomputed."
        ),
        mutation=f"file[{_SECTION_1_TAG_LENGTH_ADDR}] (section 1 `tag_length`) 0x02 → 0x08; CRC recomputed.",
        spec_refs=["§ 7.4"],
        rule_number="26",
        rule_summary=(
            "NAME section payload length MUST be ≥ 1 AND `1 + tag_length` "
            "MUST be ≤ payload length (§ 7.4 + § 11 #26)"
        ),
        derived_from="golden-names-multilocale",
        base_module=golden_names_multilocale,
    ),
]
