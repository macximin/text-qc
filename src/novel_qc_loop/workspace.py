from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from .models import MIN_CHAPTER_CHARS, MIN_CHAPTER_CHARS_NO_SPACE, RunManifest, TextInspection, WorkManifest
from .narrative import classify_bracketed_lines
from .typography import ASCII_ELLIPSIS_RE, count_style_single_quotes, normalize_korean_typography


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
    "editorial_pass",
    "editorial_pass/qc",
    "final_manuscript",
    "final_delivery",
    "exports",
)
TEXT_ENCODINGS = ("utf-8-sig", "utf-8", "cp949", "euc-kr", "utf-16", "utf-16-le", "utf-16-be")
LINE_WS = r"[^\S\r\n]"
EOL_WS = r"[^\S\n]"
HEADING_SEP = r"(?:[^\S\r\n]|[.:：_\-])"
K_NUMBER_CHAPTER_RE = re.compile(
    rf"(?im)^{LINE_WS}*ⓚ{LINE_WS}*(?:제{LINE_WS}*)?(?P<num>\d{{1,4}})"
    rf"(?:{LINE_WS}*(?:화|회|장|편|챕터))?"
    rf"(?:{HEADING_SEP}+(?P<title>[^\n]*))?{EOL_WS}*$"
)
K_ENGLISH_CHAPTER_RE = re.compile(
    rf"(?im)^{LINE_WS}*ⓚ{LINE_WS}*(?:chapter|ep(?:isode)?){LINE_WS}*(?P<num>\d{{1,4}})"
    rf"{HEADING_SEP}*(?P<title>[^\n]*)$"
)
HASH_NUMBER_CHAPTER_RE = re.compile(
    rf"(?im)^{LINE_WS}*#{{1,6}}{LINE_WS}*(?:제{LINE_WS}*)?(?P<num>\d{{1,4}})"
    rf"(?:{LINE_WS}*(?:화|회|장|편|챕터))?"
    rf"(?:{HEADING_SEP}+(?P<title>[^\n]*))?{EOL_WS}*$"
)
HASH_ENGLISH_CHAPTER_RE = re.compile(
    rf"(?im)^{LINE_WS}*#{{1,6}}{LINE_WS}*(?:chapter|ep(?:isode)?){LINE_WS}*(?P<num>\d{{1,4}})"
    rf"{HEADING_SEP}*(?P<title>[^\n]*)$"
)
MARKDOWN_HEADER_RE = re.compile(r"(?m)^#{1,6}\s+(.+?)\s*$")
EPISODE_PREFIX_CHAPTER_RE = re.compile(
    rf"(?im)^{LINE_WS}*(?:chapter|ep(?:isode)?){LINE_WS}*(?P<num>\d{{1,4}})"
    rf"{HEADING_SEP}*(?P<title>[^\n]*)$"
)
NUMBERED_CHAPTER_RE = re.compile(
    rf"(?im)^{LINE_WS}*(?:제{LINE_WS}*)?(?P<num>\d{{1,4}}){LINE_WS}*"
    rf"(?:화|회|장|편|챕터|chapter|ep(?:isode)?)"
    rf"{HEADING_SEP}*(?P<title>[^\n]*)$"
)
HASH_PREFIX_RE = re.compile(rf"^{LINE_WS}*#{{1,6}}{LINE_WS}*")
K_PREFIX_RE = re.compile(rf"^{LINE_WS}*ⓚ{LINE_WS}*")
NUMBERED_CHAPTER_BODY_RE = re.compile(
    rf"(?im)^(?:제{LINE_WS}*)?\d{{1,4}}{LINE_WS}*(?:화|회|장|편|챕터)\b.*$"
)
ENGLISH_CHAPTER_BODY_RE = re.compile(rf"(?im)^(?:chapter|ep(?:isode)?){LINE_WS}*\d{{1,4}}\b.*$")
PLAIN_NUMBER_HEADING_BODY_RE = re.compile(
    rf"(?im)^\d{{1,4}}(?:[.)．]{LINE_WS}*$|{LINE_WS}*$|{HEADING_SEP}+.+$)"
)
SCENE_BREAK_LINES = {"***", "* * *"}


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
    return normalize_newlines(decode_text_bytes(path.read_bytes()))


