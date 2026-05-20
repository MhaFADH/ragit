from __future__ import annotations

import hashlib
import os
from pathlib import Path


def walk_md_files(root: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    for dirpath, _dirnames, filenames in os.walk(root, followlinks=False):
        for fn in filenames:
            if not fn.endswith(".md"):
                continue
            abs_path = Path(dirpath) / fn
            rel_path = abs_path.relative_to(root).as_posix()
            with open(abs_path, "rb") as f:
                result[rel_path] = hashlib.sha256(f.read()).hexdigest()
    return result


def compute_diff(
    current: dict[str, str],
    stored: dict[str, str],
) -> tuple[list[str], list[str], list[str]]:
    added: list[str] = []
    modified: list[str] = []
    deleted: list[str] = []
    for path, digest in current.items():
        if path not in stored:
            added.append(path)
        elif stored[path] != digest:
            modified.append(path)
    for path in stored:
        if path not in current:
            deleted.append(path)
    return sorted(added), sorted(modified), sorted(deleted)
