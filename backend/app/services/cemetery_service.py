"""Cemetery plot assignment.

Each death gets a deterministic ``(x, y)`` plot so the frontend can render a
stable cemetery without extra queries.  The coordinates are derived from the
file's identity (original path + file id) via SHA-256, so the same file always
maps to the same plot and different files scatter uniformly across the
``0–100`` square.

The service is intentionally pure and has no DB access — the lifecycle service
calls it at death time.
"""

from __future__ import annotations

import hashlib
import struct

CEMETERY_SIZE = 100.0


def _hash_to_float(digest: bytes, offset: int) -> float:
    """Map 4 bytes of ``digest`` at ``offset`` to ``[0, CEMETERY_SIZE)``."""
    (value,) = struct.unpack_from(">I", digest, offset)
    return (value / 0xFFFFFFFF) * CEMETERY_SIZE


def deterministic_coordinates(*, key: str) -> tuple[float, float]:
    """Return a stable ``(x, y)`` in ``[0, 100)`` for ``key``.

    ``key`` should uniquely identify the death — typically
    ``f\"{file_id}:{original_path}\"``.  The same key always yields the same
    coordinates; different keys scatter.
    """
    digest = hashlib.sha256(key.encode("utf-8")).digest()
    x = _hash_to_float(digest, 0)
    y = _hash_to_float(digest, 4)
    return (x, y)


def coordinates_for_death(*, file_id: int, original_path: str) -> tuple[float, float]:
    """Convenience wrapper using the canonical death key."""
    return deterministic_coordinates(key=f"{file_id}:{original_path}")


def is_valid_coordinate(value: float) -> bool:
    """True when ``value`` lies in the cemetery square."""
    return 0.0 <= value < CEMETERY_SIZE or value == 0.0  # 0 edge inclusive
