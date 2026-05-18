/*
 * rawtiles reference reader — implementation
 *
 * SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026, Toby Murray
 */
#include "rawtiles/rawtiles.h"

#include <stddef.h>
#include <stdint.h>
#include <string.h>

/* =========================================================================
 * Header layout constants (§ 4)
 * ======================================================================= */
#define HDR_SIZE                292u
#define HDR_OFF_MAGIC             0
#define HDR_OFF_VERSION_MAJOR     4
#define HDR_OFF_VERSION_MINOR     5
#define HDR_OFF_RESERVED_V1_0     6
#define HDR_OFF_PACK_UUID         8
#define HDR_OFF_SUPERSEDES_UUID  24
#define HDR_OFF_PARENT_UUID      40
#define HDR_OFF_PIXEL_FORMAT     56
#define HDR_OFF_PROJECTION       57
#define HDR_OFF_ADDRESSING       58
#define HDR_OFF_AXIS             59
#define HDR_OFF_TILE_DIM_PX      60
#define HDR_OFF_ZOOM_MIN         62
#define HDR_OFF_ZOOM_MAX         63
#define HDR_OFF_BBOX_MIN_LON     64
#define HDR_OFF_BBOX_MIN_LAT     68
#define HDR_OFF_BBOX_MAX_LON     72
#define HDR_OFF_BBOX_MAX_LAT     76
#define HDR_OFF_BUILD_TS         80
#define HDR_OFF_TILE_COUNT       88
#define HDR_OFF_INDEX_OFFSET     92
#define HDR_OFF_ZOOM_OFFSETS     96  /* 24 entries × 8 bytes = 192 bytes */
#define HDR_OFF_EXTENSIONS_OFF  288

#define INDEX_ENTRY_SIZE         20u
#define MAX_ZOOM                 24u

/* =========================================================================
 * Little-endian byte readers (no alignment assumptions)
 * ======================================================================= */
static inline uint16_t rd_u16le(const uint8_t *p)
{
    return (uint16_t)p[0] | ((uint16_t)p[1] << 8);
}

static inline uint32_t rd_u32le(const uint8_t *p)
{
    return (uint32_t)p[0] | ((uint32_t)p[1] << 8) | ((uint32_t)p[2] << 16) |
           ((uint32_t)p[3] << 24);
}

static inline int32_t rd_i32le(const uint8_t *p)
{
    return (int32_t)rd_u32le(p);
}

/* =========================================================================
 * I/O dispatch
 * ======================================================================= */
static rawtiles_result_t io_read(const rawtiles_io_t *io, uint8_t *dest,
                                 uint32_t offset, uint32_t len)
{
    if (len == 0) return RAWTILES_OK;
    /* u64 arithmetic to avoid u32 overflow on offset + len */
    if ((uint64_t)offset + (uint64_t)len > (uint64_t)io->size)
        return RAWTILES_ERR_IO;
    if (io->mode == RAWTILES_IO_MEMORY) {
        memcpy(dest, io->u.base + offset, len);
        return RAWTILES_OK;
    }
    /* RAWTILES_IO_PREAD */
    if (io->u.pread.pread(io->u.pread.ctx, dest, offset, len) != 0)
        return RAWTILES_ERR_IO;
    return RAWTILES_OK;
}

/* =========================================================================
 * CRC-32 / ISO-HDLC (PNG / zlib variant)
 *
 * Polynomial 0xEDB88320 (reflected), initial 0xFFFFFFFF, final XOR
 * 0xFFFFFFFF. Check value for "123456789" is 0xCBF43926 (§ 10).
 * ======================================================================= */
static uint32_t crc32_table[256];
static bool crc32_table_ready = false;

static void crc32_table_init(void)
{
    for (uint32_t i = 0; i < 256; ++i) {
        uint32_t c = i;
        for (int k = 0; k < 8; ++k)
            c = (c >> 1) ^ (0xEDB88320u & (uint32_t)-(int32_t)(c & 1));
        crc32_table[i] = c;
    }
    crc32_table_ready = true;
}

static uint32_t crc32_update(uint32_t crc, const uint8_t *buf, size_t len)
{
    if (!crc32_table_ready) crc32_table_init();
    crc ^= 0xFFFFFFFFu;
    for (size_t i = 0; i < len; ++i)
        crc = crc32_table[(crc ^ buf[i]) & 0xFFu] ^ (crc >> 8);
    return crc ^ 0xFFFFFFFFu;
}

/* Computes CRC-32 over bytes [0, size-4) of the pack, comparing against the
 * trailing 4-byte footer. Reads through io_read in chunks. */
static rawtiles_result_t verify_crc(const rawtiles_io_t *io)
{
    uint8_t buf[1024];
    uint32_t crc = 0;
    uint32_t scope = io->size - 4; /* footer excluded */
    uint32_t off = 0;
    while (off < scope) {
        uint32_t want = (scope - off) > sizeof(buf) ? (uint32_t)sizeof(buf)
                                                    : (scope - off);
        rawtiles_result_t r = io_read(io, buf, off, want);
        if (r != RAWTILES_OK) return r;
        crc = crc32_update(crc, buf, want);
        off += want;
    }
    uint8_t footer[4];
    rawtiles_result_t r = io_read(io, footer, scope, 4);
    if (r != RAWTILES_OK) return r;
    uint32_t expected = rd_u32le(footer);
    if (crc != expected) return RAWTILES_ERR_RULE_24_BAD_CRC;
    return RAWTILES_OK;
}

/* =========================================================================
 * Helpers
 * ======================================================================= */
static inline uint32_t align4(uint32_t n) { return (n + 3u) & ~3u; }

static size_t bytes_per_pixel(uint8_t pixel_format)
{
    switch (pixel_format) {
    case RAWTILES_PIXEL_ABGR2222: return 1;
    case RAWTILES_PIXEL_RGB565:   return 2;
    default:                       return 0;
    }
}

static bool is_valid_pixel_format(uint8_t v)
{
    return v == RAWTILES_PIXEL_ABGR2222 || v == RAWTILES_PIXEL_RGB565;
}

static bool is_valid_compression(uint8_t v)
{
    return v == RAWTILES_COMPRESSION_NONE || v == RAWTILES_COMPRESSION_RLE8;
}

static bool is_valid_projection(uint8_t v)
{
    return v == RAWTILES_PROJ_WEBMERCATOR || v == RAWTILES_PROJ_LOCALLINEAR;
}

