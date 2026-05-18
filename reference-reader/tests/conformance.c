/*
 * rawtiles reference reader — conformance test runner
 *
 * Usage: rawtiles_conformance <path-to-spec/conformance>
 *
 *   - For each golden fixture: opens, then reads the sibling .hashes file
 *     (§ 14.5) and verifies each (z, x, y) round-trips with a matching
 *     SHA-256 digest. This exercises binary search, zoom_offsets indirection,
 *     pixel-format layout, and any compression decoders.
 *
 *   - For each negative fixture (named neg-<rule>[<sub>]-...): parses the
 *     rule number from the filename and expects rawtiles_open to return the
 *     matching RAWTILES_ERR_RULE_<n>_* code.
 *
 * SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026, Toby Murray
 */
#include "rawtiles/rawtiles.h"

#include <dirent.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>

#define MAX_PATH 1024

/* =========================================================================
 * SHA-256 (FIPS 180-4)
 *
 * Self-contained reference implementation. Verified against the standard
 * test vectors:
 *   ""               → e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
 *   "abc"            → ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad
 *   "abcdbcdec..."   → 248d6a61d20638b8e5c026930c3e6039a33ce45964ff2167f6ecedd419db06c1
 * ======================================================================= */
typedef struct {
    uint32_t state[8];
    uint64_t bitcount;
    uint8_t buffer[64];
    size_t  buflen;
} sha256_ctx;

static const uint32_t SHA256_K[64] = {
    0x428a2f98u,0x71374491u,0xb5c0fbcfu,0xe9b5dba5u,0x3956c25bu,0x59f111f1u,0x923f82a4u,0xab1c5ed5u,
    0xd807aa98u,0x12835b01u,0x243185beu,0x550c7dc3u,0x72be5d74u,0x80deb1feu,0x9bdc06a7u,0xc19bf174u,
    0xe49b69c1u,0xefbe4786u,0x0fc19dc6u,0x240ca1ccu,0x2de92c6fu,0x4a7484aau,0x5cb0a9dcu,0x76f988dau,
    0x983e5152u,0xa831c66du,0xb00327c8u,0xbf597fc7u,0xc6e00bf3u,0xd5a79147u,0x06ca6351u,0x14292967u,
    0x27b70a85u,0x2e1b2138u,0x4d2c6dfcu,0x53380d13u,0x650a7354u,0x766a0abbu,0x81c2c92eu,0x92722c85u,
    0xa2bfe8a1u,0xa81a664bu,0xc24b8b70u,0xc76c51a3u,0xd192e819u,0xd6990624u,0xf40e3585u,0x106aa070u,
    0x19a4c116u,0x1e376c08u,0x2748774cu,0x34b0bcb5u,0x391c0cb3u,0x4ed8aa4au,0x5b9cca4fu,0x682e6ff3u,
    0x748f82eeu,0x78a5636fu,0x84c87814u,0x8cc70208u,0x90befffau,0xa4506cebu,0xbef9a3f7u,0xc67178f2u,
};

static inline uint32_t rotr32(uint32_t x, unsigned n) {
    return (x >> n) | (x << (32 - n));
}

