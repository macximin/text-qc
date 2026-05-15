from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from .models import MIN_CHAPTER_CHARS_NO_SPACE, RunManifest, TextInspection, WorkManifest
from .narrative import classify_bracketed_lines


WORK_SUBDIRS = ("inputs", "extracted", "runs", "reports", "corrections", "exports", "archive")
RUN_SUBDIRS = (
    "evidence",
    "evidence/episodes",
    "evidence/facts",
    "evidence/review",
    "evidence/submission",
    "llm-facing",
    "human-facing",
    "draft_reports",
    "final_reports",
    "corrections",
    "final_manuscript",
    "exports",
)
TEXT_ENCODINGS = ("utf-8-sig", "utf-8", "cp949", "euc-kr", "utf-16", "utf-16-le", "utf-16-be")
CHAPTER_MARKER_RE = re.compile(r"(?m)^ⓚ(?:제\s*)?(\d{1,4})(?:\s*(?:화|회|장|편|챕터))?\s*$")
HASH_NUMBER_CHAPTER_RE = re.compile(r"(?m)^#(?P<num>\d{1,4})(?:\s+(?P<title>[^\n]+))?\s*$")
MARKDOWN_HEADER_RE = re.compile(r"(?m)^#{1,6}\s+(.+?)\s*$")
EPISODE_PREFIX_CHAPTER_RE = re.compile(
    r"(?im)^\s*(?:chapter|ep(?:isode)?)\s*(?P<num>\d{1,4})[\s.:：_\-]*(?P<title>[^\n]*)$"
)
NUMBERED_CHAPTER_RE = re.compile(
    r"(?im)^\s*(?:제\s*)?(?P<num>\d{1,4})\s*(?:화|회|장|편|챕터|chapter|ep(?:isode)?)"
    r"[\s.:：_\-]*(?P<title>[^\n]*)$"
)


def safe_slug(value: str) -> str:
    text = str(value or "").strip().lower()
    text = re.sub(r"\s+", "-", text)
    text = re.sub(r"[^0-9a-zA-Z가-힣_.-]+", "-", text)
    text = re.sub(r"-{2,}", "-", text).strip("-_.")
    return text or "work"


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def decode_text_bytes(data: bytes) -> str:
    for encoding in TEXT_ENCODINGS:
        try:
            text = data.decode(encoding)
        except UnicodeDecodeError:
            continue
        if "\ufffd" not in text:
            return text
    return data.decode("utf-8", errors="replace")


def read_text_auto(path: Path) -> str:
    return decode_text_bytes(path.read_bytes())


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = "\n".join(json.dumps(row, ensure_ascii=False) for row in rows)
    path.write_text(payload + ("\n" if payload else ""), encoding="utf-8")


def discover_works(*, workspace_root: Path) -> list[dict[str, Any]]:
    if not workspace_root.exists():
        return []

    works: list[dict[str, Any]] = []
    for manifest_path in sorted(workspace_root.glob("*/manifest.json")):
        try:
            manifest = read_json(manifest_path)
        except (OSError, json.JSONDecodeError):
            continue
        work_root = manifest_path.parent
        runs = discover_runs(workspace_root=workspace_root, work_slug=manifest.get("slug") or work_root.name)
        works.append(
            {
                "slug": manifest.get("slug") or work_root.name,
                "title": manifest.get("title", ""),
                "genre": manifest.get("genre", ""),
                "audience": manifest.get("audience", ""),
                "platform": manifest.get("platform", ""),
                "status": manifest.get("status", ""),
                "run_count": len(runs),
                "latest_run": runs[-1]["run_id"] if runs else "",
                "path": str(work_root),
            }
        )
    return works


def discover_runs(*, workspace_root: Path, work_slug: str) -> list[dict[str, Any]]:
    work_root = workspace_root / safe_slug(work_slug)
    runs_root = work_root / "runs"
    if not runs_root.exists():
        return []

    runs: list[dict[str, Any]] = []
    for manifest_path in sorted(runs_root.glob("*/run_manifest.json")):
        try:
            manifest = read_json(manifest_path)
        except (OSError, json.JSONDecodeError):
            continue
        stages = manifest.get("stages", {})
        pending = []
        if isinstance(stages, dict):
            pending = [name for name, status in stages.items() if str(status).lower() != "done"]
        runs.append(
            {
                "run_id": manifest.get("run_id") or manifest_path.parent.name,
                "kind": manifest.get("kind", ""),
                "status": manifest.get("status", ""),
                "created_at": manifest.get("created_at", ""),
                "pending_stage_count": len(pending),
                "next_stage": pending[0] if pending else "",
                "path": str(manifest_path.parent),
            }
        )
    return runs


