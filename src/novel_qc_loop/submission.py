from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .protocol import (
    AUTHORITY_LAYERS,
    BLIND_REVIEWERS,
    CONSISTENCY_CHECK_UNIT_ID,
    CONSISTENCY_CHECK_UNIT_SUMMARY,
    CONSISTENCY_REPETITION_RULE,
    DEFAULT_CONSISTENCY_UNIT_COUNT,
    DISPOSITION_VALUES,
    AUTHOR_INTENT_PROTECTION_RULE,
    AI_GENERATED_TEXT_CONTINUITY_RULE,
    CANONICAL_NAME_ALIAS_RULE,
    EXCLUDED_REVIEW_SCOPES,
    HARD_CARRYOVER_KINDS,
    GATE_PROFILE_DEFINITIONS,
    GATE_PROFILE_DELIVERY,
    GATE_PROFILE_ORDER,
    GLOBAL_CONTEXT_SCAN_RULE,
    NTH_REPORT_CUMULATIVE_RULE,
    NTH_REPORT_VISIBLE_PRIORITIES,
    PASS_NAMES,
    PREMISE_POLICY_SUMMARY,
    REPAIRABILITY_VALUES,
    REVIEW_AXES,
    SOURCE_RISK_CHECKLIST,
    TOTAL_CONSISTENCY_REPORT_NAME,
    gate_profile_definition,
    normalize_gate_profile,
)
from .workspace import write_json, write_jsonl


@dataclass(slots=True)
class SubmissionValidationResult:
    path: str
    status: str
    gate_profile: str
    workflow_requirements: dict[str, bool]
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


def profile_requires(profile: str, key: str) -> bool:
    return bool(gate_profile_definition(profile).get(key))


def required_axis_ids(profile: str) -> set[str]:
    definition = gate_profile_definition(profile)
    return {str(axis) for axis in definition.get("required_axes", [])}


def build_manual_review_queue(gate_profile: str = GATE_PROFILE_DELIVERY) -> list[dict[str, Any]]:
    profile = normalize_gate_profile(gate_profile)
    rows: list[dict[str, Any]] = []
    required_axes = required_axis_ids(profile)
    require_primary = profile_requires(profile, "require_primary_passes")
    require_blind = profile_requires(profile, "require_blind_reviews")
    require_total = profile_requires(profile, "require_total_report")
    require_adversarial = profile_requires(profile, "require_adversarial_passes")
    for item in SOURCE_RISK_CHECKLIST:
        rows.append(
            {
                "task_id": f"source-preflight-{item['risk_id']}",
                "phase": "source_preflight",
                "lane": "source",
                "pass": "preflight",
                "axis": item["risk_id"],
                "label": item["label"],
                "status": "pending",
                "gate_profile": profile,
                "required_for_gate": True,
                "artifact_path": "evidence/submission/manual_review_submission.json",
                "required_evidence": item["rule"],
            }
        )
    if not require_primary:
        for axis in REVIEW_AXES:
            if axis["axis"] not in required_axes:
                continue
            rows.append(
                {
                    "task_id": f"profile-axis-{axis['axis']}",
                    "phase": "profile_axis_review",
                    "lane": "profile",
                    "pass": "single",
                    "axis": axis["axis"],
                    "label": axis["label"],
                    "status": "pending",
                    "gate_profile": profile,
                    "required_for_gate": True,
                    "artifact_path": "evidence/submission/manual_review_submission.json",
                    "required_evidence": "checked_axes[].status=checked and checked_axes[].notes for this profile axis",
                }
            )
    for pass_name in PASS_NAMES:
        for axis in REVIEW_AXES:
            required_for_gate = require_primary and axis["axis"] in required_axes
            rows.append(
                {
                    "task_id": f"{pass_name}-{axis['axis']}",
                    "phase": "primary_consistency_review",
                    "lane": "primary",
                    "pass": pass_name,
                    "axis": axis["axis"],
                    "label": axis["label"],
                    "status": "pending" if required_for_gate else "skipped",
                    "gate_profile": profile,
                    "required_for_gate": required_for_gate,
                    "artifact_path": f"llm-facing/consistency_rounds/primary_{pass_name}.md",
                    "required_evidence": (
                        "episode/line/evidence/rationale/counter_evidence/"
                        "story_state_before/story_state_after/story_internal_impact/"
                        "decision/confidence_percent/final_priority/fix_hint"
                    ),
                }
            )
    for reviewer in BLIND_REVIEWERS:
        for pass_name in PASS_NAMES:
            rows.append(
                {
                    "task_id": f"{reviewer}-{pass_name}-blind-consistency",
                    "phase": "blind_consistency_review",
                    "lane": reviewer,
                    "pass": pass_name,
                    "axis": "all_axes",
                    "label": "블라인드 전 회차 정합성/맥락 장부 + 충돌 후보",
                    "status": "pending" if require_blind else "skipped",
                    "gate_profile": profile,
                    "required_for_gate": require_blind,
                    "artifact_path": f"llm-facing/blind_reviews/{reviewer}_{pass_name}.md",
                    "required_evidence": (
                        "blind reviewer must not read other lanes; include context ledger, "
                        "conflict candidates, counter_evidence, repairability, disposition"
                    ),
                }
            )
    rows.append(
        {
            "task_id": "total-consistency-report",
            "phase": "synthesis",
            "lane": "total",
            "pass": "synthesis",
            "axis": "all_axes",
            "label": "블라인드 결과 통합 total 리포트",
            "status": "pending" if require_total else "skipped",
            "gate_profile": profile,
            "required_for_gate": require_total,
            "artifact_path": "llm-facing/total_consistency_report.md",
            "required_evidence": (
                "merge primary and blind lanes; separate confirmed, deferred, author decision, "
                "irreconcilable premise, webnovel allowance, non-reader-facing notes"
            ),
        }
    )
    for pass_name in PASS_NAMES:
        rows.append(
            {
                "task_id": f"adversarial-{pass_name}",
                "phase": "adversarial_audit",
                "lane": "adversarial",
                "pass": pass_name,
                "axis": "all_axes",
                "label": "통합 리포트 이후 적대적 감리",
                "status": "pending" if require_adversarial else "skipped",
                "gate_profile": profile,
                "required_for_gate": require_adversarial,
                "artifact_path": "llm-facing/adversarial_audit_3pass.md",
                "required_evidence": (
                    "attack total report; downgrade defended items; enforce hard carryover; "
                    "require counter_evidence search before P0/P1"
                ),
            }
        )
    return rows