static void sha256_compress(uint32_t state[8], const uint8_t blk[64]) {
    uint32_t w[64];
    for (int i = 0; i < 16; ++i) {
        w[i] = ((uint32_t)blk[i*4 + 0] << 24) |
               ((uint32_t)blk[i*4 + 1] << 16) |
               ((uint32_t)blk[i*4 + 2] << 8)  |
               ((uint32_t)blk[i*4 + 3]);
    }
    for (int i = 16; i < 64; ++i) {
        uint32_t s0 = rotr32(w[i-15], 7) ^ rotr32(w[i-15], 18) ^ (w[i-15] >> 3);
        uint32_t s1 = rotr32(w[i-2], 17) ^ rotr32(w[i-2], 19)  ^ (w[i-2] >> 10);
        w[i] = w[i-16] + s0 + w[i-7] + s1;
    }
    uint32_t a = state[0], b = state[1], c = state[2], d = state[3];
    uint32_t e = state[4], f = state[5], g = state[6], h = state[7];
    for (int i = 0; i < 64; ++i) {
        uint32_t S1 = rotr32(e, 6) ^ rotr32(e, 11) ^ rotr32(e, 25);
        uint32_t ch = (e & f) ^ (~e & g);
        uint32_t t1 = h + S1 + ch + SHA256_K[i] + w[i];
        uint32_t S0 = rotr32(a, 2) ^ rotr32(a, 13) ^ rotr32(a, 22);
        uint32_t mj = (a & b) ^ (a & c) ^ (b & c);
        uint32_t t2 = S0 + mj;
        h = g; g = f; f = e;
        e = d + t1;
        d = c; c = b; b = a;
        a = t1 + t2;
    }
    state[0] += a; state[1] += b; state[2] += c; state[3] += d;
    state[4] += e; state[5] += f; state[6] += g; state[7] += h;
}

static void sha256_init(sha256_ctx *c) {
    c->state[0] = 0x6a09e667u; c->state[1] = 0xbb67ae85u;
    c->state[2] = 0x3c6ef372u; c->state[3] = 0xa54ff53au;
    c->state[4] = 0x510e527fu; c->state[5] = 0x9b05688cu;
    c->state[6] = 0x1f83d9abu; c->state[7] = 0x5be0cd19u;
    c->bitcount = 0;
    c->buflen = 0;
}

static void sha256_update(sha256_ctx *c, const uint8_t *data, size_t len) {
    c->bitcount += (uint64_t)len * 8;
    while (len > 0) {
        size_t take = 64 - c->buflen;
        if (take > len) take = len;
        memcpy(c->buffer + c->buflen, data, take);
        c->buflen += take; data += take; len -= take;
        if (c->buflen == 64) {
            sha256_compress(c->state, c->buffer);
            c->buflen = 0;
        }
    }
}

static void sha256_final(sha256_ctx *c, uint8_t out[32]) {
    c->buffer[c->buflen++] = 0x80;
    if (c->buflen > 56) {
        while (c->buflen < 64) c->buffer[c->buflen++] = 0;
        sha256_compress(c->state, c->buffer);
        c->buflen = 0;
    }
    while (c->buflen < 56) c->buffer[c->buflen++] = 0;
    uint64_t bc = c->bitcount;
    for (int i = 7; i >= 0; --i) c->buffer[c->buflen++] = (uint8_t)(bc >> (i*8));
    sha256_compress(c->state, c->buffer);
    for (int i = 0; i < 8; ++i) {
        out[i*4 + 0] = (uint8_t)(c->state[i] >> 24);
        out[i*4 + 1] = (uint8_t)(c->state[i] >> 16);
        out[i*4 + 2] = (uint8_t)(c->state[i] >> 8);
        out[i*4 + 3] = (uint8_t)(c->state[i]);
    }
}

static void sha256(const uint8_t *data, size_t len, uint8_t out[32]) {
    sha256_ctx c; sha256_init(&c); sha256_update(&c, data, len); sha256_final(&c, out);
}

/* =========================================================================
 * Helpers
 * ======================================================================= */
static int read_file(const char *path, uint8_t **out_buf, uint32_t *out_size)
{
    FILE *f = fopen(path, "rb");
    if (!f) return -1;
    if (fseek(f, 0, SEEK_END) != 0) { fclose(f); return -1; }
    long sz = ftell(f);
    if (sz < 0 || (unsigned long)sz > 0xFFFFFFFFu) { fclose(f); return -1; }
    if (fseek(f, 0, SEEK_SET) != 0) { fclose(f); return -1; }
    uint8_t *buf = (uint8_t *)malloc((size_t)sz);
    if (!buf) { fclose(f); return -1; }
    if (fread(buf, 1, (size_t)sz, f) != (size_t)sz) {
        free(buf); fclose(f); return -1;
    }
    fclose(f);
    *out_buf = buf;
    *out_size = (uint32_t)sz;
    return 0;
}

