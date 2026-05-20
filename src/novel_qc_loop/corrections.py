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
CONTEXTUAL_EDIT_CLASSES = {
    "contextual_typo",
    "contextual_typo_fix",
    "contextual_word_error",
    "contextual_grammar",
}
CONTEXT_FIELDS = ("context_before", "context_after", "context_window", "evidence_snippet")
CONTEXT_COUNTER_FIELDS = (
    "alternative_interpretation",
    "counter_evidence",
    "rejected_interpretation",
    "rejection_basis",
)
CONTEXTUAL_SIGNAL_PATTERNS = (
    "11자",
    "11자의 틈새",
    "제품에",
    "피난 주",
    "숙식간",
    "정도록",
    "책임의무게",
    "말하지마요",
    "고았다",
    "튀어 나왔다",
)
AI_SLOP_EDIT_CLASSES = {
    "ai_slop_cleanup",
    "repetition_cleanup",
    "rhythm_cleanup",
    "abstract_intensifier_cleanup",
}
REVIEW_MEMO_ONLY_PHRASES = (
    "판단 필요",
    "정본 확정 필요",
    "확정 전 보류",
    "여부 판단",
    "판단 여부",
    "backpatch",
    "역방향 보정 필요",
    "독자 반감 위험",
)


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


@dataclass(slots=True)
class ChangeContextResult:
    source_path: str
    changes_path: str
    output_path: str
    total: int
    rendered: int
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
    if (
        marker == "ⓐⓐ"
        and operation in {"replace", "insert_before", "insert_after"}
        and isinstance(replace, str)
        and looks_like_review_memo_only(replace)
    ):
        issues.append(
            {
                "index": index,
                "field": "replace",
                "message": "ⓐⓐ replace must be an applyable candidate sentence; put judgment notes in reason",
            }
        )
    occurrence = item.get("occurrence")
    if occurrence is not None:
        try:
            occurrence_value = int(occurrence)
        except (TypeError, ValueError):
            issues.append({"index": index, "field": "occurrence", "message": "required positive integer if provided"})
        else:
            if occurrence_value < 1:
                issues.append({"index": index, "field": "occurrence", "message": "required positive integer if provided"})
    confidence = item.get("confidence_percent")
    if confidence is not None:
        try:
            confidence_value = int(confidence)
        except (TypeError, ValueError):
            issues.append({"index": index, "field": "confidence_percent", "message": "required integer 0-100 if provided"})
        else:
            if not 0 <= confidence_value <= 100:
                issues.append({"index": index, "field": "confidence_percent", "message": "required integer 0-100 if provided"})
            if is_contextual_change(item) and marker == "ⓐ" and confidence_value < 95:
                issues.append(
                    {
                        "index": index,
                        "field": "confidence_percent",
                        "message": "contextual typo may be ⓐ only at 95+ confidence; otherwise use ⓐⓐ",
                    }
                )
    if is_contextual_change(item):
        if not str(item.get("reason", "")).strip():
            issues.append({"index": index, "field": "reason", "message": "contextual typo requires reason"})
        if not str(item.get("reading_basis", "")).strip():
            issues.append(
                {
                    "index": index,
                    "field": "reading_basis",
                    "message": "contextual typo requires a reading basis from surrounding context",
                }
            )
        if not any(str(item.get(field, "")).strip() for field in CONTEXT_FIELDS):
            issues.append(
                {
                    "index": index,
                    "field": "context",
                    "message": "contextual typo requires context_before/context_after/context_window/evidence_snippet",
                }
            )
        if marker == "ⓐ" and confidence is None:
            issues.append(
                {
                    "index": index,
                    "field": "confidence_percent",
                    "message": "contextual typo marked ⓐ requires confidence_percent >= 95",
                }
            )
        if marker == "ⓐ" and not any(str(item.get(field, "")).strip() for field in CONTEXT_COUNTER_FIELDS):
            issues.append(
                {
                    "index": index,
                    "field": "alternative_interpretation",
                    "message": (
                        "contextual typo marked ⓐ requires alternative_interpretation/"
                        "counter_evidence/rejected_interpretation/rejection_basis"
                    ),
                }
            )
    if is_ai_slop_cleanup(item):
        signal = str(item.get("ai_slop_signal", "")).strip()
        reason = str(item.get("reason", "")).strip()
        if not signal and "AI-slop 신호" not in reason and "AI 티" not in reason:
            issues.append(
                {
                    "index": index,
                    "field": "ai_slop_signal",
                    "message": "ai_slop cleanup requires an explicit AI-slop signal for human-facing review",
                }
            )
    return issues


