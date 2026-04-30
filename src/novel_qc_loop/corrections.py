from __future__ import annotations

import json
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .workspace import write_json


ALLOWED_MARKERS = {"ⓐ", "ⓐⓐ", ""}


@dataclass(slots=True)
class CorrectionValidationResult:
    path: str
    total: int
    valid: int
    invalid: int
    marker_counts: dict[str, int]
    issues: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def validate_changes_file(path: Path) -> CorrectionValidationResult:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("changes file must be a JSON array")

    issues: list[dict[str, Any]] = []
    marker_counts: Counter[str] = Counter()
    valid_count = 0

    for index, item in enumerate(payload, start=1):
        if not isinstance(item, dict):
            issues.append({"index": index, "field": "$", "message": "item must be object"})
            continue
        marker = str(item.get("marker", ""))
        marker_counts[marker or "(none)"] += 1
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
        issues=issues,
    )


def validate_change_item(index: int, item: dict[str, Any]) -> list[dict[str, Any]]:
    issues = []
    find = item.get("find")
    replace = item.get("replace")
    marker = str(item.get("marker", ""))
    if not isinstance(find, str) or not find:
        issues.append({"index": index, "field": "find", "message": "required non-empty string"})
    if replace is None or not isinstance(replace, str):
        issues.append({"index": index, "field": "replace", "message": "required string, empty allowed for deletion"})
    if marker not in ALLOWED_MARKERS:
        issues.append({"index": index, "field": "marker", "message": "allowed: ⓐ, ⓐⓐ, or empty"})
    if isinstance(find, str) and isinstance(replace, str) and find == replace:
        issues.append({"index": index, "field": "replace", "message": "replace is identical to find"})
    return issues


def write_validation_result(result: CorrectionValidationResult, output_path: Path) -> None:
    write_json(output_path, result.to_dict())
