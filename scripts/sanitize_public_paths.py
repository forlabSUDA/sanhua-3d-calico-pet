from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]

WINDOWS_ABSOLUTE_PATH = re.compile(r"[A-Za-z]:\\\\[^\"'\n\r,}]+")
PUBLIC_TEXT_EXTENSIONS = {
    ".json",
    ".md",
    ".txt",
    ".csv",
    ".log",
    ".html",
    ".htm",
}
SKIP_DIRS = {
    ".git",
    ".venv",
    "venv",
    "env",
    "__pycache__",
    ".pytest_cache",
    "node_modules",
}


def to_public_relative_path(path_text: str) -> str:
    normalized = path_text.replace("\\\\", "/")

    marker = "sanhua_3d_pet_motionfix_all/"
    if marker in normalized:
        return normalized.split(marker, 1)[1]

    marker = "sanhua-3d-calico-pet/"
    if marker in normalized:
        return normalized.split(marker, 1)[1]

    parts = normalized.split("/")
    for anchor in ("qa", "pet-package", "source_frames", "scripts", "build"):
        if anchor in parts:
            return "/".join(parts[parts.index(anchor):])

    return "<local-path-redacted>"


def sanitize_text(text: str) -> tuple[str, int]:
    count = 0

    def replace(match: re.Match[str]) -> str:
        nonlocal count
        count += 1
        return to_public_relative_path(match.group(0))

    return WINDOWS_ABSOLUTE_PATH.sub(replace, text), count


def sanitize_json_value(value: Any) -> tuple[Any, int]:
    if isinstance(value, str):
        sanitized, count = sanitize_text(value)
        return sanitized, count
    if isinstance(value, list):
        total = 0
        out = []
        for item in value:
            new_item, count = sanitize_json_value(item)
            total += count
            out.append(new_item)
        return out, total
    if isinstance(value, dict):
        total = 0
        out = {}
        for key, item in value.items():
            new_item, count = sanitize_json_value(item)
            total += count
            out[key] = new_item
        return out, total
    return value, 0


def should_scan(path: Path) -> bool:
    if any(part in SKIP_DIRS for part in path.parts):
        return False
    return path.suffix.lower() in PUBLIC_TEXT_EXTENSIONS


def sanitize_file(path: Path) -> int:
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".json":
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            sanitized, count = sanitize_text(text)
        else:
            data, count = sanitize_json_value(data)
            if count:
                sanitized = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
            else:
                sanitized = text
    else:
        sanitized, count = sanitize_text(text)

    if count:
        path.write_text(sanitized, encoding="utf-8")
    return count


def main() -> None:
    changed_files = []
    replacement_count = 0

    for path in sorted(REPO_ROOT.rglob("*")):
        if not path.is_file() or not should_scan(path.relative_to(REPO_ROOT)):
            continue
        count = sanitize_file(path)
        if count:
            changed_files.append(path.relative_to(REPO_ROOT).as_posix())
            replacement_count += count

    print(
        json.dumps(
            {
                "changed_files": changed_files,
                "replacement_count": replacement_count,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
