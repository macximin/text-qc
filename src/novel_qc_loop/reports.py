from __future__ import annotations

import html
import json
import os
import re
import shutil
import subprocess
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


CLAIM_LABEL_RE = re.compile(r"(?:^|[\s\-*])(?:주장|판정|문제|리스크)\s*[:：]\s*(?P<value>.+)")
EVIDENCE_LABEL_RE = re.compile(r"(?:^|[\s\-*])(?:근거|증거|원문|위치|수치|예시)\s*[:：]\s*(?P<value>.+)")
PLACEHOLDER_RE = re.compile(r"\bTBD\b|작성 필요|분석 전|없음 또는 항목 작성|미정", re.IGNORECASE)
INTERNAL_ARTIFACT_RE = re.compile(
    r"\b(?:llm-facing|task_brief|manual_review|run_manifest|schema_version|prompt)\b|프롬프트",
    re.IGNORECASE,
)


@dataclass(slots=True)
class ReportValidationResult:
    path: str
    ready_for_delivery: bool
    issue_count: int
    claim_evidence_pair_count: int
    korean_ratio: float
    hangul_count: int
    issues: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def validate_human_report(path: Path) -> ReportValidationResult:
    text = path.read_text(encoding="utf-8")
    issues: list[dict[str, Any]] = []
    korean_stats = calculate_korean_stats(text)
    if korean_stats["hangul_count"] < 80:
        issues.append(
            {
                "code": "too_little_korean",
                "line": None,
                "message": "human-korean-facing 보고서로 보기에는 한국어 본문량이 부족합니다.",
            }
        )
    if korean_stats["korean_ratio"] < 0.55:
        issues.append(
            {
                "code": "not_korean_facing",
                "line": None,
                "message": "영문/내부 표기가 많아 한국어 독자-facing 보고서로 읽히기 어렵습니다.",
            }
        )

    for line_no, line in enumerate(text.splitlines(), start=1):
        if INTERNAL_ARTIFACT_RE.search(line):
            issues.append(
                {
                    "code": "internal_artifact_leak",
                    "line": line_no,
                    "message": "human-facing 보고서에 내부 작업 파일명/프롬프트 용어가 노출되었습니다.",
                    "context": line.strip()[:240],
                }
            )
        if PLACEHOLDER_RE.search(line):
            issues.append(
                {
                    "code": "placeholder_left",
                    "line": line_no,
                    "message": "최종 보고서에 placeholder가 남아 있습니다.",
                    "context": line.strip()[:240],
                }
            )

    pair_count, pair_issues = validate_claim_evidence_pairs(text)
    issues.extend(pair_issues)
    if pair_count == 0:
        issues.append(
            {
                "code": "missing_claim_evidence_pair",
                "line": None,
                "message": "최종 보고서에는 최소 1개 이상의 주장-근거 쌍이 필요합니다.",
            }
        )

    return ReportValidationResult(
        path=str(path),
        ready_for_delivery=not issues,
        issue_count=len(issues),
        claim_evidence_pair_count=pair_count,
        korean_ratio=korean_stats["korean_ratio"],
        hangul_count=korean_stats["hangul_count"],
        issues=issues,
    )


def calculate_korean_stats(text: str) -> dict[str, Any]:
    stripped = strip_markdown_noise(text)
    hangul_count = len(re.findall(r"[가-힣]", stripped))
    latin_count = len(re.findall(r"[A-Za-z]", stripped))
    denominator = max(hangul_count + latin_count, 1)
    return {
        "hangul_count": hangul_count,
        "latin_count": latin_count,
        "korean_ratio": round(hangul_count / denominator, 3),
    }


def strip_markdown_noise(text: str) -> str:
    text = re.sub(r"```.*?```", "", text, flags=re.DOTALL)
    text = re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL)
    text = re.sub(r"`[^`]*`", "", text)
    return text


