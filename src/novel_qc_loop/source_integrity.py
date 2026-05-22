from __future__ import annotations

import difflib
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .analyze import build_chapter_metrics, split_chapters, write_episode_files
from .intake import collect_input_document_paths, read_source_text
from .workspace import (
    find_chapter_markers,
    normalize_chapter_heading_markers,
    read_json,
    read_text_auto,
    write_json,
    write_jsonl,
)


EMBEDDED_TAIL_EPISODE_RE = re.compile(r"^(?P<body>.+?)(?P<num>\d{1,4})\s*화\s*$")
AMBIGUOUS_TAIL_EPISODE_RE = re.compile(
    r"/[^\n]{0,40}\d{1,4}\s*화[^\n]{0,40}(?:끝|\))"
)
FILENAME_RANGE_RE = re.compile(r"(?P<start>\d{1,4})\s*(?:~|-|_)\s*(?P<end>\d{1,4})\s*화")
FILENAME_SINGLE_RE = re.compile(r"(?P<start>\d{1,4})\s*화")


@dataclass(slots=True)
class SourceIntegrityResult:
    output_dir: str
    repaired_source_path: str
    accepted_source_path: str
    repaired_episodes_dir: str
    change_log_path: str
    sequence_path: str
    metrics_path: str
    diff_path: str
    input_document_count: int
    before_chapter_count: int
    after_chapter_count: int
    split_count: int
    accepted_direct_count: int
    blocked_count: int
    missing_episodes: list[int]
    duplicate_episodes: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def plan_source_integrity_repair(
    *,
    run_root: Path,
    input_path: Path | None = None,
    output_dir: Path | None = None,
    version: str = "v1",
    accept_direct: bool = False,
    confidence_threshold: int = 95,
) -> SourceIntegrityResult:
    run_root = run_root.resolve()
    output_dir = output_dir.resolve() if output_dir else run_root / "source_integrity" / version
    output_dir.mkdir(parents=True, exist_ok=True)

    manifest = read_json(run_root / "run_manifest.json")
    original_source = resolve_original_source(run_root=run_root, manifest=manifest, input_path=input_path)
    document_paths = collect_repair_document_paths(original_source)
    ordered_paths = sorted(document_paths, key=document_order_key)

    original_text_path = Path(str(manifest.get("source_text_path") or "")).expanduser()
    if not original_text_path.is_absolute():
        original_text_path = run_root / original_text_path
    before_text = read_text_auto(original_text_path) if original_text_path.exists() else ""
    before_sequence = build_sequence_rows(before_text)

    changes: list[dict[str, Any]] = []
    repaired_parts: list[str] = []
    direct_status = "accepted_direct" if accept_direct else "applied_candidate"
    for order, document_path in enumerate(ordered_paths, start=1):
        raw_text = read_source_text(document_path)
        normalized = normalize_chapter_heading_markers(raw_text).strip()
        markers = find_chapter_markers(normalized)
        changes.append(
            {
                "record_type": "source_repair_change",
                "id": f"SRC-ORDER-{order:03d}",
                "operation": "order_document",
                "status": direct_status,
                "confidence_percent": 99,
                "document": document_path.name,
                "document_order": order,
                "first_episode": markers[0]["episode"] if markers else "",
                "last_episode": markers[-1]["episode"] if markers else "",
                "reason": "sort document collection by inferred episode range before analysis",
            }
        )
        split_text, split_changes = split_embedded_tail_episode_labels(
            normalized,
            document_name=document_path.name,
            next_id_start=len(changes) + 1,
            accepted_direct=accept_direct,
        )
        changes.extend(split_changes)
        repaired_parts.append(split_text.strip())

    repaired_text = "\n\n".join(part for part in repaired_parts if part)
    blocked_changes = detect_blocked_source_issues(repaired_text, next_id_start=len(changes) + 1)
    changes.extend(blocked_changes)

    repaired_source_path = output_dir / f"source_repaired_{version}.txt"
    repaired_source_path.write_text(repaired_text + "\n", encoding="utf-8")
    accepted_source_path = output_dir / f"source_accepted_{version}.txt"
    if accept_direct:
        accepted_source_path.write_text(repaired_text + "\n", encoding="utf-8")

    chapters = split_chapters(repaired_text)
    repaired_episodes_dir = output_dir / f"episodes_repaired_{version}"
    repaired_episodes_dir.mkdir(parents=True, exist_ok=True)
    write_episode_files(repaired_episodes_dir, chapters)

    sequence_rows = build_sequence_rows(repaired_text)
    metrics_rows = build_chapter_metrics(chapters)
    missing = missing_episode_numbers(sequence_rows)
    duplicates = duplicate_episode_numbers(sequence_rows)

    sequence_path = output_dir / f"chapter_sequence_{version}.jsonl"
    metrics_path = output_dir / f"chapter_metrics_{version}.jsonl"
    change_log_path = output_dir / f"source_repair_changes_{version}.jsonl"
    diff_path = output_dir / f"source_repair_diff_{version}.md"
    manifest_path = output_dir / f"source_repair_manifest_{version}.json"

    write_jsonl(sequence_path, sequence_rows)
    write_jsonl(metrics_path, metrics_rows)
    write_jsonl(change_log_path, changes)
    diff_path.write_text(
        render_sequence_diff(
            before_sequence=before_sequence,
            after_sequence=sequence_rows,
            changes=changes,
            missing=missing,
            duplicates=duplicates,
        ),
        encoding="utf-8",
    )
    write_json(
        manifest_path,
        {
            "schema_version": "source_repair_manifest.v1",
            "version": version,
            "run_root": str(run_root),
            "input": str(original_source),
            "ordered_documents": [str(path) for path in ordered_paths],
            "repaired_source_path": str(repaired_source_path),
            "accepted_source_path": str(accepted_source_path) if accept_direct else "",
            "change_log_path": str(change_log_path),
            "sequence_path": str(sequence_path),
            "metrics_path": str(metrics_path),
            "diff_path": str(diff_path),
            "policy": {
                "original_run_source_is_preserved": True,
                "candidate_is_not_final_manuscript": True,
                "accepted_direct_confidence_threshold": confidence_threshold,
                "auto_applies": [
                    "document collection reorder by inferred episode range",
                    "split only monotonic embedded tail episode labels such as sentence.54화",
                ],
                "blocked": [
                    "ambiguous tail labels",
                    "missing source ranges",
                    "duplicate episode variants",
                ],
            },
        },
    )
    if accept_direct:
        apply_accepted_source_to_run(
            run_root=run_root,
            manifest=manifest,
            accepted_source_path=accepted_source_path,
            accepted_text=repaired_text,
            version=version,
        )
    manifest.setdefault("artifacts", {}).update(
        {
            f"source_integrity_{version}_dir": str(output_dir),
            f"source_repaired_{version}_path": str(repaired_source_path),
            f"source_accepted_{version}_path": str(accepted_source_path) if accept_direct else "",
            f"source_repair_changes_{version}_path": str(change_log_path),
            f"source_repair_sequence_{version}_path": str(sequence_path),
            f"source_repair_metrics_{version}_path": str(metrics_path),
            f"source_repair_diff_{version}_path": str(diff_path),
            f"source_repair_manifest_{version}_path": str(manifest_path),
        }
    )
    if accept_direct:
        manifest["source_text_path"] = str(accepted_source_path)
        manifest.setdefault("stages", {})["02_global_audit"] = "source-integrity-accepted-direct"
        notes = manifest.setdefault("notes", [])
        if isinstance(notes, list):
            note = f"source_integrity {version}: accepted direct repairs >= {confidence_threshold}% confidence"
            if note not in notes:
                notes.append(note)
    else:
        manifest.setdefault("stages", {})["02_global_audit"] = "source-integrity-candidate"
    write_json(run_root / "run_manifest.json", manifest)

    return SourceIntegrityResult(
        output_dir=str(output_dir),
        repaired_source_path=str(repaired_source_path),
        accepted_source_path=str(accepted_source_path) if accept_direct else "",
        repaired_episodes_dir=str(repaired_episodes_dir),
        change_log_path=str(change_log_path),
        sequence_path=str(sequence_path),
        metrics_path=str(metrics_path),
        diff_path=str(diff_path),
        input_document_count=len(ordered_paths),
        before_chapter_count=len(before_sequence),
        after_chapter_count=len(sequence_rows),
        split_count=sum(1 for row in changes if row.get("operation") == "split_embedded_tail_label"),
        accepted_direct_count=sum(1 for row in changes if row.get("status") == "accepted_direct"),
        blocked_count=sum(1 for row in changes if row.get("status") == "blocked"),
        missing_episodes=missing,
        duplicate_episodes=duplicates,
    )