static bool is_valid_addressing(uint8_t v)
{
    return v == RAWTILES_ADDR_QUADTREE || v == RAWTILES_ADDR_SINGLEIMAGE;
}

static bool is_valid_axis(uint8_t v)
{
    return v == RAWTILES_AXIS_XYZ || v == RAWTILES_AXIS_TMS;
}

static bool is_legal_proj_addr_pair(uint8_t proj, uint8_t addr)
{
    /* § 8.6 legal pairs only. */
    if (proj == RAWTILES_PROJ_WEBMERCATOR && addr == RAWTILES_ADDR_QUADTREE)
        return true;
    if (proj == RAWTILES_PROJ_LOCALLINEAR && addr == RAWTILES_ADDR_SINGLEIMAGE)
        return true;
    return false;
}

static bool uuid_is_zero(const uint8_t u[16])
{
    for (int i = 0; i < 16; ++i)
        if (u[i] != 0) return false;
    return true;
}

/* =========================================================================
 * Header validation (eager subset of § 11)
 * ======================================================================= */
static rawtiles_result_t validate_header(const uint8_t *h)
{
    /* #2 magic */
    if (h[HDR_OFF_MAGIC + 0] != 'R' || h[HDR_OFF_MAGIC + 1] != 'A' ||
        h[HDR_OFF_MAGIC + 2] != 'W' || h[HDR_OFF_MAGIC + 3] != 'T')
        return RAWTILES_ERR_RULE_2_BAD_MAGIC;

    /* #3 format_version_major == 1 (minor may be > 0, accepted per #4) */
    if (h[HDR_OFF_VERSION_MAJOR] != 1)
        return RAWTILES_ERR_RULE_3_BAD_VERSION;

    /* #5 pack_uuid != all-zero */
    if (uuid_is_zero(h + HDR_OFF_PACK_UUID))
        return RAWTILES_ERR_RULE_5_UUID_ZERO;

    /* #6 parent_uuid == all-zero */
    if (!uuid_is_zero(h + HDR_OFF_PARENT_UUID))
        return RAWTILES_ERR_RULE_6_PARENT_NONZERO;

    /* #7 enum bytes */
    uint8_t pf   = h[HDR_OFF_PIXEL_FORMAT];
    uint8_t proj = h[HDR_OFF_PROJECTION];
    uint8_t addr = h[HDR_OFF_ADDRESSING];
    uint8_t axis = h[HDR_OFF_AXIS];
    if (!is_valid_pixel_format(pf) || !is_valid_projection(proj) ||
        !is_valid_addressing(addr) || !is_valid_axis(axis))
        return RAWTILES_ERR_RULE_7_BAD_ENUM;

    /* #8 projection × addressing legality */
    if (!is_legal_proj_addr_pair(proj, addr))
        return RAWTILES_ERR_RULE_8_BAD_PROJ_ADDR_PAIR;

    /* #9 tile_dim_px non-zero */
    uint16_t tile_dim = rd_u16le(h + HDR_OFF_TILE_DIM_PX);
    if (tile_dim == 0) return RAWTILES_ERR_RULE_9_TILEDIM_ZERO;

    /* #10 zoom range */
    uint8_t zmin = h[HDR_OFF_ZOOM_MIN];
    uint8_t zmax = h[HDR_OFF_ZOOM_MAX];
    if (zmax >= MAX_ZOOM || zmin > zmax)
        return RAWTILES_ERR_RULE_10_BAD_ZOOM_RANGE;

    /* #11 bbox ranges and orderings */
    int32_t min_lon = rd_i32le(h + HDR_OFF_BBOX_MIN_LON);
    int32_t min_lat = rd_i32le(h + HDR_OFF_BBOX_MIN_LAT);
    int32_t max_lon = rd_i32le(h + HDR_OFF_BBOX_MAX_LON);
    int32_t max_lat = rd_i32le(h + HDR_OFF_BBOX_MAX_LAT);
    if (min_lon < -180000000 || min_lon > 180000000 ||
        max_lon < -180000000 || max_lon > 180000000 ||
        min_lat < -90000000  || min_lat > 90000000  ||
        max_lat < -90000000  || max_lat > 90000000  ||
        min_lon > max_lon || min_lat > max_lat)
        return RAWTILES_ERR_RULE_11_BAD_BBOX;

    /* #25 index_offset must equal 292 in v1 */
    uint32_t idx_off = rd_u32le(h + HDR_OFF_INDEX_OFFSET);
    if (idx_off != HDR_SIZE)
        return RAWTILES_ERR_RULE_25_BAD_INDEX_OFFSET;

    return RAWTILES_OK;
}

/* Validates the header-resident sub-clauses of #18 (§ 11.2 rule-specific note)
 * plus the header-resident sub-clauses of #23 for SingleImage packs. */
static rawtiles_result_t validate_header_layout(const uint8_t *h,
                                                uint32_t file_size,
                                                uint32_t tile_blob_start)
{
    uint32_t tile_count = rd_u32le(h + HDR_OFF_TILE_COUNT);
    uint32_t ext_off    = rd_u32le(h + HDR_OFF_EXTENSIONS_OFF);
    uint8_t  addr       = h[HDR_OFF_ADDRESSING];
    uint8_t  zmin       = h[HDR_OFF_ZOOM_MIN];
    uint8_t  zmax       = h[HDR_OFF_ZOOM_MAX];
    uint8_t  axis       = h[HDR_OFF_AXIS];

    /* #18 header-resident sub-clauses */
    if ((ext_off & 3u) != 0) return RAWTILES_ERR_RULE_18_BAD_EXT_OFFSET;
    if (ext_off > file_size - 4) return RAWTILES_ERR_RULE_18_BAD_EXT_OFFSET;
    if (ext_off < tile_blob_start)
        return RAWTILES_ERR_RULE_18_BAD_EXT_OFFSET;
    /* For tile_count == 0 Quadtree packs, ext_off must equal 292. */
    if (addr == RAWTILES_ADDR_QUADTREE && tile_count == 0 &&
        ext_off != HDR_SIZE)
        return RAWTILES_ERR_RULE_18_BAD_EXT_OFFSET;

    /* #23 header-resident sub-clauses for SingleImage */
    if (addr == RAWTILES_ADDR_SINGLEIMAGE) {
        if (tile_count != 1)
            return RAWTILES_ERR_RULE_23_BAD_SINGLEIMAGE;
        if (zmin != 0 || zmax != 0)
            return RAWTILES_ERR_RULE_23_BAD_SINGLEIMAGE;
        if (axis != RAWTILES_AXIS_XYZ)
            return RAWTILES_ERR_RULE_23_BAD_SINGLEIMAGE;
        /* zoom_offsets[0] = (HDR_SIZE, 1); zoom_offsets[1..23] = (0, 0). */
        const uint8_t *zo = h + HDR_OFF_ZOOM_OFFSETS;
        if (rd_u32le(zo + 0) != HDR_SIZE || rd_u32le(zo + 4) != 1)
            return RAWTILES_ERR_RULE_23_BAD_SINGLEIMAGE;
        for (uint32_t z = 1; z < MAX_ZOOM; ++z) {
            const uint8_t *e = zo + z * 8;
            if (rd_u32le(e + 0) != 0 || rd_u32le(e + 4) != 0)
                return RAWTILES_ERR_RULE_23_BAD_SINGLEIMAGE;
        }
    }

    return RAWTILES_OK;
}