static int hex_nibble(char c) {
    if (c >= '0' && c <= '9') return c - '0';
    if (c >= 'a' && c <= 'f') return 10 + c - 'a';
    if (c >= 'A' && c <= 'F') return 10 + c - 'A';
    return -1;
}

static int parse_sha256_hex(const char *hex, uint8_t out[32]) {
    for (int i = 0; i < 32; ++i) {
        int hi = hex_nibble(hex[i*2 + 0]);
        int lo = hex_nibble(hex[i*2 + 1]);
        if (hi < 0 || lo < 0) return -1;
        out[i] = (uint8_t)((hi << 4) | lo);
    }
    return 0;
}

static void format_sha256_hex(const uint8_t in[32], char out[65]) {
    static const char hex[] = "0123456789abcdef";
    for (int i = 0; i < 32; ++i) {
        out[i*2 + 0] = hex[(in[i] >> 4) & 0xF];
        out[i*2 + 1] = hex[in[i] & 0xF];
    }
    out[64] = '\0';
}

/* ----------------------------------------------------------------------- */

typedef struct {
    uint8_t  z;
    uint32_t x;
    uint32_t y;
    uint8_t  hash[32];
} hash_entry_t;

/* Parse a .hashes file: returns malloced array of entries, count in *out_count.
 * Returns -1 on parse failure. Skips lines starting with '#' or blank lines. */
static int parse_hashes_file(const char *path, hash_entry_t **out_entries,
                             size_t *out_count)
{
    FILE *f = fopen(path, "r");
    if (!f) return -1;

    size_t cap = 16, cnt = 0;
    hash_entry_t *arr = (hash_entry_t *)malloc(cap * sizeof(*arr));
    if (!arr) { fclose(f); return -1; }

    char line[256];
    while (fgets(line, sizeof(line), f)) {
        char *p = line;
        while (*p == ' ' || *p == '\t') p++;
        if (*p == '#' || *p == '\n' || *p == '\0' || *p == '\r') continue;

        unsigned z, x, y;
        char hex[80] = {0};
        int n = sscanf(p, "%u %u %u %79s", &z, &x, &y, hex);
        if (n != 4 || strlen(hex) != 64) {
            fclose(f); free(arr); return -1;
        }
        if (cnt == cap) {
            cap *= 2;
            arr = (hash_entry_t *)realloc(arr, cap * sizeof(*arr));
            if (!arr) { fclose(f); return -1; }
        }
        arr[cnt].z = (uint8_t)z;
        arr[cnt].x = (uint32_t)x;
        arr[cnt].y = (uint32_t)y;
        if (parse_sha256_hex(hex, arr[cnt].hash) != 0) {
            fclose(f); free(arr); return -1;
        }
        cnt++;
    }
    fclose(f);
    *out_entries = arr;
    *out_count = cnt;
    return 0;
}

/* =========================================================================
 * Test runners
 * ======================================================================= */
static int g_passed = 0;
static int g_failed = 0;
static int g_skipped = 0;
static int g_hash_passed = 0;
static int g_hash_failed = 0;

