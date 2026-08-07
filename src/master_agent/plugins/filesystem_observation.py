"""The Observation and Normalization layers for the Filesystem Worker. See
VERIFICATION_SYSTEM.md §4 and FILESYSTEM_CAPABILITIES.md.

`normalize_observation()` is the only function, besides the Actions
themselves, that touches the filesystem. ObserveFilesystemAction and
FilesystemVerifier both call this one implementation -- no duplicated
"how do we read the filesystem" logic (ENGINEERING_PRINCIPLES.md #7).
Everything past `FilesystemObservation.as_dict()` is a plain, JSON-shaped
dict; no Path object ever crosses that boundary.

Observation facets, covering every source Mission Brief 005 named:
current path, file/folder metadata, directory listing, file content
(previews for large files), and permissions. The last two are opt-in
per call -- both are unbounded in the size of the filesystem rather
than the size of what the caller asked about, and Verification
re-observes on every verified step, so paying for them unconditionally
would tax every Mission for data most steps never check against.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


# A file content preview is unbounded in file size; a very large one
# would bloat every Evidence record that captured it (and any Memory
# record a future Miracle persists Evidence into). Capped rather than
# truncated silently -- `content_preview_truncated` says so out loud.
MAX_CONTENT_PREVIEW_CHARS = 10_000

# A directory listing is unbounded in directory size. Capped, with
# `directory_listing_truncated` reporting it.
MAX_DIRECTORY_ENTRIES = 500


@dataclass
class FileMetadata:
    """A generic, Path-free description of one file/folder metadata."""

    path: str
    name: str
    is_dir: bool
    size_bytes: int | None = None
    modified_at: str | None = None
    permissions: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "name": self.name,
            "is_dir": self.is_dir,
            "size_bytes": self.size_bytes,
            "modified_at": self.modified_at,
            "permissions": self.permissions,
        }


@dataclass
class DirectoryEntry:
    """One entry in a directory listing -- generic, Path-free."""

    name: str
    is_dir: bool
    size_bytes: int | None = None
    modified_at: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "is_dir": self.is_dir,
            "size_bytes": self.size_bytes,
            "modified_at": self.modified_at,
        }


@dataclass
class FilesystemObservation:
    """A complete, generic observation of filesystem state at a point in time.

    Always JSON-shaped via `as_dict()`. No Path objects escape.
    """

    target_path: str
    target_name: str
    target_exists: bool
    target_is_dir: bool | None = None
    target_size_bytes: int | None = None
    target_modified_at: str | None = None
    target_permissions: str | None = None
    content_preview: str | None = None
    content_preview_truncated: bool = False
    directory_listing: list[DirectoryEntry] = field(default_factory=list)
    directory_listing_truncated: bool = False
    parent_directory: str | None = None
    parent_listing: list[DirectoryEntry] = field(default_factory=list)
    captured_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def as_dict(self) -> dict[str, Any]:
        return {
            "target_path": self.target_path,
            "target_name": self.target_name,
            "target_exists": self.target_exists,
            "target_is_dir": self.target_is_dir,
            "target_size_bytes": self.target_size_bytes,
            "target_modified_at": self.target_modified_at,
            "target_permissions": self.target_permissions,
            "content_preview": self.content_preview,
            "content_preview_truncated": self.content_preview_truncated,
            "directory_listing": [entry.as_dict() for entry in self.directory_listing],
            "directory_listing_truncated": self.directory_listing_truncated,
            "parent_directory": self.parent_directory,
            "parent_listing": [entry.as_dict() for entry in self.parent_listing],
            "captured_at": self.captured_at.isoformat(),
        }


def _stat_to_metadata(target: Path, relative_to: Path) -> FileMetadata:
    """Convert a Path's stat result to generic FileMetadata."""
    stat = target.stat()
    try:
        rel_path = target.relative_to(relative_to).as_posix()
    except ValueError:
        rel_path = target.as_posix()

    # Permissions as octal string (last 3 digits)
    perms = oct(stat.st_mode & 0o777)

    return FileMetadata(
        path=rel_path,
        name=target.name,
        is_dir=target.is_dir(),
        size_bytes=stat.st_size if target.is_file() else None,
        modified_at=datetime.fromtimestamp(stat.st_mtime, UTC).isoformat(),
        permissions=perms,
    )


