"""neg-01-short-file.rawtiles — violates § 11 #1.

Targets: "Reject any file shorter than 296 bytes (292-byte header + 4-byte
CRC footer)" (§ 11 #1).

Built by truncating golden-smallest to 295 bytes (one less than the legal
minimum). The first 292 bytes are an intact header; the final 3 bytes are
the first 3 bytes of what would be the tile-index entry. There is no CRC
footer in this file.

A pure file-length check (rule #1) MUST reject before any deeper parse,
so the absence of a CRC footer doesn't add a second rejection trigger
in well-ordered readers. A reader that attempts to validate the CRC
before checking file length would also fire rule #24, but rule #1's
"file < 296" check happens before any byte interpretation per § 3.

This is the only fixture in the corpus that ships fewer than 296 bytes.
The pack is intentionally not regenerable through `mutate_and_recrc`
(which preserves file size); the truncation is the violation.
"""

from __future__ import annotations

import hashlib

from . import _lib, golden_smallest

NAME = "neg-01-short-file"
KIND = "negative"

_TRUNCATED_SIZE = 295                                         # one byte short of § 11 #1's 296


def build_pack() -> bytes:
    return golden_smallest.build_pack()[:_TRUNCATED_SIZE]


def manifest_entry(pack: bytes, hashes: str | None = None) -> dict:
    return {
        "name": NAME,
        "kind": "negative",
        "path": f"negative/{NAME}.rawtiles",
        "description": (
            "Pack truncated to 295 bytes (one less than the legal minimum 296). "
            "Header is intact in the first 292 bytes; the final 3 bytes are the "
            "first 3 bytes of the would-be tile-index entry. No CRC footer."
        ),
        "spec_refs": ["§ 3", "§ 11"],
        "expected_outcome": "reject",
        "pack_sha256": hashlib.sha256(pack).hexdigest(),
        "expected_reject_rule": {
            "rule_number": "1",
            "summary": "file size MUST be ≥ 296 bytes (292-byte header + 4-byte CRC footer) per § 11 #1",
        },
        "derived_from": "golden-smallest",
        "mutation": (
            "Truncated golden-smallest (380 bytes) to its first 295 bytes; CRC "
            "footer is absent. file_size 380 → 295."
        ),
    }
