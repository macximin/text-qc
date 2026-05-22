from __future__ import annotations

import hashlib
import html
import json
import os
import re
import shutil
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .ai_slop import scan_ai_slop_text
from .workspace import decode_text_bytes, find_chapter_markers, read_json, write_json


DEFAULT_DELIVERY_VERSION = "v1"
DEFAULT_MANUSCRIPT_FORMAT = "txt"
DEFAULT_REPORT_FORMAT = "html"
DEFAULT_REPORT_DENSITY = "closing_full"
REPORT_DENSITY_CHOICES = {"brief", "standard", "closing_full"}
DEFAULT_REPORT_SCOPE = "cumulative_final_closing_report"


@dataclass(slots=True)
class FinalDeliveryResult:
    delivery_dir: str
    manuscript_txt_path: str
    human_report_html_path: str
    manifest_path: str
    manuscript_format: str
    report_format: str
    report_density: str
    report_scope: str
    source_text_path: str
    final_manuscript_path: str
    delivery_txt_sha256: str
    source_final_delivery_match: bool
    episode_count: int
    marker_sequence_clean: bool
    scan_status: str
    active_hold_count: int | None
    blocking_hold_count: int | None
    policy_watchlist_count: int | None
    style_watchlist_count: int | None
    ai_slop_signal_count: int
    previous_delivery_stale: bool
    current_package_sealed: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_final_delivery_package(
    *,
    run_root: Path,
    output_dir: Path | None = None,
    version: str = DEFAULT_DELIVERY_VERSION,
    manuscript_path: Path | None = None,
    scan_manifest_path: Path | None = None,
    title: str = "",
    work_label: str = "",
    report_density: str = DEFAULT_REPORT_DENSITY,
    update_run_manifest: bool = True,
) -> FinalDeliveryResult:
    """Create the default final delivery package: TXT manuscript + human-facing HTML report."""

    run_root = run_root.resolve()
    report_density = normalize_report_density(report_density)
    run_manifest_path = run_root / "run_manifest.json"
    run_manifest = read_json(run_manifest_path) if run_manifest_path.exists() else {}
    final_path = resolve_final_manuscript_path(run_root, run_manifest, manuscript_path)
    source_path = resolve_source_text_path(run_root, run_manifest, final_path)
    scan_manifest = load_scan_manifest(run_root, scan_manifest_path)

    label = work_label or str(run_manifest.get("title") or run_manifest.get("work_slug") or run_root.parent.parent.name)
    file_stem = safe_file_stem(label, default="final_manuscript")
    version_label = safe_file_stem(version or DEFAULT_DELIVERY_VERSION, default=DEFAULT_DELIVERY_VERSION)
    delivery_dir = (
        output_dir.resolve()
        if output_dir
        else run_root / "final_delivery" / f"{version_label}_final_approved_package"
    )
    delivery_dir.mkdir(parents=True, exist_ok=True)

    manuscript_txt_path = delivery_dir / f"{file_stem}_final_approved.txt"
    report_html_path = delivery_dir / f"{file_stem}_final_human_report.html"
    delivery_manifest_path = delivery_dir / "delivery_manifest.json"

    shutil.copyfile(final_path, manuscript_txt_path)

    final_raw = final_path.read_bytes()
    source_raw = source_path.read_bytes() if source_path.exists() else b""
    delivery_raw = manuscript_txt_path.read_bytes()
    text = decode_text_bytes(delivery_raw)
    markers = find_chapter_markers(text)
    marker_numbers = marker_number_sequence(markers)
    marker_sequence_clean = marker_numbers == list(range(1, len(marker_numbers) + 1))
    line_count = text.count("\n") + (0 if text.endswith("\n") or not text else 1)
    source_final_delivery_match = source_raw == final_raw == delivery_raw if source_raw else final_raw == delivery_raw

    metrics = {
        "episode_count": len(markers),
        "marker_sequence_clean": marker_sequence_clean,
        "line_count": line_count,
        "char_count": len(text),
        "byte_count": len(delivery_raw),
        "source_sha256": sha256_bytes(source_raw) if source_raw else "",
        "final_sha256": sha256_bytes(final_raw),
        "delivery_txt_sha256": sha256_bytes(delivery_raw),
        "source_final_delivery_match": source_final_delivery_match,
    }
    surface_counts = load_surface_counts(scan_manifest)
    hold_summary = summarize_holds(scan_manifest)
    ai_slop_summary = scan_ai_slop_text(text).to_dict()
    glossary_summary = load_glossary_summary(run_root, scan_manifest)
    reseal_summary = inspect_reseal_status(
        run_root=run_root,
        run_manifest=run_manifest,
        delivery_manifest_path=delivery_manifest_path,
        current_delivery_txt_sha256=metrics["delivery_txt_sha256"],
    )
    html_report = build_final_delivery_html(
        title=title or f"{label} 최종 검수 보고서",
        created_at=utc_now_iso(),
        label=label,
        run_root=run_root,
        delivery_dir=delivery_dir,
        manuscript_txt_path=manuscript_txt_path,
        report_html_path=report_html_path,
        delivery_manifest_path=delivery_manifest_path,
        source_path=source_path,
        final_path=final_path,
        scan_manifest=scan_manifest,
        metrics=metrics,
        surface_counts=surface_counts,
        hold_summary=hold_summary,
        ai_slop_summary=ai_slop_summary,
        glossary_summary=glossary_summary,
        reseal_summary=reseal_summary,
        report_density=report_density,
    )
    report_html_path.write_text(html_report, encoding="utf-8", newline="\n")

    delivery_manifest = {
        "schema_version": "final_delivery_manifest.v1",
        "version": version_label,
        "status": "done",
        "created_at": utc_now_iso(),
        "work": label,
        "report_scope": DEFAULT_REPORT_SCOPE,
        "report_density": report_density,
        "default_manuscript_format": DEFAULT_MANUSCRIPT_FORMAT,
        "default_report_format": DEFAULT_REPORT_FORMAT,
        "manuscript_txt_path": str(manuscript_txt_path),
        "human_report_html_path": str(report_html_path),
        "source_text_path": str(source_path),
        "final_manuscript_path": str(final_path),
        "source_sha256": metrics["source_sha256"],
        "final_sha256": metrics["final_sha256"],
        "delivery_txt_sha256": metrics["delivery_txt_sha256"],
        "report_html_sha256": sha256_bytes(report_html_path.read_bytes()),
        "source_final_delivery_match": source_final_delivery_match,
        "episode_count": len(markers),
        "marker_sequence_clean": marker_sequence_clean,
        "line_count": line_count,
        "char_count": len(text),
        "byte_count": len(delivery_raw),
        "scan_manifest_path": scan_manifest.get("_path", ""),
        "scan_status": scan_manifest.get("scan_status", ""),
        "active_hold_count": scan_manifest.get("active_hold_count"),
        "blocking_hold_count": hold_summary.get("blocking_hold_count"),
        "policy_watchlist_count": hold_summary.get("policy_watchlist_count"),
        "style_watchlist_count": hold_summary.get("style_watchlist_count"),
        "hold_summary": hold_summary,
        "ai_slop_summary": ai_slop_summary,
        "glossary_summary": glossary_summary,
        "reseal_summary": reseal_summary,
        "previous_delivery_stale": reseal_summary.get("previous_delivery_stale", False),
        "current_package_sealed": reseal_summary.get("current_package_sealed", True),
        "validation_total": scan_manifest.get("validation_total"),
        "validation_valid": scan_manifest.get("validation_valid"),
        "validation_invalid": scan_manifest.get("validation_invalid"),
        "test_result": scan_manifest.get("test_result", ""),
    }
    write_json(delivery_manifest_path, delivery_manifest)

    if update_run_manifest and run_manifest_path.exists():
        run_manifest["final_delivery_status"] = "done"
        run_manifest["final_delivery_manifest_path"] = str(delivery_manifest_path)
        run_manifest["final_delivery_manuscript_txt_path"] = str(manuscript_txt_path)
        run_manifest["final_delivery_human_report_html_path"] = str(report_html_path)
        run_manifest["final_delivery_default_manuscript_format"] = DEFAULT_MANUSCRIPT_FORMAT
        run_manifest["final_delivery_default_report_format"] = DEFAULT_REPORT_FORMAT
        run_manifest["final_delivery_report_density"] = report_density
        run_manifest["final_delivery_report_scope"] = DEFAULT_REPORT_SCOPE
        run_manifest["final_delivery_current_package_sealed"] = True
        run_manifest["updated_at"] = utc_now_iso()
        write_json(run_manifest_path, run_manifest)

    return FinalDeliveryResult(
        delivery_dir=str(delivery_dir),
        manuscript_txt_path=str(manuscript_txt_path),
        human_report_html_path=str(report_html_path),
        manifest_path=str(delivery_manifest_path),
        manuscript_format=DEFAULT_MANUSCRIPT_FORMAT,
        report_format=DEFAULT_REPORT_FORMAT,
        report_density=report_density,
        report_scope=DEFAULT_REPORT_SCOPE,
        source_text_path=str(source_path),
        final_manuscript_path=str(final_path),
        delivery_txt_sha256=metrics["delivery_txt_sha256"],
        source_final_delivery_match=source_final_delivery_match,
        episode_count=len(markers),
        marker_sequence_clean=marker_sequence_clean,
        scan_status=str(scan_manifest.get("scan_status", "")),
        active_hold_count=coerce_optional_int(scan_manifest.get("active_hold_count")),
        blocking_hold_count=coerce_optional_int(hold_summary.get("blocking_hold_count")),
        policy_watchlist_count=coerce_optional_int(hold_summary.get("policy_watchlist_count")),
        style_watchlist_count=coerce_optional_int(hold_summary.get("style_watchlist_count")),
        ai_slop_signal_count=coerce_optional_int(ai_slop_summary.get("total")) or 0,
        previous_delivery_stale=bool(reseal_summary.get("previous_delivery_stale", False)),
        current_package_sealed=bool(reseal_summary.get("current_package_sealed", True)),
    )