def is_contextual_change(item: dict[str, Any]) -> bool:
    edit_class = str(item.get("edit_class", "")).strip().lower()
    return (
        bool(item.get("requires_context"))
        or edit_class in CONTEXTUAL_EDIT_CLASSES
        or has_contextual_signal(item)
    )


def has_contextual_signal(item: dict[str, Any]) -> bool:
    haystack = "\n".join(
        str(item.get(field, ""))
        for field in ("find", "replace", "reason", "location", "context_before", "context_after", "context_window")
    )
    if any(pattern in haystack for pattern in CONTEXTUAL_SIGNAL_PATTERNS):
        return True
    if "..." in haystack:
        return True
    if '"' in str(item.get("find", "")) or "'" in str(item.get("find", "")):
        return True
    return False


def is_ai_slop_cleanup(item: dict[str, Any]) -> bool:
    edit_class = str(item.get("edit_class", "")).strip().lower()
    return edit_class in AI_SLOP_EDIT_CLASSES


def looks_like_review_memo_only(text: str) -> bool:
    normalized = " ".join(text.split())
    return any(phrase in normalized for phrase in REVIEW_MEMO_ONLY_PHRASES)


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
    applications: list[dict[str, Any]] = []

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

        application, issue = resolve_change_application(source_text, change, index=index)
        if issue:
            issues.append(issue)
            continue
        applications.append(application)

    application_issues = validate_application_spans(applications)
    issues.extend(application_issues)
    blocked_indices = {int(issue.get("index") or -1) for issue in application_issues}
    applyable = [
        item
        for item in applications
        if int(item["index"]) not in blocked_indices
    ]
    for application in sorted(applyable, key=application_sort_key, reverse=True):
        edited_text = apply_change_span_to_text(
            edited_text,
            application["change"],
            start=int(application["start"]),
            end=int(application["end"]),
        )
    applied_changes = [
        item["change"] for item in sorted(applyable, key=lambda item: int(item["index"]))
    ]

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


def apply_change_to_text(
    text: str,
    change: dict[str, Any],
    *,
    index: int,
) -> tuple[str, dict[str, Any] | None]:
    application, issue = resolve_change_application(text, change, index=index)
    if issue:
        return text, issue
    return apply_change_span_to_text(
        text,
        change,
        start=int(application["start"]),
        end=int(application["end"]),
    ), None