/* =========================================================================
 * Tile-index walk (§ 11.2: enforces #12, #13, #14, #15, #16, #17, #18 full,
 * #31, #32, and the per-entry sub-clause of #23 — all in one O(tile_count) pass)
 * ======================================================================= */
static rawtiles_result_t walk_tile_index(rawtiles_t *rt)
{
    if (rt->tile_count == 0) {
        /* No entries to walk. #18 padded-sum already validated (== HDR_SIZE)
         * by validate_header_layout for tile_count == 0 packs. */
        /* But all zoom_offsets entries must be (0, 0) per § 4.12. */
        for (uint32_t z = 0; z < MAX_ZOOM; ++z) {
            const uint8_t *e = rt->header + HDR_OFF_ZOOM_OFFSETS + z * 8;
            if (rd_u32le(e + 0) != 0 || rd_u32le(e + 4) != 0)
                return RAWTILES_ERR_RULE_17_BAD_ZOOM_OFFSETS;
        }
        return RAWTILES_OK;
    }

    uint8_t  prev_z = 0;
    uint32_t prev_x = 0, prev_y = 0;
    bool     have_prev = false;
    uint8_t  prev_zone_z = 255; /* sentinel: no zone yet */
    uint32_t zone_count[MAX_ZOOM];
    uint32_t zone_first_off[MAX_ZOOM];
    for (uint32_t z = 0; z < MAX_ZOOM; ++z) {
        zone_count[z] = 0;
        zone_first_off[z] = 0;
    }

    uint32_t running_padded = 0;
    uint32_t entry_off = HDR_OFF_ZOOM_OFFSETS; /* unused, just to silence */
    (void)entry_off;

    uint8_t pf      = rt->pixel_format;
    uint8_t zmin    = rt->zoom_min;
    uint8_t zmax    = rt->zoom_max;
    uint8_t addr    = rt->addressing;
    uint32_t blob   = rt->tile_blob_start;
    uint32_t ext_off = rt->extensions_offset;

    size_t bpp = bytes_per_pixel(pf);

    uint8_t entry[INDEX_ENTRY_SIZE];
    for (uint32_t i = 0; i < rt->tile_count; ++i) {
        uint32_t off = HDR_SIZE + i * INDEX_ENTRY_SIZE;
        rawtiles_result_t r = io_read(&rt->io, entry, off, INDEX_ENTRY_SIZE);
        if (r != RAWTILES_OK) return r;

        uint8_t  z          = entry[0];
        uint8_t  compression= entry[1];
        uint8_t  flags      = entry[2];
        uint8_t  reserved   = entry[3];
        uint32_t x          = rd_u32le(entry + 4);
        uint32_t y          = rd_u32le(entry + 8);
        uint32_t e_offset   = rd_u32le(entry + 12);
        uint32_t e_length   = rd_u32le(entry + 16);

        /* #12 flags/reserved must be zero */
        if (flags != 0 || reserved != 0)
            return RAWTILES_ERR_RULE_12_BAD_ENTRY_FLAGS;

        /* #7 (compression byte) — eager-validate it here, even though § 11.2
         * classifies it as lazy. We do the check at open because we already
         * read the byte; deferring would mean re-reading.
         * If a future lazy-mode reader wants to defer, branch here. */
        if (!is_valid_compression(compression))
            return RAWTILES_ERR_RULE_7_BAD_ENUM;

        /* #15 z within [zoom_min, zoom_max] */
        if (z < zmin || z > zmax)
            return RAWTILES_ERR_RULE_15_ENTRY_ZOOM_OUT_OF_RANGE;
        if (z >= MAX_ZOOM)
            return RAWTILES_ERR_RULE_15_ENTRY_ZOOM_OUT_OF_RANGE;

        /* #13 sorted ascending by (z, x, y) */
        if (have_prev) {
            if (z < prev_z) return RAWTILES_ERR_RULE_13_BAD_ENTRY_ORDER;
            if (z == prev_z) {
                /* strict ascending within zoom */
                if (x < prev_x ||
                    (x == prev_x && y <= prev_y))
                    return RAWTILES_ERR_RULE_13_BAD_ENTRY_ORDER;
            }
        }

        /* #31 Quadtree x, y < 2^z (skip for SingleImage which is checked elsewhere) */
        if (addr == RAWTILES_ADDR_QUADTREE) {
            /* z < 24 here, so 2^z fits in u32 for z <= 31; safe. */
            uint64_t bound = (uint64_t)1 << z;
            if ((uint64_t)x >= bound || (uint64_t)y >= bound)
                return RAWTILES_ERR_RULE_31_QUADTREE_XY_OVERFLOW;
        }

        /* SingleImage per-entry sub-clause of #23: z=x=y=0 */
        if (addr == RAWTILES_ADDR_SINGLEIMAGE) {
            if (z != 0 || x != 0 || y != 0)
                return RAWTILES_ERR_RULE_23_BAD_SINGLEIMAGE;
        }

        /* #14 entry offset/length bounds */
        if ((e_offset & 3u) != 0)
            return RAWTILES_ERR_RULE_14_BAD_ENTRY_BOUNDS;
        if (e_offset < blob)
            return RAWTILES_ERR_RULE_14_BAD_ENTRY_BOUNDS;
        if (e_offset >= ext_off)
            return RAWTILES_ERR_RULE_14_BAD_ENTRY_BOUNDS;
        if (e_length > ext_off - e_offset)
            return RAWTILES_ERR_RULE_14_BAD_ENTRY_BOUNDS;

        /* #16 length matches format-implied size (for compression = None only) */
        if (compression == RAWTILES_COMPRESSION_NONE) {
            uint64_t expected = (uint64_t)rt->tile_dim_px *
                                (uint64_t)rt->tile_dim_px * (uint64_t)bpp;
            if ((uint64_t)e_length != expected)
                return RAWTILES_ERR_RULE_16_BAD_ENTRY_LENGTH;
        }

        /* #32 tight tile-blob layout */
        if (e_offset != blob + running_padded)
            return RAWTILES_ERR_RULE_32_TILE_LAYOUT_NOT_TIGHT;
        running_padded += align4(e_length);

        /* zone tracking for #17 (zoom_offsets consistency) */
        if (z != prev_zone_z) {
            /* first entry at this zoom */
            zone_count[z] = 1;
            zone_first_off[z] = off; /* file offset of this entry */
            prev_zone_z = z;
        } else {
            zone_count[z]++;
        }

        prev_z = z;
        prev_x = x;
        prev_y = y;
        have_prev = true;
    }

    /* #18 padded-sum equality: tile_blob_start + running_padded == ext_off */
    if (blob + running_padded != ext_off)
        return RAWTILES_ERR_RULE_18_BAD_EXT_OFFSET;

    /* #17 zoom_offsets[z] = (first_entry_byte_offset, count) when count > 0,
     *                    = (0, 0) when count == 0. */
    for (uint32_t z = 0; z < MAX_ZOOM; ++z) {
        const uint8_t *e = rt->header + HDR_OFF_ZOOM_OFFSETS + z * 8;
        uint32_t hdr_off  = rd_u32le(e + 0);
        uint32_t hdr_cnt  = rd_u32le(e + 4);
        if (zone_count[z] == 0) {
            if (hdr_off != 0 || hdr_cnt != 0)
                return RAWTILES_ERR_RULE_17_BAD_ZOOM_OFFSETS;
        } else {
            if (hdr_off != zone_first_off[z] || hdr_cnt != zone_count[z])
                return RAWTILES_ERR_RULE_17_BAD_ZOOM_OFFSETS;
        }
    }

    return RAWTILES_OK;
}

