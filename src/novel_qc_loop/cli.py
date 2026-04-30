from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .analyze import analyze_run
from .corrections import validate_changes_file, write_validation_result
from .intake import intake_inbox, intake_manuscript
from .submission import validate_manual_review_submission, write_submission_validation_result
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
        source_text_path=args.source,
        notes=args.note or [],
    )
    print(f"created run: {run_root}")
    return 0


def cmd_analyze_run(args: argparse.Namespace) -> int:
    result = analyze_run(run_root=Path(args.run_root).resolve())
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


def refresh_submission_gate(run_root: Path, validation: dict[str, Any]) -> None:
    gate_path = run_root / "evidence" / "submission" / "submission_gate.json"
    gate = read_json(gate_path) if gate_path.exists() else {"schema_version": "submission_gate.v1"}
    blockers = [str(item) for item in gate.get("blockers", [])]
    blockers = [item for item in blockers if item != "manual_review_not_complete"]
    if not validation.get("ready_for_submission"):
        blockers.append("manual_review_not_complete")
    gate["manual_review"] = validation
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
    start_run.add_argument("--source", default="")
    start_run.add_argument("--note", action="append")
    start_run.set_defaults(func=cmd_start_run)

    analyze = subparsers.add_parser("analyze-run", help="build facts/review evidence for one run")
    analyze.add_argument("--run-root", required=True)
    analyze.set_defaults(func=cmd_analyze_run)

    validate_changes = subparsers.add_parser("validate-changes", help="validate correction changes JSON")
    validate_changes.add_argument("--changes", required=True)
    validate_changes.add_argument("--output")
    validate_changes.set_defaults(func=cmd_validate_changes)

    validate_submission = subparsers.add_parser("validate-submission", help="validate manual review submission JSON")
    validate_submission.add_argument("--submission")
    validate_submission.add_argument("--run-root")
    validate_submission.add_argument("--output")
    validate_submission.set_defaults(func=cmd_validate_submission)

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
    intake.add_argument("--mode", default="full", choices=["audit", "correction", "full", "검수", "교정", "전체"])
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
    intake_box.add_argument("--mode", default="full", choices=["audit", "correction", "full", "검수", "교정", "전체"])
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
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
