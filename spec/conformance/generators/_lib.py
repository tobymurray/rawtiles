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


_RULE_7_SUMMARY = (
    "any unknown pixel_format, projection, tile_addressing_scheme, "
    "tile_axis_convention, or compression byte MUST be rejected (§ 8)"
)


def reserved_enum_fixture(
    *,
    suffix: str,
    offset: int,
    value: int,
    field: str,
    value_desc: str,
    spec_ref: str,
):
    """Factory for § 11 #7 reserved-enum negative fixtures.

    Each call returns a module-shaped object exposing NAME, KIND, build_pack,
    and manifest_entry — the same surface generate.py expects of a generator
    module. Mutation is a single-byte flip at an absolute file offset; the
    previous byte value is read from golden-smallest so the manifest's
    "prev → new" description stays in sync with the golden if it ever moves.
    """
    from . import golden_smallest as g  # local import: avoid circular module load

    name = f"neg-07{suffix}"
    base_pack = g.build_pack()
    prev_value = base_pack[offset]

    def _mut(buf: bytearray) -> None:
        buf[offset] = value

    class _Fixture:
        NAME = name
        KIND = "negative"

        @staticmethod
        def build_pack() -> bytes:
            return mutate_and_recrc(base_pack, _mut)

        @staticmethod
        def manifest_entry(pack: bytes, hashes: str | None = None) -> dict:
            return negative_entry(
                name=name,
                description=(
                    f"Pack with {field} = {value} ({value_desc}); "
                    "all other fields valid; CRC recomputed."
                ),
                spec_refs=[spec_ref],
                rule_number="7",
                rule_summary=_RULE_7_SUMMARY,
                derived_from="golden-smallest",
                mutation=(
                    f"{field} byte (file offset {offset}) "
                    f"{prev_value} → {value} ({value_desc}); CRC recomputed."
                ),
                pack=pack,
            )

    return _Fixture