def empty_pass_result() -> dict[str, Any]:
    return {"status": "pending", "notes": [], "completed_task_ids": []}


def build_pass_map() -> dict[str, dict[str, Any]]:
    return {pass_name: empty_pass_result() for pass_name in PASS_NAMES}


def build_review_protocol(gate_profile: str = GATE_PROFILE_DELIVERY) -> dict[str, Any]:
    profile = normalize_gate_profile(gate_profile)
    return {
        "authority_layers": list(AUTHORITY_LAYERS),
        "active_gate_profile": profile,
        "gate_profile": gate_profile_definition(profile),
        "gate_profile_order": list(GATE_PROFILE_ORDER),
        "gate_profiles": GATE_PROFILE_DEFINITIONS,
        "consistency_check_unit_id": CONSISTENCY_CHECK_UNIT_ID,
        "consistency_check_unit_summary": CONSISTENCY_CHECK_UNIT_SUMMARY,
        "consistency_repetition_rule": CONSISTENCY_REPETITION_RULE,
        "default_consistency_unit_count": DEFAULT_CONSISTENCY_UNIT_COUNT,
        "nth_report_visible_priorities": list(NTH_REPORT_VISIBLE_PRIORITIES),
        "nth_report_cumulative_rule": NTH_REPORT_CUMULATIVE_RULE,
        "primary_lane": "primary",
        "primary_passes": list(PASS_NAMES),
        "blind_reviewers": list(BLIND_REVIEWERS),
        "blind_passes_per_reviewer": list(PASS_NAMES),
        "adversarial_passes": list(PASS_NAMES),
        "premise_policy": PREMISE_POLICY_SUMMARY,
        "author_intent_protection_rule": AUTHOR_INTENT_PROTECTION_RULE,
        "ai_generated_text_continuity_rule": AI_GENERATED_TEXT_CONTINUITY_RULE,
        "canonical_name_alias_rule": CANONICAL_NAME_ALIAS_RULE,
        "source_risk_checklist": list(SOURCE_RISK_CHECKLIST),
        "global_context_scan_rule": GLOBAL_CONTEXT_SCAN_RULE,
        "excluded_review_scopes": list(EXCLUDED_REVIEW_SCOPES),
        "repairability_values": list(REPAIRABILITY_VALUES),
        "disposition_values": list(DISPOSITION_VALUES),
        "hard_carryover_kinds": list(HARD_CARRYOVER_KINDS),
    }


def build_consistency_repetition_contract() -> dict[str, Any]:
    return {
        "unit_definition": CONSISTENCY_CHECK_UNIT_ID,
        "requested_unit_count": DEFAULT_CONSISTENCY_UNIT_COUNT,
        "completed_unit_count": 0,
        "rule": CONSISTENCY_REPETITION_RULE,
        "units": [],
    }