def build_portfolio_status(*, workspace_root: Path) -> dict[str, Any]:
    works = discover_works(workspace_root=workspace_root)
    active_works = [work for work in works if str(work.get("status", "")).lower() != "archived"]
    works_without_runs = [work["slug"] for work in active_works if not work.get("run_count")]
    works_with_pending_runs: list[dict[str, Any]] = []

    for work in active_works:
        runs = discover_runs(workspace_root=workspace_root, work_slug=work["slug"])
        if not runs:
            continue
        latest = runs[-1]
        if latest.get("pending_stage_count", 0):
            works_with_pending_runs.append(
                {
                    "slug": work["slug"],
                    "title": work.get("title", ""),
                    "latest_run": latest.get("run_id", ""),
                    "next_stage": latest.get("next_stage", ""),
                }
            )

    return {
        "workspace": str(workspace_root),
        "work_count": len(works),
        "active_work_count": len(active_works),
        "works_without_runs": works_without_runs,
        "works_with_pending_runs": works_with_pending_runs,
        "works": works,
    }


def create_work(
    *,
    workspace_root: Path,
    slug: str,
    title: str,
    author: str = "",
    genre: str = "",
    audience: str = "",
    platform: str = "",
    source_path: str = "",
    notes: list[str] | None = None,
) -> Path:
    work_slug = safe_slug(slug or title)
    work_root = workspace_root / work_slug
    work_root.mkdir(parents=True, exist_ok=True)
    for subdir in WORK_SUBDIRS:
        (work_root / subdir).mkdir(exist_ok=True)

    manifest = WorkManifest(
        slug=work_slug,
        title=title,
        author=author,
        genre=genre,
        audience=audience,
        platform=platform,
        source_path=source_path,
        notes=list(notes or []),
    )
    write_json(work_root / "manifest.json", manifest.to_dict())
    return work_root


def create_run(
    *,
    workspace_root: Path,
    work_slug: str,
    kind: str,
    source_text_path: str = "",
    notes: list[str] | None = None,
) -> Path:
    work_root = workspace_root / safe_slug(work_slug)
    manifest_path = work_root / "manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError(f"work manifest not found: {manifest_path}")

    run_id = unique_run_id(work_root, safe_slug(kind))
    run_root = work_root / "runs" / run_id
    run_root.mkdir(parents=True, exist_ok=False)
    for subdir in RUN_SUBDIRS:
        (run_root / subdir).mkdir(exist_ok=True)

    run_manifest = RunManifest(
        run_id=run_id,
        work_slug=safe_slug(work_slug),
        kind=safe_slug(kind),
        source_text_path=source_text_path,
        notes=list(notes or []),
        stages={
            "01_intake": "pending",
            "02_global_audit": "pending",
            "03_adversarial_audit": "pending",
            "04_episode_deep_dive": "pending",
            "05_editorial_pass": "pending",
            "06_consistency_correction_loop": "pending",
            "07_human_facing_report": "pending",
            "08_final_manuscript": "pending",
            "09_export": "pending",
        },
    )
    write_json(run_root / "run_manifest.json", run_manifest.to_dict())
    return run_root


