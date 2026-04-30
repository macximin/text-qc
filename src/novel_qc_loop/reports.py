from __future__ import annotations

import json
import re
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