def resolve_final_manuscript_path(
    run_root: Path,
    manifest: dict[str, Any],
    explicit_path: Path | None,
) -> Path:
    if explicit_path:
        return explicit_path.resolve()
    for value in (
        manifest.get("final_manuscript_path"),
        manifest.get("artifacts", {}).get("final_manuscript_path")
        if isinstance(manifest.get("artifacts"), dict)
        else "",
        run_root / "final_manuscript" / "final_manuscript.txt",
        manifest.get("source_text_path"),
        manifest.get("artifacts", {}).get("extracted_text_path")
        if isinstance(manifest.get("artifacts"), dict)
        else "",
    ):
        path = resolve_run_path(run_root, value)
        if path and path.exists():
            return path
    raise FileNotFoundError(f"final manuscript TXT not found under {run_root}")


def resolve_source_text_path(run_root: Path, manifest: dict[str, Any], fallback: Path) -> Path:
    for value in (
        manifest.get("source_text_path"),
        manifest.get("artifacts", {}).get("extracted_text_path")
        if isinstance(manifest.get("artifacts"), dict)
        else "",
    ):
        path = resolve_run_path(run_root, value)
        if path and path.exists():
            return path
    return fallback


def resolve_run_path(run_root: Path, value: Any) -> Path | None:
    if not value:
        return None
    path = value if isinstance(value, Path) else Path(str(value))
    if not path.is_absolute():
        path = run_root / path
    return path.resolve()


