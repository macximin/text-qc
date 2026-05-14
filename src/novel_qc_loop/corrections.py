from __future__ import annotations

import difflib
import json
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .workspace import write_json


ALLOWED_MARKERS = {"ⓐ", "ⓐⓐ", ""}
ALLOWED_OPERATIONS = {"replace", "delete", "insert_before", "insert_after"}


@dataclass(slots=True)
class CorrectionValidationResult:
    path: str
    total: int
    valid: int
    invalid: int
    marker_counts: dict[str, int]
    operation_counts: dict[str, int]
    issues: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class ChangeApplicationResult:
    source_path: str
    changes_path: str
    output_path: str
    diff_path: str
    total: int
    applied: int
    skipped: int
    issues: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def validate_changes_file(path: Path) -> CorrectionValidationResult:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("changes file must be a JSON array")

    issues: list[dict[str, Any]] = []
    marker_counts: Counter[str] = Counter()
    operation_counts: Counter[str] = Counter()
    valid_count = 0

    for index, item in enumerate(payload, start=1):
        if not isinstance(item, dict):
            issues.append({"index": index, "field": "$", "message": "item must be object"})
            continue
        marker = str(item.get("marker", ""))
        marker_counts[marker or "(none)"] += 1
        operation_counts[infer_operation(item)] += 1
        item_issues = validate_change_item(index, item)
        if item_issues:
            issues.extend(item_issues)
        else:
            valid_count += 1

    return CorrectionValidationResult(
        path=str(path),
        total=len(payload),
        valid=valid_count,
        invalid=len(payload) - valid_count,
        marker_counts=dict(marker_counts),
        operation_counts=dict(operation_counts),
        issues=issues,
    )


def infer_operation(item: dict[str, Any]) -> str:
    operation = str(item.get("operation", "")).strip()
    if operation:
        return operation
    replace = item.get("replace")
    return "delete" if replace == "" else "replace"


def validate_change_item(index: int, item: dict[str, Any]) -> list[dict[str, Any]]:
    issues = []
    find = item.get("find")
    replace = item.get("replace")
    marker = str(item.get("marker", ""))
    operation = infer_operation(item)
    if not isinstance(find, str) or not find:
        issues.append(
            {
                "index": index,
                "field": "find",
                "message": "required non-empty string; for insertion this is the anchor text",
            }
        )
    if replace is None or not isinstance(replace, str):
        issues.append({"index": index, "field": "replace", "message": "required string, empty allowed for deletion"})
    if marker not in ALLOWED_MARKERS:
        issues.append({"index": index, "field": "marker", "message": "allowed: ⓐ, ⓐⓐ, or empty"})
    if operation not in ALLOWED_OPERATIONS:
        issues.append(
            {
                "index": index,
                "field": "operation",
                "message": "allowed: replace, delete, insert_before, insert_after",
            }
        )
    if operation == "delete" and isinstance(replace, str) and replace:
        issues.append({"index": index, "field": "replace", "message": "delete operation requires empty replace"})
    if operation in {"insert_before", "insert_after"} and isinstance(replace, str) and not replace:
        issues.append({"index": index, "field": "replace", "message": "insert operation requires non-empty replace"})
    if operation == "replace" and isinstance(find, str) and isinstance(replace, str) and find == replace:
        issues.append({"index": index, "field": "replace", "message": "replace is identical to find"})
    occurrence = item.get("occurrence")
    if occurrence is not None:
        try:
            occurrence_value = int(occurrence)
        except (TypeError, ValueError):
            issues.append({"index": index, "field": "occurrence", "message": "required positive integer if provided"})
        else:
            if occurrence_value < 1:
                issues.append({"index": index, "field": "occurrence", "message": "required positive integer if provided"})
    return issues


def write_validation_result(result: CorrectionValidationResult, output_path: Path) -> None:
    write_json(output_path, result.to_dict())