def normalize_newlines(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


def normalize_manuscript_format(text: str) -> str:
    normalized = normalize_korean_typography(normalize_chapter_heading_markers(text))
    lines = normalized.splitlines()
    output: list[str] = []
    previous_kind: str | None = None
    index = 0
    while index < len(lines):
        line = lines[index]
        stripped = line.strip()
        if not stripped:
            index += 1
            continue
        if is_chapter_heading_line(line):
            append_with_blank_rule(output, line, 0)
            output.extend(["", "", ""])
            previous_kind = "chapter_heading"
            index += 1
            continue
        if is_scene_break_line(stripped):
            append_with_blank_rule(output, line, 1 if output else 0)
            output.append("")
            previous_kind = "scene_break"
            index += 1
            continue
        current_kind = "dialogue" if is_dialogue_line(stripped) else "narration"
        if previous_kind == "chapter_heading":
            expected_blank_lines = 3
        elif previous_kind == "scene_break":
            expected_blank_lines = 1
        else:
            expected_blank_lines = 0 if previous_kind == current_kind or previous_kind is None else 1
        append_with_blank_rule(output, line, expected_blank_lines)
        previous_kind = current_kind
        index += 1
    return "\n".join(output).rstrip() + ("\n" if text else "")


def append_with_blank_rule(output: list[str], line: str, blank_lines_before: int) -> None:
    while output and output[-1] == "":
        output.pop()
    if output:
        output.extend([""] * blank_lines_before)
    output.append(line)


def build_manuscript_format_flags(text: str) -> list[dict[str, Any]]:
    lines = text.splitlines()
    flags: list[dict[str, Any]] = []
    heading_line_numbers: set[int] = set()

    for index, line in enumerate(lines):
        line_no = index + 1
        stripped = line.strip()
        if not is_chapter_heading_line(line):
            continue
        heading_line_numbers.add(line_no)
        if not stripped.startswith("ⓚ"):
            flags.append(
                {
                    "kind": "manuscript_format",
                    "subtype": "chapter_heading_missing_k",
                    "line": line_no,
                    "value": stripped,
                    "expected": "소제목/회차 제목 앞 ⓚ",
                    "review_hint": "회차 제목 또는 소제목 맨 앞에 `ⓚ`를 붙입니다.",
                }
            )
        blank_count = count_blank_lines_after(lines, index)
        if blank_count != 3:
            flags.append(
                {
                    "kind": "manuscript_format",
                    "subtype": "chapter_heading_blank_lines",
                    "line": line_no,
                    "value": stripped,
                    "actual_blank_lines": blank_count,
                    "expected_blank_lines": 3,
                    "review_hint": "제목 아래에는 빈 줄 3줄을 유지합니다.",
                }
            )

    flags.extend(build_typography_format_flags(lines))
    flags.extend(build_dialogue_spacing_flags(lines, heading_line_numbers))
    return flags


def count_blank_lines_after(lines: list[str], index: int) -> int:
    count = 0
    for line in lines[index + 1 :]:
        if line.strip():
            break
        count += 1
    return count


def build_typography_format_flags(lines: list[str]) -> list[dict[str, Any]]:
    flags: list[dict[str, Any]] = []
    for index, line in enumerate(lines, start=1):
        if '"' in line:
            flags.append(
                {
                    "kind": "manuscript_format",
                    "subtype": "straight_double_quote",
                    "line": index,
                    "value": line.strip(),
                    "expected": "“”",
                    "review_hint": "직선 쌍따옴표 대신 곡선 따옴표 `“”`를 씁니다.",
                }
            )
        single_quote_count = count_style_single_quotes(line)
        if single_quote_count:
            flags.append(
                {
                    "kind": "manuscript_format",
                    "subtype": "straight_single_quote",
                    "line": index,
                    "value": line.strip(),
                    "count": single_quote_count,
                    "expected": "‘’",
                    "review_hint": "직선 홑따옴표 대신 곡선 따옴표 `‘’`를 씁니다.",
                }
            )
        if ASCII_ELLIPSIS_RE.search(line):
            flags.append(
                {
                    "kind": "manuscript_format",
                    "subtype": "ascii_ellipsis",
                    "line": index,
                    "value": line.strip(),
                    "expected": "…",
                    "review_hint": "ASCII `...` 대신 전각 말줄임표 `…`를 씁니다.",
                }
            )
    return flags


def build_dialogue_spacing_flags(lines: list[str], heading_line_numbers: set[int]) -> list[dict[str, Any]]:
    flags: list[dict[str, Any]] = []
    previous: dict[str, Any] | None = None
    blank_count = 0
    for index, line in enumerate(lines, start=1):
        stripped = line.strip()
        if not stripped:
            blank_count += 1
            continue
        if index in heading_line_numbers or is_scene_break_line(stripped):
            previous = None
            blank_count = 0
            continue
        current = {
            "line": index,
            "kind": "dialogue" if is_dialogue_line(stripped) else "narration",
            "value": stripped,
        }
        if previous is not None:
            expected = 0 if previous["kind"] == current["kind"] else 1
            if blank_count != expected:
                flags.append(
                    {
                        "kind": "manuscript_format",
                        "subtype": "dialogue_narration_spacing",
                        "line": index,
                        "previous_line": previous["line"],
                        "previous_kind": previous["kind"],
                        "current_kind": current["kind"],
                        "actual_blank_lines": blank_count,
                        "expected_blank_lines": expected,
                        "value": stripped,
                        "review_hint": (
                            "대사-대사는 붙이고 지문-지문은 붙이며, "
                            "대사와 지문 사이에는 빈 줄 1줄을 둡니다."
                        ),
                    }
                )
        previous = current
        blank_count = 0
    return flags


def is_dialogue_line(line: str) -> bool:
    return line.startswith("“")


def is_scene_break_line(line: str) -> bool:
    return line in SCENE_BREAK_LINES


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
    gate_profile: str = "delivery",
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
        gate_profile=gate_profile,
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
                "episode": match.group("num").zfill(3),
                "title": (match.group("title") or "").strip(),
                "start": match.start(),
                "end": match.end(),
            }
            for match in K_NUMBER_CHAPTER_RE.finditer(text)
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
            for match in K_ENGLISH_CHAPTER_RE.finditer(text)
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
            for match in HASH_ENGLISH_CHAPTER_RE.finditer(text)
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


