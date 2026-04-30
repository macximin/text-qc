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
        status = item.get("status")
        notes = str(item.get("notes") or "").strip()
        if status == "checked":
            reviewed_axis_count += 1
            if not notes:
                issues.append({"field": f"checked_axes[{index}].notes", "message": "checked axis requires notes"})
        if status == "skipped" and not notes:
            issues.append({"field": f"checked_axes[{index}].notes", "message": "skipped axis requires reason"})
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
            notes = pass_payload.get("notes", [])
            task_ids = pass_payload.get("completed_task_ids", [])
            if not isinstance(notes, list) or not any(str(note).strip() for note in notes):
                issues.append({"field": f"passes.{pass_name}.notes", "message": "completed pass requires notes"})
            if not isinstance(task_ids, list) or not task_ids:
                issues.append({"field": f"passes.{pass_name}.completed_task_ids", "message": "completed pass requires task ids"})

    findings = payload.get("findings", [])
    if not isinstance(findings, list):
        findings = []
        issues.append({"field": "findings", "message": "must be an array"})

    is_complete = payload.get("status") == "complete"
    for index, finding in enumerate(findings, start=1):
        if not isinstance(finding, dict):
            issues.append({"field": f"findings[{index}]", "message": "must be an object"})
            continue
        for required in ("priority", "status", "category", "claim", "rationale"):
            if not finding.get(required):
                issues.append({"field": f"findings[{index}].{required}", "message": "required"})
        if is_complete:
            issues.extend(validate_finding_confidence_contract(finding, index))

    ready = (
        payload.get("status") == "complete"
        and reviewed_axis_count >= len(REVIEW_AXES)
        and completed_pass_count >= len(PASS_NAMES)
        and bool(str(payload.get("final_summary") or "").strip())
        and not issues
    )
    if payload.get("status") == "complete" and not str(payload.get("final_summary") or "").strip():
        issues.append({"field": "final_summary", "message": "complete submission requires final summary"})
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


def validate_finding_confidence_contract(finding: dict[str, Any], index: int) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    decision = normalize_decision(finding.get("decision") or finding.get("status"))
    confidence = finding.get("confidence_percent")
    has_evidence = bool(str(finding.get("evidence") or "").strip()) or bool(
        str(finding.get("evidence_snippet") or "").strip()
    )
    has_counter = bool(str(finding.get("counter_evidence") or "").strip())

    if confidence is not None:
        if not isinstance(confidence, int) or not 0 <= confidence <= 100:
            issues.append(
                {
                    "field": f"findings[{index}].confidence_percent",
                    "message": "must be an integer from 0 to 100",
                }
            )

    has_reaudit_fields = any(
        field in finding
        for field in (
            "decision",
            "confidence_percent",
            "evidence_snippet",
            "counter_evidence",
            "original_priority",
            "final_priority",
        )
    )
    if not has_reaudit_fields:
        return issues

    if decision == "confirmed":
        if confidence is None:
            issues.append(
                {
                    "field": f"findings[{index}].confidence_percent",
                    "message": "confirmed finding requires confidence_percent",
                }
            )
        elif isinstance(confidence, int) and confidence < 95:
            issues.append(
                {
                    "field": f"findings[{index}].confidence_percent",
                    "message": "confirmed finding must be >= 95 for 95% confidence reports",
                }
            )
        if not has_evidence:
            issues.append(
                {
                    "field": f"findings[{index}].evidence",
                    "message": "confirmed finding requires evidence or evidence_snippet",
                }
            )
    elif decision == "downgraded":
        for field in ("original_priority", "final_priority"):
            if not finding.get(field):
                issues.append({"field": f"findings[{index}].{field}", "message": "downgrade requires priority trace"})
        if not has_counter:
            issues.append(
                {
                    "field": f"findings[{index}].counter_evidence",
                    "message": "downgrade requires counter_evidence or weakening reason",
                }
            )
    elif decision == "retracted":
        if not has_counter:
            issues.append(
                {
                    "field": f"findings[{index}].counter_evidence",
                    "message": "retraction requires counter_evidence",
                }
            )
    return issues


def normalize_decision(value: Any) -> str:
    text = str(value or "").strip().lower()
    aliases = {
        "확정": "confirmed",
        "confirmed": "confirmed",
        "강등": "downgraded",
        "downgraded": "downgraded",
        "철회": "retracted",
        "기각": "retracted",
        "retracted": "retracted",
        "rejected": "retracted",
        "유보": "deferred",
        "deferred": "deferred",
    }
    return aliases.get(text, text)


def write_submission_validation_result(result: SubmissionValidationResult, output_path: Path) -> None:
    write_json(output_path, result.to_dict())