def build_blind_reviews() -> dict[str, dict[str, Any]]:
    return {
        reviewer: {"status": "pending", "passes": build_pass_map(), "notes": []}
        for reviewer in BLIND_REVIEWERS
    }


def build_empty_manual_review_submission(gate_profile: str = GATE_PROFILE_DELIVERY) -> dict[str, Any]:
    profile = normalize_gate_profile(gate_profile)
    return {
        "schema_version": "manual_review_submission.v1",
        "status": "pending",
        "gate_profile": profile,
        "reviewer": "",
        "reviewed_at": "",
        "review_protocol": build_review_protocol(profile),
        "consistency_repetition_contract": build_consistency_repetition_contract(),
        "checked_axes": [
            {"axis": item["axis"], "label": item["label"], "status": "pending", "notes": ""}
            for item in REVIEW_AXES
        ],
        "source_risk_checklist": [
            {
                "risk_id": item["risk_id"],
                "label": item["label"],
                "status": "pending",
                "notes": "",
                "rule": item["rule"],
            }
            for item in SOURCE_RISK_CHECKLIST
        ],
        "passes": build_pass_map(),
        "blind_reviews": build_blind_reviews(),
        "total_consistency_report": {
            "status": "pending",
            "path": f"llm-facing/{TOTAL_CONSISTENCY_REPORT_NAME}",
            "notes": [],
        },
        "adversarial_passes": build_pass_map(),
        "findings": [],
        "non_reader_facing_notes": [],
        "remaining_risks": [],
        "final_summary": "",
    }


def write_manual_review_scaffold(
    submission_dir: Path,
    *,
    gate_profile: str = GATE_PROFILE_DELIVERY,
) -> dict[str, Path]:
    profile = normalize_gate_profile(gate_profile)
    submission_dir.mkdir(parents=True, exist_ok=True)
    queue_path = submission_dir / "manual_review_queue.jsonl"
    submission_path = submission_dir / "manual_review_submission.json"
    write_jsonl(queue_path, build_manual_review_queue(profile))
    if not submission_path.exists():
        write_json(submission_path, build_empty_manual_review_submission(profile))
    else:
        merge_missing_review_axes(submission_path, gate_profile=profile)
    return {"queue_path": queue_path, "submission_path": submission_path}