def normalize_chapter_heading_markers(text: str) -> str:
    raw_lines = text.splitlines(keepends=True)
    plain_number_heading_count = sum(
        1
        for raw_line in raw_lines
        if is_plain_number_heading_line(split_line_ending(raw_line)[0])
    )
    allow_plain_number_headings = plain_number_heading_count >= 2
    has_numbered_heading = any(
        is_chapter_heading_line(split_line_ending(raw_line)[0])
        for raw_line in raw_lines
    ) or allow_plain_number_headings
    lines: list[str] = []
    markdown_heading_index = 0
    for raw_line in raw_lines:
        line, newline = split_line_ending(raw_line)
        if not has_numbered_heading and is_markdown_title_line(line):
            markdown_heading_index += 1
            normalized = normalize_markdown_title_heading_line(
                line,
                episode_index=markdown_heading_index,
            )
        else:
            normalized = normalize_chapter_heading_line(line, allow_plain_number=allow_plain_number_headings)
        lines.append(normalized + newline)
    if text and not lines:
        return normalize_chapter_heading_line(text)
    return "".join(lines)


def split_line_ending(raw_line: str) -> tuple[str, str]:
    if raw_line.endswith("\r\n"):
        return raw_line[:-2], "\r\n"
    if raw_line.endswith("\n"):
        return raw_line[:-1], "\n"
    if raw_line.endswith("\r"):
        return raw_line[:-1], "\r"
    return raw_line, ""


def normalize_chapter_heading_line(line: str, *, allow_plain_number: bool = False) -> str:
    indent_match = re.match(r"^(\s*)", line)
    indent = indent_match.group(1) if indent_match else ""
    stripped = line.strip()
    if not stripped:
        return line

    has_hash_marker = bool(HASH_PREFIX_RE.match(stripped))
    body = HASH_PREFIX_RE.sub("", stripped, count=1).strip() if has_hash_marker else stripped
    if K_PREFIX_RE.match(body):
        body = K_PREFIX_RE.sub("", body, count=1).strip()
        return f"{indent}ⓚ{canonicalize_chapter_heading_body(body)}" if body else line

    if is_chapter_heading_body(body, allow_plain_number=has_hash_marker or allow_plain_number):
        return f"{indent}ⓚ{canonicalize_chapter_heading_body(body)}"
    return line


def canonicalize_chapter_heading_body(body: str) -> str:
    text = re.sub(r"[^\S\r\n]+", " ", body.strip())
    match = re.match(
        r"^(?P<je>제\s*)?(?P<num>\d{1,4})\s*(?P<unit>화|회|장|편|챕터)(?P<rest>.*)$",
        text,
        flags=re.IGNORECASE,
    )
    if not match:
        return text
    prefix = "제" if match.group("je") else ""
    rest = normalize_heading_title_tail(match.group("rest") or "")
    heading = f"{prefix}{match.group('num')}{match.group('unit')}"
    return f"{heading} {rest}" if rest else heading


