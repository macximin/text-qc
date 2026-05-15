from __future__ import annotations

import re
from typing import Any

from .workspace import find_chapter_markers


SUBTITLE_MAX_CHARS = 36
TERMINAL_SENTENCE_RE = re.compile(r"(?:다|요|죠|했다|였다|였다|한다|었다|았다)[.!?…]*$")


def extract_chapter_subtitle_rows(text: str) -> list[dict[str, Any]]:
    markers = find_chapter_markers(text)
    rows: list[dict[str, Any]] = []
    seen_episodes: dict[str, int] = {}
    for index, marker in enumerate(markers):
        marker_end = int(marker["end"])
        next_start = int(markers[index + 1]["start"]) if index + 1 < len(markers) else len(text)
        episode = str(marker["episode"])
        seen_episodes[episode] = seen_episodes.get(episode, 0) + 1
        episode_key = episode if seen_episodes[episode] == 1 else f"{episode}_{seen_episodes[episode]}"
        title = str(marker.get("title") or "").strip()
        row = {
            "episode": episode_key,
            "base_episode": episode,
            "marker_start": int(marker["start"]),
            "marker_end": marker_end,
            "has_subtitle": False,
            "subtitle": "",
            "subtitle_source": "",
            "subtitle_start": None,
            "subtitle_end": None,
            "review_hint": "",
        }
        if title and is_subtitle_candidate(title):
            row.update(
                {
                    "has_subtitle": True,
                    "subtitle": title,
                    "subtitle_source": "chapter_marker_title",
                    "subtitle_start": int(marker["start"]),
                    "subtitle_end": marker_end,
                }
            )
        else:
            candidate = first_body_subtitle_candidate(text, marker_end, next_start)
            if candidate:
                row.update(candidate)
        rows.append(row)
    return rows


def first_body_subtitle_candidate(text: str, start: int, end: int) -> dict[str, Any] | None:
    position = start
    for line in text[start:end].splitlines(keepends=True):
        raw = line.rstrip("\r\n")
        stripped = raw.strip()
        line_start = position + line.find(raw) if raw else position
        line_end = line_start + len(raw)
        position += len(line)
        if not stripped:
            continue
        if is_subtitle_candidate(stripped):
            return {
                "has_subtitle": True,
                "subtitle": stripped,
                "subtitle_source": "first_body_line",
                "subtitle_start": line_start + raw.find(stripped),
                "subtitle_end": line_start + raw.find(stripped) + len(stripped),
            }
        return None
    return None


def is_subtitle_candidate(line: str) -> bool:
    text = re.sub(r"\s+", " ", line).strip()
    if not text or len(text) > SUBTITLE_MAX_CHARS:
        return False
    if text in {"***", "* * *", "---"}:
        return False
    if text.startswith(("\"", "'", "“", "‘", "「", "『", "[", "(", "ⓐ", "ⓚ")):
        return False
    if text.endswith((".", "?", "!", "…", "다.", "요.", "죠.")):
        return False
    if TERMINAL_SENTENCE_RE.search(text):
        return False
    if re.search(r"[:：]\s*$", text):
        return False
    if re.search(r"[.?!]", text):
        return False
    return bool(re.search(r"[가-힣A-Za-z0-9]", text))


def build_subtitle_consistency_flags(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not rows:
        return []
    present = [row for row in rows if row.get("has_subtitle")]
    missing = [row for row in rows if not row.get("has_subtitle")]
    if not present or not missing or len(present) == len(missing):
        return []

    examples = [str(row.get("subtitle") or "") for row in present if row.get("subtitle")][:5]
    total = len(rows)
    flags: list[dict[str, Any]] = []
    if len(present) < len(missing):
        for row in present:
            flags.append(
                {
                    "kind": "subtitle_style_imbalance",
                    "episode": row.get("episode", ""),
                    "action": "consider_deleting_existing_subtitle",
                    "subtitle": row.get("subtitle", ""),
                    "subtitle_start": row.get("subtitle_start"),
                    "subtitle_end": row.get("subtitle_end"),
                    "present_count": len(present),
                    "missing_count": len(missing),
                    "total_chapters": total,
                    "examples": examples,
                    "severity": "P3",
                    "review_hint": (
                        "소제목이 있는 회차가 소수입니다. 소제목은 무단 수정하지 말고, "
                        "전체 형식 통일을 위해 삭제 후보 의견으로만 표시합니다."
                    ),
                }
            )
        return flags

    for row in missing:
        flags.append(
            {
                "kind": "subtitle_style_imbalance",
                "episode": row.get("episode", ""),
                "action": "consider_adding_missing_subtitle",
                "marker_end": row.get("marker_end"),
                "present_count": len(present),
                "missing_count": len(missing),
                "total_chapters": total,
                "examples": examples,
                "severity": "P3",
                "review_hint": (
                    "소제목이 없는 회차가 소수입니다. 소제목은 무단 작성하지 말고, "
                    "기존 소제목 톤과 길이에 맞춘 추가 후보 의견으로만 표시합니다."
                ),
            }
        )
    return flags