def resolve_original_source(*, run_root: Path, manifest: dict[str, Any], input_path: Path | None) -> Path:
    if input_path:
        return input_path.resolve()
    artifact_path = manifest.get("artifacts", {}).get("original_path")
    if artifact_path and Path(str(artifact_path)).name == "document_collection_manifest.json":
        collection_manifest = read_json(Path(str(artifact_path)))
        copied_folder = collection_manifest.get("copied_folder")
        if copied_folder:
            return Path(str(copied_folder)).resolve()
    source_text_path = manifest.get("source_text_path")
    if source_text_path:
        return Path(str(source_text_path)).resolve()
    raise FileNotFoundError(f"cannot resolve source input for run: {run_root}")


def collect_repair_document_paths(input_path: Path) -> list[Path]:
    if input_path.is_dir():
        return collect_input_document_paths(input_path)
    return [input_path]


def document_order_key(path: Path) -> tuple[int, int, str]:
    name = path.name
    match = FILENAME_RANGE_RE.search(name)
    if match:
        return (int(match.group("start")), int(match.group("end")), name)
    match = FILENAME_SINGLE_RE.search(name)
    if match:
        start = int(match.group("start"))
        return (start, start, name)
    return (10_000, 10_000, name)


def split_embedded_tail_episode_labels(
    text: str,
    *,
    document_name: str,
    next_id_start: int,
    accepted_direct: bool = False,
) -> tuple[str, list[dict[str, Any]]]:
    output_lines: list[str] = []
    changes: list[dict[str, Any]] = []
    current_episode: int | None = None

    status = "accepted_direct" if accepted_direct else "applied_candidate"
    for line_number, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        heading_markers = find_chapter_markers(line)
        if heading_markers and heading_markers[0].get("start") == 0:
            try:
                current_episode = int(str(heading_markers[0]["episode"]))
            except ValueError:
                current_episode = None
            output_lines.append(line)
            continue

        match = EMBEDDED_TAIL_EPISODE_RE.match(line)
        if match and current_episode is not None:
            next_episode = int(match.group("num"))
            body = match.group("body").rstrip()
            if next_episode == current_episode + 1 and body:
                output_lines.append(body)
                output_lines.append(f"ⓚ제{next_episode}화")
                changes.append(
                    {
                        "record_type": "source_repair_change",
                        "id": f"SRC-SPLIT-{next_id_start + len(changes):03d}",
                        "operation": "split_embedded_tail_label",
                        "status": status,
                        "confidence_percent": 99,
                        "document": document_name,
                        "line": line_number,
                        "from_episode": f"{current_episode:03d}",
                        "to_episode": f"{next_episode:03d}",
                        "reason": "monotonic next-episode label was attached to the previous episode's last sentence",
                    }
                )
                current_episode = next_episode
                continue

        output_lines.append(line)

    return "\n".join(output_lines), changes


