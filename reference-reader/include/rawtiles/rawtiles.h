/*
 * rawtiles reference reader — public API
 *
 * Conformance target: rawtiles spec v0.6 (wire format v1.0).
 *   https://github.com/tobymurray/rawtiles
 *
 * Design:
 *   - Single conformance level per spec § 11.1, with eager and lazy validation
 *     timing exposed as caller-selectable open flags.
 *   - No heap allocation inside the library. Caller owns the rawtiles_t struct,
 *     the I/O backing, and any output buffers.
 *   - Two I/O modes: a flat in-memory pointer (host-class, mmap-backed) or a
 *     caller-supplied pread callback (MCU-class, XIP / littlefs / etc.).
 *   - Pure C99. Vendors cleanly into C and C++ projects.
 *
 * SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026, Toby Murray
 */
#ifndef RAWTILES_H
#define RAWTILES_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

/* -------------------------------------------------------------------------
 * Result codes
 *
 * RAWTILES_OK and RAWTILES_ABSENT are normal outcomes (the latter for tile
 * lookups against an unpopulated (z,x,y)). Every other code indicates a
 * § 11 rejection or an I/O / API misuse failure.
 *
 * The numeric value of the rule-specific codes equals 100 + spec rule number,
 * so RAWTILES_ERR_RULE_14 == 114. This makes it easy to map a code back to
 * the spec section that fired it.
 *
 * Some § 11 rules have multiple sub-clauses (e.g. #14 a/b/c/d). v0.1 of this
 * reader returns the umbrella code; sub-clause discrimination is a follow-up.
 * ----------------------------------------------------------------------- */
typedef enum rawtiles_result {
    RAWTILES_OK = 0,
    RAWTILES_ABSENT = 1,           /* tile (z,x,y) not present; not an error */
    RAWTILES_ERR_IO = 2,           /* caller's pread() returned non-zero */
    RAWTILES_ERR_BUFFER_TOO_SMALL = 3,
    RAWTILES_ERR_INVALID_ARG = 4,
    RAWTILES_ERR_INTERNAL = 5,     /* indicates a reader bug; should not fire */

    /* § 11 rejection rules (numeric value = 100 + rule number). */
    RAWTILES_ERR_RULE_1_SHORT_FILE                = 101,
    RAWTILES_ERR_RULE_2_BAD_MAGIC                 = 102,
    RAWTILES_ERR_RULE_3_BAD_VERSION               = 103,
    /* #4 is an accept rule */
    RAWTILES_ERR_RULE_5_UUID_ZERO                 = 105,
    RAWTILES_ERR_RULE_6_PARENT_NONZERO            = 106,
    RAWTILES_ERR_RULE_7_BAD_ENUM                  = 107,
    RAWTILES_ERR_RULE_8_BAD_PROJ_ADDR_PAIR        = 108,
    RAWTILES_ERR_RULE_9_TILEDIM_ZERO              = 109,
    RAWTILES_ERR_RULE_10_BAD_ZOOM_RANGE           = 110,
    RAWTILES_ERR_RULE_11_BAD_BBOX                 = 111,
    RAWTILES_ERR_RULE_12_BAD_ENTRY_FLAGS          = 112,
    RAWTILES_ERR_RULE_13_BAD_ENTRY_ORDER          = 113,
    RAWTILES_ERR_RULE_14_BAD_ENTRY_BOUNDS         = 114,
    RAWTILES_ERR_RULE_15_ENTRY_ZOOM_OUT_OF_RANGE  = 115,
    RAWTILES_ERR_RULE_16_BAD_ENTRY_LENGTH         = 116,
    RAWTILES_ERR_RULE_17_BAD_ZOOM_OFFSETS         = 117,
    RAWTILES_ERR_RULE_18_BAD_EXT_OFFSET           = 118,
    RAWTILES_ERR_RULE_19_BAD_SECTION_FRAMING      = 119,
    RAWTILES_ERR_RULE_20_UNKNOWN_UPPERCASE_TAG    = 120,
    /* #21 is an accept rule */
    RAWTILES_ERR_RULE_22_LOCALLINEAR_NEEDS_AFFN   = 122,
    RAWTILES_ERR_RULE_23_BAD_SINGLEIMAGE          = 123,
    RAWTILES_ERR_RULE_24_BAD_CRC                  = 124,
    RAWTILES_ERR_RULE_25_BAD_INDEX_OFFSET         = 125,
    RAWTILES_ERR_RULE_26_BAD_NAME_LENGTH          = 126,
    RAWTILES_ERR_RULE_27_BAD_TAG_FIRST_BYTE       = 127,
    RAWTILES_ERR_RULE_28_BAD_TAG_PRINTABLE        = 128,
    RAWTILES_ERR_RULE_29_DUPLICATE_TAG            = 129,
    RAWTILES_ERR_RULE_30_PACK_TOO_LARGE           = 130,
    RAWTILES_ERR_RULE_31_QUADTREE_XY_OVERFLOW     = 131,
    RAWTILES_ERR_RULE_32_TILE_LAYOUT_NOT_TIGHT    = 132,
    RAWTILES_ERR_RULE_33_NONZERO_PADDING          = 133,
    RAWTILES_ERR_RULE_34_BAD_AFFN_LENGTH          = 134,
    RAWTILES_ERR_RULE_35_AFFN_NOT_FINITE          = 135,
    RAWTILES_ERR_RULE_36_AFFN_ON_NON_LOCALLINEAR  = 136,
    RAWTILES_ERR_RULE_37_BAD_NAME_TEXT            = 137,
    RAWTILES_ERR_RULE_38_BAD_SRCD_OR_ATTR_TEXT    = 138,
    /* #39 is a reader-implementation alignment rule, not a rejection */
} rawtiles_result_t;