/* =========================================================================
 * Extension walk for eager mode (§ 11.6 rules #19, #20, #27, #28, #29, #22,
 * #34, #35, #36, #26, #37, #38 are addressed here at varying depth)
 *
 * v0.1 implements: #19 framing, #20 unknown uppercase tag, #27/#28 tag bytes,
 * #29 duplicate uppercase tags, #22 LocalLinear→AFFN required, #34/#35/#36
 * AFFN basics, #33 per-tile padding non-zero (walks padding bytes in eager
 * mode).
 *
 * Deferred to a follow-up pass: #26 NAME tag_length validity, #37 NAME UTF-8
 * + BCP-47, #38 SRCD/ATTR text rules.
 * ======================================================================= */
static const char KNOWN_UPPERCASE_TAGS[][4] = {
    { 'A', 'F', 'F', 'N' },
    { 'A', 'T', 'T', 'R' },
    { 'N', 'A', 'M', 'E' },
    { 'S', 'R', 'C', 'D' },
};
#define KNOWN_UPPERCASE_TAG_COUNT \
    (sizeof(KNOWN_UPPERCASE_TAGS) / sizeof(KNOWN_UPPERCASE_TAGS[0]))

static bool tag_is_known_uppercase(const char tag[4])
{
    for (size_t i = 0; i < KNOWN_UPPERCASE_TAG_COUNT; ++i)
        if (memcmp(KNOWN_UPPERCASE_TAGS[i], tag, 4) == 0) return true;
    return false;
}

static bool tag_first_byte_is_uppercase(uint8_t b)
{
    return b >= 'A' && b <= 'Z';
}

static bool tag_first_byte_is_lowercase(uint8_t b)
{
    return b >= 'a' && b <= 'z';
}

static rawtiles_result_t walk_extensions_eager(rawtiles_t *rt, bool *out_has_affn,
                                               uint32_t *out_affn_payload_off,
                                               uint32_t *out_affn_payload_len)
{
    *out_has_affn = false;
    *out_affn_payload_off = 0;
    *out_affn_payload_len = 0;

    uint32_t cursor = rt->extensions_offset;
    uint32_t end    = rt->io.size - 4; /* before CRC footer */

    /* Track seen uppercase tags for #29 duplicate detection. */
    char seen_tags[KNOWN_UPPERCASE_TAG_COUNT][4];
    bool seen[KNOWN_UPPERCASE_TAG_COUNT];
    size_t seen_count = 0;
    for (size_t i = 0; i < KNOWN_UPPERCASE_TAG_COUNT; ++i) seen[i] = false;
    (void)seen_tags;

    while (cursor < end) {
        if (end - cursor < 8) /* tag(4) + length(4) */
            return RAWTILES_ERR_RULE_19_BAD_SECTION_FRAMING;

        uint8_t hdr[8];
        rawtiles_result_t r = io_read(&rt->io, hdr, cursor, 8);
        if (r != RAWTILES_OK) return r;
        char tag[4] = { (char)hdr[0], (char)hdr[1], (char)hdr[2], (char)hdr[3] };
        uint32_t length = rd_u32le(hdr + 4);

        /* #27 tag first byte must be A-Z or a-z */
        uint8_t fb = (uint8_t)tag[0];
        if (!tag_first_byte_is_uppercase(fb) &&
            !tag_first_byte_is_lowercase(fb))
            return RAWTILES_ERR_RULE_27_BAD_TAG_FIRST_BYTE;

        /* #28 tag bytes 2-4 must be printable ASCII (0x20–0x7E) */
        for (int i = 1; i < 4; ++i) {
            uint8_t b = (uint8_t)tag[i];
            if (b < 0x20 || b > 0x7E)
                return RAWTILES_ERR_RULE_28_BAD_TAG_PRINTABLE;
        }

        /* #19 section bounds: length must fit before end */
        if (length > (end - cursor - 8))
            return RAWTILES_ERR_RULE_19_BAD_SECTION_FRAMING;

        uint32_t payload_off = cursor + 8;
        uint32_t padded = align4(length);

        /* #19 padding bytes between payload and next 4-aligned offset must be 0x00 */
        if (padded > length) {
            uint8_t pad[3];
            r = io_read(&rt->io, pad, payload_off + length, padded - length);
            if (r != RAWTILES_OK) return r;
            for (uint32_t i = 0; i < padded - length; ++i)
                if (pad[i] != 0x00)
                    return RAWTILES_ERR_RULE_19_BAD_SECTION_FRAMING;
        }

        /* #20 uppercase-tag unknown is fatal */
        if (tag_first_byte_is_uppercase(fb)) {
            if (!tag_is_known_uppercase(tag))
                return RAWTILES_ERR_RULE_20_UNKNOWN_UPPERCASE_TAG;
            /* #29 duplicate uppercase tag check (NAME exempt — separate rule
             * for duplicate locale; deferred to follow-up since it needs the
             * tag_length parse). */
            if (memcmp(tag, "NAME", 4) != 0) {
                for (size_t i = 0; i < KNOWN_UPPERCASE_TAG_COUNT; ++i) {
                    if (memcmp(KNOWN_UPPERCASE_TAGS[i], tag, 4) == 0) {
                        if (seen[i])
                            return RAWTILES_ERR_RULE_29_DUPLICATE_TAG;
                        seen[i] = true;
                        if (memcmp(tag, "AFFN", 4) == 0) {
                            *out_has_affn = true;
                            *out_affn_payload_off = payload_off;
                            *out_affn_payload_len = length;
                        }
                        break;
                    }
                }
            }
            /* #26 NAME basic length check */
            if (memcmp(tag, "NAME", 4) == 0) {
                if (length < 1) return RAWTILES_ERR_RULE_26_BAD_NAME_LENGTH;
                uint8_t tag_length;
                r = io_read(&rt->io, &tag_length, payload_off, 1);
                if (r != RAWTILES_OK) return r;
                if ((uint32_t)1 + (uint32_t)tag_length > length)
                    return RAWTILES_ERR_RULE_26_BAD_NAME_LENGTH;
            }
        }
        /* Lowercase tags accepted unconditionally (#21). */
        (void)seen_count;

        cursor = payload_off + padded;
    }

    /* #19 (b): final cursor must land exactly at end (no stranded bytes) */
    if (cursor != end)
        return RAWTILES_ERR_RULE_19_BAD_SECTION_FRAMING;

    return RAWTILES_OK;
}

