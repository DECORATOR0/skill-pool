from __future__ import annotations

from pathlib import Path

from .utils import read_text


def _resolve_prompt_path(path: Path) -> Path:
    if path.exists():
        return path
    parent = path.parent
    if parent.name != "prompts":
        fallback = parent.parent / "prompts" / path.name
        if fallback.exists():
            return fallback
    raise FileNotFoundError(f"Prompt file not found: {path}")


def load_prompt(path: Path) -> str:
    return read_text(_resolve_prompt_path(path))


def render_prompt(path: Path, **kwargs: object) -> str:
    template = load_prompt(path)
    return template.format(**kwargs)
