"""neg-05-uuid-zero.rawtiles — violates § 11 #5.

Targets: "Reject pack_uuid equal to all-zero (§ 4.3)."

Mutation from golden-smallest: header[8..24] (pack_uuid) overwritten with 16
zero bytes (the all-zero sentinel reserved by § 4.3). CRC recomputed.
"""

from __future__ import annotations

from . import _lib


def _mutate(buf: bytearray) -> None:
    buf[8:24] = bytes(16)


FIXTURES = [
    _lib.mutate_style_negative(
        name="neg-05-uuid-zero",
        mutate=_mutate,
        description="Pack with pack_uuid = 0 (the all-zero reserved sentinel); all other fields valid; CRC recomputed.",
        mutation="header[8..24] (pack_uuid) sha256-derived → all-zero (16 zero bytes); CRC recomputed.",
        spec_refs=["§ 4.3"],
        rule_number="5",
        rule_summary="pack_uuid MUST NOT be all-zero (§ 4.3 reserves the value)",
    ),
]
