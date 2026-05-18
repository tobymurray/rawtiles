"""neg-07[a-g] — § 11 #7 reserved enum values.

Seven sibling fixtures, each flipping ONE enum byte in the golden-smallest
pack to a value reserved by § 8. The rule under test is the same for all
seven; only the offset and the chosen reserved value differ. Per-fixture
descriptions are derived from the table below.

Fields covered:
  - pixel_format            (§ 8.1, header byte 56)
  - projection              (§ 8.2, header byte 57)
  - tile_addressing_scheme  (§ 8.3, header byte 58)
  - tile_axis_convention    (§ 8.4, header byte 59)
  - compression             (§ 8.5, byte 1 of tile-index entry 0)

For Quadtree packs the tile-index starts at file offset 292 (golden-smallest),
so the compression byte is at absolute file offset 293.
"""

from __future__ import annotations

from . import _lib

FIXTURES = [
    _lib.reserved_enum_fixture(suffix="a-pixfmt-0", offset=56,  value=0, field="pixel_format",           value_desc="reserved",                 spec_ref="§ 8.1"),
    # b-pixfmt-5: value 2 was reserved at spec v0.3 (L4 indexed); v0.4 allocated
    # value 2 to RGB565. L4 moved to the new reserved value 5; the fixture moved
    # with it.
    _lib.reserved_enum_fixture(suffix="b-pixfmt-5", offset=56,  value=5, field="pixel_format",           value_desc="reserved, L4 indexed",     spec_ref="§ 8.1"),
    _lib.reserved_enum_fixture(suffix="c-proj-0",   offset=57,  value=0, field="projection",             value_desc="reserved",                 spec_ref="§ 8.2"),
    _lib.reserved_enum_fixture(suffix="d-proj-2",   offset=57,  value=2, field="projection",             value_desc="reserved, equirectangular", spec_ref="§ 8.2"),
    _lib.reserved_enum_fixture(suffix="e-addr-0",   offset=58,  value=0, field="tile_addressing_scheme", value_desc="reserved",                 spec_ref="§ 8.3"),
    _lib.reserved_enum_fixture(suffix="f-axis-0",   offset=59,  value=0, field="tile_axis_convention",   value_desc="reserved",                 spec_ref="§ 8.4"),
    # g-comp-3: value 1 was reserved at spec v0.3 (LZ4); v0.4 allocated value 1
    # to RLE8. LZ4 moved to the new reserved value 3; the fixture moved with it.
    _lib.reserved_enum_fixture(suffix="g-comp-3",   offset=293, value=3, field="compression",            value_desc="reserved, LZ4",            spec_ref="§ 8.5"),
]