/* Verify #22, #34, #35, #36 against the discovered AFFN. */
static rawtiles_result_t verify_affn(rawtiles_t *rt, bool has_affn,
                                     uint32_t affn_off, uint32_t affn_len)
{
    bool is_locallinear = (rt->projection == RAWTILES_PROJ_LOCALLINEAR);
    if (is_locallinear && !has_affn)
        return RAWTILES_ERR_RULE_22_LOCALLINEAR_NEEDS_AFFN;
    if (!is_locallinear && has_affn)
        return RAWTILES_ERR_RULE_36_AFFN_ON_NON_LOCALLINEAR;
    if (!has_affn) return RAWTILES_OK;

    /* #34 length == 48 */
    if (affn_len != 48) return RAWTILES_ERR_RULE_34_BAD_AFFN_LENGTH;

    /* #35 every f64 finite */
    uint8_t buf[48];
    rawtiles_result_t r = io_read(&rt->io, buf, affn_off, 48);
    if (r != RAWTILES_OK) return r;
    for (int i = 0; i < 6; ++i) {
        /* IEEE 754 binary64: bits 62..52 are the exponent. NaN/Inf both have
         * all-ones exponent. We test that by reading the high u32 and checking
         * the exponent field. */
        uint32_t hi = rd_u32le(buf + i * 8 + 4);
        if ((hi & 0x7FF00000u) == 0x7FF00000u)
            return RAWTILES_ERR_RULE_35_AFFN_NOT_FINITE;
    }
    return RAWTILES_OK;
}

/* Verify #33 (per-tile padding non-zero) in eager mode by walking padding
 * bytes between tiles. */
static rawtiles_result_t verify_tile_padding(rawtiles_t *rt)
{
    if (rt->tile_count == 0) return RAWTILES_OK;

    uint8_t entry[INDEX_ENTRY_SIZE];
    for (uint32_t i = 0; i < rt->tile_count; ++i) {
        rawtiles_result_t r =
            io_read(&rt->io, entry, HDR_SIZE + i * INDEX_ENTRY_SIZE,
                    INDEX_ENTRY_SIZE);
        if (r != RAWTILES_OK) return r;
        uint32_t e_offset = rd_u32le(entry + 12);
        uint32_t e_length = rd_u32le(entry + 16);
        uint32_t padded = align4(e_length);
        if (padded > e_length) {
            uint8_t pad[3];
            r = io_read(&rt->io, pad, e_offset + e_length, padded - e_length);
            if (r != RAWTILES_OK) return r;
            for (uint32_t k = 0; k < padded - e_length; ++k)
                if (pad[k] != 0x00)
                    return RAWTILES_ERR_RULE_33_NONZERO_PADDING;
        }
    }
    return RAWTILES_OK;
}

/* =========================================================================
 * Public API: open
 * ======================================================================= */