def validate_claim_evidence_pairs(text: str) -> tuple[int, list[dict[str, Any]]]:
    lines = text.splitlines()
    pair_count = 0
    issues: list[dict[str, Any]] = []

    table_pairs, table_issues = validate_claim_evidence_tables(lines)
    pair_count += table_pairs
    issues.extend(table_issues)

    for idx, line in enumerate(lines):
        claim_match = CLAIM_LABEL_RE.search(line)
        if not claim_match:
            continue
        claim = claim_match.group("value").strip()
        if is_blank_or_placeholder(claim):
            issues.append(
                {
                    "code": "empty_claim",
                    "line": idx + 1,
                    "message": "주장 항목이 비어 있거나 placeholder입니다.",
                    "context": line.strip()[:240],
                }
            )
            continue
        evidence = evidence_near_line(lines, idx)
        if not evidence:
            issues.append(
                {
                    "code": "claim_without_evidence",
                    "line": idx + 1,
                    "message": "주장에는 같은 줄 또는 3줄 이내에 근거/원문/위치/수치가 붙어야 합니다.",
                    "context": line.strip()[:240],
                }
            )
            continue
        pair_count += 1

    return pair_count, issues


def evidence_near_line(lines: list[str], claim_idx: int) -> str:
    for offset in range(0, 4):
        line_idx = claim_idx + offset
        if line_idx >= len(lines):
            break
        evidence_match = EVIDENCE_LABEL_RE.search(lines[line_idx])
        if evidence_match and not is_blank_or_placeholder(evidence_match.group("value")):
            return evidence_match.group("value").strip()
    return ""


def validate_claim_evidence_tables(lines: list[str]) -> tuple[int, list[dict[str, Any]]]:
    pair_count = 0
    issues: list[dict[str, Any]] = []
    idx = 0
    while idx < len(lines):
        line = lines[idx]
        if "|" not in line:
            idx += 1
            continue
        header = split_table_row(line)
        if not header:
            idx += 1
            continue
        claim_col = find_header_index(header, ("주장", "판정", "문제", "리스크"))
        evidence_col = find_header_index(header, ("근거", "증거", "원문", "위치", "수치"))
        if claim_col is None or evidence_col is None:
            idx += 1
            continue

        idx += 1
        if idx < len(lines) and is_markdown_separator_row(lines[idx]):
            idx += 1
        while idx < len(lines) and "|" in lines[idx]:
            cells = split_table_row(lines[idx])
            if not cells:
                idx += 1
                continue
            claim = cells[claim_col].strip() if claim_col < len(cells) else ""
            evidence = cells[evidence_col].strip() if evidence_col < len(cells) else ""
            if is_blank_or_placeholder(claim) and is_blank_or_placeholder(evidence):
                idx += 1
                continue
            if is_blank_or_placeholder(evidence):
                issues.append(
                    {
                        "code": "table_claim_without_evidence",
                        "line": idx + 1,
                        "message": "표의 주장/문제 항목에는 근거 칸이 함께 채워져야 합니다.",
                        "context": lines[idx].strip()[:240],
                    }
                )
            else:
                pair_count += 1
            idx += 1
        continue
    return pair_count, issues


def split_table_row(line: str) -> list[str]:
    stripped = line.strip()
    if not stripped.startswith("|") or not stripped.endswith("|"):
        return []
    return [cell.strip() for cell in stripped.strip("|").split("|")]


def find_header_index(header: list[str], names: tuple[str, ...]) -> int | None:
    for idx, cell in enumerate(header):
        if any(name in cell for name in names):
            return idx
    return None


def is_markdown_separator_row(line: str) -> bool:
    cells = split_table_row(line)
    return bool(cells) and all(re.fullmatch(r":?-{3,}:?", cell.strip()) for cell in cells)


def is_blank_or_placeholder(value: str) -> bool:
    stripped = re.sub(r"<[^>]+>", "", value).strip()
    if not stripped:
        return True
    return bool(PLACEHOLDER_RE.search(stripped))


def write_report_validation_result(result: ReportValidationResult, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def render_reaudit_report(
    *,
    submission_path: Path,
    output_path: Path,
    title: str = "",
    source_label: str = "",
) -> Path:
    payload = json.loads(submission_path.read_text(encoding="utf-8"))
    findings = payload.get("findings") if isinstance(payload.get("findings"), list) else []
    groups = group_reaudit_findings(findings)
    if not any(groups.values()):
        raise ValueError("reaudit report requires at least one finding")
    report_title = title or "재감리 최종 보고서"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        build_reaudit_report_markdown(
            title=report_title,
            source_label=source_label,
            groups=groups,
            remaining_risks=payload.get("remaining_risks") or [],
            final_summary=str(payload.get("final_summary") or "").strip(),
        ),
        encoding="utf-8",
    )
    return output_path


