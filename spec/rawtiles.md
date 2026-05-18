---
title: Specification
nav_order: 1
permalink: /
---

# rawtiles format specification — version 0.6

**Status:** Provisional. The spec is in its v0.x phase: breaking changes between v0.x bumps MAY invalidate existing `pack_uuid`s and existing packs. v1.0 stabilizes the wire format once a second independent consumer has validated against this spec; until then, fixtures and on-disk packs are not guaranteed forward-compatible. v0.6 renames `RLE8` to `RLE` and redefines it as a pixel-level run-length encoding (operating in `bytes_per_pixel(pixel_format)`-byte units) so the v0.4 RGB565 motivation actually compresses; the wire format is unchanged from v0.5 and no v0.5 `RLE8` packs exist in the wild to invalidate.
**Date:** 2026-05-17.
**Wire format version**: the `format_version` bytes in conforming packs are `(1, 0)`. The spec-document version (`0.6`) is distinct from the on-disk wire-format-version bytes (see § 13 for the version semantics).

This document defines the `.rawtiles` binary file format: a byte-level contract between writers (tile-pack builders) and readers (firmware, validators, debug tools, future device-side consumers). Conforming implementations on either side need only this document. The format is intended for offline tile delivery to constrained devices (watches, embedded displays, kiosks, e-readers) where bandwidth and decode budgets are tight.

## Scope and audience

- **Writers** need every section.
- **Readers** need §§ 4–13.
- **Appendix A** is normative only for writers that need to produce byte-identical `.rawtiles` files across implementations given the same logical inputs (the offline-delivery dedup contract). Writers without that goal MAY pick any non-zero `pack_uuid`.

## 1. Conventions

- The key words **MUST**, **MUST NOT**, **SHOULD**, **MAY** are to be interpreted as in RFC 2119 / RFC 8174.
- All multi-byte integers are little-endian.
- All struct fields are tightly packed; no implicit padding between fields within the header or within a tile-index entry.
- Lengths and offsets are byte counts measured from the start of the file (byte 0) unless otherwise stated.
- "Conforming reader" / "conforming writer" mean implementations satisfying §§ 11 and 12 respectively.

## 2. Terminology

- **Pack** — one `.rawtiles` file.
- **Tile** — an addressed byte blob, identified by `(z, x, y)` for quadtree packs or by virtue of being the single image in a single-image pack.
- **Section** — one of the five top-level regions of a pack: *header*, *tile index*, *tile blob*, *extensions*, *footer*.
- **Reserved value** — a byte or tag value whose semantics are deliberately undefined in this version. Writers MUST NOT emit reserved values; readers MUST reject packs that contain them.
- **Eager check** / **lazy check** — a § 11 rule whose enforcement timing the reader chose at open versus at first access. § 11.1 defines the timing constraint (every rule MUST fire before bytes derived from the protected region are returned); § 11.2 classifies which rules MAY be deferred to first access.
- **`bytes_per_pixel(pixel_format)`** — a function from `pixel_format` (§ 8.1) to the on-disk uncompressed byte count for one pixel: `ABGR2222 → 1`, `RGB565 → 2`. Defined in § 6.2.

## 3. File structure

A `.rawtiles` file consists of five sections in fixed order:

```
+---------------------------------+ offset 0
|  Header                         |  fixed 292 bytes (§ 4)
+---------------------------------+ 292
|  Tile index                     |  20 × tile_count bytes (§ 5)
+---------------------------------+ 292 + 20 × tile_count
|  0–3 zero padding bytes         |  to 4-byte alignment
+---------------------------------+ tile_blob_start (4-aligned)
|  Tile blob                      |  per-tile bytes, each 4-aligned (§ 6)
+---------------------------------+ extensions_offset (4-aligned)
|  Extension sections             |  zero or more TLV sections (§ 7)
+---------------------------------+ file_size − 4
|  CRC-32 footer                  |  4 bytes (§ 10)
+---------------------------------+ file_size
```

A pack is at most `2^32 − 1` bytes in total size. All on-disk offsets (`index_offset`, `extensions_offset`, `zoom_offsets[].offset`, tile-index `offset`) are u32 LE. A writer that would produce a larger pack MUST fail with a "pack too large" error rather than overflow.

**Alignment.** The 292-byte header is sized so that every multi-byte header field is naturally aligned at its file offset (u16 fields on 2-byte boundaries, u32 on 4-byte, u64 on 8-byte). `index_offset = 292` is itself 4-aligned, so the u32 fields *within* tile-index entries (at +4, +8, +12, +16 within each 20-byte entry) are also naturally aligned.

**`tile_blob_start`** is the byte offset where the tile blob begins. Both writers and readers compute it as:

```
tile_blob_start := align4(index_offset + 20 × tile_count)
```