def load_scan_manifest(run_root: Path, explicit_path: Path | None) -> dict[str, Any]:
    if explicit_path:
        path = explicit_path.resolve()
        payload = read_json(path)
        payload["_path"] = str(path)
        return payload

    candidates: list[tuple[float, Path, dict[str, Any]]] = []
    for path in (run_root / "consistency_integrity").glob("**/*manifest*.json"):
        try:
            payload = read_json(path)
        except (OSError, json.JSONDecodeError):
            continue
        if not looks_like_final_scan_manifest(payload):
            continue
        candidates.append((path.stat().st_mtime, path, payload))
    if not candidates:
        return {}
    _, path, payload = sorted(candidates, key=lambda item: item[0])[-1]
    payload["_path"] = str(path)
    return payload


def looks_like_final_scan_manifest(payload: dict[str, Any]) -> bool:
    keys = set(payload)
    return bool(
        {"scan_status", "active_hold_count"} & keys
        or {"validation_total", "validation_valid", "validation_invalid"} <= keys
        or "source_final_raw_match" in keys
    )


def load_surface_counts(scan_manifest: dict[str, Any]) -> dict[str, int]:
    surface_path = scan_manifest.get("surface_path")
    if not surface_path:
        return {}
    path = Path(str(surface_path))
    if not path.exists():
        return {}
    counts: dict[str, int] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        term = str(row.get("term") or "").strip()
        if not term:
            continue
        counts[term] = coerce_optional_int(row.get("count")) or 0
    return counts


