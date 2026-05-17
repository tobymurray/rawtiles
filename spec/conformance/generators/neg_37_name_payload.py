"""neg-37 cluster — § 7.4 / § 11 #37 NAME `name`/`bcp47_tag` validity.

Three sub-fixtures derived from golden-names-multilocale. Each targets one
of rule #37's conditions:

  - (a) `name` is not valid UTF-8.
  - (b) `bcp47_tag` violates the v1 case requirement (lowercase language,
    uppercase region).
  - (c) `bcp47_tag` is a 3-letter sequence (outside the v1 restricted
    BCP-47 subset of `[a-z]{2}` or `[a-z]{2}-[A-Z]{2}`).

Section/payload offsets in golden-names-multilocale used below:

  Section 1 (`en`, "Tiles"): payload at bytes 400..408
    - byte 400: tag_length (0x02)
    - bytes 401..403: bcp47 ("en")
    - bytes 403..408: name ("Tiles")

  Section 2 (`zh`, "瓦片"): payload at bytes 416..425
    - byte 416: tag_length (0x02)
    - bytes 417..419: bcp47 ("zh")
    - bytes 419..425: name = "瓦片" = 0xE7 0x93 0xA6  0xE7 0x89 0x87 UTF-8

  Section 3 (`en-US`, "Tiles (US)"): payload at bytes 436..452
    - byte 436: tag_length (0x05)
    - bytes 437..442: bcp47 ("en-US")
    - bytes 442..452: name ("Tiles (US)")
"""

from __future__ import annotations

from . import _lib, golden_names_multilocale


# --- (a) name field is not valid UTF-8 --------------------------------------

def _mutate_bad_utf8(buf: bytearray) -> None:
    # Section 2's `name` ("瓦片") begins at byte 419 with 0xE7 (the lead byte
    # of a 3-byte UTF-8 sequence). Replace with 0xFF — never a valid UTF-8
    # byte in any sequence position.
    buf[419] = 0xFF


# --- (b) bcp47_tag violates the case requirement -----------------------------

def _mutate_bad_case(buf: bytearray) -> None:
    # Section 3's bcp47 "en-US" (bytes 437..442) → "EN-us": swap the
    # case of the language (lowercase → uppercase) and region (uppercase →
    # lowercase) halves, both required by § 7.4 in their original casing.
    buf[437] = ord("E")   # was 'e'
    buf[438] = ord("N")   # was 'n'
    # byte 439 = '-' unchanged
    buf[440] = ord("u")   # was 'U'
    buf[441] = ord("s")   # was 'S'


# --- (c) bcp47_tag is 3 letters (outside the v1 subset) ----------------------

def _mutate_three_letter(buf: bytearray) -> None:
    # Section 1's payload is `\x02enTiles` (8 bytes). Rewrite to
    # `\x03engiles` so the bcp47 is 3 letters ("eng") and the name shrinks
    # to "iles" — both still valid UTF-8, payload length still 8, so
    # rule #26 stays quiet.
    buf[400] = 0x03                                            # tag_length 2 → 3
    buf[403] = ord("g")                                        # was 'T' (first byte of "Tiles")


_RULE_37_SUMMARY = (
    "NAME `name` MUST be valid UTF-8; when tag_length > 0, `bcp47_tag` MUST "
    "match the v1 restricted BCP-47 subset (`[a-z]{2}` or "
    "`[a-z]{2}-[A-Z]{2}`) (§ 7.4 + § 11 #37)"
)


FIXTURES = [
    _lib.mutate_style_negative(
        name="neg-37a-name-bad-utf8",
        mutate=_mutate_bad_utf8,
        description=(
            "Pack with section 2's `name` UTF-8 lead byte (file offset 419, "
            "first byte of `瓦`) replaced by 0xFF — never a legal UTF-8 byte. "
            "Section framing and bcp47 unchanged; CRC recomputed."
        ),
        mutation="file[419] (section 2 `name` first UTF-8 byte) 0xE7 → 0xFF; CRC recomputed.",
        spec_refs=["§ 7.4"],
        rule_number="37",
        rule_summary=_RULE_37_SUMMARY,
        derived_from="golden-names-multilocale",
        base_module=golden_names_multilocale,
    ),
    _lib.mutate_style_negative(
        name="neg-37b-name-bcp47-bad-case",
        mutate=_mutate_bad_case,
        description=(
            "Pack with section 3's bcp47 (`en-US`, bytes 437..442) rewritten "
            "as `EN-us`: language uppercased, region lowercased. § 7.4's case "
            "requirement is normative; the resulting tag matches neither "
            "permitted shape. CRC recomputed."
        ),
        mutation=(
            "file[437..442] (section 3 `bcp47_tag`) `en-US` → `EN-us` "
            "(4-byte case swap, byte 439 `-` unchanged); CRC recomputed."
        ),
        spec_refs=["§ 7.4"],
        rule_number="37",
        rule_summary=_RULE_37_SUMMARY,
        derived_from="golden-names-multilocale",
        base_module=golden_names_multilocale,
    ),
    _lib.mutate_style_negative(
        name="neg-37c-name-bcp47-3-letter",
        mutate=_mutate_three_letter,
        description=(
            "Pack with section 1's payload rewritten so bcp47 is `eng` "
            "(3 letters): tag_length 2 → 3 and payload byte 3 'T' → 'g'. The "
            "name shrinks from `Tiles` to `iles` (still valid UTF-8); payload "
            "length stays at 8 so rule #26 stays quiet. The 3-letter tag is "
            "outside the v1 restricted subset (`[a-z]{2}` or "
            "`[a-z]{2}-[A-Z]{2}`). CRC recomputed."
        ),
        mutation=(
            "file[400] (section 1 `tag_length`) 0x02 → 0x03; file[403] "
            "(section 1 `bcp47[2]` / former first byte of name) 'T' → 'g'; "
            "CRC recomputed."
        ),
        spec_refs=["§ 7.4"],
        rule_number="37",
        rule_summary=_RULE_37_SUMMARY,
        derived_from="golden-names-multilocale",
        base_module=golden_names_multilocale,
    ),
]