def apply_changes_to_text_file(
    *,
    source_path: Path,
    changes_path: Path,
    output_path: Path,
    diff_path: Path,
    accept_aa: bool = False,
) -> ChangeApplicationResult:
    changes = json.loads(changes_path.read_text(encoding="utf-8"))
    if not isinstance(changes, list):
        raise ValueError("changes file must be a JSON array")

    source_text = source_path.read_text(encoding="utf-8")
    edited_text = source_text
    issues: list[dict[str, Any]] = []
    applied_changes: list[dict[str, Any]] = []

    for index, change in enumerate(changes, start=1):
        if not isinstance(change, dict):
            issues.append({"index": index, "field": "$", "message": "item must be object"})
            continue
        item_issues = validate_change_item(index, change)
        if item_issues:
            issues.extend(item_issues)
            continue
        if not should_apply_change(change, accept_aa=accept_aa):
            issues.append(
                {
                    "index": index,
                    "id": change.get("id", ""),
                    "message": "skipped pending author/editor approval",
                }
            )
            continue

        updated_text, issue = apply_change_to_text(edited_text, change, index=index)
        if issue:
            issues.append(issue)
            continue
        edited_text = updated_text
        applied_changes.append(change)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(edited_text, encoding="utf-8")
    write_editorial_diff(
        source_text=source_text,
        edited_text=edited_text,
        source_label=str(source_path),
        output_label=str(output_path),
        applied_changes=applied_changes,
        issues=issues,
        diff_path=diff_path,
    )

    return ChangeApplicationResult(
        source_path=str(source_path),
        changes_path=str(changes_path),
        output_path=str(output_path),
        diff_path=str(diff_path),
        total=len(changes),
        applied=len(applied_changes),
        skipped=len(changes) - len(applied_changes),
        issues=issues,
    )


def should_apply_change(change: dict[str, Any], *, accept_aa: bool) -> bool:
    status = str(change.get("status", "")).strip().lower()
    if status in {"rejected", "reject", "withdrawn", "철회", "반려"}:
        return False
    if str(change.get("marker", "")) != "ⓐⓐ":
        return True
    if accept_aa:
        return True
    return status in {"approved", "accepted", "done", "승인", "확정", "완료"}


def apply_change_to_text(text: str, change: dict[str, Any], *, index: int) -> tuple[str, dict[str, Any] | None]:
    find = str(change["find"])
    replace = str(change["replace"])
    operation = infer_operation(change)
    positions = find_occurrences(text, find)
    if not positions:
        return text, {"index": index, "id": change.get("id", ""), "field": "find", "message": "anchor not found"}

    requested_occurrence = change.get("occurrence")
    if requested_occurrence is None and len(positions) > 1:
        return (
            text,
            {
                "index": index,
                "id": change.get("id", ""),
                "field": "find",
                "message": "anchor is ambiguous; add occurrence or more surrounding context",
                "matches": len(positions),
            },
        )

    occurrence = int(requested_occurrence or 1)
    if occurrence < 1 or occurrence > len(positions):
        return (
            text,
            {
                "index": index,
                "id": change.get("id", ""),
                "field": "occurrence",
                "message": "occurrence is outside anchor match count",
                "matches": len(positions),
            },
        )

    start = positions[occurrence - 1]
    end = start + len(find)
    if operation == "replace":
        return text[:start] + replace + text[end:], None
    if operation == "delete":
        return text[:start] + text[end:], None
    if operation == "insert_before":
        return text[:start] + replace + text[start:], None
    if operation == "insert_after":
        return text[:end] + replace + text[end:], None
    return text, {"index": index, "id": change.get("id", ""), "field": "operation", "message": "unsupported operation"}


def find_occurrences(text: str, needle: str) -> list[int]:
    positions: list[int] = []
    start = 0
    while True:
        index = text.find(needle, start)
        if index < 0:
            return positions
        positions.append(index)
        start = index + max(len(needle), 1)


def write_editorial_diff(
    *,
    source_text: str,
    edited_text: str,
    source_label: str,
    output_label: str,
    applied_changes: list[dict[str, Any]],
    issues: list[dict[str, Any]],
    diff_path: Path,
) -> None:
    diff = difflib.unified_diff(
        source_text.splitlines(keepends=True),
        edited_text.splitlines(keepends=True),
        fromfile=source_label,
        tofile=output_label,
        lineterm="",
    )
    lines = [
        "# Editorial Text Diff",
        "",
        f"- Applied changes: {len(applied_changes)}",
        f"- Skipped or blocked changes: {len(issues)}",
        "",
        "## Applied",
        "",
    ]
    if applied_changes:
        for change in applied_changes:
            lines.append(
                f"- `{change.get('id', '')}` `{infer_operation(change)}` "
                f"`{change.get('marker', '') or '(none)'}`: {change.get('reason', '')}"
            )
    else:
        lines.append("- None")
    lines.extend(["", "## Issues", ""])
    if issues:
        for issue in issues:
            label = issue.get("id") or f"index {issue.get('index', '?')}"
            lines.append(f"- `{label}` {issue.get('message', '')}")
    else:
        lines.append("- None")
    lines.extend(["", "## Unified Diff", "", "```diff"])
    lines.extend(line.rstrip("\n") for line in diff)
    lines.append("```")
    diff_path.parent.mkdir(parents=True, exist_ok=True)
    diff_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
