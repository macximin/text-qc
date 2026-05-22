from __future__ import annotations

import html
import json
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


ALLOWED_QC_STATUSES = {
    "confirmed_error",
    "confirmed_internal_marker",
    "accepted_direct",
    "contextual_canon",
    "canon_hold",
    "ledger_needed",
    "policy_choice",
    "genre_allowed",
    "blocked",
    "needs_human",
    "style_only",
    "rejected",
}


@dataclass(slots=True)
class QcJsonlValidationResult:
    paths: list[str]
    total: int
    valid: int
    invalid: int
    record_type_counts: dict[str, int]
    status_counts: dict[str, int]
    issues: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class QcHtmlRenderResult:
    paths: list[str]
    output_path: str
    total: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def read_jsonl_objects(path: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    rows: list[dict[str, Any]] = []
    issues: list[dict[str, Any]] = []
    for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not raw_line.strip():
            continue
        try:
            payload = json.loads(raw_line)
        except json.JSONDecodeError as exc:
            issues.append(
                {
                    "path": str(path),
                    "line": line_number,
                    "field": "$",
                    "message": f"invalid JSON: {exc.msg}",
                }
            )
            continue
        if not isinstance(payload, dict):
            issues.append(
                {
                    "path": str(path),
                    "line": line_number,
                    "field": "$",
                    "message": "JSONL row must be an object",
                }
            )
            continue
        rows.append(payload)
    return rows, issues


def validate_qc_jsonl_files(paths: list[Path]) -> QcJsonlValidationResult:
    issues: list[dict[str, Any]] = []
    record_type_counts: Counter[str] = Counter()
    status_counts: Counter[str] = Counter()
    total = 0
    valid = 0

    for path in paths:
        rows, read_issues = read_jsonl_objects(path)
        issues.extend(read_issues)
        for index, row in enumerate(rows, start=1):
            total += 1
            row_issues = validate_qc_row(path, index, row)
            record_type = str(row.get("record_type", "") or "(missing)")
            status = str(row.get("status", "") or "(none)")
            record_type_counts[record_type] += 1
            status_counts[status] += 1
            if row_issues:
                issues.extend(row_issues)
            else:
                valid += 1

    return QcJsonlValidationResult(
        paths=[str(path) for path in paths],
        total=total,
        valid=valid,
        invalid=total - valid + len([issue for issue in issues if issue.get("line")]),
        record_type_counts=dict(record_type_counts),
        status_counts=dict(status_counts),
        issues=issues,
    )


def validate_qc_row(path: Path, index: int, row: dict[str, Any]) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    record_type = str(row.get("record_type", "")).strip()
    status = str(row.get("status", "")).strip()
    row_id = str(row.get("id", "")).strip()

    if not record_type:
        issues.append(qc_issue(path, index, "record_type", "required non-empty string"))
    if not row_id:
        issues.append(qc_issue(path, index, "id", "required non-empty string"))
    if status and status not in ALLOWED_QC_STATUSES:
        issues.append(
            qc_issue(
                path,
                index,
                "status",
                "unknown QC status; keep status vocabulary small and explicit",
            )
        )

    if record_type in {"confirmed", "entity", "hold", "ledger_queue"} and not status:
        issues.append(qc_issue(path, index, "status", "required for actionable QC rows"))
    if record_type == "confirmed":
        for field in ("source", "target", "reason", "action"):
            if row.get(field) in (None, ""):
                issues.append(qc_issue(path, index, field, "required for confirmed rows"))
    if record_type == "issue":
        for field in ("episode", "type", "status", "source", "reason", "action"):
            if row.get(field) in (None, ""):
                issues.append(qc_issue(path, index, field, "required for issue rows"))
        if status == "confirmed_error" and not row.get("target"):
            issues.append(qc_issue(path, index, "target", "required for confirmed_error issue rows"))
    return issues


def qc_issue(path: Path, index: int, field: str, message: str) -> dict[str, Any]:
    return {"path": str(path), "index": index, "field": field, "message": message}


def render_qc_html(*, paths: list[Path], output_path: Path, title: str = "QC Ledger") -> QcHtmlRenderResult:
    rows: list[dict[str, Any]] = []
    for path in paths:
        path_rows, read_issues = read_jsonl_objects(path)
        if read_issues:
            messages = "; ".join(str(issue.get("message", "")) for issue in read_issues[:3])
            raise ValueError(f"cannot render invalid JSONL {path}: {messages}")
        for row in path_rows:
            item = dict(row)
            item["_source_file"] = path.name
            rows.append(item)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(build_qc_html(rows, title=title), encoding="utf-8")
    return QcHtmlRenderResult(paths=[str(path) for path in paths], output_path=str(output_path), total=len(rows))


def build_qc_html(rows: list[dict[str, Any]], *, title: str) -> str:
    body_rows = "\n".join(render_qc_html_row(row) for row in rows)
    escaped_title = html.escape(title)
    return f"""<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <title>{escaped_title}</title>
  <style>
    body {{ font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; margin: 24px; color: #111827; }}
    table {{ border-collapse: collapse; width: 100%; font-size: 13px; }}
    th, td {{ border: 1px solid #d1d5db; padding: 6px 8px; vertical-align: top; }}
    th {{ background: #f3f4f6; position: sticky; top: 0; }}
    code {{ white-space: pre-wrap; }}
    .status-confirmed_error, .status-confirmed_internal_marker, .status-accepted_direct {{ background: #ecfdf5; }}
    .status-canon_hold, .status-ledger_needed, .status-policy_choice, .status-blocked, .status-needs_human {{ background: #fff7ed; }}
  </style>
</head>
<body>
  <h1>{escaped_title}</h1>
  <p>{len(rows)} rows</p>
  <table>
    <thead>
      <tr>
        <th>id</th>
        <th>episode/scope</th>
        <th>type</th>
        <th>status</th>
        <th>source</th>
        <th>target</th>
        <th>reason/evidence/action</th>
        <th>file</th>
      </tr>
    </thead>
    <tbody>
{body_rows}
    </tbody>
  </table>
</body>
</html>
"""


def render_qc_html_row(row: dict[str, Any]) -> str:
    status = str(row.get("status", ""))
    scope = row.get("episode") or row.get("scope") or row.get("axis") or ""
    row_type = row.get("type") or row.get("record_type") or ""
    source = row.get("source") or row.get("terms") or ""
    target = row.get("target") or row.get("canon") or ""
    note = row.get("reason") or row.get("evidence") or row.get("action") or row.get("rule") or ""
    return "      <tr class=\"status-{status}\">{cells}</tr>".format(
        status=html.escape(status),
        cells="".join(
            f"<td><code>{html.escape(render_cell(value))}</code></td>"
            for value in (
                row.get("id", ""),
                scope,
                row_type,
                status,
                source,
                target,
                note,
                row.get("_source_file", ""),
            )
        ),
    )


def render_cell(value: Any) -> str:
    if isinstance(value, list):
        return ", ".join(str(item) for item in value)
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    if value is None:
        return ""
    return str(value)
