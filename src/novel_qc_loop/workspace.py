from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from .models import RunManifest, TextInspection, WorkManifest


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
            "04_correction_plan": "pending",
            "05_human_facing_report": "pending",
            "06_final_manuscript": "pending",
            "07_export": "pending",
        },
    )
    write_json(run_root / "run_manifest.json", run_manifest.to_dict())
    return run_root


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
    text = path.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()
    nonempty = [line for line in lines if line.strip()]
    lengths = [len(line) for line in nonempty]
    chapter_matches = list(re.finditer(r"(?m)^ⓚ(\d{3})\s*$", text))
    header_matches = list(re.finditer(r"(?m)^#\s+(.+?)\s*$", text))
    chapter_chars: dict[str, int] = {}
    if chapter_matches:
        for idx, match in enumerate(chapter_matches):
            start = match.end()
            end = chapter_matches[idx + 1].start() if idx + 1 < len(chapter_matches) else len(text)
            body = text[start:end]
            chapter_chars[match.group(1)] = len(re.sub(r"\s+", "", body))
    elif header_matches:
        for idx, match in enumerate(header_matches):
            start = match.end()
            end = header_matches[idx + 1].start() if idx + 1 < len(header_matches) else len(text)
            body = text[start:end]
            chapter_chars[f"{idx + 1:03d}"] = len(re.sub(r"\s+", "", body))

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
        stage_cues=len(re.findall(r"(?m)^\[[^\]\n]{1,160}\]\s*$", text)),
        chapter_count=len(chapter_matches) or len(header_matches),
        chapter_chars_no_space=chapter_chars,
    )
