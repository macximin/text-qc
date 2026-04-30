from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .protocol import PASS_NAMES, REVIEW_AXES
from .workspace import write_json, write_jsonl


@dataclass(slots=True)
class SubmissionValidationResult:
    path: str
    status: str
    ready_for_submission: bool
    reviewed_axis_count: int
    required_axis_count: int
    completed_pass_count: int
    required_pass_count: int
    finding_count: int
    issue_count: int
    issues: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_manual_review_queue() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for pass_name in PASS_NAMES:
        for axis in REVIEW_AXES:
            rows.append(
                {
                    "task_id": f"{pass_name}-{axis['axis']}",
                    "pass": pass_name,
                    "axis": axis["axis"],
                    "label": axis["label"],
                    "status": "pending",
                    "required_evidence": "episode/line/evidence/rationale/fix_hint",
                }
            )
    return rows


def build_empty_manual_review_submission() -> dict[str, Any]:
    return {
        "schema_version": "manual_review_submission.v1",
        "status": "pending",
        "reviewer": "",
        "reviewed_at": "",
        "checked_axes": [
            {"axis": item["axis"], "label": item["label"], "status": "pending", "notes": ""}
            for item in REVIEW_AXES
        ],
        "passes": {
            pass_name: {"status": "pending", "notes": [], "completed_task_ids": []}
            for pass_name in PASS_NAMES
        },
        "findings": [],
        "remaining_risks": [],
        "final_summary": "",
    }


def write_manual_review_scaffold(submission_dir: Path) -> dict[str, Path]:
    submission_dir.mkdir(parents=True, exist_ok=True)
    queue_path = submission_dir / "manual_review_queue.jsonl"
    submission_path = submission_dir / "manual_review_submission.json"
    write_jsonl(queue_path, build_manual_review_queue())
    if not submission_path.exists():
        write_json(submission_path, build_empty_manual_review_submission())
    return {"queue_path": queue_path, "submission_path": submission_path}


def validate_manual_review_submission(path: Path) -> SubmissionValidationResult:
    payload = json.loads(path.read_text(encoding="utf-8"))
    issues: list[dict[str, Any]] = []

    checked_axes = payload.get("checked_axes")
    if not isinstance(checked_axes, list):
        checked_axes = []
        issues.append({"field": "checked_axes", "message": "must be an array"})

    reviewed_axis_count = 0
    seen_axes: set[str] = set()
    required_axes = {item["axis"] for item in REVIEW_AXES}
    for index, item in enumerate(checked_axes, start=1):
        if not isinstance(item, dict):
            issues.append({"field": f"checked_axes[{index}]", "message": "must be an object"})
            continue
        axis = str(item.get("axis", ""))
        seen_axes.add(axis)
        if item.get("status") == "checked":
            reviewed_axis_count += 1
        if axis not in required_axes:
            issues.append({"field": f"checked_axes[{index}].axis", "message": f"unknown axis: {axis}"})

    for axis in sorted(required_axes - seen_axes):
        issues.append({"field": "checked_axes", "message": f"missing axis: {axis}"})

    passes = payload.get("passes")
    if not isinstance(passes, dict):
        passes = {}
        issues.append({"field": "passes", "message": "must be an object"})

    completed_pass_count = 0
    for pass_name in PASS_NAMES:
        pass_payload = passes.get(pass_name)
        if not isinstance(pass_payload, dict):
            issues.append({"field": f"passes.{pass_name}", "message": "missing pass object"})
            continue
        if pass_payload.get("status") == "completed":
            completed_pass_count += 1

    findings = payload.get("findings", [])
    if not isinstance(findings, list):
        findings = []
        issues.append({"field": "findings", "message": "must be an array"})

    for index, finding in enumerate(findings, start=1):
        if not isinstance(finding, dict):
            issues.append({"field": f"findings[{index}]", "message": "must be an object"})
            continue
        for required in ("priority", "status", "category", "claim", "rationale"):
            if not finding.get(required):
                issues.append({"field": f"findings[{index}].{required}", "message": "required"})

    ready = (
        payload.get("status") == "complete"
        and reviewed_axis_count >= len(REVIEW_AXES)
        and completed_pass_count >= len(PASS_NAMES)
        and not issues
    )
    return SubmissionValidationResult(
        path=str(path),
        status=str(payload.get("status") or "pending"),
        ready_for_submission=ready,
        reviewed_axis_count=reviewed_axis_count,
        required_axis_count=len(REVIEW_AXES),
        completed_pass_count=completed_pass_count,
        required_pass_count=len(PASS_NAMES),
        finding_count=len(findings),
        issue_count=len(issues),
        issues=issues,
    )


def write_submission_validation_result(result: SubmissionValidationResult, output_path: Path) -> None:
    write_json(output_path, result.to_dict())
