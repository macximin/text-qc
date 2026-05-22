from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from .analyze import analyze_run
from .corrections import (
    apply_changes_to_text_file,
    render_change_contexts,
    validate_changes_file,
    write_validation_result,
)
from .delivery import build_final_delivery_package
from .hwpx_review import render_marked_manuscript_hwpx, render_marked_manuscript_md
from .intake import intake_inbox, intake_manuscript
from .package_qc import inspect_epub_packages, write_epub_package_qc
from .protocol import GATE_PROFILE_ORDER, normalize_gate_profile
from .qc import render_qc_html, validate_qc_jsonl_files
from .reports import (
    export_markdown_to_pdf,
    render_author_final_report,
    render_reaudit_report,
    require_completed_manual_review,
    validate_human_report,
    write_report_validation_result,
)
from .submission import (
    validate_manual_review_submission,
    workflow_blockers_from_validation,
    write_submission_validation_result,
)
from .source_integrity import plan_source_integrity_repair
from .typography import normalize_korean_typography_file
from .workspace import (
    build_portfolio_status,
    create_run,
    create_work,
    discover_runs,
    discover_works,
    inspect_text,
    read_json,
    write_json,
)


def _workspace_root(value: str) -> Path:
    return Path(value).expanduser().resolve()


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def cmd_init_work(args: argparse.Namespace) -> int:
    root = _workspace_root(args.workspace)
    work_root = create_work(
        workspace_root=root,
        slug=args.slug,
        title=args.title,
        author=args.author,
        genre=args.genre,
        audience=args.audience,
        platform=args.platform,
        source_path=args.source,
        notes=args.note or [],
    )
    print(f"created work: {work_root}")
    return 0


def cmd_start_run(args: argparse.Namespace) -> int:
    root = _workspace_root(args.workspace)
    run_root = create_run(
        workspace_root=root,
        work_slug=args.work,
        kind=args.kind,
        gate_profile=normalize_gate_profile(args.gate_profile or args.kind),
        source_text_path=args.source,
        notes=args.note or [],
    )
    print(f"created run: {run_root}")
    return 0


def cmd_analyze_run(args: argparse.Namespace) -> int:
    result = analyze_run(run_root=Path(args.run_root).resolve())
    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    return 0


def cmd_normalize_typography(args: argparse.Namespace) -> int:
    input_path = Path(args.input).resolve()
    output_path = Path(args.output).resolve() if args.output else input_path.with_name(
        input_path.stem + ".typography" + input_path.suffix
    )
    result = normalize_korean_typography_file(input_path=input_path, output_path=output_path)
    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    return 0


def cmd_validate_changes(args: argparse.Namespace) -> int:
    result = validate_changes_file(Path(args.changes))
    if args.output:
        write_validation_result(result, Path(args.output))
        print(f"correction validation written: {args.output}")
        return 0
    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    return 0


def resolve_qc_jsonl_paths(args: argparse.Namespace) -> list[Path]:
    if args.ledger:
        return [Path(value).resolve() for value in args.ledger]
    if not args.run_root:
        raise SystemExit("provide --ledger or --run-root")
    qc_dir = Path(args.run_root).resolve() / "editorial_pass" / "qc"
    if args.include_ssot:
        paths = (
            sorted(qc_dir.glob("qc_ssot*.jsonl"))
            + sorted(qc_dir.glob("global_context_scan*.jsonl"))
            + sorted(qc_dir.glob("qc_ledger*.jsonl"))
        )
    else:
        paths = sorted(qc_dir.glob("global_context_scan*.jsonl")) + sorted(qc_dir.glob("qc_ledger*.jsonl"))
    if not paths:
        raise SystemExit(f"no QC JSONL files found under {qc_dir}")
    return paths


def cmd_validate_qc_jsonl(args: argparse.Namespace) -> int:
    paths = resolve_qc_jsonl_paths(args)
    result = validate_qc_jsonl_files(paths)
    if args.output:
        write_json(Path(args.output), result.to_dict())
        print(f"QC JSONL validation written: {args.output}")
        return 0
    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    return 1 if result.invalid else 0


def cmd_render_qc_html(args: argparse.Namespace) -> int:
    paths = resolve_qc_jsonl_paths(args)
    if args.output:
        output_path = Path(args.output).resolve()
    elif args.run_root:
        output_path = Path(args.run_root).resolve() / "editorial_pass" / "qc" / "qc_review.html"
    else:
        output_path = paths[0].with_suffix(".html")
    result = render_qc_html(paths=paths, output_path=output_path, title=args.title)
    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    return 0


def cmd_plan_source_repair(args: argparse.Namespace) -> int:
    result = plan_source_integrity_repair(
        run_root=Path(args.run_root),
        input_path=Path(args.input).resolve() if args.input else None,
        output_dir=Path(args.output_dir).resolve() if args.output_dir else None,
        version=args.version,
        accept_direct=args.accept_direct,
        confidence_threshold=args.confidence_threshold,
    )
    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    return 0


def cmd_apply_changes_text(args: argparse.Namespace) -> int:
    if not args.run_root and not (args.source and args.changes):
        raise SystemExit("use --run-root or provide both --source and --changes")

    run_root = Path(args.run_root).resolve() if args.run_root else None
    source_path = (
        Path(args.source).resolve()
        if args.source
        else run_root / "final_manuscript" / "final_manuscript.txt"
    )
    changes_path = (
        Path(args.changes).resolve()
        if args.changes
        else run_root / "corrections" / "changes.json"
    )
    output_path = (
        Path(args.output).resolve()
        if args.output
        else (
            run_root / "final_manuscript" / "editorial_candidate.txt"
            if run_root
            else source_path.with_name(source_path.stem + ".edited" + source_path.suffix)
        )
    )
    diff_path = (
        Path(args.diff_output).resolve()
        if args.diff_output
        else (
            run_root / "corrections" / "editorial_diff.md"
            if run_root
            else output_path.with_suffix(".diff.md")
        )
    )

    validation = validate_changes_file(changes_path)
    if validation.invalid:
        print(json.dumps(validation.to_dict(), ensure_ascii=False, indent=2))
        print("changes file is invalid; fix it before applying to text")
        return 1

    result = apply_changes_to_text_file(
        source_path=source_path,
        changes_path=changes_path,
        output_path=output_path,
        diff_path=diff_path,
        accept_aa=args.accept_aa,
    )
    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    return 0


