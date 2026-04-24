"""Rename downloaded screenshots to: YYYY-MM-DD-<category>-<caption>.jpg

Strips filesystem-illegal chars, truncates caption to 10 chars, handles
collisions with -2, -3 suffixes. Optionally mirrors renamed files to an
archive directory for persistent local storage.
"""
from __future__ import annotations

import pathlib
import re
import shutil
from datetime import datetime

_ILLEGAL = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_WHITESPACE = re.compile(r"\s+")
MAX_CAPTION_CHARS = 10
MAX_CATEGORY_CHARS = 8


def _clean(text: str, max_chars: int) -> str:
    text = _ILLEGAL.sub("", text or "")
    text = _WHITESPACE.sub("_", text).strip("_-.")
    return text[:max_chars]


def compute_name(creation_time_iso: str, category: str, caption: str, ext: str = ".jpg") -> str:
    dt = datetime.fromisoformat(creation_time_iso.replace("Z", "+00:00"))
    date_str = dt.strftime("%Y-%m-%d")
    cat = _clean(category, MAX_CATEGORY_CHARS) or "未分類"
    cap = _clean(caption, MAX_CAPTION_CHARS) or "未命名"
    return f"{date_str}-{cat}-{cap}{ext}"


def _unique_path(dest_dir: pathlib.Path, name: str) -> pathlib.Path:
    candidate = dest_dir / name
    if not candidate.exists():
        return candidate
    stem = candidate.stem
    ext = candidate.suffix
    for n in range(2, 1000):
        alt = dest_dir / f"{stem}-{n}{ext}"
        if not alt.exists():
            return alt
    raise RuntimeError(f"too many collisions for {name}")


def rename_and_archive(
    old_path: pathlib.Path,
    new_name: str,
    archive_dir: pathlib.Path | None = None,
) -> pathlib.Path:
    """Rename `old_path` to a unique path with `new_name` in its directory.

    If `archive_dir` is provided, also copy the renamed file there.
    Returns the new path.
    """
    new_path = _unique_path(old_path.parent, new_name)
    old_path.rename(new_path)

    if archive_dir is not None:
        archive_dir.mkdir(parents=True, exist_ok=True)
        archive_target = _unique_path(archive_dir, new_path.name)
        shutil.copy2(new_path, archive_target)

    return new_path
