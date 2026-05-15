"""neg-06-parent-nonzero.rawtiles — violates § 11 #6.

Targets: "Reject parent_uuid not equal to all-zero (§ 4.5)."

parent_uuid is reserved in v1; the only legal value is the all-zero sentinel.
Mutation from golden-smallest: header[40] (parent_uuid byte 0) set to 1 to
make the field non-zero with a minimal one-byte change. CRC recomputed.
"""

from __future__ import annotations

from . import _lib


def _mutate(buf: bytearray) -> None:
    buf[40] = 1


FIXTURES = [
    _lib.mutate_style_negative(
        name="neg-06-parent-nonzero",
        mutate=_mutate,
        description="Pack with parent_uuid[0] = 1 (any non-zero value is reserved for future use in v1); CRC recomputed.",
        mutation="header[40] (parent_uuid byte 0) 0 → 1; CRC recomputed.",
        spec_refs=["§ 4.5"],
        rule_number="6",
        rule_summary="parent_uuid MUST be all-zero in v1 (§ 4.5 reserves the field for future use)",
    ),
]