where `align4(n) := (n + 3) & ~3` rounds up to a 4-byte boundary. With `index_offset = 292` (normative in v1, § 4.11 + § 11 #25), `index_offset + 20 × tile_count` is already 4-aligned for any `tile_count`, so in v1 `tile_blob_start = index_offset + 20 × tile_count`. Anywhere in this specification (§§ 5, 6, 11, 12) that refers to "the start of the tile blob" means this value.

## 4. Header (offset 0, 292 bytes)

| Offset | Size | Field | Notes |
|------:|----:|---|---|
| 0 | 4 | `magic` | ASCII `RAWT` (`0x52 0x41 0x57 0x54`) |
| 4 | 1 | `format_version_major` | u8; `1` in this version |
| 5 | 1 | `format_version_minor` | u8; `0` in this version |
| 6 | 2 | `reserved_v1_0` | v1.0 writers MUST set this to `0x00 0x00`; readers MUST accept any value (forward-compat hole for v1.x minor bumps) |
| 8 | 16 | `pack_uuid` | non-zero, opaque |
| 24 | 16 | `supersedes_uuid` | all-zero = none |
| 40 | 16 | `parent_uuid` | reserved; MUST be all-zero in v1 |
| 56 | 1 | `pixel_format` | enum, § 8.1 |
| 57 | 1 | `projection` | enum, § 8.2 |
| 58 | 1 | `tile_addressing_scheme` | enum, § 8.3 |
| 59 | 1 | `tile_axis_convention` | enum, § 8.4 |
| 60 | 2 | `tile_dim_px` | u16; non-zero |
| 62 | 1 | `zoom_min` | u8; ≤ `zoom_max` |
| 63 | 1 | `zoom_max` | u8; < 24 |
| 64 | 4 | `bbox.min_lon` | i32 microdegrees |
| 68 | 4 | `bbox.min_lat` | i32 microdegrees |
| 72 | 4 | `bbox.max_lon` | i32 microdegrees |
| 76 | 4 | `bbox.max_lat` | i32 microdegrees |
| 80 | 8 | `build_timestamp` | u64; Unix epoch seconds; 0 = "no freshness info" |
| 88 | 4 | `tile_count` | u32; total entries in the tile index |
| 92 | 4 | `index_offset` | u32; byte offset of tile-index start |
| 96 | 192 | `zoom_offsets[24]` | per-zoom directory (§ 4.12) |
| 288 | 4 | `extensions_offset` | u32; byte offset of first extension section |
| **292** | | **end of header** | |

### 4.1 `magic`

The four ASCII bytes `RAWT`.

### 4.2 `format_version`

A `(major, minor)` pair. This specification defines `(1, 0)`. The fixed-size header layout is frozen per major version; minor bumps add extension tags or enum values, which readers handle per §§ 7.2 and 8.

### 4.3 `pack_uuid`

16 bytes, opaque from the format's perspective. The all-zero value is reserved. Writers MAY pick any non-zero value. Appendix A defines a canonical derivation that lets two writers with the same logical inputs produce identical `pack_uuid`s. This is required for the offline-delivery dedup contract that consumers depend on.

### 4.4 `supersedes_uuid`

16 bytes. The all-zero value is the sentinel for *"this pack supersedes no other"*. A non-zero value advertises that this pack replaces a previous pack with that UUID; readers MAY use the field to drive cache eviction or deduplication.

### 4.5 `parent_uuid`

16 bytes. Reserved in v1 for future pack-compositing support; the only legal v1 value is all-zero.

### 4.6 Enum bytes

`pixel_format`, `projection`, `tile_addressing_scheme`, and `tile_axis_convention` are single-byte enums. See § 8 for legal values.

### 4.7 `tile_dim_px`

u16 little-endian. Pixel side length of one (square) tile. MUST be non-zero.

### 4.8 `zoom_min` / `zoom_max`

Inclusive on both ends. `zoom_max ≥ zoom_min`. `zoom_max < 24` (the size of the per-zoom directory, § 4.12).

For `addressing_scheme = SingleImage` the pack has only one logical image and both fields are 0.

**Canonical derivation (Quadtree).** For cross-writer-reproducible packs, `zoom_min` and `zoom_max` are the actual minimum and maximum `z` byte values present in the tile-index. The fields are derived from the tile data, not from a writer parameter. A writer that internally targets "zooms 5–15" but only finds source tiles at zooms 6–12 MUST emit `(zoom_min, zoom_max) = (6, 12)`. For `tile_count == 0` metadata-only Quadtree packs (§ 8.6), both fields MUST be `0`.

### 4.9 `bbox`

Four `i32` little-endian values, in this byte order: `min_lon`, `min_lat`, `max_lon`, `max_lat`.

- Units: integer microdegrees (= decimal degrees × 10⁶).
- Range: `lon ∈ [−180_000_000, 180_000_000]`; `lat ∈ [−90_000_000, 90_000_000]`. For `projection = WebMercator` the latitude range is further restricted by the Mercator pole limit (~±85.051129°, i.e. ±85_051_129 microdegrees); readers MUST NOT reject packs solely on the basis of latitudes slightly outside that range.
- `min_lon ≤ max_lon`, `min_lat ≤ max_lat`.

**Canonical derivation.** `bbox` is derived from the pack's tile content, not a writer parameter. Two writers given the same logical inputs MUST emit byte-identical `bbox`, subject to the ≤ 1 µ° per-component cross-implementation tolerance documented for the Quadtree formulas below (the SingleImage path is transcendental-free and admits no such slack):

- **Quadtree, `tile_count > 0`**: `bbox` is the tight i32-microdegree bounding box of the lon/lat patches covered by all tile-index entries. Per-tile coverage is computed under WebMercator (§ 8.2) with `tile_axis_convention = XYZ` using the formulas below; for `TMS`, substitute `y' = 2^z − 1 − y` before applying.
  - `lon_west_µ°(z, x) = round_half_even((x · 360_000_000 − 180_000_000 · 2^z) / 2^z)` in exact i64 arithmetic, with banker's rounding on the integer division remainder.
  - `lon_east_µ°(z, x) = lon_west_µ°(z, x + 1)`.
  - `lat_north_µ°(z, y)` = `+85_051_129` if `y == 0`; otherwise `round_half_even(atan(sinh(π · (1 − 2 · y / 2^z))) · (180_000_000 / π))` evaluated in IEEE-754 binary64 with strict rounding (no fused multiply-add, no contracted operations, no extended intermediate precision). `π` and `180_000_000 / π` are the binary64 nearest-rounded values of those mathematical constants.
  - `lat_south_µ°(z, y)` = `−85_051_129` if `y == 2^z − 1`; otherwise `lat_north_µ°(z, y + 1)`.
  - `bbox.min_lon`, `bbox.max_lon`, `bbox.min_lat`, `bbox.max_lat` are the componentwise min/max over `{lon_west_µ°, lon_east_µ°, lat_south_µ°, lat_north_µ°}` across all tile-index entries.
  - Cross-implementation `lat_north_µ°` and `lat_south_µ°` may differ by ≤ 1 µ° due to ≤ 1 ULP divergence between conforming `atan` and `sinh` implementations at non-special arguments; `bbox` divergence from this source is bounded by ≤ 1 µ° per component.
- **Quadtree, `tile_count == 0`** (metadata-only packs, § 8.6): `bbox` is `(0, 0, 0, 0)`. With no tiles there is no tile-coverage region to bound; the canonical sentinel is the origin point. A writer that needs to advertise a different bbox on a zero-tile pack falls outside cross-writer-reproducible packs and MUST document its own convention.
- **SingleImage with `projection = LocalLinear`**: `bbox` is the tight i32-microdegree bounding box of the four image-corner points `(0, 0)`, `(W, 0)`, `(0, H)`, `(W, H)` transformed by the AFFN matrix (§ 7.3), where `W = H = tile_dim_px`. Each corner maps to `(lon, lat) = (a·u + b·v + c, d·u + e·v + f)`, evaluated in IEEE-754 binary64 with strict rounding (no fused multiply-add, no contracted operations, no extended intermediate precision). Conversion to integer microdegrees uses `round_half_even(lon · 1_000_000)` and `round_half_even(lat · 1_000_000)` (§ A.3). The four corners' componentwise min/max give `bbox`.

### 4.10 `build_timestamp`

u64 little-endian; seconds since the Unix epoch (1970-01-01T00:00:00Z).

The value SHOULD represent the freshness of the underlying source data (e.g. most recent source `mtime` or HTTP `Last-Modified`), not the wall-clock build time. § 12 #20 promotes this SHOULD to a MUST for writers claiming round-trip reproducibility; `build_timestamp` is in the CRC scope but NOT in the canonical descriptor (§ A.3), so a wall-clock value produces byte-different packs with the same `pack_uuid`.

**Canonical derivation (reproducibility-claiming writers).** `build_timestamp` is the **maximum** over each source contributing one or more tile-index entries to the pack after conflict resolution (§ 12 #6) of that source's freshness-timestamp (Unix epoch seconds). Sources contributing zero tile-index entries after conflict resolution do NOT count in the max, regardless of their `mtime`. The per-source freshness is the source's filesystem `mtime` (file-backed kinds) or HTTP `Last-Modified` (URL kinds) at the time the writer ingested it; counted sources for which no freshness signal is available (HTTP responses lacking `Last-Modified`, HTTP responses whose `Last-Modified` fails the parser rule below, the `synthetic` kind, etc.) contribute `0` and do NOT count in the max. If no counted source carries a freshness signal, `build_timestamp` is `0`. A single stale source MUST NOT drag the timestamp below a fresher source's freshness.

- Filesystem `mtime` sub-second precision MUST be floored toward the Unix epoch. Future-dated `mtime` MUST be passed through unchanged.
- HTTP `Last-Modified` MUST be parsed as RFC 7231 § 7.1.1.1 IMF-fixdate; obsolete RFC 850 and `asctime()` formats are treated as no freshness signal.
- If the canonical derivation produces `0` while at least one source carried a real freshness signal (i.e. a source's `mtime` or parsed `Last-Modified` was exactly `0`), writers MUST emit `1` instead of `0`.

The value `0` is the sentinel for *"no freshness information available."*

### 4.11 `tile_count` and `index_offset`

- `tile_count` (u32): total number of entries in the tile index across all zooms.
- `index_offset` (u32): byte offset where the first tile-index entry begins.

v1.0 fixes the tile index immediately after the header: `index_offset == 292`.

### 4.12 `zoom_offsets[24]`

A fixed-size directory of 24 entries, one per zoom level `z ∈ [0, 23]`. Each entry is 8 bytes:

| Field | Type | Notes |
|---|---|---|
| `offset` | u32 LE | byte offset of the first tile-index entry at this zoom |
| `count` | u32 LE | number of tile-index entries at this zoom |

For zooms with no tiles, both fields MUST be `0`. For zooms with tiles, `offset` is the byte offset of the first tile-index entry at that zoom (computed as `index_offset + 20 × cumulative_count_of_lower_zooms`), and `count` equals the number of entries walked at that zoom in the index.

### 4.13 `extensions_offset`

u32 little-endian. Byte offset where the first extension section begins.

- MUST equal `tile_blob_start + Σ⟨padded_length(i) : i ∈ [0, tile_count)⟩` where `padded_length(i) = (length(i) + 3) & ~3`.
- For `tile_count == 0` Quadtree packs (§ 8.6), MUST equal `tile_blob_start` (= `292`).
- MUST be `≤ file_size − 4`.
- For packs with no extension sections, MUST equal `file_size − 4`.

## 5. Tile index

A contiguous array of 20-byte entries starting at `index_offset`, holding `tile_count` entries.

### 5.1 Entry layout (20 bytes)

| Offset | Size | Field | Notes |
|---|---|---|---|
| 0 | 1 | `z` | u8; tile zoom level |
| 1 | 1 | `compression` | enum, § 8.5 |
| 2 | 1 | `flags` | u8; reserved in v1, MUST be 0 |
| 3 | 1 | `reserved` | MUST be 0 |
| 4 | 4 | `x` | u32 LE; tile column |
| 8 | 4 | `y` | u32 LE; tile row (interpreted per `tile_axis_convention`) |
| 12 | 4 | `offset` | u32 LE; byte offset of the tile bytes |
| 16 | 4 | `length` | u32 LE; tile-bytes length |
| **20** | | **end of entry** | |

### 5.2 Constraints

A conforming pack satisfies all of:

- Entries are sorted ascending by `(z, x, y)`: `z` values non-decreasing, and within each contiguous run of entries sharing the same `z`, the `(x, y)` values strictly ascending in lexicographic order (the order § 5.3's binary search depends on).
- `z < 24` for every entry.
- `compression` is a value supported by the writer's `format_version` per § 8.5. (v1: `0 = None` and `1 = RLE`.)
- `flags = 0` and `reserved = 0` for every entry in v1. Readers MUST reject non-zero values.
- `offset` is 4-byte aligned and lies within the tile blob (i.e. `offset ≥ tile_blob_start`, per § 3).
- `offset + length ≤ extensions_offset`.
- No two entries share the same `(z, x, y)` triple.

### 5.3 Tile lookup

A reader looking up the bytes for `(z, x, y)` MUST:

1. Treat `z ≥ 24` as out-of-range and return the absent outcome without indexing into `zoom_offsets`. (§ 4.12 fixes the array at 24 entries; § 11 #10 ensures every conforming pack has `zoom_max < 24`, but the lookup's *caller* is unconstrained. A caller passing `z = 30` MUST NOT cause the reader to read past the array bound.)
2. Read `zoom_offsets[z]`. If `count == 0`, return the absent outcome; do NOT proceed to the binary search (a search over zero entries can read adjacent-entry bytes as garbage). § 11 #17 guarantees `offset == 0` whenever `count == 0`, so the absence test is independent of `offset`.
3. Binary-search the `count` entries starting at `offset` for the `(x, y)` key. The within-zoom ordering by `(x, y)` guarantees a well-defined search.
4. If found, read `length` bytes at the entry's `offset` from the file. If not found, return the absent outcome.

## 6. Tile blob

The tile blob is the contiguous region from the (padded) end of the tile index to `extensions_offset`. It contains the raw tile bytes referenced by each index entry's `(offset, length)`.

### 6.1 Alignment

- The blob's start offset MUST be 4-byte aligned. Writers achieve this by emitting 0–3 zero bytes after the tile index.
- Each tile MUST start at a 4-byte-aligned offset.
- Each tile MUST be followed by 0–3 zero bytes of padding so that the next tile (or `extensions_offset`) is 4-byte aligned. Padding bytes are not part of the tile and are NOT counted in the entry's `length`.

### 6.2 Content

The byte content of a tile is determined by `pixel_format` (§ 8.1) and `compression` (§ 8.5).

**Bytes per pixel.** Each v1 pixel format has a fixed on-disk uncompressed byte width:

| `pixel_format` | `bytes_per_pixel` | uncompressed tile bytes |
|---|---:|---|
| `ABGR2222` (1) | 1 | `tile_dim_px²` |
| `RGB565` (2) | 2 | `tile_dim_px² × 2` |

The function `bytes_per_pixel(pixel_format)` is referenced by §§ 6.2, 11 #16, and 14, and is normative.

**Uncompressed layout (`compression = None`).** Every tile is exactly `tile_dim_px × tile_dim_px × bytes_per_pixel(pixel_format)` bytes in row-major order: top-to-bottom rows, left-to-right within each row. The first row is the northernmost pixel row under `tile_axis_convention = XYZ` and the southernmost under `TMS` (§ 8.4). No intra-tile padding. Multi-byte pixels (RGB565) are stored at their natural byte width with intra-pixel layout per § 9; pixels do NOT cross row boundaries.

**Compressed layout (`compression ≠ None`).** The tile bytes are the encoded stream defined by the compression's § 9.10 subsection, applied to the uncompressed-byte sequence above. The encoded stream's length is the tile-index entry's `length` field (§ 5.1); it is not bounded a priori by the format and is checked only against file-layout invariants (§ 11 #14). The decoder MUST produce exactly `tile_dim_px² × bytes_per_pixel(pixel_format)` output bytes; a decode that produces a different count is a per-tile decode error and MUST be surfaced through the reader's tile-fetch return path (open-time rejection for readers that validate eagerly; first-access rejection through `getTile()` for readers that defer the check per § 11.2). Compression operates on the uncompressed pixel stream: each v1 compression encoding is defined in units of `bytes_per_pixel(pixel_format)` bytes (the on-disk pixel width). Multi-byte pixels participate at pixel-boundary granularity and never split across run boundaries in the encoded stream.

## 7. Extension sections

Extension sections begin at `extensions_offset` and continue until the CRC footer. A pack MAY contain zero or more sections.

### 7.1 Section framing

Each section is laid out as:

| Offset within section | Size | Field |
|---:|---:|---|
| 0 | 4 | `tag` (FourCC, ASCII) |
| 4 | 4 | `length` (u32 LE) |
| 8 | `length` | `payload` |
| 8 + `length` | 0–3 | zero padding to 4-byte boundary |

The next section begins at the 4-byte-aligned offset following the previous section's padding.

`length` is the payload length in bytes; it does NOT include the 8-byte section header or trailing padding.

**Section bounds (MUST).** For every extension section in a conforming pack:

- `extensions_offset` MUST be 4-byte aligned.
- The first section's start byte MUST equal `extensions_offset` (no padding between `extensions_offset` and the first tag byte).
- Each section's complete extent (`tag + length + payload + alignment padding`) MUST lie within `[extensions_offset, file_size − 4)`, i.e., before the 4-byte CRC footer.
- `length` MUST NOT cause `section_start + 8 + length` to exceed `file_size − 4`.
- The padding bytes between `payload` and the next section MUST be `0x00`.
- The end of the final section's complete extent (padding inclusive) MUST equal `file_size − 4`. No bytes may exist between the last extension section and the CRC footer. When the pack has no extensions, `extensions_offset` MUST itself equal `file_size − 4` (zero-length extensions region, directly abutting the CRC).

Readers MUST reject packs that violate any of these.

### 7.2 Tag naming and reader behavior on unknown tags

The four-byte tag is compared verbatim. Case is normative for forward-compatibility behavior:

- **Upper-case ASCII first byte** (`0x41–0x5A`, `A–Z`): the tag is **SDK-reserved** ("critical" in PNG terms). Allocated by spec versions. Readers MUST reject any pack containing an upper-case tag they do not recognise.
- **Lower-case ASCII first byte** (`0x61–0x7A`, `a–z`): the tag is **application-private** ("ancillary"). Writers MAY emit any such tag for their own purposes; readers MUST accept the pack and MAY ignore unknown lower-case tags.
- **Any other first byte** (digits, punctuation, control chars, non-ASCII, etc.): reserved for future spec use. Writers MUST NOT emit such tags in v1; readers MUST reject any pack containing one.

Tag bytes 2–4 MAY be any printable ASCII; their case has no normative meaning.

### 7.3 Reserved tags (v1)

| Tag | Meaning | Payload |
|---|---|---|
| `NAME` | Pack display name | Length-prefixed BCP-47 tag + UTF-8 name; see § 7.4. Multiple `NAME` sections MAY appear (one per locale). |
| `SRCD` | Source description | Free-form UTF-8 provenance text (e.g. *"OSM 2026-04 Geofabrik Italy extract, MapLibre style v2"*). |
| `ATTR` | Attribution | UTF-8; LF-separated attribution strings (one per active source, no trailing LF). See ATTR rules below. |
| `AFFN` | Affine matrix | 48 bytes: six little-endian IEEE-754 `f64` values `(a, b, c, d, e, f)` defining the 2×3 affine `[a b c; d e f]` that maps image-pixel coordinates `(u, v)` to geographic coordinates `(lon, lat)` in decimal degrees: `lon = a·u + b·v + c`, `lat = d·u + e·v + f`. Required when `projection = LocalLinear`. |

**Cardinality.** Each upper-case (SDK-reserved) tag MUST appear at most once per pack, except `NAME` which MAY appear multiple times (one per locale, per § 7.4). Readers MUST reject packs containing duplicate upper-case tags.

**Text normalisation.** Writers MUST emit text-bearing extension payloads (ATTR, SRCD, NAME `name`) in Unicode Normalization Form C (NFC, per [UAX #15](https://www.unicode.org/reports/tr15/)). Readers MUST NOT renormalise on read.

Conditional requirements:

- `AFFN` MUST appear exactly once when `projection = LocalLinear` and MUST NOT appear otherwise. All six coefficients MUST be finite IEEE-754 `f64` values (no NaN, no ±∞). Readers MUST reject violations. The pack's `bbox` MUST be derived from `AFFN` per § 4.9.
- Writers MUST emit positive zero (`0x0000000000000000`) for any AFFN coefficient that evaluates to mathematical zero. The negative-zero bit pattern (`0x8000000000000000`) MUST NOT appear on disk.
- AFFN coefficient computation MUST use IEEE-754 binary64 strict rounding: no fused multiply-add, no contracted operations, no extended intermediate precision.
- Writers MUST abort the build if AFFN computation produces a NaN or ±∞ at any intermediate or final step.
- Writers MUST abort the build if the AFFN-derived `bbox` (§ 4.9) falls outside the integer-microdegree ranges of § 4.9.

**ATTR payload rules.**

- Lines are separated by a single LF byte (`0x0A`, U+000A). CRLF and bare CR are NOT permitted. The payload MUST contain no ASCII C0 control character (U+0001–U+001F) other than U+000A (LF), no DEL (U+007F), and no Unicode line-break codepoint U+0085 (NEL), U+2028 (LS), or U+2029 (PS). Writers MUST reject sources carrying any of these in attribution strings; readers MUST reject packs containing them (§ 11 #38).
- No trailing LF after the last string. Readers MUST reject any `ATTR` section whose payload's final byte is `0x0A` (§ 11 #38).
- Payload length MUST NOT be zero. A pack with zero sources MUST omit the `ATTR` section. Readers MUST reject any `ATTR` section whose declared payload length is zero (§ 11 #38).
- For byte-identical reproducibility across writers, the strings MUST be ordered to match the canonical `sources` array order defined in Appendix A.4 (sorted by `(zoom_min, zoom_max, kind, identity)`).

**SRCD is OPTIONAL.** Writers claiming cross-writer reproducibility (§ 14.1) MUST omit SRCD from v1 packs; v1 does not define a canonical SRCD-derivation function. Writers that emit SRCD MUST treat its bytes as part of their intra-writer deterministic surface.

### 7.4 `NAME` payload layout

The `NAME` section's payload is length-prefixed, not delimiter-separated:

| Offset within payload | Size | Field |
|---:|---:|---|
| 0 | 1 | `tag_length` (u8) — number of bytes in the BCP-47 language tag |
| 1 | `tag_length` | `bcp47_tag` — BCP-47 language tag bytes, UTF-8 (ASCII in practice; RFC 5646 tags are ASCII-only) |
| 1 + `tag_length` | — | `name` — UTF-8 pack name, occupies the remainder of the payload |

Rules:

- `tag_length` MAY be `0`, indicating "no locale specified". A pack with multiple `NAME` sections SHOULD include exactly one section with `tag_length = 0` as the unlocalized fallback name.
- Each `bcp47_tag` value (including `tag_length = 0`) MUST appear at most once across all `NAME` sections in a pack. Readers MUST reject packs with duplicate `bcp47_tag` values.
- `bcp47_tag` MUST conform to the **v1 restricted BCP-47 subset** (see below). The full RFC 5646 grammar is not in scope for v1; its ABNF is non-trivial enough that BCP-47 libraries across languages implement it partially, which would let two writers given the same locale tag produce different acceptance behavior (cross-writer divergence trap).
- `name` MUST be valid UTF-8 and SHOULD NOT be empty.

**v1 restricted BCP-47 subset.** When `tag_length > 0`, the `bcp47_tag` byte sequence MUST match one of:

- `language` — exactly two ASCII letters, lowercase (`[a-z]{2}`). Example: `en`, `it`, `ja`.
- `language-REGION` — two lowercase ASCII letters, a hyphen `0x2D`, two uppercase ASCII letters (`[a-z]{2}-[A-Z]{2}`). Example: `en-US`, `pt-BR`.

Writers MUST emit only these two shapes (or `tag_length = 0`). Readers MUST accept these two shapes (and `tag_length = 0`) and MUST reject any other shape (§ 11 #37). The case requirement (lowercase language, uppercase region) is normative.

- The total payload length is `1 + tag_length + name.len()`; the section header's `length` field carries this total.

Readers selecting a `NAME` section for display:

1. Readers SHOULD use RFC 4647 § 3.4 lookup rules to find the best `bcp47_tag` match for the device locale. Readers MAY use a simpler strategy when an RFC 4647 parser isn't feasible (e.g., embedded readers with kilobyte budgets): byte-equal comparison of `bcp47_tag` against the device locale, falling back as below if no exact match.
2. Fall back to the `tag_length = 0` section if no locale matches.
3. If no `tag_length = 0` section exists, readers MUST select the first `NAME` section in pack-file order (canonical per § 12.1).

## 8. Enumerations

In every enum, readers MUST reject any unknown value encountered in the header or tile index. Forward-compatible additions arrive via spec minor-version bumps (§ 13), not by injecting unknown values into v1 packs.

### 8.1 `pixel_format` (header byte 56)

| Value | Name | Status | Bytes/pixel |
|---:|---|---|---:|
| 0 | reserved | reader MUST reject | — |
| 1 | `ABGR2222` | v1 (§ 9.1) | 1 |
| 2 | `RGB565` | v1 (§ 9.2) | 2 |
| 3 | reserved (`RGB888`) | reader MUST reject | — |
| 4 | reserved (`L8` grayscale) | reader MUST reject | — |
| 5 | reserved (`L4` indexed) | reader MUST reject | — |
| 6 | reserved (`L1`, 1-bit) | reader MUST reject | — |
| 7–255 | reserved | reader MUST reject | — |

`ABGR2222` is the bytes-per-pixel-minimal format optimised for displays whose framebuffer is 1 byte/pixel (Una's STM32+TouchGFX target). `RGB565` is the native framebuffer encoding for the ST77xx and ILI93xx LCD-controller families used in most low-power wearables (PineTime, many Bangle.js variants); a reader on such a target can render an `RGB565` tile by emitting bytes to the SPI bus with at most a single big/little-endian byteswap per pixel (one Cortex-M `__REV16` instruction). The remaining `pixel_format` values are reserved for future minor bumps as adoption signals warrant.

### 8.2 `projection` (header byte 57)

| Value | Name | Status |
|---:|---|---|
| 0 | reserved | reader MUST reject |
| 1 | `WebMercator` | v1 |
| 2 | reserved (equirectangular) | reader MUST reject |
| 3 | `LocalLinear` | v1 (single-image hand-drawn packs) |
| 4–255 | reserved | reader MUST reject |

### 8.3 `tile_addressing_scheme` (header byte 58)

| Value | Name | Status |
|---:|---|---|
| 0 | reserved | reader MUST reject |
| 1 | `Quadtree` | v1 |
| 2 | `SingleImage` | v1 |
| 3–255 | reserved | reader MUST reject |

`projection` and `tile_addressing_scheme` are not independently combinable; see § 8.6 for the legal pair table.

### 8.4 `tile_axis_convention` (header byte 59)

| Value | Name | Status |
|---:|---|---|
| 0 | reserved | reader MUST reject |
| 1 | `XYZ` | v1 (slippy-map default; Y increases southward) |
| 2 | `TMS` | v1 (`gdal2tiles --profile mercator` default; Y increases northward) |
| 3–255 | reserved | reader MUST reject |

Meaningful only when `tile_addressing_scheme = Quadtree`; for SingleImage, writers MUST emit `1` (§ 12 #19) and readers SHOULD ignore the byte for rendering.

### 8.5 `compression` (tile-index byte 1)

| Value | Name | Status |
|---:|---|---|
| 0 | `None` | v1 (§ 9.10) |
| 1 | `RLE` | v1 (§ 9.11) |
| 2 | reserved (`QOI`) | reader MUST reject |
| 3 | reserved (`LZ4`) | reader MUST reject |
| 4–255 | reserved | reader MUST reject |

`RLE` is the v1 baseline compression: a pixel-level run-length encoding (§ 9.11) chosen for simplicity (decoder ~30 lines of C, O(1) working memory beyond the pixel-width payload register, row-streamable) and for delivering meaningful flash savings on the synthetic and indexed map content most commonly packed for low-power wearables. Operating in pixel units rather than bytes means the same canonical encoder compresses both `ABGR2222` (1-byte pixels) and `RGB565` (2-byte pixels) without an alternating-byte-pattern blind spot. `QOI` and `LZ4` are reserved for future minor bumps when an implementation with conformance fixtures lands; the reservation prevents application-private use of those compression bytes in v1 packs.

### 8.6 Legal enum combinations and structural constraints

Not every combination of `projection` × `tile_addressing_scheme` is meaningful. v1 defines exactly two legal pairs; readers MUST reject all others.

| `projection` | `tile_addressing_scheme` | Legal in v1 |
|---|---|:---:|
| `WebMercator` (1) | `Quadtree` (1) | ✅ |
| `WebMercator` (1) | `SingleImage` (2) | ❌ — MUST reject |
| `LocalLinear` (3) | `Quadtree` (1) | ❌ — MUST reject |
| `LocalLinear` (3) | `SingleImage` (2) | ✅ |

Readers MUST verify this pairing against the header bytes at offsets 57 and 58 before doing any further parsing.

**SingleImage tile-index constraint.** When `tile_addressing_scheme = SingleImage`:

- `tile_count` MUST be exactly `1`.
- The lone index entry's `z`, `x`, and `y` MUST all be `0`. Readers MUST treat a lookup for `(0, 0, 0)` as the SingleImage tile and return the absent outcome for any other `(z, x, y)`.
- `zoom_min` and `zoom_max` in the header MUST both be `0`.
- `zoom_offsets[0]` is the only non-zero directory entry; `zoom_offsets[1..24]` MUST be all-zero.

Readers MUST reject `SingleImage` packs that violate any of these.

**Quadtree tile-index constraint.** When `tile_addressing_scheme = Quadtree`:

- `tile_count` MAY be `0` (a metadata-only pack carrying only extension sections). When `tile_count == 0` every `zoom_offsets[z]` MUST be `(0, 0)` (§ 4.12), the tile blob is empty, and `extensions_offset == 292`. Readers MUST accept such packs and report no tiles available rather than treat the pack as malformed.

## 9. Pixel formats and compression

§§ 9.1–9.9 define the v1 pixel formats; §§ 9.10 onward define the v1 compression encodings. The numbering reserves space for additional pixel formats (e.g., a future `RGB888` or grayscale `L8`) to land in §§ 9.3–9.9 without renumbering compression subsections.

### 9.1 `ABGR2222`

Each pixel is one byte. Bit layout, MSB to LSB:

```
bit:   7  6   5  4   3  2   1  0
       └─A─┘  └─B─┘  └─G─┘  └─R─┘
```

- Each channel is 2 bits, encoding quanta `{0, 1, 2, 3}` displayed as `{0, 85, 170, 255}` (8-bit equivalents).
- Writers MUST set `A = 3` (fully opaque) for every pixel in v1 packs. v1 readers MUST treat any pixel as opaque regardless of the alpha bits.

#### 9.1.1 Canonical quantisation from RGB888

The canonical quantisation maps each 8-bit channel to a 2-bit quantum via thresholds at the midpoints between displayed levels:

| Input range | Output quantum | Displayed level |
|---:|---:|---:|
| 0 – 42 | 0 | 0 |
| 43 – 127 | 1 | 85 |
| 128 – 212 | 2 | 170 |
| 213 – 255 | 3 | 255 |

The quantisation is integer-only by construction: any conforming implementation MUST produce byte-identical output for the same input across architectures, languages, and platforms.

This quantisation is identified by `quantiser_version = 1` in Appendix A's descriptor for `pixel_format = ABGR2222`. Any byte-output change to the quantisation requires a `quantiser_version` bump (per-pixel-format; § A.3).

Conformance test vectors are in § 14.4.

### 9.2 `RGB565`

Each pixel is a 16-bit little-endian word. Bit layout within the 16-bit value, MSB to LSB:

```
bit:  15 14 13 12 11   10  9  8  7  6  5    4  3  2  1  0
      └──── R ────┘    └────── G ──────┘   └──── B ────┘
```

- R is 5 bits, G is 6 bits, B is 5 bits, occupying one 16-bit word per pixel.
- The 16-bit word is stored **little-endian** on disk, consistent with the general endianness rule of § 1. The low byte (bits 7..0, containing the low 3 bits of G and all 5 bits of B) is at the lower file offset; the high byte (bits 15..8, containing all 5 bits of R and the high 3 bits of G) is at the higher file offset.
- Each pixel is exactly 2 bytes; tile bytes total `tile_dim_px² × 2` for `compression = None`.
- No alpha channel. v1 readers MUST treat every `RGB565` pixel as opaque.

**Native-display note.** The ST77xx and ILI93xx LCD-controller families that dominate low-power-wearable hardware (PineTime, most Bangle.js variants, many DIY watch projects) accept RGB565 directly over SPI but expect **big-endian** byte order on the wire (high byte first). A reader on such a target SHOULD byteswap each pixel during the SPI write rather than storing converted pixels in RAM; the Cortex-M `REV16` / `__REV16` instruction performs the byteswap in a single cycle. This convention (LE on disk, BE on wire when the LCD demands it) keeps the on-disk format aligned with § 1's overall endianness rule while imposing only a single-cycle-per-pixel cost on the target whose hardware was the motivating use case.

#### 9.2.1 Canonical conversion from RGB888

The canonical RGB888 → RGB565 conversion uses bit-truncation: drop the low 3 bits of R and B, and the low 2 bits of G. Equivalently, for an input `(r8, g8, b8)`:

```
r5 = r8 >> 3                                 ; 5 bits
g6 = g8 >> 2                                 ; 6 bits
b5 = b8 >> 3                                 ; 5 bits
pixel16 = (r5 << 11) | (g6 << 5) | b5        ; little-endian on disk
```

The conversion is integer-only by construction; any conforming implementation MUST produce byte-identical output for the same input across architectures, languages, and platforms. This conversion is identified by `quantiser_version = 1` for `pixel_format = RGB565` in Appendix A's descriptor. Any byte-output change requires a `quantiser_version` bump.

Decoder reconstruction (RGB565 → RGB888 for display libraries that need it) MUST use bit-replication (`r8 = (r5 << 3) | (r5 >> 2)`, etc.); other reconstructions (e.g. zero-fill) produce visibly different output and are non-conforming.

Conformance test vectors are in § 14.7.

### 9.10 Compression: `None` (value 0)

The tile bytes are the uncompressed pixel data as defined in § 6.2. Length-check rule § 11 #16 applies.

### 9.11 Compression: `RLE` (value 1)

A pixel-level run-length encoding. The compressor operates on the uncompressed pixel stream of § 6.2 in **pixel units** of `P = bytes_per_pixel(pixel_format)` bytes each: `P = 1` for `ABGR2222`, `P = 2` for `RGB565`. The encoded stream is a sequence of one-byte-prefixed blocks:

```
+--------+----------------------+
| H (1B) | payload (P × N B)    |
+--------+----------------------+
```

`H` is the run header. Its top bit selects the run type, and the low 7 bits give the run length in pixels minus one:

- **Literal run**: bit 7 of `H` is `0` (i.e., `H ∈ [0x00, 0x7F]`). The payload is `(H + 1)` literal pixels (1–128 pixels), occupying `(H + 1) × P` bytes on disk. Decoder copies these bytes verbatim to the output.
- **Repeat run**: bit 7 of `H` is `1` (i.e., `H ∈ [0x80, 0xFF]`). The payload is exactly **one** pixel (`P` bytes). Decoder writes that pixel `((H & 0x7F) + 1)` times to the output (1–128 repetitions), emitting `((H & 0x7F) + 1) × P` bytes total.

Both run types encode 1 to 128 decoded pixels; the encoding has no terminator — the decoder produces exactly `tile_dim_px² × P` output bytes and then stops. If the encoded stream is exhausted before the expected output count is reached, or if a final run's payload extends past the end of the encoded stream, the tile is malformed and the reader MUST surface the error per § 6.2's compressed-layout rule.

**Pixel-boundary granularity.** Runs never straddle pixel boundaries. A repeat run carries one whole pixel's bytes as its payload; a literal run carries an integral number of whole pixels. This is what makes the encoding compress `RGB565` natural content — a run of identical 2-byte pixels (e.g., a solid water region at `0x451F`) collapses to one repeat-run header plus 2 payload bytes regardless of whether the pixel's high and low bytes match.

**Canonical encoding (cross-writer reproducibility).** A writer claiming the round-trip property of § 14.1 MUST emit the canonical RLE encoding, defined as:

1. Greedy: at each pixel position, count the longest run of identical pixels starting at that position. If the run length is `≥ 3` pixels, emit it as a repeat run (capped at 128 pixels); otherwise emit literal pixels.
2. Literal runs are merged: consecutive non-runnable pixels accumulate into a single literal run, capped at 128 pixels (further pixels start a new literal run).
3. Repeat runs exceeding 128 pixels are split into back-to-back 128-pixel repeats followed by a final short repeat or literal block as required.
4. At every step the encoder MUST prefer a repeat run of length `n ≥ 3` over the equivalent `n`-pixel literal run. For runs of length `n = 2` the canonical writer MUST emit a literal run, matching the `≥ 3` threshold above. (A repeat run of length 2 is `1 + P` bytes vs. a 2-pixel literal at `1 + 2P` bytes, so repeat is strictly shorter for any `P ≥ 1`; the canonical writer nonetheless chooses literal at `n = 2` because the single repeat/literal threshold simplifies both encoder and verifier and the savings is at most 1 byte per dimer pair.)

Worst-case expansion (purely literal stream): 1 header byte per 128 input pixels, i.e. `1 / (128 × P)` of input bytes. For `ABGR2222` that is ≈ 0.78%; for `RGB565` it is ≈ 0.39%.

**Decoder state and footprint.** The decoder needs a single one-byte register for `H`, a counter for the current run, a `P`-byte buffer holding the repeat-run pixel value (or pointer to the next literal byte), and the output cursor — `O(P)` working memory beyond the output buffer, ≤ 8 bytes total for the v1 pixel formats. A reader writing decoded pixels directly into a row buffer or directly to the SPI/parallel display bus does not need to hold a whole decoded tile in RAM at any time; the decoder is row-streamable provided the encoder did not place a run boundary that crosses a row boundary in a way the consumer cannot pause (which never occurs — runs are 1..128 pixels and tile rows in v1 are ≥ 1 pixel, so a row boundary always falls within or immediately after a complete run-output cursor advance).

The reference RLE decoder is ≤ 30 lines of C. A reader that intends to be conforming against `RLE`-bearing packs MUST implement decoding; readers that do not support `RLE` MUST reject any pack containing it (the `compression` enum check of § 11 #7 is lazy per § 11.2, so the rejection MAY fire on first per-entry access rather than at open).

Conformance test vectors are in § 14.8.

## 10. Footer (CRC)

The last 4 bytes of the file are a u32 little-endian **CRC-32/ISO-HDLC** value, the variant defined in [ITU-T Rec. V.42 § 8.1.1.6.1](https://www.itu.int/rec/T-REC-V.42) and used by PNG ([RFC 2083 § 15](https://www.rfc-editor.org/rfc/rfc2083#section-15)) and zlib. Check value for the ASCII input `"123456789"` is `0xCBF43926`. Most language standard libraries ship this exact variant: Python `zlib.crc32`, Go `hash/crc32.IEEETable`, Java `java.util.zip.CRC32`, Rust `crc32fast`, Node `zlib.crc32`.

**Scope**: every byte from offset 0 up to (but not including) the CRC's own 4 bytes.

Readers MUST verify the CRC and reject the pack on mismatch. The verification window is conditional, not strict; a reader picks one of three modes and documents which (§ 11.1):

- **Eager verify**: compute the CRC at open time, before any reader API returns success. Simplest; appropriate when open-time latency is not a constraint. Recommended for host-class tooling (validators, build tools, browsers) and for any reader that buffers the full pack.
- **Streaming verify**: a reader MAY return from open before the CRC is fully computed, provided the verification runs in parallel with the reader's structural checks (the open-time tile-index walk of § 11.2 for readers that defer per-tile checks, or the structural full-walk of §§ 11 #12–#19 for readers that validate everything eagerly) and completes BEFORE any semantic content derived from the pack (`pack_uuid`, header fields, tile-index entries, extension payloads, tile bytes) is returned to the caller. The reader's open-success/failure status itself, reflecting whether magic and structural checks passed, MAY be returned synchronously since it carries no pack content. A reader that detects mismatch via streaming verify MUST surface the error on the next caller-facing read and invalidate any data already exposed. A reader that adopts streaming verify MUST document the verification window in its caller-facing API.
- **Caller-asserted trust**: a reader MAY skip the CRC entirely when the caller has provided integrity assurance through a separate channel (a signed installer, content-addressed storage, a previously-verified cache, …). The trust assertion is the caller's responsibility, not the reader's. Readers exposing this mode MUST require an explicit opt-in (e.g., a constructor flag, a "trusted source" capability token) and MUST document the absence of CRC verification in their caller-facing API; an undocumented "tries to verify, may not have finished" path is not conforming.

## 11. Reader requirements

This section is the complete reader-side conformance checklist. Every byte-format MUST defined in §§ 4–10 that a reader is responsible for verifying is restated or cross-referenced here, so a reader-implementer can validate against this single list without back-deriving requirements from prose in §§ 4–10.

### 11.1 Validation timing

v1 admits a single reader-side conformance level. Every § 11.6 rule applies to every conforming reader. *When* each check fires is an implementation choice, constrained by the byte-leak prohibition below: a reader MUST enforce each rule before returning to the caller any byte derived from the region the rule protects, but the reader MAY choose between enforcing every rule at open time and deferring per-tile, per-extension, or AFFN-payload checks to first-access time. § 11.2 classifies which rules MAY be deferred (the *lazy subset*) and which MUST fire at open (the *eager subset*).

The choice exists because the deployment surface for this format spans roughly two orders of magnitude in RAM: from MB-class host environments (browsers, desktop validators, build tools) down to MCU-class wearables with ≤ 64 KB SRAM and only ≤ 16 KB realistically available for the tile-pack reader after the rest of the firmware's working set is accounted for. Two implementation profiles cover most of that range:

- **Eager-validating reader.** Buffers the full pack (or its equivalent under mmap) and enforces every § 11 rule at open time. Open-success means the pack is fully validated — no rule in this section can fire after open. This is the simplest profile and the right choice for host-class implementations, writer round-trip validators, and any reader without a hard RAM ceiling.
- **Lazy-validating reader.** Holds the 292-byte header plus a small fixed-size working set (typically the 192-byte `zoom_offsets[24]` directory and a per-call scratch slot) resident; the rest of the pack is read on demand from the underlying storage. Typical backing storage is a memory-mapped flash region accessed via XIP, an offset-and-length `pread`-style API over a filesystem (littlefs, FAT), or a small caller-supplied buffer the reader populates per request. At open the reader enforces the eager subset of § 11.2; the lazy subset fires at first access for the rule's target. Open-success means the eager subset passed and the lazy checks are armed for per-access firing.

A target-resource sketch for the lazy profile: 292 B header + 192 B (within the header) zoom directory + ~64 B scratch + decoder state (≤ 8 B for `RLE` — header byte, run counter, and a `bytes_per_pixel`-wide repeat-pixel buffer; plus tile-row size for row-streaming output) → structural-reader working memory ≤ 1 KB, plus whatever pixel buffer the renderer chooses to allocate. This fits within an 8 KB working-set budget on the smallest nRF52832-class targets after firmware/LVGL overhead.

**Profile choice is per-reader, not per-pack.** Both profiles reject the same set of invalid packs and accept the same set of valid packs; they differ only in *when* each rejection fires. Writers MUST NOT emit packs that one profile would accept and another would reject — every § 11 rule applies to every conforming reader, regardless of when it fires.

**Documentation requirement.** A reader that defers any rule to first-access time MUST document which rules it defers and which API call surfaces each deferred-check failure (typically `getTile()`, extension iteration, AFFN read), so callers can wire error handling correctly. A reader that enforces every rule at open MAY simply state so. A tooling consumer that assumes open-success implies whole-pack validity MUST be using a reader that documents that guarantee — the two profiles are not silently interchangeable.

**Byte-leak prohibition.** A reader MUST NOT return bytes to the caller for which the relevant rule has not yet been enforced. A reader that detects a deferred-check violation mid-call (e.g., decompression-output length doesn't match the format-expected size; per-entry `flags` byte is nonzero; per-section `tag` byte 1 is outside `[A-Z, a-z]`) MUST surface the error through the call that triggered the access — `getTile()` returns an absent-with-error outcome, an extension iterator yields an error rather than a section, an AFFN reader returns a decode-failure status — and MUST NOT return the offending bytes. Partial output written to a caller-supplied row buffer before the error is detected MUST be either zeroed by the reader or marked invalid through the same error path.

### 11.2 Lazy-validation classification

A reader that defers checks to first-access time (§ 11.1) MUST enforce the *eager subset* at open and the *lazy subset* at first access. The two subsets together cover every rule in § 11.6; the partition is purely about timing.

The lazy subset comprises rules whose target is a per-tile, per-extension, or AFFN-payload region — deferring these lets a reader avoid touching the corresponding bytes until they are actually requested. A reader that defers a rule in this table MUST surface a rejection through its per-call error path without leaking the offending bytes (§ 11.1). Readers that validate every rule eagerly MAY ignore this classification; the table only governs *when* checks fire for the lazy profile.

| Rule | Target | First-access trigger |
|------|---|---|
| #7 (per-entry `compression` byte) | tile-index entry | entry consulted for `getTile()` |
| #12 (per-entry `flags` / `reserved`) | tile-index entry | entry access |
| #13 (entries sorted) | adjacent pair | each step of the § 5.3 binary search verifies the strict-ascending invariant against the two entries it touched; a full-walk equivalent is not required |
| #14 (per-entry offset/length) | tile-index entry | entry access |
| #15 (`z` within zoom range) | tile-index entry | entry access |
| #16 (length matches format) | tile-index entry | entry access |
| #17 (`zoom_offsets[z]` consistency) | zoom-directory entry | first `getTile()` at that zoom; the binary search's first-entry-touched MUST sit at the byte offset declared by `zoom_offsets[z].offset`, and the search's count bound MUST equal `zoom_offsets[z].count`. Full-walk equivalent not required. |
| #19 (per-section framing) | extension section | extension iteration or named-section query reaches the section |
| #20 (unknown upper-case tag) | extension section | reader encounters the section |
| #22 (`LocalLinear` requires AFFN) | pack-level | first AFFN read or first attempt to interpret a LocalLinear coordinate |
| #26 (NAME `tag_length` validity) | NAME section | NAME read |
| #27, #28 (tag byte values) | extension section | reader encounters the section |
| #29 (duplicate tags) | extension stream | extension iteration or a duplicate-detecting query (e.g., NAME-locale lookup); a reader that never enumerates sections is not obligated to detect duplicates |
| #31 (Quadtree `x`, `y` < 2^z) | tile-index entry | entry access |
| #34 (AFFN length) | AFFN section | AFFN read |
| #35 (AFFN finite) | AFFN section | AFFN read |
| #36 (AFFN on non-LocalLinear) | AFFN section | AFFN read |
| #37 (NAME UTF-8 / BCP-47) | NAME section | NAME read |
| #38 (SRCD/ATTR text rules) | SRCD/ATTR section | section read |

**Rule-specific notes:**

- **#18 (`extensions_offset`) and #32 (tight tile-blob layout) are eager for every reader, including lazy-validating ones.** Both are enforced via a single O(`tile_count`) walk of the tile index at open: maintain one u32 running sum of `padded_length`s; at each entry `i`, check `offset(i) == tile_blob_start + running_sum` (#32); after the final entry, check `tile_blob_start + total == extensions_offset` (#18 padded-sum equality). Working memory is one u32 accumulator. The header-resident sub-clauses of #18 (4-byte alignment; `extensions_offset ≤ file_size − 4`; `extensions_offset ≥ tile_blob_start`; for `tile_count == 0` Quadtree packs, `extensions_offset == 292`) are also eager. The walk is cheap enough that no resource-constrained profile needs an escape hatch.

- **#23 (`SingleImage` shape).** The header-resident sub-clauses (`tile_count == 1`; `zoom_min == 0`; `zoom_max == 0`; `tile_axis_convention == 1`; `zoom_offsets[0].count == 1`; `zoom_offsets[0].offset == index_offset`; `zoom_offsets[1..24]` all-zero) are eager. The per-entry sub-clause (the lone entry's `z == x == y == 0`) is lazy and fires when the SingleImage tile is requested.

- **#24 (CRC).** Handled by § 10. The eager / streaming / caller-asserted-trust choice is per-reader and is independent of the eager-vs-lazy choice for the rules in this section; § 10's documentation obligation applies to whichever mode the reader picks.

- **#33 (per-tile padding non-zero) is access-pattern-conditional.** A reader that reads per-tile alignment padding bytes (§ 6.1) MUST reject the pack on non-zero values. A reader that skips padding bytes — as a row-streaming reader naturally does, since padding is not part of the tile — does not violate § 11 by failing to detect a non-zero padding byte. Writers MUST still emit zero padding (§ 12 #8); the reader-side conditional preserves the writer-mandated invariant without forcing every reader to allocate a padding-read pathway. § 14.6 flags `neg-33` as access-pattern-conditional.

- **#39 (alignment).** Reader-implementation guideline. Obligation is unchanged regardless of validation-timing profile.

- **Rule #21** is an accept rule (unknown lower-case tags); behaviour is unchanged regardless of validation-timing profile.

**Eager subset** (every rule not in the lazy table above): #1, #2, #3, #4, #5, #6, #7 (header bytes 56–59 only), #8, #9, #10, #11, #18 (full, including padded-sum equality), #21, #23 (header-resident sub-clauses), #25, #30, #32 (full walk via the open-time index pass above), and the header-resident sub-clauses of any other rule.

**Negative-corpus protocol.** Every fixture in the § 11 negative corpus MUST be rejected by every conforming reader. For an eager-validating reader, "reject" means open-time failure with an appropriate result code. For a lazy-validating reader, "reject" means either open-time failure (eager-subset violation) or first-access failure (lazy-subset violation). The conformance harness MUST drive a lazy-validating reader through the access pattern that surfaces each deferred rule before declaring the reader compliant against that fixture. § 14.6 specifies the per-rule access pattern.

### 11.3 Rejection timing

All rejection rules in § 11.6 (#1 – #38) MUST be enforced before the bytes they protect are returned to the caller. An eager-validating reader enforces every rule at open time and MAY interleave the checks with the CRC verification window of § 10. A lazy-validating reader enforces the eager subset at open and the lazy subset at first-access time per § 11.2. Open-success on an eager-validating reader implies full validation; open-success on a lazy-validating reader implies only that the eager subset passed and the lazy checks are armed (§ 11.1). Rule #39 (alignment + endian conversion) applies before any 64-bit-payload-derived value is returned to the caller; this obligation is independent of the validation-timing profile.

### 11.4 Conformance scope

Conforming readers MUST accept any pack that does not violate one of the MUST rules below. § 11 is the complete reader-side rejection checklist; every reader-binding MUST in §§ 4–10 is restated or cross-referenced here. Readers facing operational limits MAY surface those as runtime errors at lookup or render time, and MAY refuse to open packs whose declared resource footprint exceeds the reader's configured limits, provided such refusals are reported through a distinct error path from conformance rejections. Resource-limit refusal includes, e.g., a reader rejecting a pack whose `tile_dim_px²` exceeds its tile-row-buffer budget — that refusal is operational, not a § 11 rejection.

### 11.5 Allocation ordering

Before allocating any buffer sized by the header-supplied `tile_count`, readers MUST validate that the tile index fits within the file. Compute the check overflow-safely as `file_size ≥ 296` AND `tile_count ≤ (file_size − 296) / 20` (division; u32-safe). The naive multiplicative formulation `296 + 20 × tile_count ≤ file_size` wraps on u32 for `tile_count` near `u32::MAX / 20` and MUST NOT be used directly. This bounds malformed-`tile_count` claims to legal file-size budgets and is enforced before rules below that depend on parsed tile-index entries. Readers that do not allocate a `tile_count`-sized buffer (typically lazy-validating readers per § 11.1) MUST still perform this check at open time, because the same bound is required to bounds-check binary-search entry accesses against the file's tail.

### 11.6 Conforming v1 reader rules

A conforming v1 reader MUST:

1. Reject any file shorter than 296 bytes (292-byte header + 4-byte CRC footer).
2. Reject any file whose first 4 bytes are not `RAWT`.
3. Reject any pack whose `format_version_major ≠ 1`.
4. Accept packs with `format_version_minor > 0`, applying §§ 7.2 and 8 to any extension tags or enum values they contain.
5. Reject `pack_uuid` equal to all-zero.
6. Reject `parent_uuid` not equal to all-zero.
7. Reject any unknown `pixel_format`, `projection`, `tile_addressing_scheme`, `tile_axis_convention`, or `compression` byte (§ 8).
8. Reject any `projection` × `tile_addressing_scheme` combination outside the legal v1 pairs in § 8.6.
9. Reject `tile_dim_px == 0` (§ 4.7).
10. Reject `zoom_max ≥ 24` or `zoom_min > zoom_max` (§ 4.8).
11. Reject `bbox` values outside the integer-microdegree ranges of § 4.9: `min_lon` and `max_lon` outside `[−180_000_000, 180_000_000]`, or `min_lat` and `max_lat` outside `[−90_000_000, 90_000_000]`. Reject `min_lon > max_lon` or `min_lat > max_lat`.
12. Reject any tile-index entry with non-zero `flags` or non-zero `reserved` (§ 5.2).
13. Reject the pack if entries are not sorted ascending by `(z, x, y)`: `z` non-decreasing across all entries; within each zoom, `(x, y)` strictly ascending lexicographically. The strict-within-zoom property forbids duplicate `(z, x, y)` triples and is what § 5.3's binary search depends on.
14. For each tile-index entry, reject the pack if any of the following hold, evaluated in order: (a) `offset` is not 4-byte aligned; (b) `offset < tile_blob_start` (§ 3); (c) `offset ≥ extensions_offset`; (d) `length > extensions_offset − offset`. (c) MUST precede (d); the u32 subtraction underflows otherwise. Readers MAY substitute the single u64 check `(u64)offset + (u64)length ≤ (u64)extensions_offset` for (c)+(d).
15. Reject any tile-index entry with `z > zoom_max` or `z < zoom_min` (§ 4.8).
16. Reject any tile-index entry whose `length` does not match the format-implied tile-bytes size. For `compression = None`, `length` MUST equal `tile_dim_px × tile_dim_px × bytes_per_pixel(pixel_format)` for every entry (§ 6.2). For `compression ≠ None`, this rule does not apply: the encoded payload length is variable and bounded only by § 11 #14, and the decoder's output-length check (§ 6.2's compressed-layout rule) takes over on tile access.
17. Reject the pack if `zoom_offsets[z].count` does not equal the actual count of tile-index entries at zoom `z` for any `z`, or if `zoom_offsets[z].offset` does not equal the byte offset of the first index entry at zoom `z` (when `count > 0`) or is non-zero (when `count == 0`).
18. Reject the pack if `extensions_offset` is not 4-byte aligned, if `extensions_offset > file_size − 4`, if `extensions_offset < tile_blob_start`, or if `extensions_offset ≠ tile_blob_start + Σ⟨padded_length(i) : i ∈ [0, tile_count)⟩` where `padded_length(i) = (length(i) + 3) & ~3` (§ 4.13). For `tile_count == 0` Quadtree packs, the equality reduces to `extensions_offset == 292`.
19. Reject any extension section whose extent (`tag + length + payload + alignment padding`) is not contained in `[extensions_offset, file_size − 4)` (§ 7.1). Compute the upper-bound check overflow-safely as `length ≤ (file_size − 4) − section_start − 8` (subtraction; u32-safe), not `section_start + 8 + length ≤ file_size − 4` (addition; wraps for large `length`). Additionally: (a) verify that the section's padding bytes (0–3 bytes between `payload` and the next 4-byte boundary) are all `0x00` (§ 7.1); readers MUST reject non-zero padding; (b) after the section-walk loop terminates, reject the pack if the walk's terminal position does not equal `file_size − 4`, i.e., stranded bytes exist between the last section's padded end and the CRC footer.
20. Reject any pack containing an unknown extension tag whose first byte is upper-case ASCII (`A–Z`).
21. Accept and MAY ignore any unknown extension tag whose first byte is lower-case ASCII.
22. Reject `projection = LocalLinear` packs that do not contain an `AFFN` extension.
23. When `tile_addressing_scheme = SingleImage`, reject the pack unless ALL of the following hold (§ 8.6): `tile_count == 1`; the lone tile-index entry has `z == 0`, `x == 0`, and `y == 0`; `zoom_min == 0`; `zoom_max == 0`; `tile_axis_convention == 1`; `zoom_offsets[0].count == 1` and `zoom_offsets[0].offset == index_offset`; every `zoom_offsets[z]` for `z ∈ [1, 23]` is `(0, 0)`. A lookup for `(0, 0, 0)` MUST return the SingleImage tile bytes; lookups for any other `(z, x, y)` MUST return the absent outcome.
24. Verify the CRC-32 footer per § 10 (eager, streaming, or caller-asserted-trust) and reject the pack on mismatch. Whichever window the reader chooses, no bytes derived from the pack (including parsed header field values) MUST be returned to the caller while a mismatch is possible.
25. Reject any pack where `index_offset != 292` (§ 4.11).
26. Reject any `NAME` section whose section payload length is less than `1` (no byte available for the mandatory `tag_length`), or where `1 + tag_length > section payload length` (§ 7.4).
27. Reject any extension section whose tag's first byte is outside `[A-Z, a-z]` (digits, punctuation, control chars, non-ASCII, etc., per § 7.2).
28. Reject any extension section whose tag bytes 2–4 contain any byte outside printable ASCII (`0x20`–`0x7E`), per § 7.2.
29. Reject any pack containing two or more sections with the same upper-case extension tag, except `NAME` (per § 7.3 Cardinality); reject any pack containing two or more `NAME` sections sharing the same `bcp47_tag` value (per § 7.4).
30. Reject any pack where `file_size > 2^32 − 1`.
31. For `tile_addressing_scheme = Quadtree`, reject any tile-index entry where `x ≥ 2^z` or `y ≥ 2^z` (§ 5.1).
32. For each tile-index entry `i ∈ [0, tile_count)`, reject the pack if `offset(i) ≠ tile_blob_start + Σ⟨padded_length(j) : j ∈ [0, i)⟩` where `padded_length(j) = (length(j) + 3) & ~3` (§ 12 #8).
33. Reject the pack if any per-tile alignment padding byte in the tile blob (§ 6.1) is non-zero.
34. Reject any `AFFN` section whose `length` field is not `48` (§ 7.3).
35. Reject any `AFFN` section whose six decoded IEEE-754 binary64 coefficients are not all finite (§ 7.3).
36. Reject any pack with `projection ≠ LocalLinear` that contains an `AFFN` section (§ 7.3).
37. Reject any `NAME` section whose `name` field is not valid UTF-8, or whose `bcp47_tag` field (when `tag_length > 0`) does not match the v1 restricted BCP-47 subset of § 7.4.
38. Reject any `SRCD` or `ATTR` section whose payload is not valid UTF-8. Additionally reject any `ATTR` section whose payload (a) contains any byte sequence decoding to U+0001–U+001F other than U+000A, to U+007F, to U+0085, to U+2028, or to U+2029; (b) has declared length zero; or (c) ends with byte `0x0A` (trailing LF after the last string) (§ 7.3).
39. `memcpy` 64-bit values within extension-section payloads into 8-aligned locals before decoding, then convert the little-endian on-disk bytes to host byte order. Payload-internal 64-bit fields (notably `AFFN`'s six `f64`s, § 7.3) may land 4-aligned-not-8-aligned under § 7.1's section-start-only alignment guarantee.

## 12. Writer requirements

This section is the complete writer-side conformance checklist. Every byte-format MUST defined in §§ 4–10 is restated or cross-referenced here so writer-implementers can validate against a single list without having to back-derive requirements from the reader rules in § 11. Where a MUST is detailed elsewhere, the relevant section is cited inline.

A conforming v1 writer MUST:

1. Emit exactly the bytes defined by §§ 4–10 for the inputs. This is a catch-all over the field-level MUSTs that follow; if a conflict arises, the field-level MUST wins.
2. Choose `pack_uuid` as a non-zero 16-byte value (or derive it per Appendix A).
3. Set `parent_uuid` to all-zero.
4. Place the tile index immediately after the header (`index_offset = 292`).
5. Sort the tile index ascending by `(z, x, y)`. The within-zoom `(x, y)` ordering MUST be strictly ascending lexicographic; § 5.3's binary search depends on it (§ 5.2).
6. Reject duplicate `(z, x, y)` tile inputs at write time, **after** applying the canonical conflict-resolution policy below. The policy applies to multi-source writers where two or more sources supply the same `(z, x, y)`:

   **Canonical conflict resolution (later-source-wins).** Apply § A.4's canonical `sources` ordering to the writer's source list. The policy is applied after every source has been rendered through the writer's preprocessing pipeline (§ A.4) to the pre-quantise RGB888 surface, uniformly across source kinds. When two sources supply the same `(z, x, y)` tile, the tile from the source that appears LATER in § A.4's canonical ordering wins; earlier-source tiles for that `(z, x, y)` are silently dropped. After this resolution pass, no two tile-index entries share `(z, x, y)`. If the source list contains a single source, the policy is a no-op.

   Writers that apply a different conflict policy (e.g. first-source-wins, alpha-blend, or strict-reject-any-conflict) MUST NOT claim cross-writer reproducibility; their pack bytes will differ from canonical-policy writers given the same multi-source input. Writers that do NOT accept multi-source input (e.g. only ever one source) need not implement the policy; § 12 #6's strict-reject-duplicate-input rule covers their case directly.
7. Pad the tile index to a 4-byte boundary before the tile blob.
8. Place tile bytes in the tile blob in ascending `(z, x, y)` order matching the tile-index order (§ 5.2). For tile-index entry `i` (0-based), `offset(i)` MUST equal `tile_blob_start + Σ⟨padded_length(j) : j < i⟩` where `padded_length(j) = (length(j) + 3) & ~3`. Each tile starts at a 4-byte-aligned offset; pad with 0–3 zero bytes between tiles. Padding bytes are not counted in the entry's `length`.
9. Place each extension section starting at a 4-byte-aligned offset; pad each payload to a 4-byte boundary with zero bytes.
10. Emit extension sections in a deterministic, input-derivable order (see § 12.1).
11. Populate `zoom_offsets[z] = (0, 0)` for every zoom `z` with no tiles, and `(byte_offset_of_first_entry_at_z, count_at_z)` otherwise.
12. Emit an `AFFN` extension when `projection = LocalLinear` (§ 7.3). The `AFFN` payload MUST be exactly **48 bytes**: six little-endian IEEE-754 `f64` values `(a, b, c, d, e, f)` in that order (§ 7.3).
13. Compute the CRC-32 over every preceding byte and emit it as the file's last 4 bytes.
14. Set `extensions_offset` to a 4-byte-aligned value with `extensions_offset ≤ file_size − 4`. When the pack has no extension sections, `extensions_offset` MUST equal `file_size − 4` (the offset points directly at the CRC footer; § 4.13). When the pack has at least one extension section, the section-extent invariant of § 7.1 applies: specifically, the last section's padded end MUST equal `file_size − 4` (no stranded bytes between extensions and the CRC).
15. Emit each extension section under the framing of § 7.1: 4-byte ASCII `tag`, 4-byte LE `length`, `length` bytes of payload, 0–3 zero bytes of padding to the next 4-byte boundary. The complete extent of every section MUST lie within `[extensions_offset, file_size − 4)`. The first section MUST start exactly at `extensions_offset` (no leading padding).
16. Emit `NAME` payloads under the length-prefixed layout of § 7.4: 1-byte `tag_length`, `tag_length` bytes of BCP-47 tag (UTF-8/ASCII), then the UTF-8 pack name occupying the remainder of the payload. The section header's `length` carries `1 + tag_length + name.len()`.
17. Emit `bbox` per § 4.9: four `i32` LE values in the byte order `min_lon, min_lat, max_lon, max_lat` in integer microdegrees, with `min_lon ≤ max_lon` and `min_lat ≤ max_lat`. Longitudes MUST lie in `[−180_000_000, 180_000_000]`; latitudes MUST lie in `[−90_000_000, 90_000_000]`.
18. Honour the `projection × tile_addressing_scheme` legality table of § 8.6: emit only the v1-legal pairs `(WebMercator, Quadtree)` or `(LocalLinear, SingleImage)`. The header bytes at offsets 57 and 58 MUST encode one of these two pairs and no other.
19. When `tile_addressing_scheme = SingleImage` (§ 8.6), emit exactly **one** tile-index entry whose `z = x = y = 0`; set `zoom_min = zoom_max = 0` in the header; populate `zoom_offsets[0]` only (`zoom_offsets[1..24]` MUST be all-zero); emit `tile_axis_convention = 1` (`XYZ`, the canonical SingleImage value per § 8.4).

A conforming v1 writer MUST (reproducibility-claiming subset):

A writer that advertises round-trip-byte-identical output to its downstream consumers (the dedup contract that drives offline-delivery cache invalidation) MUST additionally:

20. Set `build_timestamp` to a value deterministically derived from the logical inputs, typically the most-recent source-data freshness time (mtime / `Last-Modified`). Wall-clock build time MUST NOT be used. `build_timestamp` is in the CRC scope but NOT in the canonical descriptor (Appendix A), so a wall-clock value produces byte-different packs with the same `pack_uuid`, exactly the dedup failure mode § 14.1 exists to prevent. Writers that do not claim round-trip reproducibility MAY use wall-clock time, but in that case they MUST NOT advertise `pack_uuid` equality as implying byte equality to consumers.
21. Abort the build with a non-zero exit on any source-tile fetch failure (HTTP 4xx/5xx, TLS handshake failure, transport error, timeout, DNS failure). Skip-on-error and blank-fill substitution are not permitted. Retries are permitted if the final retained response bytes are identical to a successful first-attempt fetch.
22. Abort the build with a non-zero exit on any malformed source-tile decoding error (corrupt or unparseable payload, dimension mismatch against `tile_dim_px`, palette decode failure). Synthetic-pixel substitution is not permitted.

A conforming v1 writer MUST NOT:

23. Emit an upper-case extension tag not defined in this spec (§ 7.3).
24. Emit an extension tag whose first byte is outside `[A-Z, a-z]` (digits, punctuation, control chars, non-ASCII, etc., per § 7.2), or whose bytes 2–4 contain any byte outside printable ASCII (`0x20`–`0x7E`).
25. Emit a non-zero `flags` or `reserved` byte in any tile-index entry.

### 12.1 Extension-section ordering

For § 14.1's writer-round-trip property to hold, the order in which extension sections are emitted MUST be a deterministic function of the logical inputs. A conforming v1 writer MUST emit extension sections in this order:

1. **Primary sort: ascending by the 4-byte tag**, compared as unsigned bytes. This puts reserved tags before ancillary ones (`A–Z` < `a–z` in ASCII) and orders within each group lexicographically. For the v1-reserved tags this happens to give the canonical order **`AFFN, ATTR, NAME, SRCD`**.
2. **Secondary sort: for tags with multiple legal instances**, ascending by payload bytes (compared as unsigned bytes, shorter-payload-first when one is a prefix of the other). In v1 only `NAME` has multiple instances, ordered by their length-prefixed payloads. Because the payload's first byte is `tag_length`, the sort is dominated by tag length first, then by tag content within the same length. **This is byte-order on the raw payload, not alphabetical order on BCP-47 tags.** For an example pack with locales `tag_length=0` (fallback), `en`, `en-US`, `it`, and `pt-BR`: the order is `tag_length=0` (length 0, sorts first), then `en` and `it` (length 2, alphabetical among themselves: `en` < `it`), then `en-US` and `pt-BR` (length 5, alphabetical among themselves: `en-US` < `pt-BR`). A tag like `zh` (length 2) would correctly sort before `en-US` (length 5), even though `zh` > `en` alphabetically; the leading `tag_length` byte dominates the comparison.

## 13. Versioning

### 13.1 Semantics

The spec-document version (`0.1`, `0.2`, `1.0`, `1.1`, …) is distinct from the on-disk `format_version` bytes (currently `(1, 0)`).

- **v0.x phase** (current): the spec document is provisional. Breaking changes between v0.x bumps MAY redefine wire-format semantics under the same `format_version = (1, 0)` on-disk bytes; any such change invalidates previously-derived `pack_uuid`s and previously-emitted packs. There is no forward-compat guarantee across v0.x bumps.
- **v1.0** (future): the spec document stabilizes. Wire-format-affecting changes after v1.0 follow the major/minor rules below; pre-v1.0 packs are not guaranteed to remain valid under v1.0.
- **Wire-format major bump** (e.g. `(1, 0) → (2, 0)`): incompatible change. Header layout, tile-index layout, CRC scope, or pixel-format encoding may change. v1 readers MUST reject v2 packs.
- **Wire-format minor bump** (e.g. `(1, 0) → (1, 1)`): additive change. The header layout is frozen per major version; minor bumps allocate new extension tags, new enum values, or relax existing constraints. A v1.0 reader MUST accept v1.x packs, but the per-§ 7.2 / § 8 rules cause it to reject any v1.x pack that uses newly-allocated SDK-reserved values it doesn't know.

**Scope of the v1.x forward-compat hole.** Any v1.x assignment to `reserved_v1_0` (§ 4 header table) MUST be additive: it MAY carry new information for v1.x-aware readers but MUST NOT alter the interpretation of any other v1.0 header or tile-index field. The same constraint applies to any future reserved bytes added by minor bumps. Any v1.x assignment to `reserved_v1_0` MUST simultaneously extend the canonical descriptor schema (§ A.3) with a key reflecting the new information.

### 13.2 Adding new SDK-reserved extension tags

New upper-case tags are allocated by minor-version bumps. Writers MAY emit them in any v1.x pack with `x ≥` the minor that introduced the tag. Readers built against an earlier minor will reject such packs (per § 7.2), which is the intended forward-compatible behavior.

### 13.3 Adding new enum values

New `pixel_format`, `projection`, `addressing_scheme`, `axis_convention`, or `compression` values are allocated by minor-version bumps. Readers built against earlier minors reject packs that use them.

### 13.4 Adding new application-private extension tags

Lower-case tags can be allocated at any time by any writer without a version bump. Readers MUST tolerate unknown lower-case tags.

## 14. Conformance

### 14.1 Writer-round-trip property

A conforming writer applied twice to the same logical inputs MUST produce byte-identical output. Two parties (or two builds on different platforms with bit-equivalent IEEE-754 binary64 `atan` and `sinh` implementations) can then verify that they produced the same pack without sharing the pack bytes. A writer's libm `atan`/`sinh` implementation is part of its deterministic surface (§ 4.9); cross-platform builds dynamically linked against differing libm implementations are not the "same writer" for this purpose.

This property is the writer's responsibility, not the reader's.

**Concrete writer obligations.** The round-trip property reduces to four independent obligations that writers must satisfy together. A failure of any one re-opens the dedup gap:

1. **Preprocessing pipeline determinism.** The pipeline from source-file bytes to the pre-quantise RGB888 stream MUST be deterministic for a given writer (§ A.4). The spec does not prescribe a specific decode/resample/alpha-handling pipeline; it prescribes only that a writer's pipeline have a single byte-output for a given input. Two writers with different pipelines are allowed; they will yield different `content_hash`es and thus different `pack_uuid`s, which is the correct behavior.
2. **Canonical quantiser / format conversion.** Each v1 pixel format has a canonical RGB888 → pixel-format conversion pinned by a test vector: ABGR2222 by § 9.1.1 + § 14.4, RGB565 by § 9.2.1 + § 14.7. Writers MUST match the listed test-vector output for the `pixel_format` they emit; deviation indicates either a bug or a `quantiser_version` divergence requiring a descriptor bump (per-pixel-format; § A.3). Writers using `compression ≠ None` MUST additionally match the canonical encoder for that compression (RLE by § 9.11 + § 14.8); a non-canonical encoder produces byte-different packs and forfeits the round-trip property of this section.
3. **`build_timestamp` determinism.** § 4.10 + § 12 #20. `build_timestamp` is in the CRC scope but NOT in the canonical descriptor, so wall-clock values produce byte-different packs with the same `pack_uuid`. Reproducibility-claiming writers MUST derive `build_timestamp` from logical inputs, not wall-clock.
4. **Text normalisation.** § 7.3. Text-bearing extension payloads (ATTR, SRCD, NAME `name`) MUST be NFC-normalised before emission.

### 14.2 Cross-implementation gate

Third-party implementations SHOULD pass an independent validator against the committed golden fixtures. The golden corpus governs caller-facing tile bytes for valid packs: every conforming reader (eager- or lazy-validating, § 11.1) MUST return the same tile bytes for every `(z, x, y)` listed in each pack's hash table (§ 14.5). The negative corpus is timing-aware for lazy-validating readers: § 14.6 specifies the access pattern a lazy-validating reader's harness must drive to exercise each deferred rule.

### 14.3 Golden fixtures

A corpus of golden fixtures exercises every interesting v1 layout shape: smallest non-empty pack, largest single-zoom layout, multi-zoom `zoom_offsets[24]` directory, extension-section framing and padding (ATTR + multi-source ordering), and the end-to-end decode-quantise-pack pipeline. The corpus also exercises every v1 pixel format / compression combination materially in use: ABGR2222 + None (the v0.3 baseline), RGB565 + None, ABGR2222 + RLE, and RGB565 + RLE. Any drift requires either a deliberate `quantiser_version` / `format_version` bump or an explicit re-bless under the implementation's documented procedure.

Third-party implementations SHOULD verify their reader output against the same fixtures.

### 14.4 ABGR2222 quantiser test vector

A conforming writer applying the canonical quantisation of § 9.1.1 to this 16-pixel RGB888 input MUST produce the listed output. Mismatch indicates either a quantiser bug or a `quantiser_version` divergence.

Input (48 bytes, RGB888, 16 pixels):

```
255,  0,  0      0,255,  0      0,  0,255    255,255,255
128,  0,  0      0,128,  0      0,  0,128    128,128,128
 42, 42, 42     43, 43, 43     85, 85, 85    127,127,127
170,170,170    212,212,212    213,213,213    255,128,  0
```

Output (16 bytes, ABGR2222):

```
0xC3, 0xCC, 0xF0, 0xFF,
0xC2, 0xC8, 0xE0, 0xEA,
0xC0, 0xD5, 0xD5, 0xD5,
0xEA, 0xEA, 0xFF, 0xCB
```

### 14.5 Reader conformance — per-tile hash tables

§ 14.3 pins the *bytes* of each golden pack; § 14.4 pins the *writer* quantiser. Neither catches a reader that opens a golden pack but returns bytes for the **wrong** tile (an off-by-one in binary search, a wrong-zoom lookup, a mis-extracted index entry). Such a reader would pass every previously-listed conformance gate and still be silently wrong.

To close that gap, each golden pack has a sibling `<pack>.hashes` file listing one line per tile:

```
<z> <x> <y> <sha256-hex>
```

Lines are sorted ascending by `(z, x, y)`. Comment lines begin with `#`. A third-party reader passes this conformance check by:

1. Opening the pack.
2. For each `(z, x, y)` in the hash table, calling its tile-lookup API.
3. Computing SHA-256 of the returned bytes.
4. Comparing to the committed hex digest.

A reader that mis-implements the binary-search-within-zoom (§ 5.3), the `zoom_offsets[z]` indirection (§ 4.12), or the tile-index entry decoding (§ 5.1) will fail this test even though the byte-equality fixtures of § 14.3 would pass.

Every conforming reader MUST pass the per-tile hash-table check, regardless of validation-timing profile (§ 11.1). A lazy-validating reader's `getTile()` SHALL surface the same bytes as an eager-validating reader's for valid packs; deferring structural checks does not relax the byte-correctness obligation. For RLE-compressed fixtures the hash digest is computed over the **decoded** tile bytes (the bytes the reader returns to its caller after RLE decoding), not over the encoded payload — readers that fail to decode pass no hash.

The hash tables are committed at:

| Pack | Hash table | `pixel_format` | `compression` |
|---|---|---|---|
| `golden-grid.rawtiles` | `golden-grid.hashes` | ABGR2222 | None |
| `golden-pyramid.rawtiles` | `golden-pyramid.hashes` | ABGR2222 | None |
| `golden-attr.rawtiles` | `golden-attr.hashes` | ABGR2222 | None |
| `golden-png-to-pack-1tile.rawtiles` | `golden-png-to-pack-1tile.hashes` | ABGR2222 | None |
| `golden-png-to-pack-5tiles.rawtiles` | `golden-png-to-pack-5tiles.hashes` | ABGR2222 | None |
| `golden-rgb565-grid.rawtiles` | `golden-rgb565-grid.hashes` | RGB565 | None |
| `golden-rle-abgr.rawtiles` | `golden-rle-abgr.hashes` | ABGR2222 | RLE |
| `golden-rle-rgb565.rawtiles` | `golden-rle-rgb565.hashes` | RGB565 | RLE |

Drift in any hash table requires either re-blessing under the implementation's documented procedure (and pairing with a CHANGELOG entry if the bytes also changed) or a deliberate `quantiser_version` / `format_version` bump.

### 14.6 Negative-corpus access patterns

For lazy-validating readers (§ 11.1), the negative-corpus test (§ 11.6 / `spec/conformance/negative/`) requires the harness to drive the reader through the access that surfaces each deferred rule. Fixtures whose violated rule is in the eager subset surface on `open()` and need no per-fixture access pattern; fixtures whose violated rule is in the lazy subset surface only when the deferred check fires. Eager-validating readers surface every fixture at `open()` and do not consult this table.

The access pattern by lazy rule:

- **Per-entry rules (#7 compression byte, #12, #14, #15, #16, #31, and #13's pairwise-strict-ascending invariant):** call `getTile(z, x, y)` for the `(z, x, y)` of the offending entry. The reader MUST surface an error through `getTile()`'s return value rather than returning bytes.
- **Per-extension rules (#19, #20, #26, #27, #28, #29, #34, #35, #36, #37, #38):** iterate the pack's extension sections through the reader's extension API (or call the named-section query that would consume the section). The reader MUST surface an error through the extension API rather than yielding the section.
- **#17 (zoom_offsets consistency):** call `getTile(z, x, y)` for any `(z, x, y)` at the zoom whose `zoom_offsets[z]` is inconsistent. For an empty-count-but-nonzero-offset fixture (`neg-17c`), call `getTile(z, _, _)` for that `z`; the reader MUST either reject the pack at open or treat the zoom as empty per § 5.3 step 2 — both are conforming because the inconsistency is unobservable through any valid `(z, x, y)` lookup at that zoom.
- **#22 (LocalLinear requires AFFN):** query the AFFN section or call any API that consumes AFFN.
- **#23 per-entry sub-clauses:** call `getTile(0, 0, 0)` on the SingleImage pack; or — for `neg-23b-singleimage-entry-nonzero` — call `getTile(z, x, y)` for the offending entry's coordinates.

**Eager-only fixtures.** `neg-18d` (extensions_offset wrong padded-sum) and the `neg-32*` family (tile-gap, tile-overlap) violate rules that are eager for every conforming reader (§ 11.2), so they surface on `open()` for both validation-timing profiles and need no first-access drive.

**Access-pattern-conditional fixtures.** `neg-33` (per-tile padding non-zero) is rejection-conditional on whether the reader reads padding bytes (§ 11.2). A reader that skips padding bytes — the natural row-streaming pattern — does not violate § 11 by failing to detect this fixture's violation. The corpus manifest MUST flag this fixture as access-pattern-conditional. It is the only fixture in the corpus that need not surface for every conforming reader.

The conformance harness MUST drive each negative fixture through the access pattern listed above before declaring the reader compliant against that fixture.

### 14.7 RGB565 conversion test vector

A conforming writer applying the canonical RGB888 → RGB565 conversion of § 9.2.1 to the § 14.4 input MUST produce the listed output. Mismatch indicates either a conversion bug or a `quantiser_version` divergence for `pixel_format = RGB565`.

Input (48 bytes, RGB888, 16 pixels): same as § 14.4.

Output (32 bytes, RGB565, little-endian on disk; one 16-bit pixel per pair of bytes, low byte first):

```
0x00, 0xF8,   0xE0, 0x07,   0x1F, 0x00,   0xFF, 0xFF,
0x00, 0x80,   0x00, 0x04,   0x10, 0x00,   0x10, 0x84,
0x45, 0x29,   0x45, 0x29,   0xAA, 0x52,   0xEF, 0x7B,
0x55, 0xAD,   0xBA, 0xD6,   0xBA, 0xD6,   0x00, 0xFC
```

The pixel-by-pixel derivation for the first row, evidencing the canonical truncation:
- `(255, 0, 0)` → `(0b11111, 0b000000, 0b00000)` → `0xF800` → bytes `0x00, 0xF8`
- `(0, 255, 0)` → `(0b00000, 0b111111, 0b00000)` → `0x07E0` → bytes `0xE0, 0x07`
- `(0, 0, 255)` → `(0b00000, 0b000000, 0b11111)` → `0x001F` → bytes `0x1F, 0x00`
- `(255, 255, 255)` → `(0b11111, 0b111111, 0b11111)` → `0xFFFF` → bytes `0xFF, 0xFF`

### 14.8 RLE round-trip test vector

A conforming RLE codec MUST round-trip the following test cases byte-identically. Each case lists `(pixel_format, uncompressed bytes, canonical encoded bytes)`. The encoder under § 9.11's canonical-encoding rules MUST produce the encoded column; the decoder under § 9.11's framing MUST recover the uncompressed column. Run counts in `H` are pixels; payload widths follow `P = bytes_per_pixel(pixel_format)`.

| Case | `pixel_format` | Uncompressed | Canonical encoded | Note |
|---|---|---|---|---|
| 1 | ABGR2222 (`P=1`) | `AA` (1 pixel) | `00 AA` | literal-run header `0x00` (length 1 pixel) + 1 payload byte |
| 2 | ABGR2222 (`P=1`) | `AA BB` (2 pixels) | `01 AA BB` | literal-run header `0x01` (length 2 pixels) + 2 payload bytes — `n=2` threshold (§ 9.11 canonical rule 4) prefers literal |
| 3 | ABGR2222 (`P=1`) | `AA AA AA` (3 pixels) | `82 AA` | repeat-run header `0x82` (length 3 pixels) + 1 payload byte |
| 4 | ABGR2222 (`P=1`) | `00` × 128 (128 pixels) | `FF 00` | max repeat-run, header `0xFF` (length 128 pixels) + 1 payload byte |
| 5 | ABGR2222 (`P=1`) | `00` × 129 | `FF 00 00 00` | max repeat-run + 1-pixel literal remainder (canonical rule selects literal for `n<3`) |
| 6 | ABGR2222 (`P=1`) | `AA BB CC DD EE` (5 distinct pixels) | `04 AA BB CC DD EE` | literal-run header `0x04` (length 5 pixels) + 5 payload bytes |
| 7 | ABGR2222 (`P=1`) | `AA AA BB BB BB CC` | `01 AA AA 82 BB 00 CC` | 2-pixel literal, 3-pixel repeat, 1-pixel literal |
| 8 | RGB565 (`P=2`) | `1F 45` (1 pixel = `0x451F`) | `00 1F 45` | literal-run header `0x00` (length 1 pixel) + 2 payload bytes |
| 9 | RGB565 (`P=2`) | `1F 45 1F 45 1F 45` (3 pixels = `0x451F`×3) | `82 1F 45` | repeat-run header `0x82` (length 3 pixels) + 2 payload bytes — demonstrates RGB565 solid-region compression that byte-RLE could not capture |
| 10 | RGB565 (`P=2`) | `1F 45 D3 9C` (2 distinct pixels) | `01 1F 45 D3 9C` | literal-run header `0x01` (length 2 pixels) + 4 payload bytes |
| 11 | RGB565 (`P=2`) | `00 00` × 128 (128 zero pixels) | `FF 00 00` | max repeat-run header `0xFF` (length 128 pixels) + 2 payload bytes |
| 12 | RGB565 (`P=2`) | `1F 45 1F 45 1F 45 D3 9C` (3×`0x451F`, then `0x9CD3`) | `82 1F 45 00 D3 9C` | 3-pixel repeat then 1-pixel literal — note the literal's payload is 2 bytes, not 1, because `P=2` |
| 13 | any | empty / 0 bytes | (writers MUST emit at least one block; uncompressed tile size is `tile_dim_px² × P ≥ 1`, so empty input never occurs in legal packs) | — |

Mismatch on any encoded column for the listed input indicates a non-canonical encoder; mismatch on the decoded output indicates a decoder bug or framing misinterpretation.

## 15. File extension and MIME type

- **File extension:** `.rawtiles`
- **MIME type:** `application/vnd.rawtiles` (proposed; not registered with IANA).

---

## Appendix A — Canonical `pack_uuid` derivation

This appendix defines the canonical `pack_uuid` derivation. It is normative for writers that need to produce byte-identical packs across implementations given the same logical inputs (the offline-delivery dedup contract). Writers without that goal MAY choose any non-zero 16-byte value for `pack_uuid`.

### A.1 Namespace

The rawtiles UUID namespace is the constant:

```
RAWTILES_NAMESPACE = 4e72f962-6632-4538-8e0a-7eab63350f3f
```

This value MUST NOT vary across implementations or spec versions. Changing it would invalidate every `pack_uuid` ever produced and break the recipient-side deduplication check ("does the device already have this pack?").

### A.2 Derivation

```
pack_uuid = UUIDv5(RAWTILES_NAMESPACE, canonical_descriptor_bytes)
```

where `canonical_descriptor_bytes` is defined in § A.3 and UUIDv5 is the SHA-1-based name-based UUID per RFC 4122 § 4.3.

### A.3 Canonical source descriptor

`canonical_descriptor_bytes` is the UTF-8 encoding of a JSON object **canonicalized per [RFC 8785 (JCS)](https://www.rfc-editor.org/rfc/rfc8785)**. Conforming writers MAY use any off-the-shelf JCS library; the canonical-bytes output is required to be byte-identical to what JCS produces.

Two rawtiles-specific rules apply *on top of* JCS. Both are about content shape, not JSON canonicalization:

1. **File-content hashes** are emitted as lowercase hex SHA-256 (64 chars).
2. **Numeric coordinates** are integer microdegrees (= decimal degrees × 10⁶) using banker's rounding (round-half-to-even). Two inputs produce equivalent descriptors **iff they round to the same integer microdegrees under banker's rounding**, not "iff they differ by less than 10⁻⁶ degrees", since two inputs differing by `2×10⁻⁷` can still straddle a rounding boundary and produce different microdegrees. Banker's rounding matters because language defaults diverge: Python 3's `round()` is banker's; C's `lround()` is round-half-away-from-zero; many JavaScript paths are round-half-up. Writers MUST use banker's rounding for descriptor canonicalisation regardless of host-language default. Worked examples:
  - `0.0000005°` → `0 µ°` (the exact-half `0.5` rounds toward even, which is `0`)
  - `0.0000015°` → `2 µ°` (the exact-half `1.5` rounds toward even, which is `2`)
  - `0.0000006°` → `1 µ°` (rounds up; not a tie)
  - `0.0000004°` → `0 µ°` (rounds down; not a tie)

The JCS canonicalization rules this spec relies on are: UTF-8 encoding, no whitespace, top-level keys sorted by UTF-16 codepoint order, no trailing newline, ECMAScript `Number.toString` for numeric values (for the integers used by this descriptor, just the decimal representation: no leading zeros, no `+`/`.0`), and ECMAScript `JSON.stringify` string escape rules (`\"`, `\\`, `\b`, `\t`, `\n`, `\f`, `\r` for the five shortcut control chars; `\u00XX` for other control chars below U+0020; non-ASCII chars emitted as UTF-8 bytes verbatim). The descriptor schema (integers, strings, arrays, nulls; no floats) lands cleanly in the subset of JSON values for which JCS is fully deterministic.

**v1 descriptor invariants.** All keys at every level of the v1 descriptor are ASCII. All integer values in the v1 descriptor fit within `[−(2^53 − 1), +(2^53 − 1)]`. v1.x extensions to the descriptor schema MUST preserve both invariants.

Top-level keys, in lex order:

| Key | Type | Source |
|---|---|---|
| `affn` | array of six hex strings, or `null` | the six IEEE-754 `f64` bit-patterns of the on-disk `AFFN` extension's `(a, b, c, d, e, f)` coefficients, each as a 16-character lowercase hex u64; `null` for non-LocalLinear packs |
| `bbox` | `[i64, i64, i64, i64]` | `[min_lon_µ°, min_lat_µ°, max_lon_µ°, max_lat_µ°]` |
| `format_version` | `[u8, u8]` | from § 4.2 |
| `pixel_format` | int | from § 8.1 |
| `projection` | int | from § 8.2 |
| `quantiser_version` | int | Version of the canonical RGB888 → `pixel_format` conversion for THIS pack's `pixel_format`. Each `pixel_format` versions its conversion independently. `1` for ABGR2222 (§ 9.1.1 + § 14.4) and `1` for RGB565 (§ 9.2.1 + § 14.7) in v1; a future byte-output change to either format's conversion bumps that format's `quantiser_version` without affecting the other. |
| `sources` | array | one object per active source, ordered per § A.4 |
| `style_hash` | hex string or `null` | SHA-256 of the MapLibre style JSON when a renderer-style is in play; `null` otherwise |
| `tile_addressing_scheme` | int | from § 8.3 |
| `tile_axis_convention` | int | from § 8.4 |
| `tile_dim_px` | int | from § 4.7 |
| `zoom_range` | `[u8, u8]` | `[zoom_min, zoom_max]` from § 4.8 |

The `affn` key is **always emitted**; for non-LocalLinear packs its value is `null`.

### A.4 `sources` ordering and per-kind shape

The `sources` array is sorted ascending by `(zoom_min, zoom_max, derived_source_order)`. The derived order compares the source's `kind` name lexicographically (`dir < geotiff < image < mbtiles < pbf < pmtiles < style < synthetic < url`), then the source's *identity* (URL template for `url`; content hash for file-backed kinds; `fixture_version` for `synthetic`).

**Sources without zoom fields.** Some kinds (`synthetic`, `image`) don't carry zoom_min / zoom_max in their per-source shape. For sort-key purposes such sources MUST be treated as `zoom_min = 0, zoom_max = 0`. This puts them ahead of any kind that does carry zoom fields with non-zero values, which is what writers and readers both need to agree on for byte-identical descriptor output.

**Uniqueness.** Within a pack, no two source entries MAY share `(kind, identity)`. This pins the sort key to a total ordering and avoids descriptor-canonicalization ambiguity when otherwise-equal entries would tie on the documented sort key (e.g. two `url` sources with the same `template` but differing `auth_kinds`).

**Source-intrinsic identity.** All per-source descriptor fields (`content_hash`, `zoom_min`, `zoom_max`, `auth_kinds`, `fixture_version`, `template`) are intrinsic to the source's configuration and rendered output, independent of conflict resolution (§ 12 #6). Every configured source appears in `sources` regardless of whether its bytes materially survive conflict resolution.

**Style sources.** Style sources MUST NOT appear in `sources`. A style's effect on a pack is captured via the consuming raster source's `content_hash` and the top-level `style_hash` descriptor key (§ A.3). The `style` kind remains in the canonical kind ordering for forward compatibility.

Per-kind entry shapes (keys in lex order within each object):

- **File-backed kinds** (`dir`, `geotiff`, `mbtiles`, `pbf`, `pmtiles`):

  ```
  {"content_hash":"<sha256-hex>","kind":"<kind>","zoom_max":<int>,"zoom_min":<int>}
  ```

  The `content_hash` domain depends on the kind. **Critically, for every kind it represents the *deterministic surface* of the writer's preprocessing pipeline, never the raw source-file bytes for raster kinds.** This distinction closes the offline-delivery dedup contract: a recipient that has cached `pack_uuid X` and sees a new pack announcement for the same UUID is entitled to assume *byte-identical* tile blobs, not just "same logical inputs". Hashing source-file bytes does not give that guarantee (two writers can decode the same PNG through different sRGB / linear / alpha-handling pipelines and yield different RGB888, producing the same source-file SHA-256 but different tile blobs).

  - **Raster sources** (`dir`, `geotiff`, `mbtiles`, `pmtiles`): `content_hash` is the SHA-256 of the writer's pre-quantisation RGB888 byte stream for this source (the bytes that feed § 9.1.1, after the writer's decode/resample/alpha-handling pipeline has run). The byte stream covers the source's complete rendered tile set (every `(z, x, y)` the source would contribute in the absence of any other source); conflict resolution (§ 12 #6) does not affect `content_hash`. The canonical byte stream is the concatenation of every tile's pixel matrix in ascending `(z, x, y)` order over that complete set. Within each tile, pixels are in row-major order (§ 6.2). Each pixel is exactly 3 bytes: R, G, B (no alpha, no intra-tile padding, no inter-tile separator bytes). The writer's preprocessing pipeline (gamma, alpha-compositing, resampling) is implementation-defined; `content_hash` pins the pipeline's byte output. `zoom_min` and `zoom_max` for raster sources reflect the source's complete rendered range, not the post-conflict realized range.
  - **Vector sources** (`pbf`): `content_hash` is the SHA-256 of the concatenated raw Mapbox Vector Tile bytes in ascending `(z, x, y)` order. v1 does not specify PBF-to-pixel rendering (reserved for a future minor); the hash exists so future PBF-rendering writers can pin their tile output by the source PBF stream.

  The spec does NOT prescribe a specific decode/resample/alpha pipeline; writers MUST document their convention. The round-trip property of § 14.1 then guarantees that two runs of the same writer on the same inputs produce byte-identical packs.

- **`synthetic`** (built-in fixture):

  ```
  {"fixture_version":<int>,"kind":"synthetic"}
  ```

- **`url`** (URL template):

  ```
  {"auth_kinds":[…],"content_hash":"<sha256-hex>","kind":"url","template":"<url>","zoom_max":<int>,"zoom_min":<int>}
  ```

  `auth_kinds` is a sorted, deduplicated array drawn from `"header"` and `"query"`. Authentication *values* (API keys, tokens) MUST NOT appear in the descriptor, only the *kinds* of authentication in use. This keeps `pack_uuid` stable across credential rotations.

  `template` is the URL string as supplied to the writer, byte-verbatim: no scheme/host case folding, no percent-encoding canonicalization, no path normalization, no query-parameter sorting, no trailing-slash addition or removal.

  `content_hash` follows the raster-source rule above: SHA-256 of the writer's pre-quantisation RGB888 byte stream covering the source's complete configured tile set (every `(z, x, y)` for `z ∈ [zoom_min, zoom_max]` the source is configured to provide), ascending `(z, x, y)`, row-major per § 6.2, three bytes per pixel R, G, B, with no padding or inter-tile separator bytes. Conflict resolution (§ 12 #6) does not affect `content_hash`.

  `zoom_min` and `zoom_max` reflect the source's configured fetch range, not the post-conflict realized range.

- **`image`** (LocalLinear hand-drawn):

  ```
  {"content_hash":"<sha256-hex>","kind":"image"}
  ```

  `content_hash` follows the **raster-source** rule above: SHA-256 of the writer's pre-quantisation RGB888 byte stream, *not* the source-image file bytes. Because `image` is a `SingleImage` `tile_addressing_scheme = SingleImage` source (one logical image, no z/x/y), the canonical byte stream is the raster scanline order of the single image: **top-to-bottom rows, left-to-right within each row**, three bytes per pixel `R, G, B`.

### A.5 Worked example

Baseline descriptor for a single-source pack of OSM tiles, z=6–12, world-scale bbox. The `content_hash` value below is a placeholder (all-zero); real packs carry the SHA-256 of the writer's pre-quantisation RGB888 byte stream per § A.4. Note `"affn":null` as the lex-first key (per § A.3, the `affn` key is always emitted; non-LocalLinear packs carry `null`):

```json
{"affn":null,"bbox":[-180000000,-85000000,180000000,85000000],"format_version":[1,0],"pixel_format":1,"projection":1,"quantiser_version":1,"sources":[{"auth_kinds":[],"content_hash":"0000000000000000000000000000000000000000000000000000000000000000","kind":"url","template":"https://tile.openstreetmap.org/{z}/{x}/{y}.png","zoom_max":12,"zoom_min":6}],"style_hash":null,"tile_addressing_scheme":1,"tile_axis_convention":1,"tile_dim_px":128,"zoom_range":[6,12]}
```

Intermediate SHA-1 of (namespace bytes ‖ canonical bytes), 20 hex bytes:

```
e91e34e73c2f329c85a0513a72dbefd4bdae8aa2
```

Derived `pack_uuid` (= first 16 bytes of the SHA-1 with the version-5 bit-stamp at byte 6 and the RFC 4122 variant fixup at byte 8; see § A.2):

```
e91e34e7-3c2f-529c-85a0-513a72dbefd4
```

The intermediate SHA-1 is included so independent implementations can bisect a mismatch: if your SHA-1 differs from the value above, your canonical-bytes formation is the bug; if your SHA-1 matches but your UUID doesn't, your UUIDv5 version/variant fixup is the bug.

---

## Appendix B — Change history

| Spec version | Date | Notes |
|---|---|---|
| 0.1 | 2026-05-14 | Initial v0.x release. Wire format `(1, 0)` admits breaking changes between v0.x bumps until v1.0 stabilization. Supersedes the unreleased `1.0-rc1` draft. |
| 0.2 | 2026-05-15 | § 7.3 + § 14.1: NFC normalisation is MUST-strength for writers emitting text-bearing extension payloads (ATTR, SRCD, NAME `name`). Writer-side tightening; no reader-rejection rules added, no wire-format change. v0.1 packs whose text fields were not NFC-normalised remain readable but are no longer cross-writer-reproducible under v0.2. |
| 0.3 | 2026-05-17 | § 11 #38: extend the ATTR-specific rejection clause to also fire on (b) zero declared payload length and (c) trailing 0x0A (LF) after the last string. Both invariants already existed in § 7.3's ATTR payload rules; this revision restates them as reader rejections to match the existing codepoint-set clause. § 7.3 ATTR bullets updated with matching "readers MUST reject" language. v0.2 packs with zero-length or trailing-LF ATTR remain *writer-invalid* (those rules predated 0.3) but were previously not required to be reader-rejected; v0.3 readers MUST reject them. |
| 0.4 | 2026-05-17 | **Cross-device alignment release.** Three additive changes intended to unblock conforming readers and writers on the non-Una half of the target device class (PineTime/InfiniTime, wasp-os, Bangle.js, similar nRF52832-class wearables). (1) **Pixel format `RGB565`** added at `pixel_format = 2` (§ 8.1, § 9.2, § 9.2.1) with canonical RGB888 → RGB565 bit-truncation, little-endian on disk, and explicit ST77xx-family big-endian-on-wire guidance. Conversion test vector at § 14.7. (2) **Compression `RLE8`** added at `compression = 1` (§ 8.5, § 9.11) as the v1 baseline byte-level run-length encoding; decoder ~25 lines of C, O(1) working memory, row-streamable, canonical-encoder rules pinned for cross-writer reproducibility. Round-trip test vector at § 14.8. § 6.2 generalised to define `bytes_per_pixel(pixel_format)` and compressed-vs-uncompressed tile layout. § 11 #16 generalised to match. (3) **Conformance tiers** added: Tier-1 (Strict, current behaviour) and Tier-2 (Streaming) defined in § 11.1, with the lazy-rule classification in § 11.2. § 11 prologue's "lazy validation is NOT conforming" sentence is superseded. § 10 CRC subsection updated to make streaming verify and caller-asserted trust the normative Tier-2 default. § 14.2 / § 14.5 / new § 14.6 specify tier-agnostic golden-corpus correctness and a Tier-2 access-pattern protocol for the negative corpus. Appendix A.3 `quantiser_version` clarified as per-pixel-format. **Wire format unchanged**: existing v0.3 ABGR2222+None packs are byte-compatible with v0.4 readers. **Motivation**: v0.3 silently disqualified the smaller half of the target device class — PineTime-class targets have 64 KB SRAM, RGB565 framebuffers, and ~200 KB usable flash for map data, none of which the v0.3 spec admitted. The three changes together make a conforming Tier-2 RGB565 reader feasible in <1 KB of structural working memory plus a row-buffer-sized decode scratch, and compressed packs that fit a meaningful map area in 200 KB flash budgets. The two-tier design preserves Tier-1's strict-validation guarantees for host-class tooling while opening the bottom of the device-class range. |
| 0.5 | 2026-05-17 | **Conformance-model consolidation.** Collapses v0.4's Tier-1 / Tier-2 split into a single conformance level with lazy validation permitted as a per-reader implementation choice. (1) § 11.1 rewritten: one conformance level, two documented implementation profiles (eager-validating and lazy-validating). Every § 11 rule applies to every conforming reader; the eager-vs-lazy choice governs only *when* each check fires, subject to the byte-leak prohibition. (2) § 11.2 rewritten: lazy-validation classification table retained, but the v0.4 Tier-2 substitution clauses are deleted — #18 padded-sum equality and #32 tight tile-blob layout are now eager for every reader, enforced via a single O(`tile_count`) walk of the tile index at open with one u32 accumulator. #33 (per-tile padding non-zero) remains access-pattern-conditional, framed without tier vocabulary. (3) § 14.6 rewritten: the v0.4 "tier-conditional" fixture list (`neg-18d`, `neg-33`) collapses to a single access-pattern-conditional fixture (`neg-33`); `neg-18d` and the `neg-32*` family are now eager-surfaced for every reader. (4) § 10 CRC modes retained (eager / streaming / caller-asserted-trust) but reframed as a per-reader choice with no tier-specific defaults. (5) Terminology in § 2 replaces the Tier-1 / Tier-2 entry with eager / lazy check definitions. § 9.11, § 11.3, § 11.4, § 11.5, § 14.2, and § 14.5 updated to drop tier vocabulary. **Motivation**: v0.4's Tier-2 admitted `neg-18d` and `neg-33` as unsurfacable through any defined Tier-2 access, creating two definitions of "valid pack" (a Tier-1 reader could reject a pack a Tier-2 reader accepted). Forcing #18 padded-sum and #32 into the open-time index walk closes the gap at trivial cost (one u32 accumulator, one O(`tile_count`) pass), while preserving v0.4's lazy-validation ergonomics for MCU readers. **Wire format unchanged** from v0.4; existing v0.4 packs remain valid under v0.5. **Reader impact**: a v0.4 Tier-2 reader that relied on the substitutions of v0.4 § 11.2's #18/#32 notes must add the open-time index walk to be v0.5-conforming; the walk costs one u32 of state and is already within the resource-sketch budget of § 11.1. A v0.4 Tier-1 reader is unconditionally v0.5-conforming. |
| 0.6 | 2026-05-17 | **Compression redefined in pixel units.** Renames `compression = 1` from `RLE8` (byte-level RLE) to `RLE` (pixel-level RLE) and rewrites § 9.11 to operate over `bytes_per_pixel(pixel_format)`-byte units. The wire-format codepoint, header-byte semantics, and 1..128-unit run lengths are unchanged; what changes is the unit of measure: run lengths and literal counts are now pixels instead of bytes. **Motivation**: a byte-level RLE on RGB565 (the v0.4 PineTime-class motivation) compresses to ~90% of raw on natural map content because adjacent identical RGB565 pixels produce alternating-byte streams that byte-RLE cannot run. Empirical measurement on the `stanley.rawtiles` corpus (12 tiles, zooms 12–14): byte-RLE on RGB565 → 90.0% of raw; pixel-RLE on RGB565 → 27.0% of raw (3.7×). Pixel-RLE on `ABGR2222` is unchanged from byte-RLE since `P = 1`, so the ABGR2222 test vectors of v0.4's § 14.8 still hold (re-labelled as pixel-unit cases). **Spec deltas**: § 8.5 enum table renamed `RLE8 → RLE`; § 8.5 prose paragraph rewritten; § 6.2 compressed-layout last sentence rewritten to reflect pixel-boundary granularity; § 9.11 entirely rewritten (pixel units, removed `Operates on bytes, not pixels` admission paragraph, decoder-state footprint generalised to `O(P)`); § 11.1 lazy-profile resource sketch updated for pixel-width-aware decoder state; § 12 #2 and § 14 / § 14.2 / § 14.5 / § 14.8 references retitled; golden fixture filenames `golden-rle8-*` → `golden-rle-*`. § 14.8 test-vector table extended with five RGB565 cases (#8–#12) demonstrating 2-byte-pixel granularity. **Wire format unchanged** from v0.5; the v0.5 `RLE8` definition was never instantiated in a published fixture or pack (the `golden-rle8-*` rows in v0.5 § 14.2 were a forward declaration), so the rename costs nothing. **Reader impact**: any reader written against v0.5 § 9.11 byte-level semantics needs the inner loop reworked to read `P`-byte units; for `ABGR2222`-only readers this is a no-op. **Out-of-scope known stale fixtures**: `neg-07b-pixfmt-2.rawtiles` (asserts `pixel_format = 2` reserved — invalid since v0.4 legalised RGB565 at 2) and `neg-07g-comp-1.rawtiles` (asserts `compression = 1` reserved — invalid since v0.4 legalised RLE at 1) remain in the negative corpus from v0.3 and are not corrected here; both should be repurposed against the next reserved codepoint in a follow-up. |

Note: the *spec document* version (`0.1`, `0.2`, `1.0`, `1.1`, …) is distinct from the *wire format* `format_version` bytes in the header. Multiple spec-document revisions can describe the same wire format `(1, 0)` if the changes are editorial or normative-clarification only.
