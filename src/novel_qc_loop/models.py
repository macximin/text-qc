from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


MIN_CHAPTER_CHARS_NO_SPACE = 4000


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


@dataclass(slots=True)
class WorkManifest:
    schema_version: str = "work_manifest.v1"
    slug: str = ""
    title: str = ""
    author: str = ""
    genre: str = ""
    audience: str = ""
    platform: str = ""
    source_path: str = ""
    status: str = "active"
    created_at: str = field(default_factory=utc_now_iso)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class RunManifest:
    schema_version: str = "run_manifest.v1"
    run_id: str = ""
    work_slug: str = ""
    kind: str = "global-audit"
    gate_profile: str = "delivery"
    status: str = "created"
    created_at: str = field(default_factory=utc_now_iso)
    source_text_path: str = ""
    stages: dict[str, str] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class TextInspection:
    input_path: str
    char_count: int
    chars_no_space: int
    line_count: int
    nonempty_line_count: int
    avg_nonempty_line_len: float
    long_lines_80: int
    long_lines_120: int
    long_lines_200: int
    bang_count: int
    question_count: int
    markdown_headers: int
    stage_cues: int
    stage_cue_candidates: int
    stage_cues_allowed_by_narrative_context: int
    chapter_count: int
    minimum_chapter_chars_no_space: int
    chapter_chars_no_space: dict[str, int]
    under_min_chapter_chars_no_space: dict[str, int]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def path_as_str(path: str | Path) -> str:
    return str(Path(path))