def cmd_render_change_contexts(args: argparse.Namespace) -> int:
    if not args.run_root and not (args.source and args.changes):
        raise SystemExit("use --run-root or provide both --source and --changes")

    run_root = Path(args.run_root).resolve() if args.run_root else None
    source_path = (
        Path(args.source).resolve()
        if args.source
        else run_root / "final_manuscript" / "final_manuscript.txt"
    )
    changes_path = (
        Path(args.changes).resolve()
        if args.changes
        else run_root / "corrections" / "changes.json"
    )
    output_path = (
        Path(args.output).resolve()
        if args.output
        else (
            run_root / "corrections" / "change_contexts.md"
            if run_root
            else changes_path.with_name("change_contexts.md")
        )
    )
    result = render_change_contexts(
        source_path=source_path,
        changes_path=changes_path,
        output_path=output_path,
        window_chars=args.window_chars,
        contextual_only=args.contextual_only,
    )
    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    return 0


def cmd_render_marked_manuscript_hwpx(args: argparse.Namespace) -> int:
    if not args.run_root and not (args.source and args.changes):
        raise SystemExit("use --run-root or provide both --source and --changes")

    run_root = Path(args.run_root).resolve() if args.run_root else None
    manifest: dict[str, Any] = {}
    if run_root:
        manifest_path = run_root / "run_manifest.json"
        if manifest_path.exists():
            manifest = read_json(manifest_path)

    source_path = (
        Path(args.source).resolve()
        if args.source
        else resolve_review_source_path(run_root, manifest)
    )
    changes_path = (
        Path(args.changes).resolve()
        if args.changes
        else run_root / "corrections" / "changes.json"
    )
    loop_label = args.loop_label.strip()
    output_path = (
        Path(args.output).resolve()
        if args.output
        else (
            run_root
            / "human-facing"
            / (f"{loop_label}_marked_manuscript.hwpx" if loop_label else "marked_manuscript.hwpx")
            if run_root
            else changes_path.with_name(
                f"{loop_label}_marked_manuscript.hwpx" if loop_label else "marked_manuscript.hwpx"
            )
        )
    )
    result = render_marked_manuscript_hwpx(
        source_path=source_path,
        changes_path=changes_path,
        output_path=output_path,
        loop_label=loop_label,
        title=args.title,
        include_manual_notes=not args.no_manual_notes,
    )
    if run_root:
        manifest.setdefault("artifacts", {})
        key = (
            f"{loop_label}_marked_manuscript_hwpx_path"
            if loop_label
            else "marked_manuscript_hwpx_path"
        )
        manifest["artifacts"][key] = str(output_path)
        write_json(run_root / "run_manifest.json", manifest)
    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    return 0


def cmd_render_marked_manuscript_md(args: argparse.Namespace) -> int:
    if not args.run_root and not (args.source and args.changes):
        raise SystemExit("use --run-root or provide both --source and --changes")

    run_root = Path(args.run_root).resolve() if args.run_root else None
    manifest: dict[str, Any] = {}
    if run_root:
        manifest_path = run_root / "run_manifest.json"
        if manifest_path.exists():
            manifest = read_json(manifest_path)

    source_path = (
        Path(args.source).resolve()
        if args.source
        else resolve_review_source_path(run_root, manifest)
    )
    changes_path = (
        Path(args.changes).resolve()
        if args.changes
        else run_root / "corrections" / "changes.json"
    )
    loop_label = args.loop_label.strip()
    output_path = (
        Path(args.output).resolve()
        if args.output
        else (
            run_root
            / "human-facing"
            / (f"{loop_label}_marked_manuscript.md" if loop_label else "marked_manuscript.md")
            if run_root
            else changes_path.with_name(
                f"{loop_label}_marked_manuscript.md" if loop_label else "marked_manuscript.md"
            )
        )
    )
    result = render_marked_manuscript_md(
        source_path=source_path,
        changes_path=changes_path,
        output_path=output_path,
        loop_label=loop_label,
        title=args.title,
        include_manual_notes=not args.no_manual_notes,
    )
    if run_root:
        manifest.setdefault("artifacts", {})
        key = (
            f"{loop_label}_marked_manuscript_md_path"
            if loop_label
            else "marked_manuscript_md_path"
        )
        manifest["artifacts"][key] = str(output_path)
        write_json(run_root / "run_manifest.json", manifest)
    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    return 0


def resolve_review_source_path(run_root: Path, manifest: dict[str, Any]) -> Path:
    for value in (
        manifest.get("source_text_path"),
        manifest.get("artifacts", {}).get("extracted_text_path"),
        manifest.get("artifacts", {}).get("final_manuscript_path"),
    ):
        if not value:
            continue
        path = Path(str(value))
        if not path.is_absolute():
            path = (run_root / path).resolve()
        if path.exists():
            return path
    return run_root / "final_manuscript" / "final_manuscript.txt"


def resolve_one_page_report_path(run_root: Path) -> Path:
    manifest_path = run_root / "run_manifest.json"
    if manifest_path.exists():
        manifest = read_json(manifest_path)
        report_value = manifest.get("artifacts", {}).get("one_page_report_path")
        if report_value:
            report_path = Path(str(report_value))
            if not report_path.is_absolute():
                report_path = (run_root / report_path).resolve()
            if report_path.exists():
                return report_path

    human_dir = run_root / "human-facing"
    if human_dir.exists():
        numbered_reports = [
            item
            for item in human_dir.iterdir()
            if item.is_file() and item.name.endswith("_one_page_report.md")
        ]
        if numbered_reports:
            return sorted(numbered_reports, key=numbered_report_sort_key)[-1]
    return human_dir / "one_page_report.md"