def apply_accepted_source_to_run(
    *,
    run_root: Path,
    manifest: dict[str, Any],
    accepted_source_path: Path,
    accepted_text: str,
    version: str,
) -> None:
    artifacts = manifest.setdefault("artifacts", {})
    final_value = artifacts.get("final_manuscript_path")
    if not final_value:
        return
    final_path = Path(str(final_value))
    if not final_path.is_absolute():
        final_path = (run_root / final_path).resolve()
    if final_path.exists():
        backup_path = final_path.with_name(f"{final_path.stem}.pre_source_integrity_{version}{final_path.suffix}")
        if not backup_path.exists():
            backup_path.write_text(final_path.read_text(encoding="utf-8"), encoding="utf-8")
            artifacts[f"final_manuscript_pre_source_integrity_{version}_path"] = str(backup_path)
    final_path.write_text(accepted_text + "\n", encoding="utf-8")
    artifacts["final_manuscript_path"] = str(final_path)
    artifacts[f"active_source_after_source_integrity_{version}_path"] = str(accepted_source_path)


def detect_blocked_source_issues(text: str, *, next_id_start: int) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    sequence = build_sequence_rows(text)
    for index, episode in enumerate(missing_episode_numbers(sequence), start=next_id_start):
        rows.append(
            {
                "record_type": "source_repair_change",
                "id": f"SRC-BLOCK-{index:03d}",
                "operation": "missing_episode",
                "status": "blocked",
                "episode": f"{episode:03d}",
                "reason": "episode marker is absent after safe reorder/split candidate; recover from source before content edits",
            }
        )

    offset = next_id_start + len(rows)
    for index, episode in enumerate(duplicate_episode_numbers(sequence), start=offset):
        rows.append(
            {
                "record_type": "source_repair_change",
                "id": f"SRC-BLOCK-{index:03d}",
                "operation": "duplicate_episode",
                "status": "blocked",
                "episode": episode,
                "reason": "duplicate episode variant exists; do not auto-renumber until source variant is chosen",
            }
        )

    offset = next_id_start + len(rows)
    for index, line in enumerate(text.splitlines(), start=1):
        if AMBIGUOUS_TAIL_EPISODE_RE.search(line) and not EMBEDDED_TAIL_EPISODE_RE.match(line):
            rows.append(
                {
                    "record_type": "source_repair_change",
                    "id": f"SRC-BLOCK-{offset + len(rows):03d}",
                    "operation": "ambiguous_tail_label",
                    "status": "blocked",
                    "line": index,
                    "reason": "tail episode label is not a monotonic standalone split marker; requires source check",
                }
            )
    return rows