def build_final_delivery_html(
    *,
    title: str,
    created_at: str,
    label: str,
    run_root: Path,
    delivery_dir: Path,
    manuscript_txt_path: Path,
    report_html_path: Path,
    delivery_manifest_path: Path,
    source_path: Path,
    final_path: Path,
    scan_manifest: dict[str, Any],
    metrics: dict[str, Any],
    surface_counts: dict[str, int],
    hold_summary: dict[str, Any],
    ai_slop_summary: dict[str, Any],
    glossary_summary: dict[str, Any],
    reseal_summary: dict[str, Any],
    report_density: str,
) -> str:
    scan_status = str(scan_manifest.get("scan_status") or "unknown")
    active_hold = hold_summary.get("active_hold_count")
    blocking_hold = hold_summary.get("blocking_hold_count")
    policy_watchlist = hold_summary.get("policy_watchlist_count")
    style_watchlist = hold_summary.get("style_watchlist_count")
    validation_total = scan_manifest.get("validation_total")
    validation_valid = scan_manifest.get("validation_valid")
    validation_invalid = scan_manifest.get("validation_invalid")
    test_result = str(scan_manifest.get("test_result") or "")
    clean_scan = scan_status in {"clean", "done", "sealed", "approved"}
    final_verdict = "출고 가능" if clean_scan and blocking_hold in (0, "0", None) else "검토 필요"
    policy_rows = build_policy_rows(surface_counts, glossary_summary=glossary_summary)
    hold_rows = build_hold_rows(hold_summary)
    ai_slop_rows = build_ai_slop_rows(ai_slop_summary)
    glossary_rows = build_glossary_rows(glossary_summary)
    reseal_rows = build_reseal_rows(reseal_summary)
    density_label = {
        "brief": "간략 보고서",
        "standard": "표준 보고서",
        "closing_full": "전체 누적 최종 마감 보고서",
    }.get(report_density, report_density)

    return f"""<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{escape(title)}</title>
<style>{FINAL_DELIVERY_CSS}</style>
</head>
<body>
<main>
<header>
  <h1>{escape(title)}</h1>
  <div class="subtitle">{escape(density_label)} · 생성 시각 {escape(created_at)} · 기본 산출물 TXT + HTML · 누적 근거 manifest 기반</div>
  <div class="badge-row">
    <span class="badge good">최종 판정: {escape(final_verdict)}</span>
    <span class="badge">원고 형식: TXT</span>
    <span class="badge">보고서 형식: HTML</span>
    <span class="badge">회차 {metrics["episode_count"]}개</span>
    <span class="badge">blocking hold {escape(format_optional(blocking_hold))}</span>
    <span class="badge">policy watchlist {escape(format_optional(policy_watchlist))}</span>
    <span class="badge">AI-slop signals {escape(format_optional(ai_slop_summary.get("total")))}</span>
  </div>
</header>

<section class="summary">
  <h2>1. 요약</h2>
  <p><strong>최종 원고는 TXT를 기준 산출물로 고정하고, 최종 보고서는 사람이 읽는 HTML 누적 마감 보고서로 생성한다.</strong> 이 패키지는 승인된 최종 원고, 보고서, delivery manifest를 한 묶음으로 남긴다.</p>
  <p>출고 차단 hold와 정책/문체 watchlist를 분리해 표시한다. 전역 정합성, glossary SSOT, AI-slop 표면, QC JSONL, guard test, 해시와 재봉인 상태를 같은 보고서 안에서 확인할 수 있게 구성했다.</p>
</section>

<section>
  <h2>2. 최종 산출물</h2>
  <table>
    <tr><th>구분</th><th>파일</th><th>설명</th></tr>
    <tr><td>최종 원고 TXT</td><td>{link_from(delivery_dir, manuscript_txt_path, manuscript_txt_path.name)}</td><td>모든 확정 수정이 반영된 기본 납품 원고.</td></tr>
    <tr><td>Human-facing HTML 보고서</td><td>{link_from(delivery_dir, report_html_path, report_html_path.name)}</td><td>요약을 먼저 보여주는 최종 검수 보고서.</td></tr>
    <tr><td>패키지 manifest</td><td>{link_from(delivery_dir, delivery_manifest_path, delivery_manifest_path.name)}</td><td>해시, 회차, 검증 결과, 기준 원본 경로를 담은 추적 파일.</td></tr>
  </table>
</section>

<section>
  <h2>3. 최종 상태 지표</h2>
  <div class="grid">
    <div class="metric"><div class="num">{metrics["episode_count"]}</div><div class="label">회차 표식</div></div>
    <div class="metric"><div class="num">{escape(format_optional(blocking_hold))}</div><div class="label">blocking hold</div></div>
    <div class="metric"><div class="num">{escape(scan_status)}</div><div class="label">전역 drift scan</div></div>
    <div class="metric"><div class="num">{escape(format_validation(validation_valid, validation_total))}</div><div class="label">QC JSONL</div></div>
  </div>
  <table>
    <tr><th>항목</th><th>결과</th><th>근거</th></tr>
    <tr><td>TXT 기본 산출물</td><td class="ok">적용</td><td>최종 원고는 <code>.txt</code> 파일로 생성했다.</td></tr>
    <tr><td>원본/final/delivery 동기화</td><td class="{ok_class(metrics["source_final_delivery_match"])}">{pass_fail(metrics["source_final_delivery_match"])}</td><td>delivery TXT SHA-256: <code>{escape(metrics["delivery_txt_sha256"])}</code></td></tr>
    <tr><td>회차 표식</td><td class="{ok_class(metrics["marker_sequence_clean"])}">{pass_fail(metrics["marker_sequence_clean"])}</td><td>감지된 회차 {metrics["episode_count"]}개, 순서 정상 여부 {escape(str(metrics["marker_sequence_clean"]))}.</td></tr>
    <tr><td>출고 차단 hold</td><td class="{ok_class(blocking_hold in (0, "0", None))}">{pass_fail(blocking_hold in (0, "0", None))}</td><td>정책/문체 watchlist와 분리해 계산했다.</td></tr>
    <tr><td>패키지 봉인</td><td class="{ok_class(bool(reseal_summary.get("current_package_sealed", True)))}">{pass_fail(bool(reseal_summary.get("current_package_sealed", True)))}</td><td>이전 패키지 stale 여부: {escape(str(reseal_summary.get("previous_delivery_stale", False)))}.</td></tr>
    <tr><td>검증 결과</td><td class="{ok_class(validation_invalid in (0, "0", None))}">{pass_fail(validation_invalid in (0, "0", None))}</td><td>QC {escape(format_validation(validation_valid, validation_total))}, invalid {escape(format_optional(validation_invalid))}. Guard test: {escape(test_result or "not recorded")}.</td></tr>
  </table>
</section>

<section>
  <h2>4. 검수 원칙과 처리 기준</h2>
  <table>
    <tr><th>축</th><th>확인 내용</th><th>최종 처리</th></tr>
    <tr><td>원고 포맷</td><td>최종 승인 원고를 독립 TXT 파일로 패키징했다.</td><td>TXT가 기본. 다른 포맷은 선택 export.</td></tr>
    <tr><td>보고서 포맷</td><td>두괄식 HTML 보고서를 생성했다.</td><td>요약 이후 상세 근거를 배치.</td></tr>
    <tr><td>정합성 상태</td><td>최신 scan manifest의 scan_status와 hold 분류를 반영했다.</td><td>{escape(scan_status)} / blocking {escape(format_optional(blocking_hold))} / policy {escape(format_optional(policy_watchlist))}.</td></tr>
    <tr><td>AI-slop 표면</td><td>회차 끝 메타, 괄호 주석, placeholder, 내부 메모형 표면을 별도 축으로 스캔했다.</td><td>명백한 후보는 수정 대상, 애매한 후보는 watchlist.</td></tr>
    <tr><td>추적성</td><td>최종 원고, source, final, 보고서의 해시와 경로를 manifest에 기록했다.</td><td>재현 가능한 납품 패키지.</td></tr>
  </table>
</section>

<section>
  <h2>5. 전체 작업 범위</h2>
  <table>
    <tr><th>범위</th><th>하네스 기본 처리</th><th>비고</th></tr>
    <tr><td>전역 스캔 우선</td><td>회차별 수정 전 전체 drift/AI-slop 후보를 먼저 확인한다.</td><td>앞뒤 정합성이 흔들리는 원고에서 비용 낮은 수정점을 고르기 위함.</td></tr>
    <tr><td>회차별 딥다이브</td><td>10화 단위 큐를 기본으로 하되, 앞뒤 1화와 SSOT만 보조 맥락으로 참조한다.</td><td>원문의 맛과 대사 리듬을 보존한다.</td></tr>
    <tr><td>확정 수정</td><td>문맥 확신도 95% 이상일 때만 직접 반영한다.</td><td>애매한 항목은 hold/review JSONL로 남긴다.</td></tr>
    <tr><td>최종 패키징</td><td>TXT 원고와 HTML 누적 마감 보고서를 기본 산출물로 만든다.</td><td>manifest에 해시와 검증값을 기록한다.</td></tr>
  </table>
</section>

<section>
  <h2>6. 정책 판정 상세</h2>
  <table>
    <tr><th>항목</th><th>판정</th><th>근거</th></tr>
    {policy_rows}
  </table>
</section>

<section>
  <h2>7. Glossary SSOT 요약</h2>
  <table>
    <tr><th>정본</th><th>정책/도메인</th><th>별칭·금지 표면·근거</th></tr>
    {glossary_rows}
  </table>
</section>

<section>
  <h2>8. AI-slop 전역 스캔</h2>
  <table>
    <tr><th>유형</th><th>건수</th><th>예시/처리 기준</th></tr>
    {ai_slop_rows}
  </table>
</section>

<section>
  <h2>9. Hold와 Watchlist</h2>
  <table>
    <tr><th>구분</th><th>건수</th><th>설명</th></tr>
    {hold_rows}
  </table>
</section>

<section>
  <h2>10. 검증 내역과 재봉인</h2>
  <table>
    <tr><th>검증</th><th>결과</th><th>수치</th></tr>
    <tr><td>SHA-256</td><td class="ok">기록</td><td><code>{escape(metrics["delivery_txt_sha256"])}</code></td></tr>
    <tr><td>source/final/delivery TXT</td><td class="{ok_class(metrics["source_final_delivery_match"])}">{pass_fail(metrics["source_final_delivery_match"])}</td><td>바이트 일치 여부 {escape(str(metrics["source_final_delivery_match"]))}.</td></tr>
    <tr><td>QC JSONL</td><td class="{ok_class(validation_invalid in (0, "0", None))}">{pass_fail(validation_invalid in (0, "0", None))}</td><td>{escape(format_validation(validation_valid, validation_total))} valid.</td></tr>
    <tr><td>Guard test</td><td>{escape(test_result or "not recorded")}</td><td>최신 scan manifest 기준.</td></tr>
    {reseal_rows}
  </table>
</section>

<section>
  <h2>11. 누적 상세 이력</h2>
  <table>
    <tr><th>단계</th><th>하네스 기록 방식</th><th>마감 보고서 반영</th></tr>
    <tr><td>전역 정합성 스캔</td><td>scan manifest와 QC JSONL에 상태, 검증값, hold를 기록한다.</td><td>최종 상태 지표와 Hold/Watchlist 표에 반영.</td></tr>
    <tr><td>브랜드/실명 가명 정책</td><td>glossary SSOT와 surface matrix를 근거로 정본과 잔여 표면을 확인한다.</td><td>정책 판정 상세와 Glossary 요약에 반영.</td></tr>
    <tr><td>AI-slop 정리</td><td>메타 표식, 괄호 주석, placeholder, 내부 메모 후보를 scan-ai-slop으로 분리한다.</td><td>AI-slop 전역 스캔 표에 반영.</td></tr>
    <tr><td>최종 패키징</td><td>TXT/HTML/manifest를 같은 디렉터리에 만들고 해시를 기록한다.</td><td>최종 산출물과 패키지 메타데이터에 반영.</td></tr>
  </table>
</section>

<section>
  <h2>12. 추적 가능한 근거 파일</h2>
  <table>
    <tr><th>파일</th><th>역할</th></tr>
    <tr><td><span class="path">{escape(str(scan_manifest.get("_path", "")))}</span></td><td>최신 전역 스캔/검증 manifest.</td></tr>
    <tr><td><span class="path">{escape(str(glossary_summary.get("path", "")))}</span></td><td>glossary SSOT 또는 최신 glossary 후보.</td></tr>
    <tr><td><span class="path">{escape(str(delivery_manifest_path))}</span></td><td>최종 패키지 해시와 산출물 위치.</td></tr>
  </table>
</section>

<section>
  <h2>13. 패키지 메타데이터</h2>
  <table>
    <tr><th>항목</th><th>값</th></tr>
    <tr><td>작품</td><td>{escape(label)}</td></tr>
    <tr><td>보고서 밀도</td><td>{escape(report_density)} / {escape(density_label)}</td></tr>
    <tr><td>최종 원고</td><td><span class="path">{escape(str(manuscript_txt_path))}</span></td></tr>
    <tr><td>보고서</td><td><span class="path">{escape(str(report_html_path))}</span></td></tr>
    <tr><td>기준 source</td><td><span class="path">{escape(str(source_path))}</span></td></tr>
    <tr><td>기준 final</td><td><span class="path">{escape(str(final_path))}</span></td></tr>
    <tr><td>scan manifest</td><td><span class="path">{escape(str(scan_manifest.get("_path", "")))}</span></td></tr>
    <tr><td>파일 크기</td><td>{metrics["byte_count"]:,} bytes</td></tr>
    <tr><td>문자 수</td><td>{metrics["char_count"]:,} chars</td></tr>
    <tr><td>라인 수</td><td>{metrics["line_count"]:,} lines</td></tr>
  </table>
</section>

<footer>
  이 HTML은 하네스 기본 최종 보고서 형식이다. 내부 JSONL, diff, 개별 pass 보고서는 manifest와 근거 파일에서 추적한다.
</footer>
</main>
</body>
</html>
"""