def numbered_report_sort_key(path: Path) -> tuple[int, str]:
    prefix = path.name.split("차_", 1)[0]
    return (int(prefix) if prefix.isdecimal() else -1, path.name)


def cmd_validate_submission(args: argparse.Namespace) -> int:
    if not args.run_root and not args.submission:
        raise SystemExit("one of --run-root or --submission is required")
    if args.run_root:
        run_root = Path(args.run_root).resolve()
        submission_dir = run_root / "evidence" / "submission"
        submission_path = submission_dir / "manual_review_submission.json"
        default_output = submission_dir / "manual_review_validation.json"
    else:
        run_root = None
        submission_path = Path(args.submission).resolve()
        default_output = submission_path.with_name("manual_review_validation.json")
    result = validate_manual_review_submission(submission_path)
    if args.output or args.run_root:
        output_path = Path(args.output).resolve() if args.output else default_output
        write_submission_validation_result(result, output_path)
        if run_root:
            refresh_submission_gate(run_root, result.to_dict())
        print(f"manual review validation written: {output_path}")
        return 0
    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    return 0


def cmd_validate_report(args: argparse.Namespace) -> int:
    if not args.run_root and not args.report:
        raise SystemExit("one of --run-root or --report is required")
    if args.run_root:
        run_root = Path(args.run_root).resolve()
        report_path = resolve_one_page_report_path(run_root)
        default_output = run_root / "human-facing" / "report_validation.json"
    else:
        run_root = None
        report_path = Path(args.report).resolve()
        default_output = report_path.with_name("report_validation.json")
    result = validate_human_report(report_path)
    manual_validation: dict[str, Any] | None = None
    if args.run_root:
        manual_path = run_root / "evidence" / "submission" / "manual_review_submission.json"
        if manual_path.exists():
            manual_validation = validate_manual_review_submission(manual_path).to_dict()
        requirements = manual_validation.get("workflow_requirements") if isinstance(manual_validation, dict) else None
        require_delivery_report = not isinstance(requirements, dict) or bool(requirements.get("require_delivery_report"))
        if require_delivery_report:
            result = require_completed_manual_review(result, manual_validation)
    if args.output or args.run_root:
        output_path = Path(args.output).resolve() if args.output else default_output
        write_report_validation_result(result, output_path)
        if args.run_root:
            refresh_submission_gate_report(run_root, result.to_dict(), manual_validation=manual_validation)
        print(f"human report validation written: {output_path}")
        return 0
    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    return 0


def cmd_render_reaudit_report(args: argparse.Namespace) -> int:
    run_root = Path(args.run_root).resolve()
    submission_path = (
        Path(args.submission).resolve()
        if args.submission
        else run_root / "evidence" / "submission" / "manual_review_submission.json"
    )
    submission_validation = validate_manual_review_submission(submission_path)
    validation_output = submission_path.with_name("manual_review_validation.json")
    write_submission_validation_result(submission_validation, validation_output)
    if not submission_validation.ready_for_submission and not args.allow_incomplete:
        print(json.dumps(submission_validation.to_dict(), ensure_ascii=False, indent=2))
        print("manual review submission is not ready; use --allow-incomplete to render a draft")
        return 1
    output_path = (
        Path(args.output).resolve()
        if args.output
        else run_root / "human-facing" / "reaudit_report.md"
    )
    manifest_path = run_root / "run_manifest.json"
    work_title = args.title
    source_label = args.source_label
    if manifest_path.exists():
        manifest = read_json(manifest_path)
        if not source_label:
            source_label = str(manifest.get("source_text_path") or "")
        if not work_title:
            work_title = f"{manifest.get('work_slug', '작품')} 95% 재감리 보고서"
    render_reaudit_report(
        submission_path=submission_path,
        output_path=output_path,
        title=work_title,
        source_label=source_label,
    )
    validation_result = require_completed_manual_review(
        validate_human_report(output_path),
        submission_validation.to_dict(),
    )
    validation = validation_result.to_dict()
    write_report_validation_result(validation_result, output_path.with_name("reaudit_report_validation.json"))
    refresh_submission_gate_reaudit(
        run_root,
        str(output_path),
        validation,
        submission_path=submission_path,
        submission_validation=submission_validation.to_dict(),
    )
    print(f"reaudit report written: {output_path}")
    print(json.dumps(validation, ensure_ascii=False, indent=2))
    return 0


def cmd_render_author_final_report(args: argparse.Namespace) -> int:
    run_root = Path(args.run_root).resolve()
    submission_path = (
        Path(args.submission).resolve()
        if args.submission
        else run_root / "evidence" / "submission" / "manual_review_submission.json"
    )
    submission_validation = validate_manual_review_submission(submission_path)
    validation_output = submission_path.with_name("manual_review_validation.json")
    write_submission_validation_result(submission_validation, validation_output)
    if not submission_validation.ready_for_submission and not args.allow_incomplete:
        print(json.dumps(submission_validation.to_dict(), ensure_ascii=False, indent=2))
        print("manual review submission is not ready; use --allow-incomplete to render a draft")
        return 1
    output_path = (
        Path(args.output).resolve()
        if args.output
        else run_root / "human-facing" / "author_final_report.md"
    )
    manifest_path = run_root / "run_manifest.json"
    work_title = args.title
    source_label = args.source_label
    if manifest_path.exists():
        manifest = read_json(manifest_path)
        if not source_label:
            source_label = str(manifest.get("source_text_path") or "")
        if not work_title:
            work_title = f"{manifest.get('work_slug', '작품')} 작가전달용 최종검수보고서"
    render_author_final_report(
        submission_path=submission_path,
        output_path=output_path,
        title=work_title,
        source_label=source_label,
    )
    validation_result = require_completed_manual_review(
        validate_human_report(output_path),
        submission_validation.to_dict(),
    )
    validation = validation_result.to_dict()
    write_report_validation_result(validation_result, output_path.with_name("author_final_report_validation.json"))
    pdf_path = None
    if args.pdf:
        pdf_path = Path(args.pdf).resolve() if isinstance(args.pdf, str) else output_path.with_suffix(".pdf")
        export_markdown_to_pdf(output_path, pdf_path)
    refresh_submission_gate_author_final(
        run_root,
        str(output_path),
        validation,
        pdf_path=str(pdf_path) if pdf_path else "",
        submission_path=submission_path,
        submission_validation=submission_validation.to_dict(),
    )
    print(f"author final report written: {output_path}")
    if pdf_path:
        print(f"author final report PDF written: {pdf_path}")
    print(json.dumps(validation, ensure_ascii=False, indent=2))
    return 0