def normalize_heading_title_tail(value: str) -> str:
    text = value.strip()
    text = re.sub(r"^[.:：_\-]+\s*", "", text)
    return re.sub(r"\s+", " ", text).strip()


def is_markdown_title_line(line: str) -> bool:
    stripped = line.strip()
    if not HASH_PREFIX_RE.match(stripped):
        return False
    body = HASH_PREFIX_RE.sub("", stripped, count=1).strip()
    return bool(body)


def normalize_markdown_title_heading_line(line: str, *, episode_index: int) -> str:
    indent_match = re.match(r"^(\s*)", line)
    indent = indent_match.group(1) if indent_match else ""
    body = HASH_PREFIX_RE.sub("", line.strip(), count=1).strip()
    return f"{indent}ⓚ제{episode_index}화 {body}" if body else line


def is_chapter_heading_line(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return False
    has_hash_marker = bool(HASH_PREFIX_RE.match(stripped))
    body = HASH_PREFIX_RE.sub("", stripped, count=1).strip() if has_hash_marker else stripped
    if K_PREFIX_RE.match(body):
        body = K_PREFIX_RE.sub("", body, count=1).strip()
        return is_chapter_heading_body(body, allow_plain_number=True)
    return is_chapter_heading_body(body, allow_plain_number=has_hash_marker)


def is_plain_number_heading_line(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return False
    if HASH_PREFIX_RE.match(stripped) or K_PREFIX_RE.match(stripped):
        return False
    return bool(PLAIN_NUMBER_HEADING_BODY_RE.match(stripped))


def is_chapter_heading_body(body: str, *, allow_plain_number: bool = False) -> bool:
    text = body.strip()
    if not text:
        return False
    if NUMBERED_CHAPTER_BODY_RE.match(text):
        return True
    if ENGLISH_CHAPTER_BODY_RE.match(text):
        return True
    return allow_plain_number and bool(PLAIN_NUMBER_HEADING_BODY_RE.match(text))


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
    manuscript_format_flags = build_manuscript_format_flags(text)
    chapter_chars: dict[str, int] = {}
    chapter_chars_no_space: dict[str, int] = {}
    if chapter_markers:
        seen_episodes: dict[str, int] = {}
        for idx, marker in enumerate(chapter_markers):
            start = int(marker["end"])
            end = int(chapter_markers[idx + 1]["start"]) if idx + 1 < len(chapter_markers) else len(text)
            body = text[start:end]
            episode = str(marker["episode"])
            seen_episodes[episode] = seen_episodes.get(episode, 0) + 1
            key = episode if seen_episodes[episode] == 1 else f"{episode}_{seen_episodes[episode]}"
            chapter_chars[key] = len(body)
            chapter_chars_no_space[key] = len(re.sub(r"\s+", "", body))
    under_min_chapter_chars = {
        episode: chars
        for episode, chars in chapter_chars.items()
        if chars < MIN_CHAPTER_CHARS
    }
    under_min_chapter_chars_no_space = {
        episode: chars
        for episode, chars in chapter_chars_no_space.items()
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
        minimum_chapter_chars=MIN_CHAPTER_CHARS,
        chapter_chars=chapter_chars,
        under_min_chapter_chars=under_min_chapter_chars,
        minimum_chapter_chars_no_space=MIN_CHAPTER_CHARS_NO_SPACE,
        chapter_chars_no_space=chapter_chars_no_space,
        under_min_chapter_chars_no_space=under_min_chapter_chars_no_space,
        straight_double_quote_count=text.count('"'),
        straight_single_quote_count=count_style_single_quotes(text),
        ascii_ellipsis_count=len(ASCII_ELLIPSIS_RE.findall(text)),
        chapter_heading_without_k_count=sum(
            1 for row in manuscript_format_flags if row.get("subtype") == "chapter_heading_missing_k"
        ),
        chapter_heading_spacing_violation_count=sum(
            1 for row in manuscript_format_flags if row.get("subtype") == "chapter_heading_blank_lines"
        ),
        dialogue_narration_spacing_violation_count=sum(
            1 for row in manuscript_format_flags if row.get("subtype") == "dialogue_narration_spacing"
        ),
        manuscript_format_violation_count=len(manuscript_format_flags),
    )