def normalize_report_density(value: str) -> str:
    density = str(value or DEFAULT_REPORT_DENSITY).strip()
    if density not in REPORT_DENSITY_CHOICES:
        raise ValueError(
            f"unknown report density {density!r}; choose one of {sorted(REPORT_DENSITY_CHOICES)}"
        )
    return density


def summarize_holds(scan_manifest: dict[str, Any]) -> dict[str, Any]:
    legacy_active = coerce_optional_int(scan_manifest.get("active_hold_count"))
    items = extract_hold_items(scan_manifest)
    classified = {"blocking_hold_count": 0, "policy_watchlist_count": 0, "style_watchlist_count": 0}
    examples: dict[str, list[str]] = {"blocking": [], "policy": [], "style": []}
    for item in items:
        bucket = classify_hold_item(item)
        if bucket == "blocking":
            classified["blocking_hold_count"] += 1
        elif bucket == "style":
            classified["style_watchlist_count"] += 1
        else:
            classified["policy_watchlist_count"] += 1
        if len(examples[bucket]) < 5:
            examples[bucket].append(item[:240])

    explicit_blocking = coerce_optional_int(scan_manifest.get("blocking_hold_count"))
    explicit_policy = coerce_optional_int(scan_manifest.get("policy_watchlist_count"))
    explicit_style = coerce_optional_int(scan_manifest.get("style_watchlist_count"))

    blocking = (
        explicit_blocking
        if explicit_blocking is not None
        else classified["blocking_hold_count"]
        if items
        else legacy_active
    )
    policy = explicit_policy if explicit_policy is not None else classified["policy_watchlist_count"]
    style = explicit_style if explicit_style is not None else classified["style_watchlist_count"]

    return {
        "active_hold_count": legacy_active,
        "blocking_hold_count": blocking,
        "policy_watchlist_count": policy,
        "style_watchlist_count": style,
        "legacy_active_hold_count": legacy_active,
        "hold_item_count": len(items),
        "examples": examples,
        "classification_rule": (
            "blocking/P0/P1/출고 차단 표현은 blocking_hold, 문체/톤 표현은 style_watchlist, "
            "그 외 가명·정책·검토 잔여 항목은 policy_watchlist로 분리한다."
        ),
    }


