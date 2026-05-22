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

from .workspace import decode_text_bytes, find_chapter_markers, read_json, write_json


DEFAULT_DELIVERY_VERSION = "v1"
DEFAULT_MANUSCRIPT_FORMAT = "txt"
DEFAULT_REPORT_FORMAT = "html"


@dataclass(slots=True)
class FinalDeliveryResult:
    delivery_dir: str
    manuscript_txt_path: str
    human_report_html_path: str
    manifest_path: str
    manuscript_format: str
    report_format: str
    source_text_path: str
    final_manuscript_path: str
    delivery_txt_sha256: str
    source_final_delivery_match: bool
    episode_count: int
    marker_sequence_clean: bool
    scan_status: str
    active_hold_count: int | None

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
    update_run_manifest: bool = True,
) -> FinalDeliveryResult:
    """Create the default final delivery package: TXT manuscript + human-facing HTML report."""

    run_root = run_root.resolve()
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
    )
    report_html_path.write_text(html_report, encoding="utf-8", newline="\n")

    delivery_manifest = {
        "schema_version": "final_delivery_manifest.v1",
        "version": version_label,
        "status": "done",
        "created_at": utc_now_iso(),
        "work": label,
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
        run_manifest["updated_at"] = utc_now_iso()
        write_json(run_manifest_path, run_manifest)

    return FinalDeliveryResult(
        delivery_dir=str(delivery_dir),
        manuscript_txt_path=str(manuscript_txt_path),
        human_report_html_path=str(report_html_path),
        manifest_path=str(delivery_manifest_path),
        manuscript_format=DEFAULT_MANUSCRIPT_FORMAT,
        report_format=DEFAULT_REPORT_FORMAT,
        source_text_path=str(source_path),
        final_manuscript_path=str(final_path),
        delivery_txt_sha256=metrics["delivery_txt_sha256"],
        source_final_delivery_match=source_final_delivery_match,
        episode_count=len(markers),
        marker_sequence_clean=marker_sequence_clean,
        scan_status=str(scan_manifest.get("scan_status", "")),
        active_hold_count=coerce_optional_int(scan_manifest.get("active_hold_count")),
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
) -> str:
    scan_status = str(scan_manifest.get("scan_status") or "unknown")
    active_hold = scan_manifest.get("active_hold_count")
    validation_total = scan_manifest.get("validation_total")
    validation_valid = scan_manifest.get("validation_valid")
    validation_invalid = scan_manifest.get("validation_invalid")
    test_result = str(scan_manifest.get("test_result") or "")
    final_verdict = "출고 가능" if scan_status == "clean" and active_hold in (0, "0", None) else "검토 필요"
    policy_rows = build_policy_rows(surface_counts)

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
  <div class="subtitle">최종 납품 패키지 · 생성 시각 {escape(created_at)} · 기본 산출물 TXT + HTML</div>
  <div class="badge-row">
    <span class="badge good">최종 판정: {escape(final_verdict)}</span>
    <span class="badge">원고 형식: TXT</span>
    <span class="badge">보고서 형식: HTML</span>
    <span class="badge">회차 {metrics["episode_count"]}개</span>
    <span class="badge">active hold {escape(format_optional(active_hold))}</span>
  </div>
</header>

<section class="summary">
  <h2>요약</h2>
  <p><strong>최종 원고는 TXT를 기준 산출물로 고정했다.</strong> 이 패키지는 승인된 최종 원고 TXT, 사람이 읽는 HTML 보고서, 추적용 manifest를 함께 생성한다. HWP/HWPX/PDF는 별도 요구가 있을 때만 추가 export로 다룬다.</p>
  <p>보고서는 먼저 결론을 제시하고, 그 아래에 산출물, 상태 지표, 처리 내역, 정책 판정, 검증 내역, 추적 가능한 근거 파일을 배치한다. 내부 작업 로그는 본문 설명이 아니라 부록/manifest로 낮춰 둔다.</p>
</section>

<section>
  <h2>최종 산출물</h2>
  <table>
    <tr><th>구분</th><th>파일</th><th>설명</th></tr>
    <tr><td>최종 원고 TXT</td><td>{link_from(delivery_dir, manuscript_txt_path, manuscript_txt_path.name)}</td><td>모든 확정 수정이 반영된 기본 납품 원고.</td></tr>
    <tr><td>Human-facing HTML 보고서</td><td>{link_from(delivery_dir, report_html_path, report_html_path.name)}</td><td>요약을 먼저 보여주는 최종 검수 보고서.</td></tr>
    <tr><td>패키지 manifest</td><td>{link_from(delivery_dir, delivery_manifest_path, delivery_manifest_path.name)}</td><td>해시, 회차, 검증 결과, 기준 원본 경로를 담은 추적 파일.</td></tr>
  </table>
</section>

<section>
  <h2>최종 상태 지표</h2>
  <div class="grid">
    <div class="metric"><div class="num">{metrics["episode_count"]}</div><div class="label">회차 표식</div></div>
    <div class="metric"><div class="num">{escape(format_optional(active_hold))}</div><div class="label">active hold</div></div>
    <div class="metric"><div class="num">{escape(scan_status)}</div><div class="label">전역 drift scan</div></div>
    <div class="metric"><div class="num">{escape(format_validation(validation_valid, validation_total))}</div><div class="label">QC JSONL</div></div>
  </div>
  <table>
    <tr><th>항목</th><th>결과</th><th>근거</th></tr>
    <tr><td>TXT 기본 산출물</td><td class="ok">적용</td><td>최종 원고는 <code>.txt</code> 파일로 생성했다.</td></tr>
    <tr><td>원본/final/delivery 동기화</td><td class="{ok_class(metrics["source_final_delivery_match"])}">{pass_fail(metrics["source_final_delivery_match"])}</td><td>delivery TXT SHA-256: <code>{escape(metrics["delivery_txt_sha256"])}</code></td></tr>
    <tr><td>회차 표식</td><td class="{ok_class(metrics["marker_sequence_clean"])}">{pass_fail(metrics["marker_sequence_clean"])}</td><td>감지된 회차 {metrics["episode_count"]}개, 순서 정상 여부 {escape(str(metrics["marker_sequence_clean"]))}.</td></tr>
    <tr><td>검증 결과</td><td class="{ok_class(validation_invalid in (0, "0", None))}">{pass_fail(validation_invalid in (0, "0", None))}</td><td>QC {escape(format_validation(validation_valid, validation_total))}, invalid {escape(format_optional(validation_invalid))}. Guard test: {escape(test_result or "not recorded")}.</td></tr>
  </table>
</section>

<section>
  <h2>무엇을 확인했나</h2>
  <table>
    <tr><th>축</th><th>확인 내용</th><th>최종 처리</th></tr>
    <tr><td>원고 포맷</td><td>최종 승인 원고를 독립 TXT 파일로 패키징했다.</td><td>TXT가 기본. 다른 포맷은 선택 export.</td></tr>
    <tr><td>보고서 포맷</td><td>두괄식 HTML 보고서를 생성했다.</td><td>요약 이후 상세 근거를 배치.</td></tr>
    <tr><td>정합성 상태</td><td>최신 scan manifest의 scan_status와 active_hold_count를 반영했다.</td><td>{escape(scan_status)} / hold {escape(format_optional(active_hold))}.</td></tr>
    <tr><td>추적성</td><td>최종 원고, source, final, 보고서의 해시와 경로를 manifest에 기록했다.</td><td>재현 가능한 납품 패키지.</td></tr>
  </table>
</section>

<section>
  <h2>정책 판정</h2>
  <table>
    <tr><th>항목</th><th>판정</th><th>근거</th></tr>
    {policy_rows}
  </table>
</section>

<section>
  <h2>검증 내역</h2>
  <table>
    <tr><th>검증</th><th>결과</th><th>수치</th></tr>
    <tr><td>SHA-256</td><td class="ok">기록</td><td><code>{escape(metrics["delivery_txt_sha256"])}</code></td></tr>
    <tr><td>source/final/delivery TXT</td><td class="{ok_class(metrics["source_final_delivery_match"])}">{pass_fail(metrics["source_final_delivery_match"])}</td><td>바이트 일치 여부 {escape(str(metrics["source_final_delivery_match"]))}.</td></tr>
    <tr><td>QC JSONL</td><td class="{ok_class(validation_invalid in (0, "0", None))}">{pass_fail(validation_invalid in (0, "0", None))}</td><td>{escape(format_validation(validation_valid, validation_total))} valid.</td></tr>
    <tr><td>Guard test</td><td>{escape(test_result or "not recorded")}</td><td>최신 scan manifest 기준.</td></tr>
  </table>
</section>

<section>
  <h2>패키지 메타데이터</h2>
  <table>
    <tr><th>항목</th><th>값</th></tr>
    <tr><td>작품</td><td>{escape(label)}</td></tr>
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
  이 HTML은 하네스 기본 최종 보고서 형식이다. 내부 JSONL, diff, 개별 pass 보고서는 manifest에서 추적한다.
</footer>
</main>
</body>
</html>
"""


def build_policy_rows(surface_counts: dict[str, int]) -> str:
    if not surface_counts:
        return (
            "<tr><td>정책 표면</td><td>참고</td>"
            "<td>surface matrix가 없어 개별 카운트는 보고서에 싣지 않았다.</td></tr>"
        )

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