def render_author_final_report(
    *,
    submission_path: Path,
    output_path: Path,
    title: str = "",
    source_label: str = "",
) -> Path:
    payload = json.loads(submission_path.read_text(encoding="utf-8"))
    findings = payload.get("findings") if isinstance(payload.get("findings"), list) else []
    included = [item for item in findings if isinstance(item, dict) and should_include_author_finding(item)]
    if not included:
        raise ValueError("author final report requires at least one deliverable finding")
    report_title = title or "작가전달용 최종검수보고서"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        build_author_final_report_markdown(
            title=report_title,
            source_label=source_label,
            findings=included,
            remaining_risks=payload.get("remaining_risks") or [],
            final_summary=str(payload.get("final_summary") or "").strip(),
        ),
        encoding="utf-8",
    )
    return output_path


def should_include_author_finding(finding: dict[str, Any]) -> bool:
    decision = normalize_report_decision(finding.get("decision") or finding.get("status"))
    if decision == "retracted" and not finding.get("final_priority"):
        return False
    return bool(str(finding.get("claim") or "").strip())


def build_author_final_report_markdown(
    *,
    title: str,
    source_label: str,
    findings: list[dict[str, Any]],
    remaining_risks: list[Any],
    final_summary: str,
) -> str:
    groups = group_author_findings(findings)
    counts = {priority: len(groups.get(priority, [])) for priority in ("P0", "P1", "P2", "P3")}
    lines = [
        f"# {title}",
        "",
    ]
    if source_label:
        lines.extend([f"대상: `{source_label}`", ""])
    lines.extend(
        [
            "## 검수 기준",
            "",
            "이 보고서는 작가님과 편집자가 바로 수정 판단을 할 수 있도록, 발견 사항을 `위치`, `원문 근거`, `문제`, `근거`, `해석`, `수정 방향` 순서로 정리했습니다.",
            "",
            "대체 해석이나 장면상 방어가 가능한 항목은 P0/P1로 올리지 않고 P2 또는 P3 보강 권고로 낮춰 적습니다.",
            "",
            "| 등급 | 의미 |",
            "|---|---|",
            "| P0 | 방어 여지가 거의 없는 핵심 모순입니다. 같은 사건의 정산값이 직접 충돌하거나 주요 승부 장면이 중복 실행되는 수준입니다. |",
            "| P1 | 작품 신뢰도를 크게 흔드는 하드 고증/설정 오류입니다. 날짜, 요일, 금융 제도, 인물 기본정보처럼 독자가 쉽게 확인할 수 있고 대체 해석이 약한 정보입니다. |",
            "| P2 | 장면 연결, 명칭, 소품, 자금 흐름 보강이 필요한 항목입니다. 한 항목만으로 치명적이지는 않지만 누적되면 완성도를 떨어뜨립니다. |",
            "| P3 | 주의, 교정, 표현, 패키징 정리 항목입니다. 빠르게 고칠 수 있고 납품 전 정리하면 좋은 문제입니다. |",
            "",
            "## 우선 수정 순서",
            "",
            f"1. P0 {counts['P0']}건을 먼저 확인합니다.",
            f"2. P1 {counts['P1']}건은 고증과 기본 설정 신뢰도에 영향을 주므로 다음으로 확인합니다.",
            f"3. P2 {counts['P2']}건은 장면 연결과 산식 보강 중심으로 정리합니다.",
            f"4. P3 {counts['P3']}건은 최종 교정 단계에서 함께 처리합니다.",
        ]
    )
    if final_summary:
        lines.extend(["", "## 한줄 판정", "", final_summary])

    section_titles = {
        "P0": "방어 여지가 거의 없는 핵심 모순",
        "P1": "작품 신뢰도를 크게 흔드는 하드 오류",
        "P2": "중요 보강 권장",
        "P3": "주의/교정/폴리싱 권장",
    }
    for priority in ("P0", "P1", "P2", "P3"):
        rows = groups.get(priority, [])
        if not rows:
            continue
        lines.extend(["", "---", "", f"## {priority}. {section_titles[priority]}", ""])
        for index, finding in enumerate(rows, start=1):
            lines.extend(render_author_finding(priority, index, finding))
            lines.append("")

    if remaining_risks:
        lines.extend(["", "---", "", "## 남은 리스크", ""])
        for risk in remaining_risks:
            lines.append(f"- {risk}")

    return "\n".join(lines).rstrip() + "\n"