static void run_golden(const char *dir, const char *fname)
{
    char pack_path[MAX_PATH], hash_path[MAX_PATH];
    snprintf(pack_path, sizeof(pack_path), "%s/%s", dir, fname);
    /* Derive sibling .hashes path: same name with .rawtiles → .hashes */
    snprintf(hash_path, sizeof(hash_path), "%s/%.*s.hashes", dir,
             (int)(strlen(fname) - 9 /* len(".rawtiles") */), fname);

    uint8_t *buf = NULL;
    uint32_t sz = 0;
    if (read_file(pack_path, &buf, &sz) != 0) {
        printf("  [SKIP] %s (read failed)\n", fname);
        g_skipped++;
        return;
    }

    rawtiles_t rt;
    rawtiles_result_t r =
        rawtiles_open(&rt, rawtiles_io_memory(buf, sz), RAWTILES_OPEN_DEFAULT);
    if (r != RAWTILES_OK) {
        printf("  [FAIL] %s — open: %s\n", fname, rawtiles_strerror(r));
        g_failed++;
        free(buf);
        return;
    }

    /* Load hash table. Missing .hashes is a test-setup error, not a reader bug;
     * skip with a note. */
    hash_entry_t *entries = NULL;
    size_t entry_count = 0;
    if (parse_hashes_file(hash_path, &entries, &entry_count) != 0) {
        printf("  [SKIP] %s (no .hashes file or unparseable)\n", fname);
        g_skipped++;
        free(buf);
        return;
    }

    size_t decoded_size = rawtiles_decoded_tile_size(&rt);
    uint8_t *tile_buf = (uint8_t *)malloc(decoded_size > 0 ? decoded_size : 1);

    int per_pack_pass = 0, per_pack_fail = 0;
    char first_fail_msg[256] = {0};

    for (size_t i = 0; i < entry_count; ++i) {
        rawtiles_result_t tr = rawtiles_get_tile(&rt, entries[i].z,
                                                  entries[i].x, entries[i].y,
                                                  tile_buf, decoded_size);
        if (tr != RAWTILES_OK) {
            if (!*first_fail_msg) {
                snprintf(first_fail_msg, sizeof(first_fail_msg),
                         "getTile(%u, %u, %u): %s", entries[i].z, entries[i].x,
                         entries[i].y, rawtiles_strerror(tr));
            }
            per_pack_fail++;
            continue;
        }
        uint8_t got[32];
        sha256(tile_buf, decoded_size, got);
        if (memcmp(got, entries[i].hash, 32) != 0) {
            if (!*first_fail_msg) {
                char got_hex[65], want_hex[65];
                format_sha256_hex(got, got_hex);
                format_sha256_hex(entries[i].hash, want_hex);
                snprintf(first_fail_msg, sizeof(first_fail_msg),
                         "(%u, %u, %u) hash mismatch:\n             got  %s\n             want %s",
                         entries[i].z, entries[i].x, entries[i].y, got_hex, want_hex);
            }
            per_pack_fail++;
            continue;
        }
        per_pack_pass++;
    }

    if (per_pack_fail == 0) {
        printf("  [PASS] %s — open OK, %zu/%zu tile hashes match\n",
               fname, (size_t)per_pack_pass, entry_count);
        g_passed++;
    } else {
        printf("  [FAIL] %s — open OK, %d/%zu tile hashes match\n             %s\n",
               fname, per_pack_pass, entry_count, first_fail_msg);
        g_failed++;
    }
    g_hash_passed += per_pack_pass;
    g_hash_failed += per_pack_fail;

    free(tile_buf);
    free(entries);
    free(buf);
}

/* Parse expected rule number from a filename like "neg-14a-offset-misaligned.rawtiles". */
static int parse_expected_rule(const char *fname)
{
    if (strncmp(fname, "neg-", 4) != 0) return 0;
    const char *p = fname + 4;
    int rule = 0;
    while (*p >= '0' && *p <= '9') {
        rule = rule * 10 + (*p - '0');
        p++;
    }
    return rule;
}