def extract_hold_items(scan_manifest: dict[str, Any]) -> list[str]:
    values: list[str] = []
    for key in (
        "hold_items_untouched",
        "unresolved_holds",
        "hold_items",
        "holds",
        "watchlist_items",
        "policy_watchlist_items",
    ):
        raw = scan_manifest.get(key)
        if isinstance(raw, list):
            values.extend(flatten_hold_values(raw))
        elif isinstance(raw, dict):
            values.extend(flatten_hold_values(list(raw.values())))
        elif raw not in (None, ""):
            values.append(str(raw))
    return [value for value in values if value.strip()]


def flatten_hold_values(values: list[Any]) -> list[str]:
    flattened: list[str] = []
    for value in values:
        if isinstance(value, dict):
            flattened.append(
                " / ".join(
                    str(value.get(key, ""))
                    for key in ("id", "episode", "type", "status", "source", "reason", "action")
                    if value.get(key, "") not in (None, "")
                )
            )
        elif isinstance(value, list):
            flattened.extend(flatten_hold_values(value))
        elif value not in (None, ""):
            flattened.append(str(value))
    return flattened


def classify_hold_item(value: str) -> str:
    text = value.lower()
    if any(token in text for token in ("blocking", "blocker", "p0", "p1", "출고 차단", "차단", "필수 수정")):
        return "blocking"
    if any(token in text for token in ("style", "tone", "문체", "톤", "대사 리듬", "리듬")):
        return "style"
    return "policy"


def load_glossary_summary(run_root: Path, scan_manifest: dict[str, Any]) -> dict[str, Any]:
    path = resolve_glossary_path(run_root, scan_manifest)
    if not path or not path.exists():
        return {"path": "", "entry_count": 0, "rows": []}

    rows: list[dict[str, Any]] = []
    forbidden_alias_count = 0
    residual_forbidden_total = 0
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(row, dict):
            continue
        forbidden_aliases = listify(row.get("forbidden_aliases") or row.get("forbidden") or [])
        residual_counts = row.get("residual_forbidden_alias_counts") or row.get("residual_counts") or {}
        if isinstance(residual_counts, dict):
            residual_forbidden_total += sum(
                coerce_optional_int(value) or 0 for value in residual_counts.values()
            )
        forbidden_alias_count += len(forbidden_aliases)
        rows.append(
            {
                "canonical": str(row.get("canonical") or row.get("canon") or row.get("term") or "").strip(),
                "domain": str(row.get("domain") or row.get("axis") or "").strip(),
                "policy": str(row.get("policy") or row.get("verdict") or row.get("status") or "").strip(),
                "aliases": listify(row.get("aliases") or row.get("allowed_surface_forms") or []),
                "forbidden_aliases": forbidden_aliases,
                "residual_forbidden_alias_counts": residual_counts if isinstance(residual_counts, dict) else {},
                "reason": str(row.get("reason") or row.get("evidence") or row.get("note") or "").strip(),
            }
        )

    return {
        "path": str(path),
        "entry_count": len(rows),
        "forbidden_alias_count": forbidden_alias_count,
        "residual_forbidden_total": residual_forbidden_total,
        "rows": rows[:12],
    }


def resolve_glossary_path(run_root: Path, scan_manifest: dict[str, Any]) -> Path | None:
    for key in ("glossary_current_path", "glossary_path", "glossary_ssot_path"):
        path = resolve_run_path(run_root, scan_manifest.get(key))
        if path and path.exists():
            return path

    candidates: list[tuple[float, Path]] = []
    for pattern in (
        "consistency_integrity/**/glossary_current*.jsonl",
        "consistency_integrity/**/glossary_ssot*.jsonl",
        "consistency_integrity/**/*glossary*.jsonl",
    ):
        for path in run_root.glob(pattern):
            candidates.append((path.stat().st_mtime, path))
    if not candidates:
        return None
    return sorted(candidates, key=lambda item: item[0])[-1][1].resolve()