rawtiles_result_t rawtiles_open(rawtiles_t *rt, rawtiles_io_t io,
                                uint32_t flags)
{
    if (!rt) return RAWTILES_ERR_INVALID_ARG;
    memset(rt, 0, sizeof(*rt));

    /* #30 / #1 — file size sanity */
    if (io.size < 296) return RAWTILES_ERR_RULE_1_SHORT_FILE;
    /* #30: io.size is uint32_t, so it cannot exceed 2^32 - 1 already. The
     * spec is enforced by the type system on platforms where size_t > u32 the
     * caller would have to pass io.size as uint32_t anyway. */

    rt->io = io;
    rt->flags = flags;

    /* Read the 292-byte header. */
    rawtiles_result_t r = io_read(&rt->io, rt->header, 0, HDR_SIZE);
    if (r != RAWTILES_OK) return r;

    /* Eager header rules. */
    r = validate_header(rt->header);
    if (r != RAWTILES_OK) return r;

    /* Hoist convenience fields. */
    rt->pixel_format    = rt->header[HDR_OFF_PIXEL_FORMAT];
    rt->projection      = rt->header[HDR_OFF_PROJECTION];
    rt->addressing      = rt->header[HDR_OFF_ADDRESSING];
    rt->axis            = rt->header[HDR_OFF_AXIS];
    rt->tile_dim_px     = rd_u16le(rt->header + HDR_OFF_TILE_DIM_PX);
    rt->zoom_min        = rt->header[HDR_OFF_ZOOM_MIN];
    rt->zoom_max        = rt->header[HDR_OFF_ZOOM_MAX];
    rt->tile_count      = rd_u32le(rt->header + HDR_OFF_TILE_COUNT);
    rt->extensions_offset = rd_u32le(rt->header + HDR_OFF_EXTENSIONS_OFF);

    /* § 11.5 — overflow-safe tile-index fit check.
     * Required even for lazy readers (bounds-check binary search vs file tail). */
    if (io.size < 296)
        return RAWTILES_ERR_RULE_1_SHORT_FILE;
    if (rt->tile_count > (io.size - 296) / 20)
        return RAWTILES_ERR_RULE_14_BAD_ENTRY_BOUNDS;

    /* tile_blob_start (§ 3) — v1 always equals 292 + 20 * tile_count, which is
     * 4-aligned because both 292 and 20 are multiples of 4. */
    rt->tile_blob_start = HDR_SIZE + INDEX_ENTRY_SIZE * rt->tile_count;

    /* Eager header-layout rules: header-resident sub-clauses of #18 and #23. */
    r = validate_header_layout(rt->header, io.size, rt->tile_blob_start);
    if (r != RAWTILES_OK) return r;

    /* CRC verification (§ 10). v0.1: eager-only unless RAWTILES_OPEN_TRUST_CRC.
     * STREAM_CRC is accepted but treated as eager (documented). */
    if ((flags & RAWTILES_OPEN_TRUST_CRC) == 0) {
        r = verify_crc(&rt->io);
        if (r != RAWTILES_OK) return r;
    }

    /* Open-time tile-index walk: #12, #13, #14, #15, #16, #17, #18 padded-sum,
     * #31, #32, #23 per-entry. Eager for every reader per § 11.2. */
    r = walk_tile_index(rt);
    if (r != RAWTILES_OK) return r;

    /* Extension walk: #19, #20, #27, #28, #29, locates AFFN. */
    bool has_affn = false;
    uint32_t affn_off = 0, affn_len = 0;
    r = walk_extensions_eager(rt, &has_affn, &affn_off, &affn_len);
    if (r != RAWTILES_OK) return r;

    /* AFFN rules #22, #34, #35, #36. */
    r = verify_affn(rt, has_affn, affn_off, affn_len);
    if (r != RAWTILES_OK) return r;

    /* #33 padding bytes — only the eager profile checks this; lazy readers
     * are not required to read padding (§ 11.2 rule note). v0.1 is eager-only,
     * so we always check. */
    if ((flags & RAWTILES_OPEN_LAZY) == 0) {
        r = verify_tile_padding(rt);
        if (r != RAWTILES_OK) return r;
    }

    return RAWTILES_OK;
}

/* =========================================================================
 * Public API: getTile, accessors, misc
 * ======================================================================= */

rawtiles_result_t rawtiles_validate_all(rawtiles_t *rt)
{
    (void)rt;
    /* v0.1: open is eager so this is a no-op. When LAZY is implemented,
     * this drives every lazy check. */
    return RAWTILES_OK;
}

size_t rawtiles_decoded_tile_size(const rawtiles_t *rt)
{
    return (size_t)rt->tile_dim_px * (size_t)rt->tile_dim_px *
           bytes_per_pixel(rt->pixel_format);
}

/* Binary search the tile-index for an entry matching (z, x, y) within the
 * zone for zoom z. Returns RAWTILES_OK with entry filled, or RAWTILES_ABSENT. */
static rawtiles_result_t find_entry(rawtiles_t *rt, uint8_t z, uint32_t x,
                                    uint32_t y, uint8_t out_entry[INDEX_ENTRY_SIZE])
{
    /* § 5.3 step 1: z >= 24 → absent */
    if (z >= MAX_ZOOM) return RAWTILES_ABSENT;

    /* zoom_offsets[z] */
    const uint8_t *zoe = rt->header + HDR_OFF_ZOOM_OFFSETS + z * 8;
    uint32_t zone_off   = rd_u32le(zoe + 0);
    uint32_t zone_count = rd_u32le(zoe + 4);
    if (zone_count == 0) return RAWTILES_ABSENT;

    /* Binary search [zone_off, zone_off + 20*zone_count). Key is (x, y). */
    uint32_t lo = 0, hi = zone_count;
    while (lo < hi) {
        uint32_t mid = lo + (hi - lo) / 2;
        rawtiles_result_t r = io_read(&rt->io, out_entry,
                                       zone_off + mid * INDEX_ENTRY_SIZE,
                                       INDEX_ENTRY_SIZE);
        if (r != RAWTILES_OK) return r;
        uint32_t mx = rd_u32le(out_entry + 4);
        uint32_t my = rd_u32le(out_entry + 8);
        if (mx < x || (mx == x && my < y)) lo = mid + 1;
        else if (mx > x || (mx == x && my > y)) hi = mid;
        else return RAWTILES_OK;
    }
    return RAWTILES_ABSENT;
}

