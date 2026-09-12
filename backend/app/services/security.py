"""Security utilities: path validation, symlink safety, traversal guards.

All checks are pure functions — no I/O — so they can be called from both the
live watcher and the initial scan without side effects.
"""

from __future__ import annotations

import os
import stat
from pathlib import Path


class SecurityError(Exception):
    """Raised when a path fails a security check."""

    def __init__(self, message: str, code: str = "security_error") -> None:
        super().__init__(message)
        self.code = code


def resolve_within_roots(path: str, roots: list[str]) -> Path:
    """Resolve ``path`` and ensure it lives under one of ``roots``.

    Args:
        path: User-supplied or watcher-reported path (may be relative).
        roots: Absolute, pre-validated root directories (watched dirs).

    Returns:
        The resolved ``Path`` (symlinks resolved) guaranteed to be inside a root.

    Raises:
        SecurityError: if path escapes all roots, contains traversal, or
            roots list is empty.
    """
    if not roots:
        raise SecurityError("No watched directories configured", "no_roots")

    requested = Path(path)
    # Resolve symlinks to their true location
    try:
        real = requested.resolve(strict=False)
    except (OSError, RuntimeError) as e:
        raise SecurityError(f"Cannot resolve path: {e}", "resolve_failed")

    # Ensure the resolved path is under at least one root (after resolving roots too)
    for root in roots:
        try:
            real_root = Path(root).resolve(strict=True)
        except (OSError, RuntimeError):
            continue
        try:
            real.relative_to(real_root)
            return real
        except ValueError:
            continue

    raise SecurityError(
        f"Path {real} is outside all watched directories", "traversal"
    )


def is_safe_path(path: str, roots: list[str]) -> bool:
    """True when ``path`` passes ``resolve_within_roots`` without raising."""
    try:
        resolve_within_roots(path, roots)
        return True
    except SecurityError:
        return False


def validate_regular_file(path: Path) -> None:
    """Ensure ``path`` exists and is a regular file (not symlink, dir, device)."""
    try:
        st = path.lstat()
    except OSError as e:
        raise SecurityError(f"Cannot stat path: {e}", "stat_failed")
    if not stat.S_ISREG(st.st_mode):
        raise SecurityError("Path is not a regular file", "not_regular")


def is_absolute_and_safe(path: str, roots: list[str]) -> bool:
    """Quick check: absolute, no '..', under roots."""
    if not os.path.isabs(path):
        return False
    if ".." in Path(path).parts:
        return False
    return is_safe_path(path, roots)