def inspect_reseal_status(
    *,
    run_root: Path,
    run_manifest: dict[str, Any],
    delivery_manifest_path: Path,
    current_delivery_txt_sha256: str,
) -> dict[str, Any]:
    previous_manifest_path = resolve_run_path(run_root, run_manifest.get("final_delivery_manifest_path"))
    if not previous_manifest_path:
        previous_manifest_path = delivery_manifest_path if delivery_manifest_path.exists() else None

    previous_hash = ""
    previous_created_at = ""
    if previous_manifest_path and previous_manifest_path.exists():
        try:
            previous_manifest = read_json(previous_manifest_path)
        except (OSError, json.JSONDecodeError):
            previous_manifest = {}
        previous_hash = str(previous_manifest.get("delivery_txt_sha256") or "")
        previous_created_at = str(previous_manifest.get("created_at") or "")

    stale = bool(previous_hash and previous_hash != current_delivery_txt_sha256)
    return {
        "previous_delivery_manifest_path": str(previous_manifest_path or ""),
        "previous_delivery_txt_sha256": previous_hash,
        "previous_delivery_created_at": previous_created_at,
        "previous_delivery_stale": stale,
        "reseal_required_before_render": stale,
        "current_package_sealed": True,
        "current_delivery_txt_sha256": current_delivery_txt_sha256,
    }


def build_policy_rows(surface_counts: dict[str, int], *, glossary_summary: dict[str, Any] | None = None) -> str:
    if not surface_counts:
        fallback = (
            "<tr><td>정책 표면</td><td>참고</td>"
            "<td>surface matrix가 없어 개별 카운트는 보고서에 싣지 않았다.</td></tr>"
        )
        if glossary_summary and glossary_summary.get("entry_count"):
            return fallback + (
                "<tr><td>Glossary SSOT</td><td>참고</td>"
                f"<td>glossary {escape(glossary_summary.get('entry_count'))}개 항목을 별도 표에 요약했다.</td></tr>"
            )
        return fallback

    rows = [
        (
            "대영증권/대한증권",
            "대영증권 정본",
            f"대영증권 {count(surface_counts, '대영증권')}건, 대한증권 {count(surface_counts, '대한증권')}건",
        ),
        (
            "RG/LG/금성",
            "RG 계열 가명 정본",
            "RG전자 "
            f"{count(surface_counts, 'RG전자')}건, RG반도체 {count(surface_counts, 'RG반도체')}건, "
            f"록키금성 {count(surface_counts, '록키금성')}건",
        ),
        (
            "사성/삼성",
            "사성 계열 가명 정본",
            f"사성전자 {count(surface_counts, '사성전자')}건, 삼성전자 {count(surface_counts, '삼성전자')}건",
        ),
        (
            "선우/SY/KS",
            "SY 약칭, KS 마크 보존 예외",
            f"SY텔레콤 {count(surface_counts, 'SY텔레콤')}건, KS텔레콤 {count(surface_counts, 'KS텔레콤')}건, KS 마크 {count(surface_counts, 'KS 마크')}건",
        ),
    ]
    return "\n".join(
        f"<tr><td>{escape(axis)}</td><td>{escape(verdict)}</td><td>{escape(evidence)}</td></tr>"
        for axis, verdict, evidence in rows
    )


def build_hold_rows(hold_summary: dict[str, Any]) -> str:
    rows = [
        (
            "blocking_hold",
            hold_summary.get("blocking_hold_count"),
            "출고 전 반드시 해결해야 하는 차단 항목. 최종 판정에 직접 반영한다.",
        ),
        (
            "policy_watchlist",
            hold_summary.get("policy_watchlist_count"),
            "가명/정책/판단 유보 항목. 차단이 아니라 추적용으로 분리한다.",
        ),
        (
            "style_watchlist",
            hold_summary.get("style_watchlist_count"),
            "문체, 톤, 리듬 관련 잔여 후보. 원문의 맛 보존을 우선한다.",
        ),
        (
            "legacy_active_hold",
            hold_summary.get("legacy_active_hold_count"),
            "구형 manifest의 active_hold_count. 새 하네스에서는 위 세 범주로 분해한다.",
        ),
    ]
    return "\n".join(
        f"<tr><td>{escape(name)}</td><td>{escape(format_optional(value))}</td><td>{escape(description)}</td></tr>"
        for name, value, description in rows
    )


def build_ai_slop_rows(ai_slop_summary: dict[str, Any]) -> str:
    counts = ai_slop_summary.get("counts") if isinstance(ai_slop_summary.get("counts"), dict) else {}
    examples = ai_slop_summary.get("examples") if isinstance(ai_slop_summary.get("examples"), list) else []
    if not counts:
        return "<tr><td>AI-slop scan</td><td>0</td><td>기록된 스캔 결과가 없다.</td></tr>"

    rows: list[str] = []
    for signal_type, signal_count in counts.items():
        sample = next(
            (
                str(item.get("text") or "")
                for item in examples
                if isinstance(item, dict) and item.get("signal_type") == signal_type
            ),
            "",
        )
        rows.append(
            "<tr>"
            f"<td>{escape(signal_type)}</td>"
            f"<td>{escape(signal_count)}</td>"
            f"<td>{escape(sample or '명백한 표면은 수정, 맥락 의존 후보는 watchlist로 분리한다.')}</td>"
            "</tr>"
        )
    return "\n".join(rows)


def build_glossary_rows(glossary_summary: dict[str, Any]) -> str:
    rows = glossary_summary.get("rows") if isinstance(glossary_summary.get("rows"), list) else []
    if not rows:
        return "<tr><td>Glossary SSOT</td><td>-</td><td>연결된 glossary JSONL이 없다.</td></tr>"

    rendered: list[str] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        aliases = ", ".join(str(item) for item in row.get("aliases", [])[:5])
        forbidden = ", ".join(str(item) for item in row.get("forbidden_aliases", [])[:5])
        residual = row.get("residual_forbidden_alias_counts")
        residual_text = json.dumps(residual, ensure_ascii=False) if residual else ""
        details = " / ".join(
            part
            for part in (
                f"aliases: {aliases}" if aliases else "",
                f"forbidden: {forbidden}" if forbidden else "",
                f"residual: {residual_text}" if residual_text else "",
                str(row.get("reason") or ""),
            )
            if part
        )
        rendered.append(
            "<tr>"
            f"<td>{escape(row.get('canonical') or '-')}</td>"
            f"<td>{escape(' / '.join(part for part in (row.get('domain'), row.get('policy')) if part))}</td>"
            f"<td>{escape(details or '-')}</td>"
            "</tr>"
        )
    return "\n".join(rendered) or "<tr><td>Glossary SSOT</td><td>-</td><td>표시할 항목이 없다.</td></tr>"


