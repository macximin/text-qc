from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


MIN_CHAPTER_CHARS = 4000
MIN_CHAPTER_CHARS_NO_SPACE = MIN_CHAPTER_CHARS


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
    minimum_chapter_chars: int
    chapter_chars: dict[str, int]
    under_min_chapter_chars: dict[str, int]
    minimum_chapter_chars_no_space: int
    chapter_chars_no_space: dict[str, int]
    under_min_chapter_chars_no_space: dict[str, int]
    straight_double_quote_count: int = 0
    straight_single_quote_count: int = 0
    ascii_ellipsis_count: int = 0
    chapter_heading_without_k_count: int = 0
    chapter_heading_spacing_violation_count: int = 0
    dialogue_narration_spacing_violation_count: int = 0
    manuscript_format_violation_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def path_as_str(path: str | Path) -> str:
    return str(Path(path))
