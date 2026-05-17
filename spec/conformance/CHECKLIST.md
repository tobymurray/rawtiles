---
title: Conformance checklist
nav_order: 2
permalink: /conformance/
---

# rawtiles conformance corpus — fixture checklist

Tracking list of golden and negative fixtures for the rawtiles v1 (spec v0.1) reference corpus. Tick boxes as fixtures land.

Layout (planned):

```
spec/conformance/
├── CHECKLIST.md          (this file)
├── golden/
│   ├── <name>.rawtiles
│   └── <name>.hashes     (per § 14.5)
└── negative/
    └── neg-<rule#>-<short>.rawtiles
```

Numbers in `[brackets]` reference § 11 rejection rules.

---

## Golden fixtures (positive corpus)

Each pack ships with a sibling `<pack>.hashes` file per § 14.5.

### Named in spec § 14.5
- [x] `golden-grid.rawtiles` — regular full grid at a single zoom; the "largest single-zoom layout" of § 14.3
- [x] `golden-pyramid.rawtiles` — multi-zoom; exercises every populated slot of the `zoom_offsets[24]` indirection
- [x] `golden-attr.rawtiles` — exercises extension framing/padding and ATTR multi-source ordering per § 12.1 / Appendix A.4
- [ ] `golden-png-to-pack-1tile.rawtiles` — end-to-end PNG → quantiser → pack pipeline; one tile
- [ ] `golden-png-to-pack-5tiles.rawtiles` — same pipeline, multi-tile; pins resample/alpha-handling output

### Gap-fillers (not named in spec, but the v1 surface needs them)
- [x] `golden-smallest.rawtiles` — minimum-legal non-empty pack (1 tile, no extensions); the "smallest non-empty pack" of § 14.3
- [x] `golden-singleimage-affn.rawtiles` — `(LocalLinear, SingleImage)` with AFFN; the only path that exercises § 7.3 AFFN encoding and § 4.9 LocalLinear bbox derivation
- [x] `golden-tms.rawtiles` — `tile_axis_convention = TMS`; covers the §§ 4.9 / 6.2 / 8.4 TMS branch
- [x] `golden-empty-quadtree.rawtiles` — Quadtree with `tile_count = 0`, NAME-only or ATTR-only payload; § 8.6 metadata-only path
- [ ] `golden-names-multilocale.rawtiles` — multiple `NAME` sections including `tag_length=0` fallback; pins § 7.4 + § 12.1 NAME ordering (the `zh` vs `en-US` byte-order trap)
- [x] `golden-supersedes.rawtiles` — non-zero `supersedes_uuid`
- [ ] `golden-zmax.rawtiles` — tile at `z = 23` (max legal zoom) and `(x, y)` near `2^23 − 1`
- [ ] `golden-canonical-uuid.rawtiles` — pack whose `pack_uuid` is derived per Appendix A, verifying the derivation pipeline against the § A.5 worked example methodology
- [x] `golden-orientation.rawtiles` — 256×256 directional test tile (RED/BLUE/GREEN/YELLOW edge stripes + BLACK/WHITE/MAGENTA/CYAN corner dots) covering § 6.2 row order, § 8.4 XYZ axis, and § 9.1 ABGR2222 saturated palette; lets a renderer detect intra-tile orientation-pipeline bugs by eye
- [x] `golden-orientation-mosaic.rawtiles` — 4×4 grid at z=2, 32×32 px tiles; same intra-tile pattern as `golden-orientation` plus a 24×24 interior byte encoding `0xD0 + (y << 2) + x` per tile, so the composed 128×128 mosaic marches the 16 interior colors `0xD0..0xDF` in row-major order; catches inter-tile placement bugs (x/y swap, row inversion) that `golden-orientation` cannot see