def build_sequence_rows(text: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen: dict[str, int] = {}
    for order, marker in enumerate(find_chapter_markers(text), start=1):
        base = str(marker["episode"])
        seen[base] = seen.get(base, 0) + 1
        episode = base if seen[base] == 1 else f"{base}_{seen[base]}"
        rows.append(
            {
                "order": order,
                "episode": episode,
                "base_episode": base,
                "title": marker.get("title", ""),
                "start": marker.get("start"),
                "end": marker.get("end"),
            }
        )
    return rows


def missing_episode_numbers(sequence: list[dict[str, Any]]) -> list[int]:
    nums = sorted({int(row["base_episode"]) for row in sequence if str(row.get("base_episode", "")).isdigit()})
    if not nums:
        return []
    present = set(nums)
    return [num for num in range(min(nums), max(nums) + 1) if num not in present]


def duplicate_episode_numbers(sequence: list[dict[str, Any]]) -> list[str]:
    counts: dict[str, int] = {}
    for row in sequence:
        base = str(row.get("base_episode", ""))
        counts[base] = counts.get(base, 0) + 1
    return sorted([episode for episode, count in counts.items() if count > 1])


def render_sequence_diff(
    *,
    before_sequence: list[dict[str, Any]],
    after_sequence: list[dict[str, Any]],
    changes: list[dict[str, Any]],
    missing: list[int],
    duplicates: list[str],
) -> str:
    before_lines = [sequence_line(row) for row in before_sequence]
    after_lines = [sequence_line(row) for row in after_sequence]
    diff = "\n".join(
        difflib.unified_diff(
            before_lines,
            after_lines,
            fromfile="before_sequence",
            tofile="after_sequence",
            lineterm="",
        )
    )
    applied = [row for row in changes if row.get("status") == "applied_candidate"]
    accepted = [row for row in changes if row.get("status") == "accepted_direct"]
    blocked = [row for row in changes if row.get("status") == "blocked"]
    summary = {
        "before_chapter_count": len(before_sequence),
        "after_chapter_count": len(after_sequence),
        "applied_candidate_count": len(applied),
        "accepted_direct_count": len(accepted),
        "blocked_count": len(blocked),
        "missing_episodes": [f"{num:03d}" for num in missing],
        "duplicate_episodes": duplicates,
    }
    return (
        "# Source Integrity Repair Diff\n\n"
        "This diff tracks chapter sequence changes only. The original manuscript text is preserved.\n\n"
        "```json\n"
        + json.dumps(summary, ensure_ascii=False, indent=2)
        + "\n```\n\n"
        "```diff\n"
        + diff
        + "\n```\n"
    )


def sequence_line(row: dict[str, Any]) -> str:
    episode = str(row.get("episode", ""))
    title = str(row.get("title", ""))
    return f"{int(row.get('order', 0)):03d} {episode} {title}".rstrip()