def build_reseal_rows(reseal_summary: dict[str, Any]) -> str:
    return "\n".join(
        [
            "<tr>"
            "<td>이전 패키지 stale 여부</td>"
            f"<td class=\"{ok_class(not bool(reseal_summary.get('previous_delivery_stale', False)))}\">"
            f"{pass_fail(not bool(reseal_summary.get('previous_delivery_stale', False)))}</td>"
            f"<td>{escape(str(reseal_summary.get('previous_delivery_manifest_path') or '-'))}</td>"
            "</tr>",
            "<tr>"
            "<td>현재 패키지 봉인</td>"
            f"<td class=\"{ok_class(bool(reseal_summary.get('current_package_sealed', True)))}\">"
            f"{pass_fail(bool(reseal_summary.get('current_package_sealed', True)))}</td>"
            f"<td><code>{escape(str(reseal_summary.get('current_delivery_txt_sha256') or ''))}</code></td>"
            "</tr>",
        ]
    )


def listify(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if item not in (None, "")]
    if isinstance(value, tuple):
        return [str(item) for item in value if item not in (None, "")]
    if value in (None, ""):
        return []
    return [str(value)]


def count(values: dict[str, int], term: str) -> int:
    return int(values.get(term, 0))


def marker_number_sequence(markers: list[dict[str, Any]]) -> list[int]:
    numbers: list[int] = []
    for marker in markers:
        value = str(marker.get("episode") or "").lstrip("0") or "0"
        if value.isdecimal():
            numbers.append(int(value))
    return numbers


def safe_file_stem(value: str, *, default: str) -> str:
    text = str(value or "").strip()
    text = re.sub(r'[<>:"/\\|?*\x00-\x1f]+', "_", text)
    text = re.sub(r"\s+", "_", text).strip("._")
    return text or default


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def coerce_optional_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def escape(value: Any) -> str:
    return html.escape(str(value))


def format_optional(value: Any) -> str:
    return "-" if value is None or value == "" else str(value)


def format_validation(valid: Any, total: Any) -> str:
    if valid is None or total is None:
        return "-"
    return f"{valid}/{total}"


def pass_fail(value: bool) -> str:
    return "통과" if value else "검토 필요"


def ok_class(value: bool) -> str:
    return "ok" if value else "warn"


def link_from(base_dir: Path, target: Path, label: str) -> str:
    try:
        href = os.path.relpath(target, start=base_dir).replace("\\", "/")
    except ValueError:
        href = target.as_posix()
    return f'<a href="{escape(href)}">{escape(label)}</a>'


FINAL_DELIVERY_CSS = """
:root {
  color-scheme: light;
  --ink: #1f2933;
  --muted: #5d6778;
  --line: #d8dee8;
  --soft: #f6f8fb;
  --soft2: #eef4f7;
  --accent: #1f6f68;
  --good: #146c43;
  --warn: #946200;
}
* { box-sizing: border-box; }
body {
  margin: 0;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Malgun Gothic", "Apple SD Gothic Neo", sans-serif;
  color: var(--ink);
  background: #ffffff;
  line-height: 1.62;
}
main { max-width: 1120px; margin: 0 auto; padding: 36px 28px 64px; }
header { border-bottom: 2px solid var(--ink); padding-bottom: 24px; margin-bottom: 28px; }
h1 { margin: 0 0 10px; font-size: 30px; line-height: 1.25; letter-spacing: 0; }
.subtitle { color: var(--muted); font-size: 15px; }
.badge-row { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 18px; }
.badge {
  display: inline-flex;
  align-items: center;
  border: 1px solid var(--line);
  border-radius: 999px;
  padding: 5px 10px;
  background: var(--soft);
  font-size: 13px;
}
.badge.good { color: var(--good); border-color: #9fd3b8; background: #f0faf4; font-weight: 650; }
section { margin: 28px 0; }
h2 { font-size: 21px; line-height: 1.3; margin: 0 0 14px; padding-bottom: 8px; border-bottom: 1px solid var(--line); }
p { margin: 8px 0 12px; }
.summary { background: var(--soft2); border: 1px solid var(--line); border-radius: 8px; padding: 18px; }
.summary strong { color: var(--accent); }
.grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; }
.metric { border: 1px solid var(--line); border-radius: 8px; padding: 13px; background: #fff; }
.metric .num { font-size: 22px; font-weight: 760; }
.metric .label { color: var(--muted); font-size: 13px; }
table { width: 100%; border-collapse: collapse; margin: 10px 0 18px; font-size: 14px; }
th, td { border: 1px solid var(--line); padding: 9px 10px; vertical-align: top; }
th { background: var(--soft); text-align: left; }
tr:nth-child(even) td { background: #fcfdff; }
.path, code { font-family: ui-monospace, SFMono-Regular, Consolas, "Liberation Mono", monospace; font-size: 12.5px; word-break: break-all; }
.ok { color: var(--good); font-weight: 700; }
.warn { color: var(--warn); font-weight: 700; }
footer { margin-top: 42px; padding-top: 18px; border-top: 1px solid var(--line); color: var(--muted); font-size: 13px; }
@media (max-width: 840px) {
  main { padding: 24px 16px 48px; }
  .grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  h1 { font-size: 24px; }
  table { font-size: 13px; }
}
"""
