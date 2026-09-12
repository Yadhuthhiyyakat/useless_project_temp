"""File identity service.

Paths are not a reliable file identity: a rename or move changes the path while
the physical file stays the same. This service provides an abstraction so the
backend can recognise "the same physical file under a new name" instead of
recording it as a brand-new file.

Identity strategy
=================

Primary (preferred)
    A composition of the device id and inode number obtained from ``lstat``
    (``"device:inode"``). This survives renames and moves on the same
    filesystem because the inode travels with the file.

Fallback
    When a reliable filesystem identity is unavailable (virtual/network
    filesystems that expose no inode, or paths that no longer exist) the
    service falls back to matching by the last known path.

Platform differences
====================

* Linux / macOS / BSD — ``st_ino`` and ``st_dev`` are reliable on local
  filesystems. ``st_ino`` survives rename within the same filesystem.
* Windows — modern Python exposes ``st_ino``/``st_dev``; device is the volume
  number, so identity is stable within a volume. Recycle-bin moves go through
  low-level copies and can produce a new identity (see trash limitations).
* Network / virtual filesystems (NFS, some FUSE mounts, ``/proc``) — inodes may
  be ``0`` or unstable; matching then degrades to the path fallback.

Known limitations
=================

* Inode reuse: after deletion, a filesystem may assign the same inode to a new
  file. To avoid resurrecting a dead record, identity matching only considers
  records that are currently alive.
* Identity changes when a file is replaced (rename-over or copy) because that
  is genuinely a new physical file with a new inode.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from app.database.repositories import FileRepository


@dataclass(frozen=True)
class FileIdentity:
    """A stable, stat-derived identity for a physical file."""

    device: int
    inode: int

    @property
    def key(self) -> str:
        """Database-friendly ``"device:inode"`` string key."""
        return f"{self.device}:{self.inode}"


class FileIdentityService:
    """Stateless helper that derives identities and matches database records."""

    @staticmethod
    def identity_from_stat(st: os.stat_result) -> FileIdentity | None:
        """Build an identity from a stat result, or ``None`` if unavailable."""
        if st.st_dev and st.st_ino:
            return FileIdentity(device=st.st_dev, inode=st.st_ino)
        return None

    def identity_of(self, path: str) -> FileIdentity | None:
        """Return the identity for a path, or ``None`` if it cannot be derived.

        Also returns ``None`` when the path does not exist (the file may have
        just been deleted) or when ``lstat`` raises on a stat-unfriendly path.
        """
        try:
            st = os.lstat(path)
        except OSError:
            return None
        return self.identity_from_stat(st)

    def match_existing_file(
        self, files: FileRepository, path: str
    ) -> File | None:
        """Find the existing alive database record for a physical file at path.

        Identity-based lookup is tried first, then the path fallback. Returns
        ``None`` when nothing is known about the file.
        """
        identity = self.identity_of(path)
        if identity is not None:
            record = files.get_alive_by_filesystem_id(identity.key)
            if record is not None:
                return record
        return files.get_alive_by_path(path)