def cmd_render_final_delivery(args: argparse.Namespace) -> int:
    result = build_final_delivery_package(
        run_root=Path(args.run_root).resolve(),
        output_dir=Path(args.output_dir).resolve() if args.output_dir else None,
        version=args.version,
        manuscript_path=Path(args.manuscript).resolve() if args.manuscript else None,
        scan_manifest_path=Path(args.scan_manifest).resolve() if args.scan_manifest else None,
        title=args.title,
        work_label=args.work_label,
        update_run_manifest=not args.no_manifest_update,
    )
    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    return 0


def cmd_export_report_pdf(args: argparse.Namespace) -> int:
    report_path = Path(args.report).resolve()
    output_path = Path(args.output).resolve() if args.output else report_path.with_suffix(".pdf")
    export_markdown_to_pdf(report_path, output_path)
    print(f"PDF written: {output_path}")
    return 0


def cmd_inspect_epub_package(args: argparse.Namespace) -> int:
    input_path = Path(args.input).resolve()
    try:
        payload = inspect_epub_packages(input_path)
    except ValueError as exc:
        print(str(exc))
        return 1
    output_dir = Path(args.output_dir).resolve() if args.output_dir else (input_path if input_path.is_dir() else input_path.parent)
    paths = write_epub_package_qc(payload, output_dir)
    print(json.dumps({"summary": payload["summary"], "findings": payload["findings"], "outputs": {key: str(value) for key, value in paths.items()}}, ensure_ascii=False, indent=2))
    return 0


def refresh_submission_gate(run_root: Path, validation: dict[str, Any]) -> None:
    gate_path = run_root / "evidence" / "submission" / "submission_gate.json"
    gate_exists = gate_path.exists()
    gate = read_json(gate_path) if gate_exists else {"schema_version": "submission_gate.v1"}
    blockers = [str(item) for item in gate.get("blockers", [])]
    blockers = [
        item
        for item in blockers
        if item
        not in {
            "manual_review_not_complete",
            "manual_review_submission_invalid_json",
            "human_report_not_claim_evidence_ready",
            "human_report_missing",
            "primary_consistency_passes_not_complete",
            "blind_reviews_not_complete",
            "total_consistency_report_not_complete",
            "adversarial_3pass_not_complete",
            "manual_review_axes_not_complete",
        }
    ]
    if not gate_exists:
        blockers.append("evidence_not_generated")
    if not validation.get("ready_for_submission"):
        blockers.append("manual_review_not_complete")
    blockers.extend(workflow_blockers_from_validation(validation))
    report_path = resolve_one_page_report_path(run_root)
    requirements = validation.get("workflow_requirements")
    require_delivery_report = not isinstance(requirements, dict) or bool(requirements.get("require_delivery_report"))
    if report_path.exists():
        if require_delivery_report:
            report_validation = require_completed_manual_review(
                validate_human_report(report_path),
                validation,
            ).to_dict()
        else:
            report_validation = validate_human_report(report_path).to_dict()
        gate["human_report"] = report_validation
        if require_delivery_report and not report_validation.get("ready_for_delivery"):
            blockers.append("human_report_not_claim_evidence_ready")
    gate["manual_review"] = validation
    gate["blockers"] = sorted(set(blockers))
    gate["ready_for_submission"] = not gate["blockers"]
    gate["status"] = "ready" if gate["ready_for_submission"] else "blocked"
    write_json(gate_path, gate)


def refresh_submission_gate_report(
    run_root: Path,
    validation: dict[str, Any],
    *,
    manual_validation: dict[str, Any] | None = None,
) -> None:
    gate_path = run_root / "evidence" / "submission" / "submission_gate.json"
    gate_exists = gate_path.exists()
    gate = read_json(gate_path) if gate_exists else {"schema_version": "submission_gate.v1"}
    blockers = [str(item) for item in gate.get("blockers", [])]
    blockers = [
        item
        for item in blockers
        if item
        not in {
            "human_report_not_claim_evidence_ready",
            "human_report_missing",
            "primary_consistency_passes_not_complete",
            "blind_reviews_not_complete",
            "total_consistency_report_not_complete",
            "adversarial_3pass_not_complete",
            "manual_review_axes_not_complete",
        }
    ]
    if not gate_exists:
        blockers.append("evidence_not_generated")
    manual_path = run_root / "evidence" / "submission" / "manual_review_submission.json"
    if manual_path.exists():
        manual_validation = manual_validation or validate_manual_review_submission(manual_path).to_dict()
        manual_validation = {**manual_validation, "path": str(manual_path)}
    requirements = manual_validation.get("workflow_requirements") if isinstance(manual_validation, dict) else None
    require_delivery_report = not isinstance(requirements, dict) or bool(requirements.get("require_delivery_report"))
    if require_delivery_report and not validation.get("ready_for_delivery"):
        blockers.append("human_report_not_claim_evidence_ready")
    if manual_validation:
        gate["manual_review"] = manual_validation
        blockers = [item for item in blockers if item != "manual_review_not_complete"]
        if not manual_validation.get("ready_for_submission"):
            blockers.append("manual_review_not_complete")
        blockers.extend(workflow_blockers_from_validation(manual_validation))
    else:
        blockers.append("manual_review_not_complete")
    gate["human_report"] = validation
    gate["blockers"] = sorted(set(blockers))
    gate["ready_for_submission"] = not gate["blockers"]
    gate["status"] = "ready" if gate["ready_for_submission"] else "blocked"
    write_json(gate_path, gate)


