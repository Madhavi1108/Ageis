"""Sortable, unique id generation for AEGIS records.

See docs/AEGIS_IMPLEMENTATION_PLAN.md Section 10 ("sortable UUID ids") and
docs/DATA_MODEL.md Section 5. Ids are UUIDv7 (RFC 9562): a 48-bit millisecond
timestamp prefix followed by random bits, so lexicographic/string ordering of
generated ids matches creation order without a separate sequence column.
"""

from __future__ import annotations

import os
import time
import uuid


def new_id() -> str:
    """Generate a new sortable, unique id (UUIDv7) as a lowercase hex string."""
    unix_ms = time.time_ns() // 1_000_000
    rand_bytes = os.urandom(10)

    ts_bytes = unix_ms.to_bytes(6, "big")
    # Version (7) in the high nibble of byte 6, low nibble from randomness.
    byte6 = 0x70 | (rand_bytes[0] & 0x0F)
    # Variant (RFC 9562: 0b10xxxxxx) in byte 8.
    byte8 = 0x80 | (rand_bytes[2] & 0x3F)

    uuid_bytes = (
        ts_bytes
        + bytes([byte6, rand_bytes[1]])
        + bytes([byte8, rand_bytes[3]])
        + rand_bytes[4:10]
    )
    return str(uuid.UUID(bytes=uuid_bytes))
