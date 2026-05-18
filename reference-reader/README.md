# rawtiles reference reader

A v0.6-conformant C99 reader for the [rawtiles](../spec/rawtiles.md) binary
file format. Designed to be vendored into both C and C++ projects, including
constrained-display embedded firmware (PineTime / InfiniTime class, ESP32,
M5Stack, Cortex-M MCUs in general).

**License:** BSD-3-Clause (see [LICENSE](../LICENSE) at repo root).

## Design

- **C99.** Vendors cleanly into both C and C++. No STL allocations.
- **No internal heap.** Caller owns the `rawtiles_t` struct, the I/O backing,
  and any output buffers. The reader does not call `malloc`.
- **Two I/O modes:**
  - `RAWTILES_IO_MEMORY` — flat in-memory pointer (mmap, fully-loaded file).
  - `RAWTILES_IO_PREAD` — caller-supplied `pread`-style callback. Suits XIP
    flash, littlefs, FAT, BLE-streamed buffers.
- **Validation timing per spec § 11.1.** Default (eager) validates every
  § 11 rule at open. `RAWTILES_OPEN_LAZY` defers per-tile / per-extension /
  AFFN rules to first-access time. v0.1 of this reader implements eager
  validation; lazy mode is a planned follow-up.
- **Result codes carry spec rule numbers.** `RAWTILES_ERR_RULE_<n>_*` = 100 +
  rule number, so `RAWTILES_ERR_RULE_14_*` == 114. Makes mapping a rejection
  back to the spec section trivial.

## Status (v0.1, this directory)

| Area | Status |
|---|---|
| Header parsing + all eager rules | ✅ |
| Tile-index walk (#12, #13, #14, #15, #16, #17, #18 padded-sum, #31, #32) | ✅ |
| CRC-32/ISO-HDLC verification (eager) | ✅ |
| Extension framing (#19, #20, #27, #28, #29 for non-NAME, #33) | ✅ |
| AFFN (#22, #34, #35, #36) | ✅ |
| `getTile()` for ABGR2222 / None | ✅ |
| `getTile()` for RGB565 / None | ✅ |
| RLE decoder | ✅ |
| Extension iterator | ✅ |
| Conformance corpus runner | ✅ |
| Lazy validation mode | ⏳ planned |
| NAME duplicate-locale check (#29) | ⏳ planned |
| NAME UTF-8 + BCP-47 validation (#37) | ⏳ planned |
| SRCD/ATTR text-rule validation (#38) | ⏳ planned |
| Streaming-verify CRC (§ 10) | ⏳ planned |
| § 14.5 per-tile SHA-256 hash-table verification | ⏳ planned |

## Build

CMake is the canonical build, but the reader has no external dependencies, so
a one-line invocation works too:

```sh
# CMake
mkdir build && cd build && cmake .. && make && ctest --output-on-failure

# Direct
cc -std=c99 -Wall -Wextra -Iinclude src/rawtiles.c tests/conformance.c \
   -o build/rawtiles_conformance
./build/rawtiles_conformance ../spec/conformance
```

## Quick start

```c
#include "rawtiles/rawtiles.h"

uint8_t *pack_bytes = /* mmap or fread your .rawtiles file */;
uint32_t pack_size  = /* its size in bytes */;

rawtiles_t rt;
rawtiles_result_t r = rawtiles_open(
    &rt, rawtiles_io_memory(pack_bytes, pack_size), RAWTILES_OPEN_DEFAULT);
if (r != RAWTILES_OK) {
    fprintf(stderr, "open failed: %s\n", rawtiles_strerror(r));
    return 1;
}

size_t tile_size = rawtiles_decoded_tile_size(&rt);
uint8_t *tile_buf = malloc(tile_size);

r = rawtiles_get_tile(&rt, /*z*/ 2, /*x*/ 1, /*y*/ 2, tile_buf, tile_size);
if (r == RAWTILES_OK) {
    /* tile_buf holds decoded pixels in ABGR2222 or RGB565 layout */
} else if (r == RAWTILES_ABSENT) {
    /* (z, x, y) not in pack — normal outcome */
} else {
    fprintf(stderr, "getTile: %s\n", rawtiles_strerror(r));
}
```

## Embedded usage (PineTime / nRF52832 example)

```c
/* littlefs-backed pread */
static int littlefs_pread(void *ctx, uint8_t *dst, uint32_t off, uint32_t n) {
    lfs_file_t *f = (lfs_file_t *)ctx;
    if (lfs_file_seek(&lfs, f, off, LFS_SEEK_SET) < 0) return -1;
    return lfs_file_read(&lfs, f, dst, n) == (lfs_ssize_t)n ? 0 : -1;
}

rawtiles_t rt;
rawtiles_open(&rt,
              rawtiles_io_pread(littlefs_pread, &pack_file, pack_size),
              RAWTILES_OPEN_LAZY); /* lazy mode keeps RAM ≤ 1 KB */
```

The handle is `~330 bytes`. The full pack is never loaded; only the 292-byte
header is buffered at open. Decoder state for RLE is O(1).

## Footprint (preliminary)

Measured on macOS arm64 with `-O2` (not the target architecture; an ARM
Cortex-M build will give different numbers — that benchmark is upcoming):

| Artifact | Size |
|---|---:|
| Compiled object (`-O2`) | ~24 KB |
| `sizeof(rawtiles_t)` | ~330 B |
| Stack peak (parse golden-pyramid) | TBD |
| Stack peak (decode RLE tile) | TBD |

A target-platform benchmark on Cortex-M0+ is the next milestone after
this v0.1 cut.