def refresh_submission_gate_reaudit(
    run_root: Path,
    report_path: str,
    validation: dict[str, Any],
    *,
    submission_path: Path | None = None,
    submission_validation: dict[str, Any] | None = None,
) -> None:
    gate_path = run_root / "evidence" / "submission" / "submission_gate.json"
    gate_exists = gate_path.exists()
    gate = read_json(gate_path) if gate_exists else {"schema_version": "submission_gate.v1"}
    gate["reaudit_report"] = {
        "path": report_path,
        "validation": validation,
    }
    blockers = [str(item) for item in gate.get("blockers", [])]
    blockers = [
        item
        for item in blockers
        if item not in {"reaudit_report_missing", "reaudit_report_not_claim_evidence_ready"}
    ]
    if not validation.get("ready_for_delivery"):
        blockers.append("reaudit_report_not_claim_evidence_ready")
    manual_path = submission_path or run_root / "evidence" / "submission" / "manual_review_submission.json"
    if manual_path.exists():
        manual_validation = submission_validation or validate_manual_review_submission(manual_path).to_dict()
        manual_validation = {**manual_validation, "path": str(manual_path)}
        gate["manual_review"] = manual_validation
        blockers = [item for item in blockers if item != "manual_review_not_complete"]
        if not manual_validation.get("ready_for_submission"):
            blockers.append("manual_review_not_complete")
        blockers.extend(workflow_blockers_from_validation(manual_validation))
    gate["blockers"] = sorted(set(blockers))
    gate["ready_for_submission"] = not gate["blockers"]
    gate["status"] = "ready" if gate["ready_for_submission"] else "blocked"
    write_json(gate_path, gate)


def refresh_submission_gate_author_final(
    run_root: Path,
    report_path: str,
    validation: dict[str, Any],
    *,
    pdf_path: str = "",
    submission_path: Path | None = None,
    submission_validation: dict[str, Any] | None = None,
) -> None:
    gate_path = run_root / "evidence" / "submission" / "submission_gate.json"
    gate_exists = gate_path.exists()
    gate = read_json(gate_path) if gate_exists else {"schema_version": "submission_gate.v1"}
    gate["author_final_report"] = {
        "path": report_path,
        "pdf_path": pdf_path,
        "validation": validation,
    }
    blockers = [str(item) for item in gate.get("blockers", [])]
    blockers = [
        item
        for item in blockers
        if item not in {"author_final_report_missing", "author_final_report_not_claim_evidence_ready"}
    ]
    if not validation.get("ready_for_delivery"):
        blockers.append("author_final_report_not_claim_evidence_ready")
    manual_path = submission_path or run_root / "evidence" / "submission" / "manual_review_submission.json"
    if manual_path.exists():
        manual_validation = submission_validation or validate_manual_review_submission(manual_path).to_dict()
        manual_validation = {**manual_validation, "path": str(manual_path)}
        gate["manual_review"] = manual_validation
        blockers = [item for item in blockers if item != "manual_review_not_complete"]
        if not manual_validation.get("ready_for_submission"):
            blockers.append("manual_review_not_complete")
    gate["blockers"] = sorted(set(blockers))
    gate["ready_for_submission"] = not gate["blockers"]
    gate["status"] = "ready" if gate["ready_for_submission"] else "blocked"
    write_json(gate_path, gate)


def cmd_mark_stage(args: argparse.Namespace) -> int:
    run_root = Path(args.run_root).resolve()
    manifest_path = run_root / "run_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    stages = manifest.setdefault("stages", {})
    if args.stage not in stages and not args.allow_new:
        known = ", ".join(stages.keys())
        raise SystemExit(f"unknown stage: {args.stage}\nknown stages: {known}")
    stages[args.stage] = args.status
    if args.note:
        manifest.setdefault("notes", []).append(args.note)
    write_json(manifest_path, manifest)
    print(f"stage updated: {args.stage}={args.status}")
    return 0


def cmd_intake(args: argparse.Namespace) -> int:
    result = intake_manuscript(
        input_path=Path(args.input),
        workspace_root=_workspace_root(args.workspace),
        templates_root=Path(args.templates).resolve(),
        mode=args.mode,
        gate_profile=args.gate_profile or "",
        title=args.title,
        slug=args.slug,
        author=args.author,
        genre=args.genre,
        audience=args.audience,
        platform=args.platform,
        source_note=args.note or "",
    )
    payload = result.to_dict()
    if args.analyze:
        payload["analysis"] = analyze_run(run_root=Path(result.run_root)).to_dict()
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def cmd_intake_inbox(args: argparse.Namespace) -> int:
    results = intake_inbox(
        inbox_root=Path(args.inbox).resolve(),
        workspace_root=_workspace_root(args.workspace),
        templates_root=Path(args.templates).resolve(),
        mode=args.mode,
        gate_profile=args.gate_profile or "",
        genre=args.genre,
        audience=args.audience,
        platform=args.platform,
    )
    items = []
    for result in results:
        item = result.to_dict()
        if args.analyze:
            item["analysis"] = analyze_run(run_root=Path(result.run_root)).to_dict()
        items.append(item)
    payload = {"count": len(results), "items": items}
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def cmd_list_works(args: argparse.Namespace) -> int:
    root = _workspace_root(args.workspace)
    works = discover_works(workspace_root=root)
    if args.json:
        print(json.dumps({"workspace": str(root), "works": works}, ensure_ascii=False, indent=2))
        return 0

    if not works:
        print(f"no works found under {root}")
        return 0

    print(f"workspace: {root}")
    for work in works:
        latest = work["latest_run"] or "-"
        print(
            f"- {work['slug']} | {work['title']} | {work['genre']} | "
            f"runs={work['run_count']} | latest={latest}"
        )
    return 0


