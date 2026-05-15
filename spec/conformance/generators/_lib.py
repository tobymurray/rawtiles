"""Shared building blocks for rawtiles fixture generators.

`mutate_and_recrc` and `negative_entry` capture the boilerplate for the most
common negative-fixture shape: take a golden base, flip a small number of
bytes that DON'T shift any offsets, recompute the CRC, and emit a manifest
entry. With this helper a mutate-style fixture reduces to a NAME, a mutator
closure, and a metadata block.

Reshape-style negatives (offsets shift, cross-references update) don't fit
this helper — they rebuild from scratch. See neg_25_index_offset_296.
"""

from __future__ import annotations

import hashlib
import struct
import zlib
from typing import Callable

CRC_SIZE = 4


def mutate_and_recrc(base: bytes, mutate: Callable[[bytearray], None]) -> bytes:
    """Apply `mutate` to a copy of `base[:-CRC_SIZE]` and append a fresh CRC.

    The returned bytes differ from `base` ONLY in (a) the bytes the mutator
    touched and (b) the recomputed CRC footer. This keeps the targeted § 11
    rule as the lone violation — neither offsets nor structural cross-refs
    move, and rule #24 (CRC mismatch) is excluded.
    """
    buf = bytearray(base)
    mutate(buf)
    body = bytes(buf[:-CRC_SIZE])
    crc = zlib.crc32(body) & 0xFFFFFFFF
    return body + struct.pack("<I", crc)


def negative_entry(
    *,
    name: str,
    description: str,
    spec_refs: list[str],
    rule_number: str,
    rule_summary: str,
    derived_from: str,
    mutation: str,
    pack: bytes,
) -> dict:
    """Assemble a manifest entry dict for a negative fixture."""
    return {
        "name": name,
        "kind": "negative",
        "path": f"negative/{name}.rawtiles",
        "description": description,
        "spec_refs": spec_refs,
        "expected_outcome": "reject",
        "pack_sha256": hashlib.sha256(pack).hexdigest(),
        "expected_reject_rule": {
            "rule_number": rule_number,
            "summary": rule_summary,
        },
        "derived_from": derived_from,
        "mutation": mutation,
    }