### Accept-path positives (cover § 11 rules that are accept, not reject)
- [x] `golden-minor-1.rawtiles` — `format_version = (1, 1)`; covers § 11 #4 (readers MUST accept) — kept tag-free for clean rule-#4 isolation; the ancillary-tag accept path is anchored by golden-ancillary-tag instead
- [x] `golden-ancillary-tag.rawtiles` — pack carrying an unknown lower-case extension tag (`xnot`); covers § 11 #21 (readers MUST accept and MAY ignore)

---

## Negative corpus (one fixture per § 11 rejection condition)

Each fixture differs from a known-good golden by **one** byte/field. Every file MUST be rejected by a conforming reader.

### Header / file structure
- [x] `neg-01-short-file.rawtiles` — file < 296 bytes [#1]
- [x] `neg-02-bad-magic.rawtiles` — first 4 bytes ≠ `RAWT` [#2]
- [x] `neg-03-major-2.rawtiles` — `format_version_major = 2` [#3]
- [x] `neg-05-uuid-zero.rawtiles` — `pack_uuid` = all-zero [#5]
- [x] `neg-06-parent-nonzero.rawtiles` — `parent_uuid` ≠ all-zero [#6]
- [x] `neg-09-tiledim-zero.rawtiles` — `tile_dim_px = 0` [#9]
- [x] `neg-25-index-offset-296.rawtiles` — `index_offset = 296` (not 292) [#25]
- [ ] `neg-30-pack-too-large.rawtiles` — declared `file_size > 2^32 − 1` *(may be marked "no fixture; impractical to ship 4 GiB" — document the rule as enforced by writer per § 3)*

### Enums (§ 8) [#7]
- [x] `neg-07a-pixfmt-0.rawtiles` — reserved `pixel_format = 0`
- [x] `neg-07b-pixfmt-2.rawtiles` — reserved `pixel_format = 2` (`L4`)
- [x] `neg-07c-proj-0.rawtiles` — reserved `projection = 0`
- [x] `neg-07d-proj-2.rawtiles` — reserved `projection = 2` (equirectangular)
- [x] `neg-07e-addr-0.rawtiles` — reserved `tile_addressing_scheme = 0`
- [x] `neg-07f-axis-0.rawtiles` — reserved `tile_axis_convention = 0`
- [x] `neg-07g-comp-1.rawtiles` — reserved `compression = 1` (LZ4)

### Legal enum pair (§ 8.6) [#8]
- [x] `neg-08a-webmerc-singleimage.rawtiles` — `(WebMercator, SingleImage)`
- [x] `neg-08b-locallinear-quadtree.rawtiles` — `(LocalLinear, Quadtree)`

### Zoom (§ 4.8) [#10]
- [x] `neg-10a-zmax-24.rawtiles` — `zoom_max = 24`
- [x] `neg-10b-zmin-gt-zmax.rawtiles` — `zoom_min > zoom_max`

### bbox (§ 4.9) [#11]
- [x] `neg-11a-lon-overflow.rawtiles` — `max_lon = 180_000_001`
- [x] `neg-11b-lat-overflow.rawtiles` — `min_lat = −90_000_001`
- [x] `neg-11c-lon-inverted.rawtiles` — `min_lon > max_lon`
- [x] `neg-11d-lat-inverted.rawtiles` — `min_lat > max_lat`

### Tile-index entry (§ 5) [#12 – #16, #31, #32]
- [x] `neg-12a-flags-nonzero.rawtiles` — entry `flags ≠ 0` [#12]
- [x] `neg-12b-reserved-nonzero.rawtiles` — entry `reserved ≠ 0` [#12]
- [x] `neg-13a-z-non-monotone.rawtiles` — entries with `z` non-monotone [#13]
- [x] `neg-13b-xy-not-strict.rawtiles` — within a zoom, `(x, y)` not strictly ascending [#13]
- [x] `neg-13c-duplicate-zxy.rawtiles` — two entries with identical `(z, x, y)` [#13]
- [ ] `neg-14a-offset-misaligned.rawtiles` — entry `offset` not 4-aligned [#14a]
- [ ] `neg-14b-offset-below-blob.rawtiles` — entry `offset < tile_blob_start` [#14b]
- [ ] `neg-14c-offset-into-ext.rawtiles` — entry `offset ≥ extensions_offset` [#14c]
- [ ] `neg-14d-length-overruns-blob.rawtiles` — entry `length > extensions_offset − offset` [#14d]
- [x] `neg-15a-z-above-zmax.rawtiles` — entry `z > zoom_max` [#15]
- [x] `neg-15b-z-below-zmin.rawtiles` — entry `z < zoom_min` [#15]
- [x] `neg-16-length-mismatch.rawtiles` — entry `length ≠ tile_dim_px²` for ABGR2222/None [#16]
- [x] `neg-31a-x-overflow.rawtiles` — Quadtree entry `x ≥ 2^z` [#31]
- [x] `neg-31b-y-overflow.rawtiles` — Quadtree entry `y ≥ 2^z` [#31]
- [x] `neg-32a-tile-gap.rawtiles` — gap between consecutive tiles (offset > expected) [#32]
- [x] `neg-32b-tile-overlap.rawtiles` — tiles overlap (offset < expected) [#32]
- [ ] `neg-33-padding-nonzero.rawtiles` — non-zero byte in per-tile alignment padding [#33]

### zoom_offsets directory (§ 4.12) [#17]
- [x] `neg-17a-count-mismatch.rawtiles` — `zoom_offsets[z].count` ≠ actual count at z
- [x] `neg-17b-offset-mismatch.rawtiles` — `zoom_offsets[z].offset` ≠ first-entry-byte-offset at z
- [x] `neg-17c-offset-nonzero-empty.rawtiles` — `zoom_offsets[z] = (nonzero, 0)`

### extensions_offset (§ 4.13) [#18]
- [ ] `neg-18a-extoff-misaligned.rawtiles` — `extensions_offset` not 4-aligned
- [ ] `neg-18b-extoff-past-crc.rawtiles` — `extensions_offset > file_size − 4`
- [ ] `neg-18c-extoff-below-blob.rawtiles` — `extensions_offset < tile_blob_start`
- [ ] `neg-18d-extoff-wrong-sum.rawtiles` — `extensions_offset` doesn't match the padded-length sum

### Extension framing (§ 7.1) [#19]
- [x] `neg-19a-section-overruns.rawtiles` — section `tag+8+length+pad` extends past `file_size − 4`
- [x] `neg-19b-section-padding-nonzero.rawtiles` — section's trailing pad byte ≠ 0x00
- [x] `neg-19c-stranded-bytes.rawtiles` — bytes between last section and CRC footer

### Extension tag rules (§ 7.2 / 7.3) [#20, #27, #28, #29]
- [x] `neg-20-unknown-uppercase-tag.rawtiles` — unknown SDK-reserved tag (e.g. `XYZQ`) [#20]
- [x] `neg-27-tag-digit-first.rawtiles` — first byte is `'1'` (0x31), digit [#27]
- [x] `neg-28-tag-nonprintable.rawtiles` — tag bytes 2–4 contain a control byte [#28]
- [x] `neg-29a-duplicate-uppercase.rawtiles` — two `ATTR` sections [#29]
- [ ] `neg-29b-duplicate-name-locale.rawtiles` — two `NAME` sections with identical `bcp47_tag` [#29]

### AFFN (§ 7.3) [#22, #34, #35, #36]
- [x] `neg-22-locallinear-no-affn.rawtiles` — `projection = LocalLinear` and no AFFN section [#22]
- [x] `neg-34-affn-length.rawtiles` — AFFN `length = 40` [#34]
- [x] `neg-35a-affn-nan.rawtiles` — AFFN coefficient is NaN [#35]
- [x] `neg-35b-affn-inf.rawtiles` — AFFN coefficient is +∞ [#35]
- [x] `neg-36-affn-with-webmercator.rawtiles` — AFFN present with `projection ≠ LocalLinear` [#36]

### NAME (§ 7.4) [#26, #37]
- [ ] `neg-26a-name-payload-empty.rawtiles` — `NAME` payload length = 0 [#26]
- [ ] `neg-26b-name-tag-overruns.rawtiles` — `1 + tag_length > payload length` [#26]
- [ ] `neg-37a-name-bad-utf8.rawtiles` — `name` field contains invalid UTF-8 [#37]
- [ ] `neg-37b-name-bcp47-bad-case.rawtiles` — `bcp47_tag = "EN-us"` (wrong case) [#37]
- [ ] `neg-37c-name-bcp47-3-letter.rawtiles` — `bcp47_tag = "eng"` (3-letter, outside v1 subset) [#37]

### SRCD / ATTR text rules (§ 7.3) [#38]
- [x] `neg-38a-srcd-bad-utf8.rawtiles` — SRCD payload contains invalid UTF-8
- [x] `neg-38b-attr-bad-utf8.rawtiles` — ATTR payload contains invalid UTF-8
- [x] `neg-38c-attr-crlf.rawtiles` — ATTR contains a CRLF line break
- [x] `neg-38d-attr-bare-cr.rawtiles` — ATTR contains a bare CR (0x0D)
- [x] `neg-38e-attr-c0-control.rawtiles` — ATTR contains a C0 control byte (e.g. 0x07)
- [x] `neg-38f-attr-nel.rawtiles` — ATTR contains U+0085 (NEL)
- [x] `neg-38g-attr-ls.rawtiles` — ATTR contains U+2028 (line separator)
- [ ] `neg-38h-attr-trailing-lf.rawtiles` — ATTR ends with a trailing LF *(blocked: § 11 #38 as currently worded explicitly excludes U+000A; needs spec amendment to restate § 7.3's no-trailing-LF rule)*
- [ ] `neg-38i-attr-empty.rawtiles` — ATTR with zero-length payload *(blocked: § 11 #38 as currently worded covers UTF-8 + forbidden codepoints only; needs spec amendment to restate § 7.3's non-zero-length rule)*

### SingleImage shape (§ 8.6) [#23]
Pick representative violations rather than every sub-condition — one fixture per failure mode that the others reduce to:
- [ ] `neg-23a-singleimage-tilecount-2.rawtiles` — `tile_count = 2` *(blocked: needs reshape-style builder; § 5.2 strict-ascending entangles with a second entry)*
- [x] `neg-23b-singleimage-entry-nonzero.rawtiles` — lone entry has `(z, x, y) ≠ (0, 0, 0)`
- [x] `neg-23c-singleimage-zmax-nonzero.rawtiles` — header `zoom_max = 5`
- [x] `neg-23d-singleimage-axis-tms.rawtiles` — `tile_axis_convention = 2` (TMS)
- [ ] `neg-23e-singleimage-zoomoffsets-leak.rawtiles` — `zoom_offsets[1]` non-zero *(blocked: any leak entangles with rule #17 directory consistency)*

### CRC (§ 10) [#24]
- [x] `neg-24-crc-flipped.rawtiles` — final 4 bytes XOR'd with `0x00000001`

---

## Out of scope as fixtures

- **§ 11 #4** — *accept* path (`format_version_minor > 0`); covered by the `golden-minor-1` positive fixture above
- **§ 11 #21** — *accept* path (unknown lowercase tag); covered by the `golden-ancillary-tag` positive fixture above
- **§ 11 #39** — alignment/endian conversion is a reader-implementation guideline, not a content-level rule; no fixture
- **§ 11 #30** — requires a 4 GiB pack; documented as "no fixture" rather than shipping one

---

## Totals

- **Golden corpus:** 15 packs (5 spec-named + 8 gap-fillers + 2 accept-path)
- **Negative corpus:** ~72 fixtures across 38 rules (#1–#38, with #4/#21/#30/#39 excluded as above)