def group_author_findings(findings: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    groups: dict[str, list[dict[str, Any]]] = {priority: [] for priority in ("P0", "P1", "P2", "P3")}
    for finding in findings:
        priority = effective_priority(finding)
        groups.setdefault(priority, []).append(finding)
    for rows in groups.values():
        rows.sort(
            key=lambda row: (
                priority_sort_key(effective_priority(row)),
                -coerce_confidence(row.get("confidence_percent")),
                str(row.get("claim") or ""),
            )
        )
    return groups


def effective_priority(finding: dict[str, Any]) -> str:
    priority = str(finding.get("final_priority") or finding.get("priority") or "").strip()
    return priority if priority in {"P0", "P1", "P2", "P3"} else "P3"


def render_author_finding(priority: str, index: int, finding: dict[str, Any]) -> list[str]:
    title = str(finding.get("claim") or "").strip()
    decision = decision_label(finding.get("decision") or finding.get("status"))
    original_priority = str(finding.get("original_priority") or "").strip()
    confidence = format_confidence(finding.get("confidence_percent"))
    evidence = str(finding.get("evidence") or "").strip()
    evidence_snippet = str(finding.get("evidence_snippet") or "").strip()
    rationale = str(finding.get("rationale") or "").strip()
    counter = str(finding.get("counter_evidence") or "").strip()
    reader_risk = str(finding.get("reader_risk") or "").strip()
    fix_hint = str(finding.get("fix_hint") or "").strip()
    lines = [f"### {priority}-{index:02d}. {title}", ""]
    if evidence:
        lines.extend([f"위치: `{evidence}`", ""])
    if evidence_snippet:
        lines.extend(["원문 근거:", ""])
        lines.extend(format_evidence_snippet(evidence_snippet))
        lines.append("")
    lines.extend([f"문제: {title}", ""])
    basis_parts = []
    if rationale:
        basis_parts.append(rationale)
    if confidence != "-":
        basis_parts.append(f"검수 확신도는 {confidence}입니다.")
    if decision == "강등" and original_priority:
        basis_parts.append(f"초기 등급 {original_priority}에서 {priority}로 낮춘 항목입니다.")
    elif decision == "철회" and finding.get("final_priority"):
        basis_parts.append(f"강한 오류로 보지 않고 {priority} 참고 항목으로 남겼습니다.")
    lines.extend([f"근거: {' '.join(basis_parts) if basis_parts else '원문 근거를 기준으로 확인이 필요합니다.'}", ""])
    interpretation_parts = []
    if counter:
        interpretation_parts.append(f"방어 가능한 해석: {counter}")
    if reader_risk:
        interpretation_parts.append(f"독자 영향: {reader_risk}")
    if not interpretation_parts:
        interpretation_parts.append("해당 표현은 독자가 앞뒤 문맥을 다시 계산하게 만들 수 있습니다.")
    lines.extend([f"해석: {' '.join(interpretation_parts)}", ""])
    lines.append(f"수정 방향: {fix_hint or '작가 의도에 맞춰 표기, 산식, 장면 브릿지 중 하나를 보강합니다.'}")
    return lines


def format_evidence_snippet(value: str) -> list[str]:
    lines = [line.strip() for line in value.splitlines() if line.strip()]
    if not lines:
        return []
    if len(lines) == 1:
        return [f"- {lines[0]}"]
    formatted = []
    for line in lines:
        formatted.append(line if line.startswith(("-", "*")) else f"- {line}")
    return formatted


def group_reaudit_findings(findings: list[Any]) -> dict[str, list[dict[str, Any]]]:
    groups: dict[str, list[dict[str, Any]]] = {
        "confirmed": [],
        "downgraded": [],
        "retracted": [],
        "deferred": [],
    }
    for item in findings:
        if not isinstance(item, dict):
            continue
        decision = normalize_report_decision(item.get("decision") or item.get("status"))
        groups.setdefault(decision, []).append(item)
    for rows in groups.values():
        rows.sort(
            key=lambda row: (
                priority_sort_key(str(row.get("final_priority") or row.get("priority") or "")),
                -coerce_confidence(row.get("confidence_percent")),
            )
        )
    return groups


def build_reaudit_report_markdown(
    *,
    title: str,
    source_label: str,
    groups: dict[str, list[dict[str, Any]]],
    remaining_risks: list[Any],
    final_summary: str,
) -> str:
    confirmed = groups.get("confirmed", [])
    downgraded = groups.get("downgraded", [])
    retracted = groups.get("retracted", [])
    deferred = groups.get("deferred", [])
    lines = [
        f"# {title}",
        "",
        "## 한줄 판정",
        "",
        f"- 주장: 95% 이상 확신으로 유지할 항목은 {len(confirmed)}건입니다.",
        f"- 근거: 확정 {len(confirmed)}건, 강등 {len(downgraded)}건, 철회 {len(retracted)}건, 유보 {len(deferred)}건으로 분리했습니다.",
    ]
    if source_label:
        lines.append(f"- 원문 기준: {source_label}")
    if final_summary:
        lines.extend(["", final_summary])

    lines.extend(["", "## 95% 이상 확정", ""])
    lines.extend(render_finding_table(confirmed, include_counter=False))
    lines.extend(["", "## 강등 또는 완화", ""])
    lines.extend(render_finding_table(downgraded, include_counter=True))
    lines.extend(["", "## 철회", ""])
    lines.extend(render_finding_table(retracted, include_counter=True))
    if deferred:
        lines.extend(["", "## 유보", ""])
        lines.extend(render_finding_table(deferred, include_counter=True))
    if remaining_risks:
        lines.extend(["", "## 남은 리스크", ""])
        for risk in remaining_risks:
            lines.append(f"- {risk}")
    lines.extend(
        [
            "",
            "## 전달 원칙",
            "",
            "- 주장: 확정 항목은 원문 위치와 근거가 붙은 경우에만 강하게 전달합니다.",
            "- 근거: 강등/철회 항목은 반례 또는 방어 가능한 해석을 함께 남겼습니다.",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def render_finding_table(findings: list[dict[str, Any]], *, include_counter: bool) -> list[str]:
    if not findings:
        return ["- 해당 없음."]
    headers = ["우선순위", "판정", "확신", "주장", "근거", "처리 방향"]
    if include_counter:
        headers.insert(5, "반례/완화 사유")
    rows = ["| " + " | ".join(headers) + " |", "|" + "|".join("---" for _ in headers) + "|"]
    for finding in findings:
        priority = str(finding.get("final_priority") or finding.get("priority") or "")
        if finding.get("original_priority") and finding.get("final_priority"):
            priority = f"{finding.get('original_priority')}->{finding.get('final_priority')}"
        cells = [
            priority,
            decision_label(finding.get("decision") or finding.get("status")),
            format_confidence(finding.get("confidence_percent")),
            table_cell(str(finding.get("claim") or "")),
            table_cell(str(finding.get("evidence_snippet") or finding.get("evidence") or "")),
        ]
        if include_counter:
            cells.append(table_cell(str(finding.get("counter_evidence") or finding.get("rationale") or "")))
        cells.append(table_cell(str(finding.get("fix_hint") or "")))
        rows.append("| " + " | ".join(cells) + " |")
    return rows


def normalize_report_decision(value: Any) -> str:
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
    return aliases.get(text, "deferred")


def decision_label(value: Any) -> str:
    normalized = normalize_report_decision(value)
    return {
        "confirmed": "확정",
        "downgraded": "강등",
        "retracted": "철회",
        "deferred": "유보",
    }.get(normalized, "유보")


def format_confidence(value: Any) -> str:
    if value is None or value == "":
        return "-"
    return f"{coerce_confidence(value)}%"


def coerce_confidence(value: Any) -> int:
    if isinstance(value, bool):
        return 0
    if isinstance(value, int):
        return max(0, min(100, value))
    if isinstance(value, str):
        match = re.search(r"\d+", value)
        if match:
            return max(0, min(100, int(match.group(0))))
    return 0


def priority_sort_key(value: str) -> int:
    return {"P0": 0, "P1": 1, "P2": 2, "P3": 3}.get(value, 9)


def table_cell(value: str) -> str:
    text = re.sub(r"\s+", " ", value).strip()
    return text.replace("|", "/")[:420]


def export_markdown_to_pdf(markdown_path: Path, output_path: Path) -> Path:
    markdown_path = markdown_path.resolve()
    output_path = output_path.resolve()
    if not markdown_path.exists():
        raise FileNotFoundError(markdown_path)
    chrome_path = find_chromium_executable()
    if not chrome_path:
        raise RuntimeError(
            "Chrome/Edge/Playwright Chromium executable not found. "
            "Set CHROME_PATH or install a Chromium-compatible browser."
        )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    html_text = markdown_to_standalone_html(markdown_path.read_text(encoding="utf-8"), title=markdown_path.stem)
    with tempfile.TemporaryDirectory(prefix="novel-qc-report-") as temp_dir:
        html_path = Path(temp_dir) / "report.html"
        html_path.write_text(html_text, encoding="utf-8")
        args = [
            str(chrome_path),
            "--headless=new",
            "--disable-gpu",
            "--no-pdf-header-footer",
            f"--print-to-pdf={output_path}",
            html_path.resolve().as_uri(),
        ]
        result = subprocess.run(args, capture_output=True, text=True, check=False)
        if result.returncode != 0:
            fallback_args = args.copy()
            fallback_args[1] = "--headless"
            result = subprocess.run(fallback_args, capture_output=True, text=True, check=False)
        if result.returncode != 0:
            raise RuntimeError(
                "PDF export failed: "
                + (result.stderr or result.stdout or f"exit code {result.returncode}").strip()
            )
    if not output_path.exists() or output_path.stat().st_size == 0:
        raise RuntimeError(f"PDF export did not create output: {output_path}")
    return output_path


def find_chromium_executable() -> Path | None:
    candidates: list[Path] = []
    env_path = re.sub(r"^['\"]|['\"]$", "", str(os.environ.get("CHROME_PATH", "")).strip())
    if env_path:
        candidates.append(Path(env_path))
    for name in ("msedge", "chrome", "chromium", "google-chrome"):
        found = shutil.which(name)
        if found:
            candidates.append(Path(found))
    home = Path.home()
    candidates.extend(
        [
            home / "AppData/Local/Google/Chrome/Application/chrome.exe",
            home / "AppData/Local/Microsoft/Edge/Application/msedge.exe",
            Path("C:/Program Files/Google/Chrome/Application/chrome.exe"),
            Path("C:/Program Files (x86)/Google/Chrome/Application/chrome.exe"),
            Path("C:/Program Files/Microsoft/Edge/Application/msedge.exe"),
            Path("C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe"),
        ]
    )
    playwright_root = home / "AppData/Local/ms-playwright"
    if playwright_root.exists():
        candidates.extend(sorted(playwright_root.glob("chromium-*/chrome-win64/chrome.exe"), reverse=True))
        candidates.extend(
            sorted(
                playwright_root.glob("chromium_headless_shell-*/chrome-headless-shell-win64/chrome-headless-shell.exe"),
                reverse=True,
            )
        )
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def markdown_to_standalone_html(markdown: str, *, title: str) -> str:
    body = markdown_to_html(markdown)
    css = """
      @page { size: A4; margin: 18mm 16mm 18mm 16mm; }
      * { box-sizing: border-box; }
      body {
        margin: 0;
        color: #111827;
        font-family: "Malgun Gothic", "맑은 고딕", "Noto Sans CJK KR", "Noto Sans KR", Arial, sans-serif;
        font-size: 10.5pt;
        line-height: 1.58;
        word-break: keep-all;
        overflow-wrap: anywhere;
      }
      h1, h2, h3 { color: #111827; line-height: 1.25; break-after: avoid; }
      h1 { font-size: 22pt; margin: 0 0 14mm; padding-bottom: 5mm; border-bottom: 2px solid #111827; }
      h2 { font-size: 16pt; margin: 12mm 0 4mm; padding-top: 2mm; border-top: 1px solid #d1d5db; }
      h3 { font-size: 12.5pt; margin: 8mm 0 3mm; }
      p { margin: 0 0 3.2mm; }
      ul, ol { margin-top: 2mm; margin-bottom: 4mm; padding-left: 6mm; }
      li { margin: 1.4mm 0; }
      table { width: 100%; border-collapse: collapse; margin: 4mm 0 6mm; font-size: 9.2pt; }
      th, td { border: 1px solid #d1d5db; padding: 2.2mm 2.5mm; vertical-align: top; }
      th { background: #f3f4f6; font-weight: 700; }
      tr { break-inside: avoid; }
      code {
        font-family: Consolas, "D2Coding", "Courier New", monospace;
        font-size: 0.92em;
        background: #f3f4f6;
        border: 1px solid #e5e7eb;
        border-radius: 3px;
        padding: 0.2mm 0.8mm;
        word-break: break-all;
      }
      a { color: #1d4ed8; text-decoration: none; word-break: break-all; }
      hr { border: 0; border-top: 1px solid #d1d5db; margin: 7mm 0; }
      strong { font-weight: 700; }
    """
    return (
        "<!doctype html><html lang=\"ko\"><head><meta charset=\"utf-8\">"
        f"<title>{html.escape(title)}</title><style>{css}</style></head><body>{body}</body></html>"
    )


def markdown_to_html(markdown: str) -> str:
    lines = markdown.splitlines()
    chunks: list[str] = []
    idx = 0
    while idx < len(lines):
        line = lines[idx]
        stripped = line.strip()
        if not stripped:
            idx += 1
            continue
        if stripped == "---":
            chunks.append("<hr>")
            idx += 1
            continue
        heading = re.match(r"^(#{1,6})\s+(.+)$", stripped)
        if heading:
            level = len(heading.group(1))
            chunks.append(f"<h{level}>{inline_markdown(heading.group(2))}</h{level}>")
            idx += 1
            continue
        if stripped.startswith("|") and stripped.endswith("|"):
            table_lines = []
            while idx < len(lines) and lines[idx].strip().startswith("|") and lines[idx].strip().endswith("|"):
                table_lines.append(lines[idx].strip())
                idx += 1
            chunks.append(markdown_table_to_html(table_lines))
            continue
        if re.match(r"^[-*]\s+", stripped):
            items = []
            while idx < len(lines) and re.match(r"^[-*]\s+", lines[idx].strip()):
                items.append(re.sub(r"^[-*]\s+", "", lines[idx].strip()))
                idx += 1
            chunks.append("<ul>" + "".join(f"<li>{inline_markdown(item)}</li>" for item in items) + "</ul>")
            continue
        if re.match(r"^\d+\.\s+", stripped):
            items = []
            while idx < len(lines) and re.match(r"^\d+\.\s+", lines[idx].strip()):
                items.append(re.sub(r"^\d+\.\s+", "", lines[idx].strip()))
                idx += 1
            chunks.append("<ol>" + "".join(f"<li>{inline_markdown(item)}</li>" for item in items) + "</ol>")
            continue
        paragraph = [stripped]
        idx += 1
        while idx < len(lines) and lines[idx].strip() and not starts_markdown_block(lines[idx].strip()):
            paragraph.append(lines[idx].strip())
            idx += 1
        chunks.append(f"<p>{inline_markdown(' '.join(paragraph))}</p>")
    return "\n".join(chunks)


def starts_markdown_block(stripped: str) -> bool:
    return (
        stripped == "---"
        or stripped.startswith("#")
        or stripped.startswith("|")
        or bool(re.match(r"^[-*]\s+", stripped))
        or bool(re.match(r"^\d+\.\s+", stripped))
    )


def markdown_table_to_html(table_lines: list[str]) -> str:
    rows = [split_table_row(line) for line in table_lines]
    rows = [row for row in rows if row]
    if not rows:
        return ""
    header = rows[0]
    body_rows = rows[1:]
    if body_rows and all(re.fullmatch(r":?-{3,}:?", cell.strip()) for cell in body_rows[0]):
        body_rows = body_rows[1:]
    html_rows = [
        "<thead><tr>" + "".join(f"<th>{inline_markdown(cell)}</th>" for cell in header) + "</tr></thead>"
    ]
    if body_rows:
        html_rows.append(
            "<tbody>"
            + "".join(
                "<tr>" + "".join(f"<td>{inline_markdown(cell)}</td>" for cell in row) + "</tr>"
                for row in body_rows
            )
            + "</tbody>"
        )
    return "<table>" + "".join(html_rows) + "</table>"


def inline_markdown(value: str) -> str:
    code_spans: list[str] = []

    def code_repl(match: re.Match[str]) -> str:
        code_spans.append(f"<code>{html.escape(match.group(1))}</code>")
        return f"\u0000CODE{len(code_spans) - 1}\u0000"

    text = re.sub(r"`([^`]*)`", code_repl, value)
    text = html.escape(text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(
        r"\[([^\]]+)\]\(([^)]+)\)",
        lambda m: f'<a href="{html.escape(m.group(2), quote=True)}">{m.group(1)}</a>',
        text,
    )
    for index, code in enumerate(code_spans):
        text = text.replace(f"\u0000CODE{index}\u0000", code)
    return text