/* -------------------------------------------------------------------------
 * Enum values (mirroring spec § 8).
 *
 * The numeric values match the on-disk enum bytes, so callers MAY compare
 * directly against the parsed header field.
 * ----------------------------------------------------------------------- */
typedef enum rawtiles_pixel_format {
    RAWTILES_PIXEL_ABGR2222 = 1,
    RAWTILES_PIXEL_RGB565   = 2,
} rawtiles_pixel_format_t;

typedef enum rawtiles_compression {
    RAWTILES_COMPRESSION_NONE = 0,
    RAWTILES_COMPRESSION_RLE  = 1, /* pixel-level RLE per § 9.11 (v0.6) */
} rawtiles_compression_t;

typedef enum rawtiles_projection {
    RAWTILES_PROJ_WEBMERCATOR = 1,
    RAWTILES_PROJ_LOCALLINEAR = 3,
} rawtiles_projection_t;

typedef enum rawtiles_addressing {
    RAWTILES_ADDR_QUADTREE    = 1,
    RAWTILES_ADDR_SINGLEIMAGE = 2,
} rawtiles_addressing_t;

typedef enum rawtiles_axis {
    RAWTILES_AXIS_XYZ = 1,
    RAWTILES_AXIS_TMS = 2,
} rawtiles_axis_t;

/* -------------------------------------------------------------------------
 * I/O descriptor
 *
 * The caller picks one of two modes:
 *   - RAWTILES_IO_MEMORY: a contiguous in-memory buffer (mmap, file fully
 *     loaded, etc.). Use rawtiles_io_memory() to construct.
 *   - RAWTILES_IO_PREAD: a callback that fills caller-supplied buffers from
 *     the underlying storage on demand. Use rawtiles_io_pread() to construct.
 *     The callback returns 0 on success, non-zero on I/O error.
 * ----------------------------------------------------------------------- */
typedef int (*rawtiles_pread_fn)(void *ctx, uint8_t *dest, uint32_t offset,
                                 uint32_t len);

typedef struct rawtiles_io {
    enum { RAWTILES_IO_MEMORY, RAWTILES_IO_PREAD } mode;
    uint32_t size; /* total pack size in bytes (both modes) */
    union {
        const uint8_t *base; /* RAWTILES_IO_MEMORY */
        struct {
            rawtiles_pread_fn pread;
            void *ctx;
        } pread; /* RAWTILES_IO_PREAD */
    } u;
} rawtiles_io_t;

static inline rawtiles_io_t rawtiles_io_memory(const uint8_t *base,
                                               uint32_t size)
{
    rawtiles_io_t io;
    io.mode = RAWTILES_IO_MEMORY;
    io.size = size;
    io.u.base = base;
    return io;
}

static inline rawtiles_io_t rawtiles_io_pread(rawtiles_pread_fn fn, void *ctx,
                                              uint32_t size)
{
    rawtiles_io_t io;
    io.mode = RAWTILES_IO_PREAD;
    io.size = size;
    io.u.pread.pread = fn;
    io.u.pread.ctx = ctx;
    return io;
}