rawtiles_result_t rawtiles_get_tile(rawtiles_t *rt, uint8_t z, uint32_t x,
                                    uint32_t y, uint8_t *out_buf,
                                    size_t out_buf_size)
{
    if (!rt || !out_buf) return RAWTILES_ERR_INVALID_ARG;

    /* SingleImage packs accept only (0,0,0). */
    if (rt->addressing == RAWTILES_ADDR_SINGLEIMAGE) {
        if (z != 0 || x != 0 || y != 0) return RAWTILES_ABSENT;
    }

    uint8_t entry[INDEX_ENTRY_SIZE];
    rawtiles_result_t r = find_entry(rt, z, x, y, entry);
    if (r != RAWTILES_OK) return r;

    uint8_t  compression = entry[1];
    uint32_t e_offset    = rd_u32le(entry + 12);
    uint32_t e_length    = rd_u32le(entry + 16);

    size_t decoded_size = rawtiles_decoded_tile_size(rt);
    if (out_buf_size < decoded_size) return RAWTILES_ERR_BUFFER_TOO_SMALL;

    if (compression == RAWTILES_COMPRESSION_NONE) {
        if ((size_t)e_length != decoded_size)
            return RAWTILES_ERR_RULE_16_BAD_ENTRY_LENGTH;
        return io_read(&rt->io, out_buf, e_offset, e_length);
    }

    if (compression == RAWTILES_COMPRESSION_RLE8) {
        /* RLE8 decoder. § 9.11.
         * Reads encoded bytes from [e_offset, e_offset + e_length) and emits
         * exactly decoded_size bytes to out_buf. Errors on under/overflow. */
        size_t produced = 0;
        uint32_t in_cursor = e_offset;
        uint32_t in_end    = e_offset + e_length;
        while (produced < decoded_size) {
            if (in_cursor >= in_end)
                return RAWTILES_ERR_RULE_16_BAD_ENTRY_LENGTH;
            uint8_t h;
            r = io_read(&rt->io, &h, in_cursor++, 1);
            if (r != RAWTILES_OK) return r;
            if ((h & 0x80u) == 0) {
                /* literal run of (h+1) bytes */
                uint32_t n = (uint32_t)h + 1u;
                if (in_cursor + n > in_end)
                    return RAWTILES_ERR_RULE_16_BAD_ENTRY_LENGTH;
                if (produced + n > decoded_size)
                    return RAWTILES_ERR_RULE_16_BAD_ENTRY_LENGTH;
                r = io_read(&rt->io, out_buf + produced, in_cursor, n);
                if (r != RAWTILES_OK) return r;
                in_cursor += n;
                produced += n;
            } else {
                /* repeat run: payload 1 byte, written (h&0x7F)+1 times */
                if (in_cursor >= in_end)
                    return RAWTILES_ERR_RULE_16_BAD_ENTRY_LENGTH;
                uint8_t b;
                r = io_read(&rt->io, &b, in_cursor++, 1);
                if (r != RAWTILES_OK) return r;
                uint32_t n = (uint32_t)(h & 0x7Fu) + 1u;
                if (produced + n > decoded_size)
                    return RAWTILES_ERR_RULE_16_BAD_ENTRY_LENGTH;
                memset(out_buf + produced, b, n);
                produced += n;
            }
        }
        /* Spec § 9.11: encoded stream is consumed exactly. Trailing bytes are
         * a malformed tile. */
        if (in_cursor != in_end)
            return RAWTILES_ERR_RULE_16_BAD_ENTRY_LENGTH;
        return RAWTILES_OK;
    }

    return RAWTILES_ERR_RULE_7_BAD_ENUM;
}

uint16_t rawtiles_tile_dim_px(const rawtiles_t *rt) { return rt->tile_dim_px; }
uint32_t rawtiles_tile_count(const rawtiles_t *rt) { return rt->tile_count; }
uint8_t  rawtiles_zoom_min(const rawtiles_t *rt) { return rt->zoom_min; }
uint8_t  rawtiles_zoom_max(const rawtiles_t *rt) { return rt->zoom_max; }
rawtiles_pixel_format_t rawtiles_pixel_format(const rawtiles_t *rt) {
    return (rawtiles_pixel_format_t)rt->pixel_format;
}
rawtiles_compression_t rawtiles_default_compression(const rawtiles_t *rt) {
    (void)rt; return RAWTILES_COMPRESSION_NONE;
}
rawtiles_projection_t rawtiles_projection(const rawtiles_t *rt) {
    return (rawtiles_projection_t)rt->projection;
}
rawtiles_addressing_t rawtiles_addressing(const rawtiles_t *rt) {
    return (rawtiles_addressing_t)rt->addressing;
}
rawtiles_axis_t rawtiles_axis(const rawtiles_t *rt) {
    return (rawtiles_axis_t)rt->axis;
}

void rawtiles_pack_uuid(const rawtiles_t *rt, uint8_t out_uuid[16]) {
    memcpy(out_uuid, rt->header + HDR_OFF_PACK_UUID, 16);
}

void rawtiles_bbox(const rawtiles_t *rt, int32_t *min_lon, int32_t *min_lat,
                   int32_t *max_lon, int32_t *max_lat) {
    if (min_lon) *min_lon = rd_i32le(rt->header + HDR_OFF_BBOX_MIN_LON);
    if (min_lat) *min_lat = rd_i32le(rt->header + HDR_OFF_BBOX_MIN_LAT);
    if (max_lon) *max_lon = rd_i32le(rt->header + HDR_OFF_BBOX_MAX_LON);
    if (max_lat) *max_lat = rd_i32le(rt->header + HDR_OFF_BBOX_MAX_LAT);
}

/* AFFN accessor. Locates the AFFN section by walking extensions (rare op).
 * Returns RAWTILES_OK + fills out_coeffs for LocalLinear packs; ABSENT for
 * non-LocalLinear (the per-rule errors are caught at open). */
rawtiles_result_t rawtiles_get_affn(rawtiles_t *rt, double out_coeffs[6])
{
    if (rt->projection != RAWTILES_PROJ_LOCALLINEAR) return RAWTILES_ABSENT;

    uint32_t cursor = rt->extensions_offset;
    uint32_t end    = rt->io.size - 4;
    while (cursor < end) {
        uint8_t hdr[8];
        rawtiles_result_t r = io_read(&rt->io, hdr, cursor, 8);
        if (r != RAWTILES_OK) return r;
        uint32_t length = rd_u32le(hdr + 4);
        if (hdr[0] == 'A' && hdr[1] == 'F' && hdr[2] == 'F' && hdr[3] == 'N') {
            uint8_t buf[48];
            r = io_read(&rt->io, buf, cursor + 8, 48);
            if (r != RAWTILES_OK) return r;
            /* Pull doubles via memcpy to avoid alignment issues. */
            for (int i = 0; i < 6; ++i) memcpy(&out_coeffs[i], buf + i * 8, 8);
            return RAWTILES_OK;
        }
        cursor += 8 + align4(length);
    }
    return RAWTILES_ERR_RULE_22_LOCALLINEAR_NEEDS_AFFN;
}

/* Extension iterator. v0.1: minimal implementation. */
rawtiles_result_t rawtiles_ext_iter_init(rawtiles_t *rt,
                                         rawtiles_ext_iter_t *it)
{
    if (!rt || !it) return RAWTILES_ERR_INVALID_ARG;
    it->rt = rt;
    it->cursor = rt->extensions_offset;
    it->end = rt->io.size - 4;
    it->have_current = false;
    it->current_payload_offset = 0;
    it->current_payload_length = 0;
    return RAWTILES_OK;
}