def cmd_list_runs(args: argparse.Namespace) -> int:
    root = _workspace_root(args.workspace)
    runs = discover_runs(workspace_root=root, work_slug=args.work)
    if args.json:
        print(json.dumps({"workspace": str(root), "work": args.work, "runs": runs}, ensure_ascii=False, indent=2))
        return 0

    if not runs:
        print(f"no runs found for {args.work} under {root}")
        return 0

    print(f"work: {args.work}")
    for run in runs:
        next_stage = run["next_stage"] or "done"
        print(
            f"- {run['run_id']} | {run['kind']} | {run['status']} | "
            f"pending={run['pending_stage_count']} | next={next_stage}"
        )
    return 0


def cmd_portfolio_status(args: argparse.Namespace) -> int:
    root = _workspace_root(args.workspace)
    status = build_portfolio_status(workspace_root=root)
    if args.output:
        write_json(Path(args.output), status)
        print(f"portfolio status written: {args.output}")
        return 0
    if args.json:
        print(json.dumps(status, ensure_ascii=False, indent=2))
        return 0

    print(f"workspace: {status['workspace']}")
    print(f"works: {status['work_count']} total, {status['active_work_count']} active")
    if status["works_without_runs"]:
        print("works without runs:")
        for slug in status["works_without_runs"]:
            print(f"- {slug}")
    if status["works_with_pending_runs"]:
        print("pending latest runs:")
        for item in status["works_with_pending_runs"]:
            print(f"- {item['slug']} | {item['latest_run']} | next={item['next_stage']}")
    if not status["works_without_runs"] and not status["works_with_pending_runs"]:
        print("all active works are either done or have no detected blocker")
    return 0