def _safe_listdir(target: Path, max_entries: int) -> tuple[list[DirectoryEntry], bool]:
    """List directory entries safely, returning (entries, truncated)."""
    entries: list[DirectoryEntry] = []
    truncated = False
    try:
        all_entries = sorted(target.iterdir(), key=lambda p: p.name.lower())
    except OSError:
        return [], False

    if len(all_entries) > max_entries:
        truncated = True
        all_entries = all_entries[:max_entries]

    for entry in all_entries:
        try:
            stat = entry.stat()
            entries.append(
                DirectoryEntry(
                    name=entry.name,
                    is_dir=entry.is_dir(),
                    size_bytes=stat.st_size if entry.is_file() else None,
                    modified_at=datetime.fromtimestamp(stat.st_mtime, UTC).isoformat(),
                )
            )
        except OSError:
            # Failed to stat this entry -- report what we can
            entries.append(
                DirectoryEntry(
                    name=entry.name,
                    is_dir=entry.is_dir(),
                )
            )
    return entries, truncated


def _safe_read_preview(target: Path, max_chars: int) -> tuple[str | None, bool]:
    """Read a text file preview safely, returning (preview, truncated)."""
    try:
        content = target.read_text()
    except (OSError, UnicodeDecodeError):
        return None, False

    if len(content) > max_chars:
        return content[:max_chars], True
    return content, False


def normalize_observation(
    target: Path,
    base: Path,
    include_content_preview: bool = False,
    include_directory_listing: bool = False,
) -> FilesystemObservation:
    """Reads generic, universal facts off a live filesystem path.

    `include_content_preview` opts into reading file content (for files only).
    `include_directory_listing` opts into listing directory contents (for dirs only).

    Both are opt-in rather than always-on because both are unbounded in
    filesystem size rather than the size of what the caller asked about,
    and Verification re-observes on every verified step, so paying for
    them unconditionally would tax every Mission for data most steps
    never check against.
    """
    target_exists = target.exists()

    if target_exists:
        target_is_dir = target.is_dir()
        stat = target.stat()
        target_size = stat.st_size if target.is_file() else None
        target_modified = datetime.fromtimestamp(stat.st_mtime, UTC).isoformat()
        target_perms = oct(stat.st_mode & 0o777)
        target_name = target.name
        try:
            target_path = target.relative_to(base).as_posix()
        except ValueError:
            target_path = target.as_posix()

        parent_dir = "."
        try:
            if target.parent != base:
                parent_dir = target.parent.relative_to(base).as_posix()
        except ValueError:
            parent_dir = target.parent.as_posix()
    else:
        target_is_dir = None
        target_size = None
        target_modified = None
        target_perms = None
        target_name = target.name
        try:
            target_path = target.relative_to(base).as_posix()
        except ValueError:
            target_path = target.as_posix()
        parent_dir = target.parent.relative_to(base).as_posix() if target.parent != base else "."

    content_preview = None
    content_truncated = False
    if include_content_preview and target_exists and target.is_file():
        content_preview, content_truncated = _safe_read_preview(target, MAX_CONTENT_PREVIEW_CHARS)

    directory_listing: list[DirectoryEntry] = []
    dir_truncated = False
    if include_directory_listing and target_exists and target.is_dir():
        directory_listing, dir_truncated = _safe_listdir(target, MAX_DIRECTORY_ENTRIES)

    parent_listing: list[DirectoryEntry] = []
    if target.parent.exists() and target.parent.is_dir():
        parent_listing, _ = _safe_listdir(target.parent, MAX_DIRECTORY_ENTRIES)

    return FilesystemObservation(
        target_path=target_path,
        target_name=target_name,
        target_exists=target_exists,
        target_is_dir=target_is_dir,
        target_size_bytes=target_size,
        target_modified_at=target_modified,
        target_permissions=target_perms,
        content_preview=content_preview,
        content_preview_truncated=content_truncated,
        directory_listing=directory_listing,
        directory_listing_truncated=dir_truncated,
        parent_directory=parent_dir,
        parent_listing=parent_listing,
        captured_at=datetime.now(UTC),
    )