/* -------------------------------------------------------------------------
 * Open flags
 *
 *   RAWTILES_OPEN_DEFAULT
 *     Eager validation: every § 11 rule is checked at open time. Equivalent
 *     to the host-class profile.
 *
 *   RAWTILES_OPEN_LAZY
 *     Lazy validation per § 11.2: per-tile, per-extension, and AFFN rules
 *     defer to first-access time. Open validates only the eager subset
 *     (header-resident rules plus the open-time tile-index walk that checks
 *     #18 padded-sum and #32 tight layout). Appropriate for MCU profiles.
 *
 *   RAWTILES_OPEN_TRUST_CRC
 *     Skip CRC verification (§ 10 caller-asserted-trust). The caller is
 *     responsible for integrity assurance through a separate channel.
 *
 *   RAWTILES_OPEN_STREAM_CRC
 *     Streaming-verify CRC (§ 10): open() may return success before the CRC
 *     is fully validated, but no semantic content (header fields, tile bytes,
 *     extensions) will be returned to the caller before the verification
 *     completes. v0.1 of this reader does not implement this and treats it as
 *     equivalent to RAWTILES_OPEN_DEFAULT (eager CRC).
 * ----------------------------------------------------------------------- */
typedef enum rawtiles_open_flags {
    RAWTILES_OPEN_DEFAULT    = 0,
    RAWTILES_OPEN_LAZY       = 1u << 0,
    RAWTILES_OPEN_TRUST_CRC  = 1u << 1,
    RAWTILES_OPEN_STREAM_CRC = 1u << 2,
} rawtiles_open_flags_t;

/* -------------------------------------------------------------------------
 * Handle
 *
 * The caller stack-allocates one rawtiles_t per open pack. Fields are
 * documented as internal; treat the struct as opaque except through the
 * accessor functions below.
 *
 * Approximate sizeof(rawtiles_t) on a 32-bit target: ~320 bytes
 *  (292 B header copy + I/O descriptor + flags + small scratch).
 * ----------------------------------------------------------------------- */
typedef struct rawtiles {
    /* I/O backing (copy of caller's descriptor). */
    rawtiles_io_t io;
    /* Open flags as supplied. */
    uint32_t flags;
    /* Verbatim 292-byte header for in-handle field access. */
    uint8_t header[292];
    /* Computed: byte offset where the tile blob begins (4-aligned). */
    uint32_t tile_blob_start;
    /* Convenience parsed fields hoisted from header[] for hot paths. */
    uint32_t tile_count;
    uint32_t extensions_offset;
    uint16_t tile_dim_px;
    uint8_t  pixel_format;
    uint8_t  compression_supported; /* bitset over rawtiles_compression_t */
    uint8_t  projection;
    uint8_t  addressing;
    uint8_t  axis;
    uint8_t  zoom_min;
    uint8_t  zoom_max;
    /* Last CRC verification outcome: 0 = pending/verified-ok, non-zero on mismatch.
       For lazy CRC modes the value may be deferred. */
    uint32_t crc_state;
} rawtiles_t;

/* -------------------------------------------------------------------------
 * Lifecycle
 * ----------------------------------------------------------------------- */

/* Validate the pack and prepare *rt for lookup. The exact subset of § 11 rules
 * checked depends on the open flags; see RAWTILES_OPEN_LAZY above. Returns
 * RAWTILES_OK on success or a rule-specific error code on rejection. */
rawtiles_result_t rawtiles_open(rawtiles_t *rt, rawtiles_io_t io,
                                uint32_t flags);

/* Trigger every deferred check (lazy subset of § 11.2). Equivalent to driving
 * the reader through every tile-index entry and every extension section, then
 * verifying AFFN if present. Returns RAWTILES_OK if every rule passed, or the
 * first rejection encountered. For readers opened with RAWTILES_OPEN_DEFAULT
 * this is a no-op that returns RAWTILES_OK. */
rawtiles_result_t rawtiles_validate_all(rawtiles_t *rt);

/* -------------------------------------------------------------------------
 * Tile access
 * ----------------------------------------------------------------------- */

/* Decoded tile size in bytes: tile_dim_px * tile_dim_px * bytes_per_pixel.
 * Constant per pack. The caller's getTile output buffer MUST be at least
 * this size. */
size_t rawtiles_decoded_tile_size(const rawtiles_t *rt);