def resolve_change_application(
    text: str,
    change: dict[str, Any],
    *,
    index: int,
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    find = str(change["find"])
    positions = find_occurrences(text, find)
    if not positions:
        return {}, {
            "index": index,
            "id": change.get("id", ""),
            "field": "find",
            "message": "anchor not found",
        }

    requested_occurrence = change.get("occurrence")
    if requested_occurrence is None and len(positions) > 1:
        return {}, {
            "index": index,
            "id": change.get("id", ""),
            "field": "find",
            "message": "anchor is ambiguous; add occurrence or more surrounding context",
            "matches": len(positions),
        }

    occurrence = int(requested_occurrence or 1)
    if occurrence < 1 or occurrence > len(positions):
        return {}, {
            "index": index,
            "id": change.get("id", ""),
            "field": "occurrence",
            "message": "occurrence is outside anchor match count",
            "matches": len(positions),
        }

    start = positions[occurrence - 1]
    return {
        "index": index,
        "change": change,
        "start": start,
        "end": start + len(find),
        "operation": infer_operation(change),
    }, None


def validate_application_spans(applications: list[dict[str, Any]]) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    previous: dict[str, Any] | None = None
    non_insert_spans: list[dict[str, Any]] = []
    for application in sorted(
        applications,
        key=lambda item: (int(item["start"]), int(item["end"])),
    ):
        operation = str(application.get("operation") or "")
        if operation in {"insert_before", "insert_after"}:
            continue
        if previous is not None and int(application["start"]) < int(previous["end"]):
            change = application["change"]
            previous_change = previous["change"]
            issues.append(
                {
                    "index": application["index"],
                    "id": change.get("id", ""),
                    "field": "find",
                    "message": "change overlaps another selected change",
                    "overlaps_with": previous_change.get("id", ""),
                }
            )
            continue
        previous = application
        non_insert_spans.append(application)

    for application in applications:
        operation = str(application.get("operation") or "")
        if operation not in {"insert_before", "insert_after"}:
            continue
        point = application_position(application)
        for span in non_insert_spans:
            if int(span["start"]) < point < int(span["end"]):
                change = application["change"]
                span_change = span["change"]
                issues.append(
                    {
                        "index": application["index"],
                        "id": change.get("id", ""),
                        "field": "find",
                        "message": "insertion anchor is inside another selected change",
                        "overlaps_with": span_change.get("id", ""),
                    }
                )
                break
    return issues


def application_sort_key(application: dict[str, Any]) -> tuple[int, int, int]:
    return (
        application_position(application),
        application_apply_priority(application),
        int(application["index"]),
    )


def application_position(application: dict[str, Any]) -> int:
    operation = str(application.get("operation") or "")
    if operation == "insert_after":
        return int(application["end"])
    return int(application["start"])


def application_apply_priority(application: dict[str, Any]) -> int:
    operation = str(application.get("operation") or "")
    if operation == "insert_after":
        return 2
    if operation in {"replace", "delete"}:
        return 1
    return 0


def apply_change_span_to_text(text: str, change: dict[str, Any], *, start: int, end: int) -> str:
    replace = str(change["replace"])
    operation = infer_operation(change)
    if operation == "replace":
        return text[:start] + replace + text[end:]
    if operation == "delete":
        return text[:start] + text[end:]
    if operation == "insert_before":
        return text[:start] + replace + text[start:]
    if operation == "insert_after":
        return text[:end] + replace + text[end:]
    return text


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


def render_change_contexts(
    *,
    source_path: Path,
    changes_path: Path,
    output_path: Path,
    window_chars: int = 360,
    contextual_only: bool = False,
) -> ChangeContextResult:
    changes = json.loads(changes_path.read_text(encoding="utf-8"))
    if not isinstance(changes, list):
        raise ValueError("changes file must be a JSON array")

    source_text = source_path.read_text(encoding="utf-8")
    issues: list[dict[str, Any]] = []
    rendered = 0
    lines = [
        "# Change Contexts",
        "",
        f"- Source: `{source_path}`",
        f"- Changes: `{changes_path}`",
        f"- Window chars: {window_chars}",
        "",
    ]

    for index, change in enumerate(changes, start=1):
        if not isinstance(change, dict):
            issues.append({"index": index, "field": "$", "message": "item must be object"})
            continue
        if contextual_only and not is_contextual_change(change):
            continue
        find = str(change.get("find", ""))
        if not find:
            issues.append({"index": index, "id": change.get("id", ""), "field": "find", "message": "missing anchor"})
            continue
        positions = find_occurrences(source_text, find)
        if not positions:
            issues.append({"index": index, "id": change.get("id", ""), "field": "find", "message": "anchor not found"})
            continue

        requested_occurrence = change.get("occurrence")
        if requested_occurrence is not None:
            try:
                occurrence = int(requested_occurrence)
                if occurrence < 1:
                    raise IndexError
                selected_positions = [positions[occurrence - 1]]
            except (ValueError, IndexError):
                issues.append(
                    {
                        "index": index,
                        "id": change.get("id", ""),
                        "field": "occurrence",
                        "message": "occurrence is outside anchor match count",
                        "matches": len(positions),
                    }
                )
                continue
        else:
            selected_positions = positions[:3]

        lines.extend(
            [
                f"## {change.get('id') or f'change-{index:04d}'}",
                "",
                f"- operation: `{infer_operation(change)}`",
                f"- marker: `{change.get('marker', '') or '(none)'}`",
                f"- edit_class: `{change.get('edit_class', '') or '(none)'}`",
                f"- matches: {len(positions)}",
                f"- reason: {change.get('reason', '')}",
                f"- reading_basis: {change.get('reading_basis', '')}",
                "",
            ]
        )
        for match_index, position in enumerate(selected_positions, start=1):
            start = max(0, position - window_chars)
            end = min(len(source_text), position + len(find) + window_chars)
            before = source_text[start:position]
            target = source_text[position : position + len(find)]
            after = source_text[position + len(find) : end]
            lines.extend(
                [
                    f"### Match {match_index}",
                    "",
                    "```text",
                    before + "[[" + target + "]]" + after,
                    "```",
                    "",
                ]
            )
        rendered += 1

    lines.extend(["## Issues", ""])
    if issues:
        for issue in issues:
            label = issue.get("id") or f"index {issue.get('index', '?')}"
            lines.append(f"- `{label}` {issue.get('message', '')}")
    else:
        lines.append("- None")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return ChangeContextResult(
        source_path=str(source_path),
        changes_path=str(changes_path),
        output_path=str(output_path),
        total=len(changes),
        rendered=rendered,
        issues=issues,
    )
