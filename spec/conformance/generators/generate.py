#!/usr/bin/env python3
"""Orchestrate rawtiles conformance fixture generation.

Imports each per-fixture generator module, runs it, writes the .rawtiles and
(for golden fixtures) .hashes artifacts under conformance/, and assembles
conformance/manifest.json.

Usage:
    python3 -m generators.generate
or
    python3 generators/generate.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Allow running either as a module (`python3 -m generators.generate`) or as a
# script (`python3 generators/generate.py`).
if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from generators import (
        golden_smallest,
        neg_02_bad_magic,
        neg_03_major_2,
        neg_07_reserved_enums,
        neg_25_index_offset_296,
    )
else:
    from . import (
        golden_smallest,
        neg_02_bad_magic,
        neg_03_major_2,
        neg_07_reserved_enums,
        neg_25_index_offset_296,
    )


GENERATORS = [
    golden_smallest,
    neg_02_bad_magic,
    neg_03_major_2,
    *neg_07_reserved_enums.FIXTURES,
    neg_25_index_offset_296,
]
SPEC_VERSION = "0.1"
MANIFEST_VERSION = 1
GENERATED_BY = "rawtiles-conformance generators v1"


def main() -> int:
    conformance_dir = Path(__file__).resolve().parent.parent
    (conformance_dir / "golden").mkdir(parents=True, exist_ok=True)
    (conformance_dir / "negative").mkdir(parents=True, exist_ok=True)

    entries: list[dict] = []
    for gen in GENERATORS:
        pack = gen.build_pack()
        hashes = gen.build_hashes(pack) if gen.KIND == "golden" else None
        entry = gen.manifest_entry(pack, hashes)

        (conformance_dir / entry["path"]).write_bytes(pack)
        if hashes is not None:
            (conformance_dir / entry["hashes_path"]).write_text(hashes)
        entries.append(entry)
        print(f"  {entry['name']:30s} {len(pack):>6d} B  {entry['kind']:8s} sha256={entry['pack_sha256'][:12]}…")

    manifest = {
        "spec_version": SPEC_VERSION,
        "manifest_version": MANIFEST_VERSION,
        "generated_by": GENERATED_BY,
        "fixtures": entries,
    }
    (conformance_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n"
    )
    print(f"wrote manifest.json ({len(entries)} fixtures)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