/* Fetch the tile at (z, x, y). On RAWTILES_OK, exactly rawtiles_decoded_tile_size()
 * bytes are written to out_buf. On RAWTILES_ABSENT, no bytes are written.
 * Any other return code is a § 11 rejection encountered during lazy validation
 * of the underlying tile-index entry. */
rawtiles_result_t rawtiles_get_tile(rawtiles_t *rt, uint8_t z, uint32_t x,
                                    uint32_t y, uint8_t *out_buf,
                                    size_t out_buf_size);

/* -------------------------------------------------------------------------
 * Header field accessors
 * ----------------------------------------------------------------------- */

uint16_t rawtiles_tile_dim_px(const rawtiles_t *rt);
uint32_t rawtiles_tile_count(const rawtiles_t *rt);
uint8_t  rawtiles_zoom_min(const rawtiles_t *rt);
uint8_t  rawtiles_zoom_max(const rawtiles_t *rt);
rawtiles_pixel_format_t rawtiles_pixel_format(const rawtiles_t *rt);
rawtiles_compression_t  rawtiles_default_compression(const rawtiles_t *rt);
rawtiles_projection_t   rawtiles_projection(const rawtiles_t *rt);
rawtiles_addressing_t   rawtiles_addressing(const rawtiles_t *rt);
rawtiles_axis_t         rawtiles_axis(const rawtiles_t *rt);

/* Pack UUID as 16 raw bytes. */
void rawtiles_pack_uuid(const rawtiles_t *rt, uint8_t out_uuid[16]);

/* Bounding box in integer microdegrees (= decimal degrees * 1e6). */
void rawtiles_bbox(const rawtiles_t *rt, int32_t *min_lon, int32_t *min_lat,
                   int32_t *max_lon, int32_t *max_lat);

/* -------------------------------------------------------------------------
 * Extension access
 * ----------------------------------------------------------------------- */

/* AFFN coefficients for LocalLinear packs. Returns RAWTILES_OK and fills
 * out_coeffs with (a, b, c, d, e, f) per § 7.3. Returns
 * RAWTILES_ERR_RULE_22_LOCALLINEAR_NEEDS_AFFN if projection is LocalLinear
 * but no AFFN section exists; returns RAWTILES_ABSENT if projection is not
 * LocalLinear. */
rawtiles_result_t rawtiles_get_affn(rawtiles_t *rt, double out_coeffs[6]);

/* Extension iterator. The iterator is stack-allocated by the caller; treat
 * its contents as opaque. Iteration walks sections in pack-file order
 * (canonical per § 12.1 for writers that emit canonical packs). */
typedef struct rawtiles_ext_iter {
    rawtiles_t *rt;
    uint32_t cursor; /* byte offset of next section to read */
    uint32_t end;    /* file_size − 4 */
    uint32_t current_payload_offset;
    uint32_t current_payload_length;
    char     current_tag[4];
    bool     have_current;
} rawtiles_ext_iter_t;

/* Initialise iterator at the start of the extensions region. */
rawtiles_result_t rawtiles_ext_iter_init(rawtiles_t *rt,
                                         rawtiles_ext_iter_t *it);

/* Advance to the next extension section. On RAWTILES_OK, out_tag is filled
 * with the 4-byte tag (NOT null-terminated) and out_length with the payload
 * byte count. On RAWTILES_ABSENT, no more sections remain. Any other code
 * is a § 11 rejection of the section just read (or of a preceding section's
 * framing that the iterator only now detected). */
rawtiles_result_t rawtiles_ext_iter_next(rawtiles_ext_iter_t *it,
                                         char out_tag[4],
                                         uint32_t *out_length);

/* Read the payload of the most recently advanced-to section into out_buf.
 * The buffer must be at least *out_length bytes (from rawtiles_ext_iter_next).
 * Returns RAWTILES_ERR_BUFFER_TOO_SMALL if the caller's buffer is smaller. */
rawtiles_result_t rawtiles_ext_iter_read_payload(rawtiles_ext_iter_t *it,
                                                 uint8_t *out_buf,
                                                 size_t out_buf_size);

/* -------------------------------------------------------------------------
 * Misc.
 * ----------------------------------------------------------------------- */

/* Short human-readable string for a result code, for logging / debugging.
 * Pointer is to static storage; do not free. */
const char *rawtiles_strerror(rawtiles_result_t code);

#ifdef __cplusplus
} /* extern "C" */
#endif

#endif /* RAWTILES_H */
