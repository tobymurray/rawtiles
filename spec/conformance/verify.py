#!/usr/bin/env python3
"""verify.py — rawtiles conformance corpus self-check.

Walks manifest.json and asserts that the .rawtiles and .hashes files on disk
match the SHA-256 digests recorded in the manifest. Catches accidental edits
to fixture artifacts, missing files, and generator-vs-manifest drift.

This is the *corpus*-side integrity check, not an implementation conformance
check. A separate tool driving an actual rawtiles reader is required to
verify that an implementation correctly accepts goldens and rejects negatives;
that tool lives wherever the reader does (e.g. Una SDK CI, slippypack CI).

Run from the conformance/ directory:
    python3 verify.py
or with an explicit manifest path:
    python3 verify.py path/to/manifest.json

Exits 0 on full pass, 1 on any drift.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify(manifest_path: Path) -> int:
    manifest = json.loads(manifest_path.read_text())
    root = manifest_path.parent
    fails = 0
    fixtures = manifest["fixtures"]

    for f in fixtures:
        name = f["name"]
        pack_path = root / f["path"]

        if not pack_path.is_file():
            print(f"FAIL  {name:30s}  missing: {f['path']}")
            fails += 1
            continue

        actual_pack = _sha256(pack_path)
        if actual_pack != f["pack_sha256"]:
            print(f"FAIL  {name:30s}  pack sha256 drift")
            print(f"        expected {f['pack_sha256']}")
            print(f"        actual   {actual_pack}")
            fails += 1
            continue

        if f["kind"] == "golden":
            hashes_path = root / f["hashes_path"]
            if not hashes_path.is_file():
                print(f"FAIL  {name:30s}  missing: {f['hashes_path']}")
                fails += 1
                continue
            actual_hashes = _sha256(hashes_path)
            if actual_hashes != f["hashes_sha256"]:
                print(f"FAIL  {name:30s}  hashes sha256 drift")
                print(f"        expected {f['hashes_sha256']}")
                print(f"        actual   {actual_hashes}")
                fails += 1
                continue

        print(f"ok    {name:30s}  {f['kind']:8s}  sha256={actual_pack[:12]}…")

    n = len(fixtures)
    print()
    if fails:
        print(f"FAIL: {fails} of {n} fixtures failed self-check")
        return 1
    print(f"PASS: {n} of {n} fixtures clean")
    return 0


if __name__ == "__main__":
    default = Path(__file__).resolve().parent / "manifest.json"
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else default
    raise SystemExit(verify(path))