def merge_missing_review_axes(
    submission_path: Path,
    *,
    gate_profile: str = GATE_PROFILE_DELIVERY,
) -> None:
    try:
        payload = json.loads(submission_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return
    changed = merge_missing_submission_contract(payload, gate_profile=gate_profile)
    if changed:
        write_json(submission_path, payload)


def merge_missing_submission_contract(
    payload: dict[str, Any],
    *,
    gate_profile: str = GATE_PROFILE_DELIVERY,
) -> bool:
    changed = False
    profile = normalize_gate_profile(payload.get("gate_profile") or gate_profile)
    if payload.get("gate_profile") != profile:
        payload["gate_profile"] = profile
        changed = True
    if not isinstance(payload.get("review_protocol"), dict):
        payload["review_protocol"] = build_review_protocol(profile)
        changed = True
    else:
        protocol = payload["review_protocol"]
        defaults = build_review_protocol(profile)
        for key, default in defaults.items():
            if key not in protocol:
                protocol[key] = default
                changed = True
        if protocol.get("active_gate_profile") != profile:
            protocol["active_gate_profile"] = profile
            protocol["gate_profile"] = gate_profile_definition(profile)
            changed = True
    if not isinstance(payload.get("consistency_repetition_contract"), dict):
        payload["consistency_repetition_contract"] = build_consistency_repetition_contract()
        changed = True
    else:
        contract = payload["consistency_repetition_contract"]
        for key, default in build_consistency_repetition_contract().items():
            if key not in contract:
                contract[key] = default
                changed = True
    checked_axes = payload.get("checked_axes")
    if not isinstance(checked_axes, list):
        payload["checked_axes"] = [
            {"axis": item["axis"], "label": item["label"], "status": "pending", "notes": ""}
            for item in REVIEW_AXES
        ]
        changed = True
    else:
        seen = {str(item.get("axis") or "") for item in checked_axes if isinstance(item, dict)}
        for item in REVIEW_AXES:
            if item["axis"] in seen:
                continue
            checked_axes.append({"axis": item["axis"], "label": item["label"], "status": "pending", "notes": ""})
            changed = True

    source_risks = payload.get("source_risk_checklist")
    if not isinstance(source_risks, list):
        payload["source_risk_checklist"] = [
            {
                "risk_id": item["risk_id"],
                "label": item["label"],
                "status": "pending",
                "notes": "",
                "rule": item["rule"],
            }
            for item in SOURCE_RISK_CHECKLIST
        ]
        changed = True
    else:
        seen_risks = {str(item.get("risk_id") or "") for item in source_risks if isinstance(item, dict)}
        for item in SOURCE_RISK_CHECKLIST:
            if item["risk_id"] in seen_risks:
                continue
            source_risks.append(
                {
                    "risk_id": item["risk_id"],
                    "label": item["label"],
                    "status": "pending",
                    "notes": "",
                    "rule": item["rule"],
                }
            )
            changed = True

    if not isinstance(payload.get("passes"), dict):
        payload["passes"] = build_pass_map()
        changed = True
    else:
        changed = merge_missing_passes(payload["passes"]) or changed

    if not isinstance(payload.get("blind_reviews"), dict):
        payload["blind_reviews"] = build_blind_reviews()
        changed = True
    else:
        for reviewer in BLIND_REVIEWERS:
            review = payload["blind_reviews"].setdefault(reviewer, {"status": "pending", "passes": {}, "notes": []})
            if not isinstance(review, dict):
                payload["blind_reviews"][reviewer] = {"status": "pending", "passes": build_pass_map(), "notes": []}
                changed = True
                continue
            if not isinstance(review.get("passes"), dict):
                review["passes"] = build_pass_map()
                changed = True
            else:
                changed = merge_missing_passes(review["passes"]) or changed
            if not isinstance(review.get("notes"), list):
                review["notes"] = []
                changed = True

    if not isinstance(payload.get("total_consistency_report"), dict):
        payload["total_consistency_report"] = {"status": "pending", "path": "", "notes": []}
        changed = True
    else:
        report = payload["total_consistency_report"]
        for key, default in (
            ("status", "pending"),
            ("path", f"llm-facing/{TOTAL_CONSISTENCY_REPORT_NAME}"),
            ("notes", []),
        ):
            if key not in report:
                report[key] = default
                changed = True
        if not str(report.get("path") or "").strip():
            report["path"] = f"llm-facing/{TOTAL_CONSISTENCY_REPORT_NAME}"
            changed = True

    if not isinstance(payload.get("adversarial_passes"), dict):
        payload["adversarial_passes"] = build_pass_map()
        changed = True
    else:
        changed = merge_missing_passes(payload["adversarial_passes"]) or changed

    if not isinstance(payload.get("non_reader_facing_notes"), list):
        payload["non_reader_facing_notes"] = []
        changed = True

    return changed


def merge_missing_passes(pass_map: dict[str, Any]) -> bool:
    changed = False
    for pass_name in PASS_NAMES:
        if not isinstance(pass_map.get(pass_name), dict):
            pass_map[pass_name] = empty_pass_result()
            changed = True
            continue
        for key, default in (("status", "pending"), ("notes", []), ("completed_task_ids", [])):
            if key not in pass_map[pass_name]:
                pass_map[pass_name][key] = default
                changed = True
    return changed


def validate_manual_review_submission(path: Path) -> SubmissionValidationResult:
    payload = json.loads(path.read_text(encoding="utf-8"))
    issues: list[dict[str, Any]] = []
    protocol = payload.get("review_protocol")
    protocol_profile = ""
    if isinstance(protocol, dict):
        protocol_profile = str(protocol.get("active_gate_profile") or "")
    profile = normalize_gate_profile(payload.get("gate_profile") or protocol_profile)
    require_primary = profile_requires(profile, "require_primary_passes")
    require_blind = profile_requires(profile, "require_blind_reviews")
    require_total = profile_requires(profile, "require_total_report")
    require_adversarial = profile_requires(profile, "require_adversarial_passes")
    require_repetition = profile_requires(profile, "require_consistency_repetition")
    require_delivery_report = profile_requires(profile, "require_delivery_report")

    checked_axes = payload.get("checked_axes")
    if not isinstance(checked_axes, list):
        checked_axes = []
        issues.append({"field": "checked_axes", "message": "must be an array"})

    reviewed_axis_count = 0
    reviewed_required_axis_count = 0
    seen_axes: set[str] = set()
    required_axes = {item["axis"] for item in REVIEW_AXES}
    profile_required_axes = required_axis_ids(profile)
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
            if axis in profile_required_axes:
                reviewed_required_axis_count += 1
            if not notes:
                issues.append({"field": f"checked_axes[{index}].notes", "message": "checked axis requires notes"})
        if status == "skipped" and not notes:
            issues.append({"field": f"checked_axes[{index}].notes", "message": "skipped axis requires reason"})
        if axis not in required_axes:
            issues.append({"field": f"checked_axes[{index}].axis", "message": f"unknown axis: {axis}"})

    for axis in sorted(required_axes - seen_axes):
        issues.append({"field": "checked_axes", "message": f"missing axis: {axis}"})

    is_complete = payload.get("status") == "complete"

    required_pass_count = 0
    if require_primary:
        required_pass_count += len(PASS_NAMES)
    if require_blind:
        required_pass_count += len(PASS_NAMES) * len(BLIND_REVIEWERS)
    if require_adversarial:
        required_pass_count += len(PASS_NAMES)
    completed_pass_count = validate_pass_map_status(
        payload.get("passes"),
        "passes",
        issues,
        require_present=require_primary,
        require_complete=is_complete and require_primary,
    )
    completed_pass_count += validate_blind_reviews(
        payload.get("blind_reviews"),
        issues,
        require_complete=is_complete and require_blind,
    )
    completed_pass_count += validate_pass_map_status(
        payload.get("adversarial_passes"),
        "adversarial_passes",
        issues,
        require_present=require_adversarial,
        require_complete=is_complete and require_adversarial,
    )
    total_report_ready = validate_total_consistency_report(
        payload.get("total_consistency_report"),
        issues,
        require_complete=is_complete and require_total,
    )
    repetition_ready = validate_consistency_repetition_contract(
        payload.get("consistency_repetition_contract"),
        issues,
        require_complete=is_complete and require_repetition,
    )

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
        issues.extend(validate_finding_taxonomy_contract(finding, index))
        if is_complete:
            issues.extend(validate_complete_finding_contract(finding, index))
            issues.extend(validate_finding_confidence_contract(finding, index))

    if is_complete and reviewed_required_axis_count < len(profile_required_axes):
        issues.append(
            {
                "field": "checked_axes",
                "message": f"complete {profile} submission requires profile axes checked",
                "required_axes": sorted(profile_required_axes),
            }
        )
    if is_complete and require_total and not total_report_ready:
        issues.append({"field": "total_consistency_report", "message": "complete submission requires completed total report"})
    if is_complete and completed_pass_count < required_pass_count:
        issues.append(
            {
                "field": "passes",
                "message": f"complete {profile} submission requires required gate workflow passes",
            }
        )

    ready = (
        payload.get("status") == "complete"
        and reviewed_required_axis_count >= len(profile_required_axes)
        and completed_pass_count >= required_pass_count
        and (total_report_ready or not require_total)
        and repetition_ready
        and bool(str(payload.get("final_summary") or "").strip())
        and not issues
    )
    if payload.get("status") == "complete" and not str(payload.get("final_summary") or "").strip():
        issues.append({"field": "final_summary", "message": "complete submission requires final summary"})
    return SubmissionValidationResult(
        path=str(path),
        status=str(payload.get("status") or "pending"),
        gate_profile=profile,
        workflow_requirements={
            "require_primary_passes": require_primary,
            "require_blind_reviews": require_blind,
            "require_total_report": require_total,
            "require_adversarial_passes": require_adversarial,
            "require_consistency_repetition": require_repetition,
            "require_delivery_report": require_delivery_report,
        },
        ready_for_submission=ready,
        reviewed_axis_count=reviewed_axis_count,
        required_axis_count=len(profile_required_axes),
        completed_pass_count=completed_pass_count,
        required_pass_count=required_pass_count,
        finding_count=len(findings),
        issue_count=len(issues),
        issues=issues,
    )


def validate_pass_map_status(
    pass_map: Any,
    field_prefix: str,
    issues: list[dict[str, Any]],
    *,
    require_present: bool,
    require_complete: bool,
) -> int:
    if not isinstance(pass_map, dict):
        if require_present:
            issues.append({"field": field_prefix, "message": "must be an object"})
        return 0

    completed_count = 0
    for pass_name in PASS_NAMES:
        pass_payload = pass_map.get(pass_name)
        if not isinstance(pass_payload, dict):
            if require_present:
                issues.append({"field": f"{field_prefix}.{pass_name}", "message": "missing pass object"})
            continue
        status = pass_payload.get("status")
        if status == "completed":
            completed_count += 1
            notes = pass_payload.get("notes", [])
            task_ids = pass_payload.get("completed_task_ids", [])
            if not isinstance(notes, list) or not any(str(note).strip() for note in notes):
                issues.append({"field": f"{field_prefix}.{pass_name}.notes", "message": "completed pass requires notes"})
            if not isinstance(task_ids, list) or not task_ids:
                issues.append(
                    {
                        "field": f"{field_prefix}.{pass_name}.completed_task_ids",
                        "message": "completed pass requires task ids",
                    }
                )
        elif require_complete:
            issues.append({"field": f"{field_prefix}.{pass_name}.status", "message": "must be completed"})
    return completed_count


def validate_blind_reviews(
    blind_reviews: Any,
    issues: list[dict[str, Any]],
    *,
    require_complete: bool,
) -> int:
    if not isinstance(blind_reviews, dict):
        if require_complete:
            issues.append({"field": "blind_reviews", "message": "must be an object"})
        return 0

    completed_count = 0
    for reviewer in BLIND_REVIEWERS:
        review = blind_reviews.get(reviewer)
        if not isinstance(review, dict):
            if require_complete:
                issues.append({"field": f"blind_reviews.{reviewer}", "message": "missing blind reviewer object"})
            continue
        if require_complete and review.get("status") != "completed":
            issues.append({"field": f"blind_reviews.{reviewer}.status", "message": "must be completed"})
        completed_count += validate_pass_map_status(
            review.get("passes"),
            f"blind_reviews.{reviewer}.passes",
            issues,
            require_present=require_complete,
            require_complete=require_complete,
        )
    return completed_count


def validate_total_consistency_report(
    report: Any,
    issues: list[dict[str, Any]],
    *,
    require_complete: bool,
) -> bool:
    if not isinstance(report, dict):
        if require_complete:
            issues.append({"field": "total_consistency_report", "message": "must be an object"})
        return False
    ready = report.get("status") == "completed"
    if require_complete and not ready:
        issues.append({"field": "total_consistency_report.status", "message": "must be completed"})
    if report.get("status") == "completed":
        notes = report.get("notes", [])
        if not str(report.get("path") or "").strip():
            issues.append({"field": "total_consistency_report.path", "message": "completed total report requires path"})
            ready = False
        if not isinstance(notes, list) or not any(str(note).strip() for note in notes):
            issues.append({"field": "total_consistency_report.notes", "message": "completed total report requires notes"})
            ready = False
    return ready


def validate_consistency_repetition_contract(
    contract: Any,
    issues: list[dict[str, Any]],
    *,
    require_complete: bool,
) -> bool:
    if not isinstance(contract, dict):
        if require_complete:
            issues.append({"field": "consistency_repetition_contract", "message": "must be an object"})
        return not require_complete

    requested = contract.get("requested_unit_count", DEFAULT_CONSISTENCY_UNIT_COUNT)
    completed = contract.get("completed_unit_count", 0)
    if isinstance(requested, bool) or not isinstance(requested, int) or requested < 1:
        issues.append(
            {
                "field": "consistency_repetition_contract.requested_unit_count",
                "message": "must be an integer >= 1",
            }
        )
        requested = DEFAULT_CONSISTENCY_UNIT_COUNT
    if isinstance(completed, bool) or not isinstance(completed, int) or completed < 0:
        issues.append(
            {
                "field": "consistency_repetition_contract.completed_unit_count",
                "message": "must be an integer >= 0",
            }
        )
        completed = 0

    units = contract.get("units", [])
    if units is None:
        units = []
    if not isinstance(units, list):
        issues.append({"field": "consistency_repetition_contract.units", "message": "must be an array"})
        units = []

    completed_units = 0
    for index, unit in enumerate(units, start=1):
        if not isinstance(unit, dict):
            issues.append({"field": f"consistency_repetition_contract.units[{index}]", "message": "must be an object"})
            continue
        if unit.get("status") == "completed":
            completed_units += 1
            if not str(unit.get("unit_id") or "").strip():
                issues.append(
                    {
                        "field": f"consistency_repetition_contract.units[{index}].unit_id",
                        "message": "completed unit requires unit_id",
                    }
                )
            if not str(unit.get("total_report_path") or "").strip():
                issues.append(
                    {
                        "field": f"consistency_repetition_contract.units[{index}].total_report_path",
                        "message": "completed unit requires total_report_path",
                    }
                )
            notes = unit.get("notes", [])
            if not isinstance(notes, list) or not any(str(note).strip() for note in notes):
                issues.append(
                    {
                        "field": f"consistency_repetition_contract.units[{index}].notes",
                        "message": "completed unit requires notes",
                    }
                )

    effective_completed = max(completed, completed_units)
    if require_complete and requested > 1 and effective_completed < requested:
        issues.append(
            {
                "field": "consistency_repetition_contract.completed_unit_count",
                "message": (
                    "`정합성 검사 N번` means N full consistency_3x3_unit repetitions; "
                    "completed_unit_count must be >= requested_unit_count"
                ),
            }
        )
        return False
    return True


def validate_finding_taxonomy_contract(finding: dict[str, Any], index: int) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    repairability = str(finding.get("repairability") or "").strip()
    disposition = str(finding.get("disposition") or "").strip()
    final_priority = normalize_priority(finding.get("final_priority") or finding.get("priority"))

    if repairability and repairability not in REPAIRABILITY_VALUES:
        issues.append(
            {
                "field": f"findings[{index}].repairability",
                "message": f"must be one of: {', '.join(REPAIRABILITY_VALUES)}",
            }
        )
    if disposition and disposition not in DISPOSITION_VALUES:
        issues.append(
            {
                "field": f"findings[{index}].disposition",
                "message": f"must be one of: {', '.join(DISPOSITION_VALUES)}",
            }
        )
    if final_priority in {"P0", "P1"}:
        if repairability in {"irreconcilable_premise", "webnovel_allowance"}:
            issues.append(
                {
                    "field": f"findings[{index}].repairability",
                    "message": "irreconcilable premise or webnovel allowance must not remain P0/P1 local-fix issue",
                }
            )
        if disposition in {"accepted_world_premise", "genre_hyperbole_allowance", "external_fact_soft"}:
            issues.append(
                {
                    "field": f"findings[{index}].disposition",
                    "message": "accepted premise, genre allowance, or soft external fact must be downgraded/deferred from P0/P1",
                }
            )
    return issues


def validate_finding_confidence_contract(finding: dict[str, Any], index: int) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    decision = normalize_decision(finding.get("decision") or finding.get("status"))
    confidence = finding.get("confidence_percent")
    has_evidence = bool(str(finding.get("evidence") or "").strip()) or bool(
        str(finding.get("evidence_snippet") or "").strip()
    )
    has_counter = bool(str(finding.get("counter_evidence") or "").strip())

    if confidence is not None:
        if isinstance(confidence, bool) or not isinstance(confidence, int) or not 0 <= confidence <= 100:
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


def validate_complete_finding_contract(finding: dict[str, Any], index: int) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    decision = normalize_decision(finding.get("decision") or finding.get("status"))
    initial_priority = normalize_priority(finding.get("original_priority") or finding.get("priority"))
    final_priority = normalize_priority(finding.get("final_priority") or finding.get("priority"))
    confidence = finding.get("confidence_percent")
    category = str(finding.get("category") or "").strip().lower()
    has_evidence = bool(str(finding.get("evidence") or "").strip()) or bool(
        str(finding.get("evidence_snippet") or "").strip()
    )
    has_counter = bool(str(finding.get("counter_evidence") or "").strip())
    has_internal_impact = any(
        str(finding.get(field) or "").strip()
        for field in ("story_internal_impact", "story_state_before", "story_state_after")
    )

    for required in ("decision", "confidence_percent", "final_priority", "fix_hint", "reader_risk"):
        if finding.get(required) in (None, ""):
            issues.append(
                {
                    "field": f"findings[{index}].{required}",
                    "message": "complete review finding requires final triage fields",
                }
            )

    if final_priority in {"P0", "P1"}:
        if decision != "confirmed":
            issues.append(
                {
                    "field": f"findings[{index}].decision",
                    "message": "P0/P1 must be confirmed after final review",
                }
            )
        if isinstance(confidence, bool) or not isinstance(confidence, int) or confidence < 95:
            issues.append(
                {
                    "field": f"findings[{index}].confidence_percent",
                    "message": "P0/P1 requires >= 95 confidence",
                }
            )
        if not has_evidence:
            issues.append(
                {
                    "field": f"findings[{index}].evidence",
                    "message": "P0/P1 requires direct evidence or evidence_snippet",
                }
            )
        if has_counter:
            issues.append(
                {
                    "field": f"findings[{index}].counter_evidence",
                    "message": "P0/P1 cannot keep unresolved counter_evidence; downgrade to P2/P3 or retract",
                }
            )
        if not has_internal_impact:
            issues.append(
                {
                    "field": f"findings[{index}].story_internal_impact",
                    "message": "P0/P1 requires story-internal plausibility impact, not just external fact checking",
                }
            )
        if is_external_fact_category(category) and not str(finding.get("story_internal_impact") or "").strip():
            issues.append(
                {
                    "field": f"findings[{index}].story_internal_impact",
                    "message": "external fact findings need clear story-internal impact to remain P0/P1",
                }
            )
        if is_hard_carryover_finding(finding, category):
            if not str(finding.get("story_state_before") or "").strip():
                issues.append(
                    {
                        "field": f"findings[{index}].story_state_before",
                        "message": "hard carryover P0/P1 requires prior state",
                    }
                )
            if not str(finding.get("story_state_after") or "").strip():
                issues.append(
                    {
                        "field": f"findings[{index}].story_state_after",
                        "message": "hard carryover P0/P1 requires later conflicting state",
                    }
                )

    if has_counter and final_priority in {"P0", "P1"}:
        issues.append(
            {
                "field": f"findings[{index}].final_priority",
                "message": "findings with defensible counter_evidence must not remain P0/P1",
            }
        )
    if decision in {"downgraded", "retracted", "deferred"} and final_priority in {"P0", "P1"}:
        issues.append(
            {
                "field": f"findings[{index}].final_priority",
                "message": "downgraded/retracted/deferred findings must be P2/P3 or omitted from final report",
            }
        )
    if decision == "downgraded" and priority_rank(final_priority) <= priority_rank(initial_priority):
        issues.append(
            {
                "field": f"findings[{index}].final_priority",
                "message": "downgrade requires final_priority to be lower severity than original_priority/priority",
            }
        )
    return issues


def is_hard_carryover_finding(finding: dict[str, Any], category: str) -> bool:
    strictness = str(finding.get("strictness") or "").strip()
    disposition = str(finding.get("disposition") or "").strip()
    kind = str(finding.get("kind") or finding.get("fact_kind") or "").strip()
    category_text = category.lower()
    if strictness == "hard_carryover" or disposition == "hard_carryover_conflict":
        return True
    if kind in HARD_CARRYOVER_KINDS:
        return True
    return any(
        term in category_text
        for term in (
            "numeric",
            "money",
            "percent",
            "date",
            "time",
            "timeline",
            "state",
            "role",
            "amount",
            "수치",
            "숫자",
            "금액",
            "퍼센트",
            "지분",
            "날짜",
            "시간",
            "상태",
            "직함",
        )
    )


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


def normalize_priority(value: Any) -> str:
    text = str(value or "").strip().upper()
    return text if text in {"P0", "P1", "P2", "P3"} else "P3"


def is_external_fact_category(category: str) -> bool:
    return any(
        term in category
        for term in (
            "era",
            "external",
            "calendar",
            "weekday",
            "bank",
            "holiday",
            "고증",
            "외부",
            "달력",
            "영업일",
        )
    )


def priority_rank(value: str) -> int:
    return {"P0": 0, "P1": 1, "P2": 2, "P3": 3}.get(value, 3)


def write_submission_validation_result(result: SubmissionValidationResult, output_path: Path) -> None:
    write_json(output_path, result.to_dict())


def workflow_blockers_from_validation(validation: dict[str, Any]) -> list[str]:
    blockers: set[str] = set()
    requirements = validation.get("workflow_requirements")
    if not isinstance(requirements, dict):
        requirements = {
            "require_primary_passes": True,
            "require_blind_reviews": True,
            "require_total_report": True,
            "require_adversarial_passes": True,
            "require_consistency_repetition": True,
        }
    if int(validation.get("reviewed_axis_count") or 0) < int(validation.get("required_axis_count") or 0):
        blockers.add("manual_review_axes_not_complete")
    if int(validation.get("completed_pass_count") or 0) < int(validation.get("required_pass_count") or 0):
        if requirements.get("require_primary_passes"):
            blockers.add("primary_consistency_passes_not_complete")
        if requirements.get("require_blind_reviews"):
            blockers.add("blind_reviews_not_complete")
        if requirements.get("require_adversarial_passes"):
            blockers.add("adversarial_3pass_not_complete")
    if requirements.get("require_total_report") and (
        validation.get("status") != "complete"
        or int(validation.get("completed_pass_count") or 0) < int(validation.get("required_pass_count") or 0)
    ):
        blockers.add("total_consistency_report_not_complete")
    for issue in validation.get("issues", []):
        if not isinstance(issue, dict):
            continue
        field = str(issue.get("field") or "")
        if field.startswith("blind_reviews.") and requirements.get("require_blind_reviews"):
            blockers.add("blind_reviews_not_complete")
        elif field.startswith("total_consistency_report") and requirements.get("require_total_report"):
            blockers.add("total_consistency_report_not_complete")
        elif field.startswith("adversarial_passes.") and requirements.get("require_adversarial_passes"):
            blockers.add("adversarial_3pass_not_complete")
        elif field.startswith("passes") and requirements.get("require_primary_passes"):
            blockers.add("primary_consistency_passes_not_complete")
        elif field.startswith("checked_axes"):
            blockers.add("manual_review_axes_not_complete")
        elif field.startswith("consistency_repetition_contract") and requirements.get("require_consistency_repetition"):
            blockers.add("consistency_repetitions_not_complete")
    return sorted(blockers)