static rawtiles_result_t expected_code_for_rule(int rule)
{
    switch (rule) {
    case  1: return RAWTILES_ERR_RULE_1_SHORT_FILE;
    case  2: return RAWTILES_ERR_RULE_2_BAD_MAGIC;
    case  3: return RAWTILES_ERR_RULE_3_BAD_VERSION;
    case  5: return RAWTILES_ERR_RULE_5_UUID_ZERO;
    case  6: return RAWTILES_ERR_RULE_6_PARENT_NONZERO;
    case  7: return RAWTILES_ERR_RULE_7_BAD_ENUM;
    case  8: return RAWTILES_ERR_RULE_8_BAD_PROJ_ADDR_PAIR;
    case  9: return RAWTILES_ERR_RULE_9_TILEDIM_ZERO;
    case 10: return RAWTILES_ERR_RULE_10_BAD_ZOOM_RANGE;
    case 11: return RAWTILES_ERR_RULE_11_BAD_BBOX;
    case 12: return RAWTILES_ERR_RULE_12_BAD_ENTRY_FLAGS;
    case 13: return RAWTILES_ERR_RULE_13_BAD_ENTRY_ORDER;
    case 14: return RAWTILES_ERR_RULE_14_BAD_ENTRY_BOUNDS;
    case 15: return RAWTILES_ERR_RULE_15_ENTRY_ZOOM_OUT_OF_RANGE;
    case 16: return RAWTILES_ERR_RULE_16_BAD_ENTRY_LENGTH;
    case 17: return RAWTILES_ERR_RULE_17_BAD_ZOOM_OFFSETS;
    case 18: return RAWTILES_ERR_RULE_18_BAD_EXT_OFFSET;
    case 19: return RAWTILES_ERR_RULE_19_BAD_SECTION_FRAMING;
    case 20: return RAWTILES_ERR_RULE_20_UNKNOWN_UPPERCASE_TAG;
    case 22: return RAWTILES_ERR_RULE_22_LOCALLINEAR_NEEDS_AFFN;
    case 23: return RAWTILES_ERR_RULE_23_BAD_SINGLEIMAGE;
    case 24: return RAWTILES_ERR_RULE_24_BAD_CRC;
    case 25: return RAWTILES_ERR_RULE_25_BAD_INDEX_OFFSET;
    case 26: return RAWTILES_ERR_RULE_26_BAD_NAME_LENGTH;
    case 27: return RAWTILES_ERR_RULE_27_BAD_TAG_FIRST_BYTE;
    case 28: return RAWTILES_ERR_RULE_28_BAD_TAG_PRINTABLE;
    case 29: return RAWTILES_ERR_RULE_29_DUPLICATE_TAG;
    case 31: return RAWTILES_ERR_RULE_31_QUADTREE_XY_OVERFLOW;
    case 32: return RAWTILES_ERR_RULE_32_TILE_LAYOUT_NOT_TIGHT;
    case 33: return RAWTILES_ERR_RULE_33_NONZERO_PADDING;
    case 34: return RAWTILES_ERR_RULE_34_BAD_AFFN_LENGTH;
    case 35: return RAWTILES_ERR_RULE_35_AFFN_NOT_FINITE;
    case 36: return RAWTILES_ERR_RULE_36_AFFN_ON_NON_LOCALLINEAR;
    case 37: return RAWTILES_ERR_RULE_37_BAD_NAME_TEXT;
    case 38: return RAWTILES_ERR_RULE_38_BAD_SRCD_OR_ATTR_TEXT;
    default: return RAWTILES_OK;
    }
}

static void run_negative(const char *dir, const char *fname)
{
    char path[MAX_PATH];
    snprintf(path, sizeof(path), "%s/%s", dir, fname);

    int rule = parse_expected_rule(fname);
    if (rule == 0) {
        printf("  [SKIP] %s (can't parse expected rule from filename)\n", fname);
        g_skipped++;
        return;
    }
    rawtiles_result_t expected = expected_code_for_rule(rule);
    if (expected == RAWTILES_OK) {
        printf("  [SKIP] %s (no rule code for #%d)\n", fname, rule);
        g_skipped++;
        return;
    }

    uint8_t *buf = NULL;
    uint32_t sz = 0;
    if (read_file(path, &buf, &sz) != 0) {
        printf("  [SKIP] %s (read failed)\n", fname);
        g_skipped++;
        return;
    }

    rawtiles_t rt;
    rawtiles_result_t r =
        rawtiles_open(&rt, rawtiles_io_memory(buf, sz), RAWTILES_OPEN_DEFAULT);
    if (r == expected) {
        printf("  [PASS] %s (rejected with rule #%d)\n", fname, rule);
        g_passed++;
    } else if (r == RAWTILES_OK) {
        printf("  [FAIL] %s — expected rule #%d rejection, got OK\n",
               fname, rule);
        g_failed++;
    } else {
        printf("  [FAIL] %s — expected rule #%d (%d), got %d (%s)\n",
               fname, rule, (int)expected, (int)r, rawtiles_strerror(r));
        g_failed++;
    }
    free(buf);
}