rawtiles_result_t rawtiles_ext_iter_next(rawtiles_ext_iter_t *it,
                                         char out_tag[4], uint32_t *out_length)
{
    if (!it) return RAWTILES_ERR_INVALID_ARG;
    if (it->cursor >= it->end) {
        it->have_current = false;
        return RAWTILES_ABSENT;
    }
    uint8_t hdr[8];
    rawtiles_result_t r = io_read(&it->rt->io, hdr, it->cursor, 8);
    if (r != RAWTILES_OK) return r;
    memcpy(out_tag, hdr, 4);
    memcpy(it->current_tag, hdr, 4);
    uint32_t length = rd_u32le(hdr + 4);
    it->current_payload_offset = it->cursor + 8;
    it->current_payload_length = length;
    *out_length = length;
    it->have_current = true;
    it->cursor = it->current_payload_offset + align4(length);
    return RAWTILES_OK;
}

rawtiles_result_t rawtiles_ext_iter_read_payload(rawtiles_ext_iter_t *it,
                                                 uint8_t *out_buf,
                                                 size_t out_buf_size)
{
    if (!it || !out_buf) return RAWTILES_ERR_INVALID_ARG;
    if (!it->have_current) return RAWTILES_ERR_INVALID_ARG;
    if (out_buf_size < it->current_payload_length)
        return RAWTILES_ERR_BUFFER_TOO_SMALL;
    return io_read(&it->rt->io, out_buf, it->current_payload_offset,
                   it->current_payload_length);
}

const char *rawtiles_strerror(rawtiles_result_t code)
{
    switch (code) {
    case RAWTILES_OK: return "ok";
    case RAWTILES_ABSENT: return "absent";
    case RAWTILES_ERR_IO: return "I/O error";
    case RAWTILES_ERR_BUFFER_TOO_SMALL: return "buffer too small";
    case RAWTILES_ERR_INVALID_ARG: return "invalid argument";
    case RAWTILES_ERR_INTERNAL: return "internal reader bug";
    case RAWTILES_ERR_RULE_1_SHORT_FILE: return "§11 #1: file < 296 bytes";
    case RAWTILES_ERR_RULE_2_BAD_MAGIC: return "§11 #2: magic != RAWT";
    case RAWTILES_ERR_RULE_3_BAD_VERSION: return "§11 #3: format_version_major != 1";
    case RAWTILES_ERR_RULE_5_UUID_ZERO: return "§11 #5: pack_uuid = all-zero";
    case RAWTILES_ERR_RULE_6_PARENT_NONZERO: return "§11 #6: parent_uuid != all-zero";
    case RAWTILES_ERR_RULE_7_BAD_ENUM: return "§11 #7: unknown enum byte";
    case RAWTILES_ERR_RULE_8_BAD_PROJ_ADDR_PAIR: return "§11 #8: illegal projection × addressing pair";
    case RAWTILES_ERR_RULE_9_TILEDIM_ZERO: return "§11 #9: tile_dim_px = 0";
    case RAWTILES_ERR_RULE_10_BAD_ZOOM_RANGE: return "§11 #10: bad zoom range";
    case RAWTILES_ERR_RULE_11_BAD_BBOX: return "§11 #11: bad bbox";
    case RAWTILES_ERR_RULE_12_BAD_ENTRY_FLAGS: return "§11 #12: non-zero entry flags/reserved";
    case RAWTILES_ERR_RULE_13_BAD_ENTRY_ORDER: return "§11 #13: entries not sorted";
    case RAWTILES_ERR_RULE_14_BAD_ENTRY_BOUNDS: return "§11 #14: bad entry offset/length";
    case RAWTILES_ERR_RULE_15_ENTRY_ZOOM_OUT_OF_RANGE: return "§11 #15: entry z out of [zmin, zmax]";
    case RAWTILES_ERR_RULE_16_BAD_ENTRY_LENGTH: return "§11 #16: entry length doesn't match format";
    case RAWTILES_ERR_RULE_17_BAD_ZOOM_OFFSETS: return "§11 #17: zoom_offsets inconsistent";
    case RAWTILES_ERR_RULE_18_BAD_EXT_OFFSET: return "§11 #18: bad extensions_offset";
    case RAWTILES_ERR_RULE_19_BAD_SECTION_FRAMING: return "§11 #19: bad section framing";
    case RAWTILES_ERR_RULE_20_UNKNOWN_UPPERCASE_TAG: return "§11 #20: unknown uppercase tag";
    case RAWTILES_ERR_RULE_22_LOCALLINEAR_NEEDS_AFFN: return "§11 #22: LocalLinear missing AFFN";
    case RAWTILES_ERR_RULE_23_BAD_SINGLEIMAGE: return "§11 #23: bad SingleImage shape";
    case RAWTILES_ERR_RULE_24_BAD_CRC: return "§11 #24: CRC mismatch";
    case RAWTILES_ERR_RULE_25_BAD_INDEX_OFFSET: return "§11 #25: index_offset != 292";
    case RAWTILES_ERR_RULE_26_BAD_NAME_LENGTH: return "§11 #26: bad NAME length";
    case RAWTILES_ERR_RULE_27_BAD_TAG_FIRST_BYTE: return "§11 #27: tag first byte outside [A-Z, a-z]";
    case RAWTILES_ERR_RULE_28_BAD_TAG_PRINTABLE: return "§11 #28: tag bytes 2-4 non-printable";
    case RAWTILES_ERR_RULE_29_DUPLICATE_TAG: return "§11 #29: duplicate uppercase tag";
    case RAWTILES_ERR_RULE_30_PACK_TOO_LARGE: return "§11 #30: pack too large";
    case RAWTILES_ERR_RULE_31_QUADTREE_XY_OVERFLOW: return "§11 #31: Quadtree x/y >= 2^z";
    case RAWTILES_ERR_RULE_32_TILE_LAYOUT_NOT_TIGHT: return "§11 #32: tile layout not tight";
    case RAWTILES_ERR_RULE_33_NONZERO_PADDING: return "§11 #33: non-zero per-tile padding";
    case RAWTILES_ERR_RULE_34_BAD_AFFN_LENGTH: return "§11 #34: AFFN length != 48";
    case RAWTILES_ERR_RULE_35_AFFN_NOT_FINITE: return "§11 #35: AFFN coefficient non-finite";
    case RAWTILES_ERR_RULE_36_AFFN_ON_NON_LOCALLINEAR: return "§11 #36: AFFN on non-LocalLinear";
    case RAWTILES_ERR_RULE_37_BAD_NAME_TEXT: return "§11 #37: NAME UTF-8 / BCP-47 invalid";
    case RAWTILES_ERR_RULE_38_BAD_SRCD_OR_ATTR_TEXT: return "§11 #38: SRCD/ATTR text invalid";
    default: return "unknown";
    }
}