def cmd_inspect_text(args: argparse.Namespace) -> int:
    result = inspect_text(Path(args.input))
    payload = result.to_dict()
    if args.output:
        write_json(Path(args.output), payload)
        print(f"inspection written: {args.output}")
    else:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def cmd_report_skeleton(args: argparse.Namespace) -> int:
    template_path = Path(args.template)
    template = template_path.read_text(encoding="utf-8")
    rendered = (
        template.replace("{{work_slug}}", args.work)
        .replace("{{run_id}}", args.run)
        .replace("{{report_title}}", args.title)
    )
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(rendered, encoding="utf-8")
    print(f"report skeleton written: {output_path}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="novel-qc-loop")
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_work = subparsers.add_parser("init-work", help="create a multi-work workspace entry")
    init_work.add_argument("--workspace", default="workspace")
    init_work.add_argument("--slug", required=True)
    init_work.add_argument("--title", required=True)
    init_work.add_argument("--author", default="")
    init_work.add_argument("--genre", default="")
    init_work.add_argument("--audience", default="")
    init_work.add_argument("--platform", default="")
    init_work.add_argument("--source", default="")
    init_work.add_argument("--note", action="append")
    init_work.set_defaults(func=cmd_init_work)

    start_run = subparsers.add_parser("start-run", help="create a run under a work")
    start_run.add_argument("--workspace", default="workspace")
    start_run.add_argument("--work", required=True)
    start_run.add_argument("--kind", default="global-audit")
    start_run.add_argument("--gate-profile", choices=list(GATE_PROFILE_ORDER), help="override kind-derived gate profile")
    start_run.add_argument("--source", default="")
    start_run.add_argument("--note", action="append")
    start_run.set_defaults(func=cmd_start_run)

    analyze = subparsers.add_parser("analyze-run", help="build facts/review evidence for one run")
    analyze.add_argument("--run-root", required=True)
    analyze.set_defaults(func=cmd_analyze_run)

    normalize_typography = subparsers.add_parser(
        "normalize-typography",
        help="normalize Korean manuscript typography: “”, ‘’, and …",
    )
    normalize_typography.add_argument("--input", required=True)
    normalize_typography.add_argument("--output")
    normalize_typography.set_defaults(func=cmd_normalize_typography)

    validate_changes = subparsers.add_parser("validate-changes", help="validate correction changes JSON")
    validate_changes.add_argument("--changes", required=True)
    validate_changes.add_argument("--output")
    validate_changes.set_defaults(func=cmd_validate_changes)

    apply_text = subparsers.add_parser(
        "apply-changes-text",
        help="apply changes JSON to plain text and write an editorial candidate plus Markdown diff",
    )
    apply_text.add_argument("--run-root", help="run folder; defaults paths under final_manuscript/ and corrections/")
    apply_text.add_argument("--source", help="source text path; default: RUN/final_manuscript/final_manuscript.txt")
    apply_text.add_argument("--changes", help="changes JSON path; default: RUN/corrections/changes.json")
    apply_text.add_argument("--output", help="output text path; default: RUN/final_manuscript/editorial_candidate.txt")
    apply_text.add_argument("--diff-output", help="Markdown diff path; default: RUN/corrections/editorial_diff.md")
    apply_text.add_argument("--accept-aa", action="store_true", help="apply ⓐⓐ changes too")
    apply_text.set_defaults(func=cmd_apply_changes_text)

    change_contexts = subparsers.add_parser(
        "render-change-contexts",
        help="render surrounding source context for changes JSON anchors",
    )
    change_contexts.add_argument("--run-root", help="run folder; defaults paths under final_manuscript/ and corrections/")
    change_contexts.add_argument("--source", help="source text path; default: RUN/final_manuscript/final_manuscript.txt")
    change_contexts.add_argument("--changes", help="changes JSON path; default: RUN/corrections/changes.json")
    change_contexts.add_argument("--output", help="Markdown output path; default: RUN/corrections/change_contexts.md")
    change_contexts.add_argument("--window-chars", type=int, default=360)
    change_contexts.add_argument("--contextual-only", action="store_true", help="render only contextual edit classes")
    change_contexts.set_defaults(func=cmd_render_change_contexts)

    marked_hwpx = subparsers.add_parser(
        "render-marked-manuscript-hwpx",
        help="render the full source manuscript with visible ⓐ/ⓐⓐ markers inserted in order",
    )
    marked_hwpx.add_argument("--run-root", help="run folder; defaults paths from run_manifest and corrections/")
    marked_hwpx.add_argument("--source", help="source text path; default: run manifest source/extracted text")
    marked_hwpx.add_argument("--changes", help="changes JSON path; default: RUN/corrections/changes.json")
    marked_hwpx.add_argument("--output", help="HWPX output path; default: RUN/human-facing/*_marked_manuscript.hwpx")
    marked_hwpx.add_argument("--loop-label", default="", help="label used in output name, e.g. loop_01")
    marked_hwpx.add_argument("--title", default="", help="document title")
    marked_hwpx.add_argument(
        "--no-manual-notes",
        action="store_true",
        help="skip generated opinion notes",
    )
    marked_hwpx.set_defaults(func=cmd_render_marked_manuscript_hwpx)

    marked_md = subparsers.add_parser(
        "render-marked-manuscript-md",
        help="render the full source manuscript with visible ⓐ/ⓐⓐ markers inserted in Markdown",
    )
    marked_md.add_argument("--run-root", help="run folder; defaults paths from run_manifest and corrections/")
    marked_md.add_argument("--source", help="source text path; default: run manifest source/extracted text")
    marked_md.add_argument("--changes", help="changes JSON path; default: RUN/corrections/changes.json")
    marked_md.add_argument("--output", help="Markdown output path; default: RUN/human-facing/*_marked_manuscript.md")
    marked_md.add_argument("--loop-label", default="", help="label used in output name, e.g. loop_01")
    marked_md.add_argument("--title", default="", help="document title")
    marked_md.add_argument(
        "--no-manual-notes",
        action="store_true",
        help="skip generated opinion notes",
    )
    marked_md.set_defaults(func=cmd_render_marked_manuscript_md)

    validate_submission = subparsers.add_parser("validate-submission", help="validate manual review submission JSON")
    validate_submission.add_argument("--submission")
    validate_submission.add_argument("--run-root")
    validate_submission.add_argument("--output")
    validate_submission.set_defaults(func=cmd_validate_submission)

    validate_qc = subparsers.add_parser("validate-qc-jsonl", help="validate lightweight QC JSONL ledgers")
    validate_qc.add_argument("--run-root", help="run folder; defaults to RUN/editorial_pass/qc/qc_ledger*.jsonl")
    validate_qc.add_argument("--ledger", nargs="*", help="one or more QC JSONL files")
    validate_qc.add_argument("--include-ssot", action="store_true", help="also validate qc_ssot*.jsonl under --run-root")
    validate_qc.add_argument("--output", help="write validation JSON")
    validate_qc.set_defaults(func=cmd_validate_qc_jsonl)

    qc_html = subparsers.add_parser("render-qc-html", help="render lightweight QC JSONL ledgers to HTML on demand")
    qc_html.add_argument("--run-root", help="run folder; defaults output to RUN/editorial_pass/qc/qc_review.html")
    qc_html.add_argument("--ledger", nargs="*", help="one or more QC JSONL files")
    qc_html.add_argument("--include-ssot", action="store_true", help="also render qc_ssot*.jsonl under --run-root")
    qc_html.add_argument("--output", help="HTML output path")
    qc_html.add_argument("--title", default="QC Ledger")
    qc_html.set_defaults(func=cmd_render_qc_html)

    source_repair = subparsers.add_parser(
        "plan-source-repair",
        help="create a traceable source integrity repair candidate without changing the original run source",
    )
    source_repair.add_argument("--run-root", required=True)
    source_repair.add_argument("--input", help="optional source file/folder override")
    source_repair.add_argument("--output-dir", help="output folder; default RUN/source_integrity/VERSION")
    source_repair.add_argument("--version", default="v1")
    source_repair.add_argument(
        "--accept-direct",
        action="store_true",
        help="promote safe >= confidence-threshold source repairs into the run working source",
    )
    source_repair.add_argument("--confidence-threshold", type=int, default=95)
    source_repair.set_defaults(func=cmd_plan_source_repair)

    validate_report = subparsers.add_parser("validate-report", help="validate Korean human-facing final report")
    validate_report.add_argument("--report")
    validate_report.add_argument("--run-root")
    validate_report.add_argument("--output")
    validate_report.set_defaults(func=cmd_validate_report)

    render_reaudit = subparsers.add_parser("render-reaudit-report", help="render a 95%% confidence re-audit report")
    render_reaudit.add_argument("--run-root", required=True)
    render_reaudit.add_argument("--submission")
    render_reaudit.add_argument("--output")
    render_reaudit.add_argument("--title", default="")
    render_reaudit.add_argument("--source-label", default="")
    render_reaudit.add_argument("--allow-incomplete", action="store_true")
    render_reaudit.set_defaults(func=cmd_render_reaudit_report)

    render_author = subparsers.add_parser(
        "render-author-final-report",
        help="render a detailed author/editor-facing final QC report",
    )
    render_author.add_argument("--run-root", required=True)
    render_author.add_argument("--submission")
    render_author.add_argument("--output")
    render_author.add_argument("--title", default="")
    render_author.add_argument("--source-label", default="")
    render_author.add_argument(
        "--pdf",
        nargs="?",
        const=True,
        default=False,
        help="also export PDF; optionally provide the PDF output path",
    )
    render_author.add_argument("--allow-incomplete", action="store_true")
    render_author.set_defaults(func=cmd_render_author_final_report)

    final_delivery = subparsers.add_parser(
        "render-final-delivery",
        help="package the approved TXT manuscript and human-facing HTML final report",
    )
    final_delivery.add_argument("--run-root", required=True)
    final_delivery.add_argument("--output-dir", help="output folder; default: RUN/final_delivery/VERSION_final_approved_package")
    final_delivery.add_argument("--version", default="v1")
    final_delivery.add_argument("--manuscript", help="approved manuscript source; default: run final_manuscript.txt")
    final_delivery.add_argument("--scan-manifest", help="final scan manifest; default: latest consistency_integrity manifest")
    final_delivery.add_argument("--title", default="")
    final_delivery.add_argument("--work-label", default="")
    final_delivery.add_argument("--no-manifest-update", action="store_true")
    final_delivery.set_defaults(func=cmd_render_final_delivery)

    export_pdf = subparsers.add_parser("export-report-pdf", help="export a Markdown report to PDF")
    export_pdf.add_argument("--report", required=True)
    export_pdf.add_argument("--output")
    export_pdf.set_defaults(func=cmd_export_report_pdf)

    epub_package = subparsers.add_parser("inspect-epub-package", help="inspect EPUB package metadata")
    epub_package.add_argument("--input", required=True)
    epub_package.add_argument("--output-dir")
    epub_package.set_defaults(func=cmd_inspect_epub_package)

    mark_stage = subparsers.add_parser("mark-stage", help="update one run stage status")
    mark_stage.add_argument("--run-root", required=True)
    mark_stage.add_argument("--stage", required=True)
    mark_stage.add_argument("--status", required=True)
    mark_stage.add_argument("--note")
    mark_stage.add_argument("--allow-new", action="store_true")
    mark_stage.set_defaults(func=cmd_mark_stage)

    intake = subparsers.add_parser("intake", help="ingest one manuscript and create a harness run")
    intake.add_argument("--input", required=True)
    intake.add_argument("--workspace", default="workspace")
    intake.add_argument("--templates", default=str(_repo_root() / "templates"))
    intake.add_argument(
        "--mode",
        default="full",
        choices=[
            "audit",
            "correction",
            "editor",
            "editorial",
            "full",
            "proofread",
            "검수",
            "교정",
            "편집",
            "편집자",
            "전체",
            "표면교정",
        ],
    )
    intake.add_argument("--gate-profile", choices=list(GATE_PROFILE_ORDER), help="override mode-derived gate profile")
    intake.add_argument("--title", default="")
    intake.add_argument("--slug", default="")
    intake.add_argument("--author", default="")
    intake.add_argument("--genre", default="")
    intake.add_argument("--audience", default="")
    intake.add_argument("--platform", default="")
    intake.add_argument("--note", default="")
    intake.add_argument("--analyze", action="store_true", help="run evidence extraction immediately after intake")
    intake.set_defaults(func=cmd_intake)

    intake_box = subparsers.add_parser("intake-inbox", help="ingest all supported files in an inbox")
    intake_box.add_argument("--inbox", default="inbox/initial_manuscripts")
    intake_box.add_argument("--workspace", default="workspace")
    intake_box.add_argument("--templates", default=str(_repo_root() / "templates"))
    intake_box.add_argument(
        "--mode",
        default="full",
        choices=[
            "audit",
            "correction",
            "editor",
            "editorial",
            "full",
            "proofread",
            "검수",
            "교정",
            "편집",
            "편집자",
            "전체",
            "표면교정",
        ],
    )
    intake_box.add_argument("--gate-profile", choices=list(GATE_PROFILE_ORDER), help="override mode-derived gate profile")
    intake_box.add_argument("--genre", default="")
    intake_box.add_argument("--audience", default="")
    intake_box.add_argument("--platform", default="")
    intake_box.add_argument("--analyze", action="store_true", help="run evidence extraction for each ingested file")
    intake_box.set_defaults(func=cmd_intake_inbox)

    list_works = subparsers.add_parser("list-works", help="list works in the workspace")
    list_works.add_argument("--workspace", default="workspace")
    list_works.add_argument("--json", action="store_true")
    list_works.set_defaults(func=cmd_list_works)

    list_runs = subparsers.add_parser("list-runs", help="list runs for one work")
    list_runs.add_argument("--workspace", default="workspace")
    list_runs.add_argument("--work", required=True)
    list_runs.add_argument("--json", action="store_true")
    list_runs.set_defaults(func=cmd_list_runs)

    portfolio = subparsers.add_parser("portfolio-status", help="summarize all work/runs")
    portfolio.add_argument("--workspace", default="workspace")
    portfolio.add_argument("--json", action="store_true")
    portfolio.add_argument("--output")
    portfolio.set_defaults(func=cmd_portfolio_status)

    inspect = subparsers.add_parser("inspect-text", help="inspect text readability and chapter stats")
    inspect.add_argument("--input", required=True)
    inspect.add_argument("--output")
    inspect.set_defaults(func=cmd_inspect_text)

    skeleton = subparsers.add_parser("report-skeleton", help="render a markdown report skeleton")
    skeleton.add_argument("--template", default="templates/report_global_audit.md")
    skeleton.add_argument("--work", required=True)
    skeleton.add_argument("--run", required=True)
    skeleton.add_argument("--title", default="검수 보고서")
    skeleton.add_argument("--output", required=True)
    skeleton.set_defaults(func=cmd_report_skeleton)

    return parser


def main() -> int:
    configure_stdio()
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


def configure_stdio() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass


if __name__ == "__main__":
    raise SystemExit(main())