/* ----------------------------------------------------------------------- */

static int has_suffix(const char *s, const char *suf)
{
    size_t ls = strlen(s), lf = strlen(suf);
    if (lf > ls) return 0;
    return strcmp(s + ls - lf, suf) == 0;
}

typedef void (*runner_fn)(const char *dir, const char *fname);

static void walk_dir(const char *dir, runner_fn run)
{
    DIR *d = opendir(dir);
    if (!d) {
        fprintf(stderr, "opendir(%s) failed\n", dir);
        return;
    }
    char **names = NULL;
    size_t count = 0, cap = 0;
    struct dirent *e;
    while ((e = readdir(d)) != NULL) {
        if (!has_suffix(e->d_name, ".rawtiles")) continue;
        if (count == cap) {
            cap = cap ? cap * 2 : 32;
            names = (char **)realloc(names, cap * sizeof(*names));
        }
        names[count++] = strdup(e->d_name);
    }
    closedir(d);
    for (size_t i = 1; i < count; ++i) {
        char *k = names[i];
        size_t j = i;
        while (j > 0 && strcmp(names[j - 1], k) > 0) {
            names[j] = names[j - 1];
            j--;
        }
        names[j] = k;
    }
    for (size_t i = 0; i < count; ++i) {
        run(dir, names[i]);
        free(names[i]);
    }
    free(names);
}

/* ----------------------------------------------------------------------- */

/* Sanity-check SHA-256 against the standard "abc" test vector before walking
 * the corpus. If this fails the SHA-256 implementation is broken and every
 * hash-table check would mislead. */
static int self_test_sha256(void)
{
    uint8_t out[32];
    sha256((const uint8_t *)"abc", 3, out);
    static const uint8_t want[32] = {
        0xba,0x78,0x16,0xbf,0x8f,0x01,0xcf,0xea,0x41,0x41,0x40,0xde,0x5d,0xae,0x22,0x23,
        0xb0,0x03,0x61,0xa3,0x96,0x17,0x7a,0x9c,0xb4,0x10,0xff,0x61,0xf2,0x00,0x15,0xad,
    };
    return memcmp(out, want, 32) == 0;
}

int main(int argc, char **argv)
{
    if (argc < 2) {
        fprintf(stderr, "usage: %s <path-to-spec/conformance>\n", argv[0]);
        return 2;
    }
    if (!self_test_sha256()) {
        fprintf(stderr, "FATAL: SHA-256 self-test failed\n");
        return 3;
    }
    const char *corpus = argv[1];

    char golden_dir[MAX_PATH], negative_dir[MAX_PATH];
    snprintf(golden_dir, sizeof(golden_dir), "%s/golden", corpus);
    snprintf(negative_dir, sizeof(negative_dir), "%s/negative", corpus);

    printf("=== Golden fixtures (open + § 14.5 hash-table) ===\n");
    walk_dir(golden_dir, run_golden);

    printf("\n=== Negative fixtures (expect rule rejection) ===\n");
    walk_dir(negative_dir, run_negative);

    printf("\n=== Summary ===\n");
    printf("  fixtures:    passed %d, failed %d, skipped %d\n",
           g_passed, g_failed, g_skipped);
    printf("  tile hashes: matched %d, mismatched %d\n",
           g_hash_passed, g_hash_failed);
    return g_failed == 0 ? 0 : 1;
}