def find_chapter_markers(text: str) -> list[dict[str, Any]]:
    markers: list[dict[str, Any]] = []
    markers.extend(
        [
            {
                "episode": match.group(1).zfill(3),
                "title": "",
                "start": match.start(),
                "end": match.end(),
            }
            for match in CHAPTER_MARKER_RE.finditer(text)
        ]
    )
    markers.extend(
        [
            {
                "episode": match.group("num").zfill(3),
                "title": (match.group("title") or "").strip(),
                "start": match.start(),
                "end": match.end(),
            }
            for match in HASH_NUMBER_CHAPTER_RE.finditer(text)
        ]
    )
    markers.extend(
        [
            {
                "episode": match.group("num").zfill(3),
                "title": (match.group("title") or "").strip(),
                "start": match.start(),
                "end": match.end(),
            }
            for match in EPISODE_PREFIX_CHAPTER_RE.finditer(text)
        ]
    )
    markers.extend(
        [
            {
                "episode": match.group("num").zfill(3),
                "title": match.group("title").strip(),
                "start": match.start(),
                "end": match.end(),
            }
            for match in NUMBERED_CHAPTER_RE.finditer(text)
        ]
    )
    if markers:
        return dedupe_chapter_markers(markers)

    markdown_matches = list(MARKDOWN_HEADER_RE.finditer(text))
    if markdown_matches:
        return [
            {
                "episode": f"{idx + 1:03d}",
                "title": match.group(1).strip(),
                "start": match.start(),
                "end": match.end(),
            }
            for idx, match in enumerate(markdown_matches)
        ]

    return []


def dedupe_chapter_markers(markers: list[dict[str, Any]]) -> list[dict[str, Any]]:
    deduped: list[dict[str, Any]] = []
    seen_starts: set[int] = set()
    for marker in sorted(markers, key=lambda item: int(item["start"])):
        start = int(marker["start"])
        if start in seen_starts:
            continue
        seen_starts.add(start)
        deduped.append(marker)
    return deduped


def unique_run_id(work_root: Path, kind_slug: str) -> str:
    base = datetime.now().strftime("%Y%m%d_%H%M%S") + "__" + kind_slug
    runs_root = work_root / "runs"
    candidate = base
    idx = 2
    while (runs_root / candidate).exists():
        candidate = f"{base}-{idx:02d}"
        idx += 1
    return candidate


def inspect_text(path: Path) -> TextInspection:
    text = read_text_auto(path)
    lines = text.splitlines()
    nonempty = [line for line in lines if line.strip()]
    lengths = [len(line) for line in nonempty]
    chapter_markers = find_chapter_markers(text)
    bracketed_rows = classify_bracketed_lines(text)
    blocking_stage_cues = [row for row in bracketed_rows if row.get("blocks_submission")]
    allowed_stage_cues = [row for row in bracketed_rows if not row.get("blocks_submission")]
    chapter_chars: dict[str, int] = {}
    if chapter_markers:
        seen_episodes: dict[str, int] = {}
        for idx, marker in enumerate(chapter_markers):
            start = int(marker["end"])
            end = int(chapter_markers[idx + 1]["start"]) if idx + 1 < len(chapter_markers) else len(text)
            body = text[start:end]
            episode = str(marker["episode"])
            seen_episodes[episode] = seen_episodes.get(episode, 0) + 1
            key = episode if seen_episodes[episode] == 1 else f"{episode}_{seen_episodes[episode]}"
            chapter_chars[key] = len(re.sub(r"\s+", "", body))
    under_min_chapter_chars = {
        episode: chars
        for episode, chars in chapter_chars.items()
        if chars < MIN_CHAPTER_CHARS_NO_SPACE
    }

    avg_len = round(sum(lengths) / len(lengths), 1) if lengths else 0.0
    return TextInspection(
        input_path=str(path),
        char_count=len(text),
        chars_no_space=len(re.sub(r"\s+", "", text)),
        line_count=len(lines),
        nonempty_line_count=len(nonempty),
        avg_nonempty_line_len=avg_len,
        long_lines_80=sum(1 for line in nonempty if len(line) >= 80),
        long_lines_120=sum(1 for line in nonempty if len(line) >= 120),
        long_lines_200=sum(1 for line in nonempty if len(line) >= 200),
        bang_count=text.count("!"),
        question_count=text.count("?"),
        markdown_headers=len(re.findall(r"(?m)^#{1,6}\s+", text)),
        stage_cues=len(blocking_stage_cues),
        stage_cue_candidates=len(bracketed_rows),
        stage_cues_allowed_by_narrative_context=len(allowed_stage_cues),
        chapter_count=len(chapter_markers),
        minimum_chapter_chars_no_space=MIN_CHAPTER_CHARS_NO_SPACE,
        chapter_chars_no_space=chapter_chars,
        under_min_chapter_chars_no_space=under_min_chapter_chars,
    )
