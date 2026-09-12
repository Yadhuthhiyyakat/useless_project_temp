"""Epitaph generation for death records.

Each death gets a short, deterministic epitaph so the cemetery feels alive
without calling any external service.  The epitaph is derived from the file's
own metadata (name, extension, size, lifespan, cause) via a stable hash, so
the same file always gets the same epitaph and different files vary.

The service is pure — no I/O, no AI, no config — and is called at death time
by the lifecycle service.
"""

from __future__ import annotations

import hashlib

from app.database.models import File
from app.services.cause_service import DeathCause
from app.services.lifespan_service import Lifespan

_TEMPLATES: list[str] = [
    'Here lies {filename} — a humble {extension} that lived {lifespan}.',
    '{filename} lived {lifespan} before it was {cause}. Gone but not forgotten.',
    'Rest in peace, {filename} ({size}). {lifespan} of faithful service.',
    '{filename} — {extension} file, {size} — survived {lifespan} until {cause}.',
    'In memory of {filename}. It endured {lifespan}. Cause: {cause}.',
    'Farewell, {filename}. After {lifespan}, it met its end by {cause}.',
    '{filename} ({extension}) — {lifespan} on disk, now at rest.',
    'Here rests {filename}. Size {size}, lifespan {lifespan}, cause {cause}.',
]


def _pick_template(key: str) -> str:
    digest = hashlib.sha256(key.encode("utf-8")).digest()
    idx = digest[0] % len(_TEMPLATES)
    return _TEMPLATES[idx]


def _format_size(size_bytes: int) -> str:
    if size_bytes < 1024:
        return f"{size_bytes} bytes"
    if size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    return f"{size_bytes / (1024 * 1024):.1f} MB"


def generate_epitaph(
    *,
    file: File,
    lifespan: Lifespan,
    cause: DeathCause,
) -> str:
    """Return a deterministic epitaph for ``file``.

    The template is chosen by hashing ``file.id:file.path`` so the epitaph is
    stable per death but varies across deaths.
    """
    key = f"{file.id}:{file.path}"
    template = _pick_template(key)
    extension = file.extension.lstrip(".") or "unknown"
    if extension == "unknown" and file.extension == "":
        extension_label = "unknown type"
    else:
        extension_label = extension
    return template.format(
        filename=file.filename,
        extension=extension_label,
        size=_format_size(file.size_bytes),
        lifespan=lifespan.label,
        cause=cause.label.lower(),
    )


def is_valid_epitaph(value: str | None) -> bool:
    """True when ``value`` is a non-empty epitaph."""
    return isinstance(value, str) and len(value.strip()) > 0
