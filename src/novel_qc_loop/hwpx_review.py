from __future__ import annotations

import json
import re
import zipfile
from collections import Counter
from dataclasses import asdict, dataclass
from html import escape as xml_escape
from pathlib import Path
from typing import Any

from .subtitles import build_subtitle_consistency_flags, extract_chapter_subtitle_rows


BLUE = "#0000FF"
BLACK_CHARPR = "0"
BLUE_CHARPR = "1"
LINE_CHARS = 230
HWPX_FONT_HEIGHT = 2000
HWPX_CHARS_PER_LINE = 24
LINE_HEIGHT = 3200
LINE_SEG_TEXT_HEIGHT = 2000
LINE_SEG_BASELINE = 1700
LINE_SEG_SPACING = 1200
HWPX_RENDERER_OWNS_LAYOUT = True
HWPX_PAGE_WIDTH = 59528
HWPX_PAGE_HEIGHT = 84188
HWPX_MARGIN_TOP = 5668
HWPX_MARGIN_HEADER = 4252
HWPX_MARGIN_LEFT = 8504
HWPX_MARGIN_RIGHT = 8504
HWPX_MARGIN_GUTTER = 0
HWPX_MARGIN_FOOTER = 4252
HWPX_MARGIN_BOTTOM = 4252
HWPX_TEXT_WIDTH = HWPX_PAGE_WIDTH - HWPX_MARGIN_LEFT - HWPX_MARGIN_RIGHT - HWPX_MARGIN_GUTTER


@dataclass(slots=True)
class HwpxReviewResult:
    source_path: str
    changes_path: str
    output_path: str
    loop_label: str
    total_changes: int
    aa_changes: int
    rendered: int
    issues: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class MarkedManuscriptResult:
    source_path: str
    changes_path: str
    output_path: str
    loop_label: str
    total_changes: int
    marker_counts: dict[str, int]
    rendered_changes: int
    rendered_marker_counts: dict[str, int]
    manual_notes: int
    rendered_total_opinions: int
    counting_rule: str
    issues: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class ReviewRun:
    text: str
    char_pr: str = BLACK_CHARPR


@dataclass(slots=True)
class MarkerEvent:
    start: int
    end: int
    order: int
    runs: list[ReviewRun]
    change_id: str
    marker: str = ""


def render_aa_review_hwpx(
    *,
    source_path: Path,
    changes_path: Path,
    output_path: Path,
    loop_label: str = "",
    title: str = "",
    window_chars: int = 220,
) -> HwpxReviewResult:
    source_text = source_path.read_text(encoding="utf-8")
    changes = json.loads(changes_path.read_text(encoding="utf-8"))
    if not isinstance(changes, list):
        raise ValueError("changes file must be a JSON array")

    aa_changes = [
        change
        for change in changes
        if isinstance(change, dict) and change.get("marker") == "ⓐⓐ"
    ]
    issues: list[dict[str, Any]] = []
    lines = build_review_lines(
        source_text=source_text,
        changes=aa_changes,
        issues=issues,
        title=title or "ⓐⓐ 승인 판단표",
        loop_label=loop_label,
        window_chars=window_chars,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    write_hwpx(output_path, lines, title=title or "AA decision review")
    return HwpxReviewResult(
        source_path=str(source_path),
        changes_path=str(changes_path),
        output_path=str(output_path),
        loop_label=loop_label,
        total_changes=len(changes),
        aa_changes=len(aa_changes),
        rendered=len(aa_changes),
        issues=issues,
    )


def render_marked_manuscript_hwpx(
    *,
    source_path: Path,
    changes_path: Path,
    output_path: Path,
    loop_label: str = "",
    title: str = "",
    include_manual_notes: bool = True,
) -> MarkedManuscriptResult:
    source_text = source_path.read_text(encoding="utf-8")
    changes = json.loads(changes_path.read_text(encoding="utf-8"))
    if not isinstance(changes, list):
        raise ValueError("changes file must be a JSON array")

    issues: list[dict[str, Any]] = []
    marker_counts: Counter[str] = Counter(
        normalize_review_marker(change)
        for change in changes
        if isinstance(change, dict)
    )
    events = build_marker_events(
        source_text,
        [change for change in changes if isinstance(change, dict)],
        issues=issues,
    )
    manual_notes = 0
    if include_manual_notes:
        manual_events = build_manual_note_events(source_text)
        manual_notes = len(manual_events)
        events.extend(manual_events)
    runs = apply_marker_events(source_text, events, issues=issues)
    paragraphs = split_runs_to_paragraphs(runs)

    heading = title or "기호 적용 원고"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    write_hwpx(output_path, paragraphs, title=heading)
    rendered_change_events = [
        event for event in events if not str(event.change_id).endswith("-note")
    ]
    rendered_marker_counts: Counter[str] = Counter(
        event.marker or "(unknown)" for event in rendered_change_events
    )
    rendered_changes = len(rendered_change_events)
    rendered_total_opinions = rendered_marker_counts.get("ⓐⓐ", 0) + manual_notes
    return MarkedManuscriptResult(
        source_path=str(source_path),
        changes_path=str(changes_path),
        output_path=str(output_path),
        loop_label=loop_label,
        total_changes=len(changes),
        marker_counts=dict(marker_counts),
        rendered_changes=rendered_changes,
        rendered_marker_counts=dict(rendered_marker_counts),
        manual_notes=manual_notes,
        rendered_total_opinions=rendered_total_opinions,
        counting_rule=(
            "count ⓐ corrections and ⓐⓐ opinions separately; never use raw "
            "text.count('ⓐ{') because it can include ⓐⓐ{"
        ),
        issues=issues,
    )


def build_marker_events(
    source_text: str,
    changes: list[dict[str, Any]],
    *,
    issues: list[dict[str, Any]],
) -> list[MarkerEvent]:
    events: list[MarkerEvent] = []
    order = 0
    for index, change in enumerate(changes, start=1):
        change_id = str(change.get("id") or f"change-{index:04d}")
        find = str(change.get("find", ""))
        if not find:
            issues.append({"id": change_id, "field": "find", "message": "find anchor is empty"})
            continue
        positions = find_occurrences(source_text, find)
        if not positions:
            issues.append({"id": change_id, "field": "find", "message": "anchor not found"})
            continue
        occurrence = int(change.get("occurrence") or 1)
        if occurrence < 1 or occurrence > len(positions):
            issues.append(
                {
                    "id": change_id,
                    "field": "occurrence",
                    "message": "occurrence is outside anchor match count",
                    "matches": len(positions),
                }
            )
            continue

        start = positions[occurrence - 1]
        end = start + len(find)
        operation = infer_operation(change)
        marker = normalize_review_marker(change)
        replacement = marker_replacement_text(change, operation)

        if marker == "ⓐⓐ":
            note_at = start if operation == "insert_before" else end
            event = MarkerEvent(
                start=note_at,
                end=note_at,
                order=order,
                change_id=change_id,
                marker=marker,
                runs=[
                    ReviewRun(" ⓐⓐ("),
                    ReviewRun(aa_opinion_text(change, operation), BLUE_CHARPR),
                    ReviewRun(")"),
                ],
            )
        if operation in {"replace", "delete"}:
            if marker != "ⓐⓐ":
                event = MarkerEvent(
                    start=start,
                    end=end,
                    order=order,
                    change_id=change_id,
                    marker=marker,
                    runs=[
                        ReviewRun(f"{marker}{{{find}|"),
                        ReviewRun(replacement, BLUE_CHARPR),
                        ReviewRun("}"),
                    ],
                )
        elif operation == "insert_before":
            if marker != "ⓐⓐ":
                event = MarkerEvent(
                    start=start,
                    end=start,
                    order=order,
                    change_id=change_id,
                    marker=marker,
                    runs=[
                        ReviewRun(f"{marker}{{|"),
                        ReviewRun(replacement, BLUE_CHARPR),
                        ReviewRun("}"),
                    ],
                )
        elif operation == "insert_after":
            if marker != "ⓐⓐ":
                event = MarkerEvent(
                    start=end,
                    end=end,
                    order=order,
                    change_id=change_id,
                    marker=marker,
                    runs=[
                        ReviewRun(f"{marker}{{|"),
                        ReviewRun(replacement, BLUE_CHARPR),
                        ReviewRun("}"),
                    ],
                )
        else:
            issues.append(
                {"id": change_id, "field": "operation", "message": "unsupported operation"}
            )
            continue
        events.append(event)
        order += 1
    return events


def normalize_review_marker(change: dict[str, Any]) -> str:
    return str(change.get("marker") or "ⓐⓐ")


def aa_opinion_text(change: dict[str, Any], operation: str) -> str:
    reason = review_reason_text(change)
    replacement = normalize_inline(str(change.get("replace", "")))
    parts: list[str] = []
    if is_ai_slop_change(change):
        if operation == "delete":
            parts.append("의견: AI-slop 신호 삭제 후보")
        elif operation in {"insert_before", "insert_after"}:
            parts.append("의견: AI-slop 신호 보강 후보")
        else:
            parts.append("의견: AI-slop 신호 완화 윤문 후보")
    elif operation == "delete":
        parts.append("의견: 삭제 후보")
    elif operation in {"insert_before", "insert_after"}:
        parts.append("의견: 추가 후보")
    else:
        parts.append("의견: 윤문 후보")
    if reason:
        parts.append(reason)
    if replacement:
        parts.append(f"제안: {replacement}")
    return " / ".join(parts)


def marker_replacement_text(change: dict[str, Any], operation: str) -> str:
    if operation == "delete" and not str(change.get("replace", "")):
        reason = review_reason_text(change)
        return f"삭제 의견: {reason}" if reason else "삭제 의견"
    replacement = str(change.get("replace", ""))
    return replacement.strip()


def is_ai_slop_change(change: dict[str, Any]) -> bool:
    edit_class = str(change.get("edit_class", "")).lower().replace("_", "-")
    return "slop" in edit_class or "ai-ti" in edit_class or "ai티" in edit_class


def review_reason_text(change: dict[str, Any]) -> str:
    reason = normalize_inline(str(change.get("reason", "")))
    if not is_ai_slop_change(change):
        return reason
    if re.search(r"ai[- ]?slop|ai\s*티|ai티", reason, re.IGNORECASE):
        return reason
    if not reason:
        return "AI-slop 신호"
    return f"AI-slop 신호: {reason}"


def build_manual_note_events(source_text: str) -> list[MarkerEvent]:
    events: list[MarkerEvent] = []
    positions = find_occurrences(source_text, "ⓚ제11화") or find_occurrences(source_text, "제11화")
    if len(positions) >= 2:
        events.append(
            MarkerEvent(
                start=positions[1],
                end=positions[1],
                order=-10,
                change_id="manual-note",
                marker="ⓐⓐ",
                runs=[
                    ReviewRun("ⓐⓐ("),
                    ReviewRun(
                        "의견: 11화가 비동일 중복입니다. 11_2를 정본 후보로 보고 "
                        "기존 11화 삭제 여부를 판단해야 합니다.",
                        BLUE_CHARPR,
                    ),
                    ReviewRun(")\n\n"),
                ],
            )
        )
    events.extend(build_subtitle_note_events(source_text))
    return events


def build_subtitle_note_events(source_text: str) -> list[MarkerEvent]:
    rows = extract_chapter_subtitle_rows(source_text)
    flags = build_subtitle_consistency_flags(rows)
    events: list[MarkerEvent] = []
    for index, flag in enumerate(flags):
        action = str(flag.get("action") or "")
        examples = [str(value) for value in flag.get("examples") or [] if str(value).strip()]
        example_text = ", ".join(examples[:3]) if examples else "기존 소제목 없음"
        if action == "consider_deleting_existing_subtitle":
            position = flag.get("subtitle_end")
            if position is None:
                continue
            opinion = (
                "의견: 소제목이 있는 회차가 소수입니다. 소제목은 무단 수정하지 말고 "
                "전체 형식 통일을 위해 이 소제목 삭제 후보로 검토하세요. "
                f"현황: 있음 {flag.get('present_count')} / 없음 {flag.get('missing_count')}."
            )
        elif action == "consider_adding_missing_subtitle":
            position = flag.get("marker_end")
            if position is None:
                continue
            opinion = (
                "의견: 소제목이 없는 회차가 소수입니다. 소제목은 무단 작성하지 말고 "
                "기존 소제목 톤과 길이에 맞춘 추가 후보로 검토하세요. "
                f"현황: 있음 {flag.get('present_count')} / 없음 {flag.get('missing_count')}. "
                f"기존 예시: {example_text}."
            )
        else:
            continue
        events.append(
            MarkerEvent(
                start=int(position),
                end=int(position),
                order=-9 + index,
                change_id="subtitle-note",
                marker="ⓐⓐ",
                runs=[
                    ReviewRun(" ⓐⓐ("),
                    ReviewRun(opinion, BLUE_CHARPR),
                    ReviewRun(")"),
                ],
            )
        )
    return events


def apply_marker_events(
    source_text: str,
    events: list[MarkerEvent],
    *,
    issues: list[dict[str, Any]],
) -> list[ReviewRun]:
    runs: list[ReviewRun] = []
    cursor = 0
    for event in sorted(events, key=lambda item: (item.start, item.end, item.order)):
        if event.start < cursor:
            issues.append(
                {
                    "id": event.change_id,
                    "field": "find",
                    "message": "marker event overlaps a previous change; skipped",
                }
            )
            continue
        if event.start > cursor:
            runs.append(ReviewRun(source_text[cursor : event.start]))
        runs.extend(event.runs)
        cursor = event.end
    if cursor < len(source_text):
        runs.append(ReviewRun(source_text[cursor:]))
    return runs


def split_runs_to_paragraphs(runs: list[ReviewRun]) -> list[list[ReviewRun]]:
    paragraphs: list[list[ReviewRun]] = [[]]
    for run in runs:
        text = run.text.replace("\r\n", "\n").replace("\r", "\n")
        parts = text.split("\n")
        for index, part in enumerate(parts):
            if index:
                paragraphs.append([])
            if part:
                paragraphs[-1].append(ReviewRun(part, run.char_pr))
    return paragraphs


def build_review_lines(
    *,
    source_text: str,
    changes: list[dict[str, Any]],
    issues: list[dict[str, Any]],
    title: str,
    loop_label: str,
    window_chars: int,
) -> list[list[ReviewRun]]:
    lines: list[list[ReviewRun]] = []

    def add(text: str = "", *, blue: bool = False) -> None:
        if not text:
            lines.append([])
            return
        for chunk in chunk_text(text):
            lines.append([ReviewRun(chunk, BLUE_CHARPR if blue else BLACK_CHARPR)])

    def add_mixed(parts: list[tuple[str, bool]]) -> None:
        runs = [
            ReviewRun(text, BLUE_CHARPR if blue else BLACK_CHARPR)
            for text, blue in parts
            if text
        ]
        lines.append(runs)

    add(title)
    add(f"Loop: {loop_label or '(not specified)'}")
    add("이 문서는 원고 적용본이 아니라 중간 승인 판단용 HWPX입니다.")
    add("파란색 = 승인하면 실제로 들어가거나 실행되는 제안. 검정색 = 원문/근거/질문.")
    add("체크 기준: 승인 / 반려 / 수정 후 승인 중 하나로 보면 됩니다.")
    add()
    add("요약")
    add(f"ⓐⓐ 판단 항목: {len(changes)}건")
    add("우선순위: 중복 삭제, 브리지 추가, 회차 분량 보강, AI 티 완화 순으로 확인합니다.")
    add()

    if not changes:
        add("현재 changes 파일에는 ⓐⓐ 항목이 없습니다.")
        return lines

    for index, change in enumerate(changes, start=1):
        operation = infer_operation(change)
        context, issue = context_for_change(source_text, change, window_chars=window_chars)
        if issue:
            issues.append({"id": change.get("id", f"change-{index:04d}"), **issue})

        add(f"[{index}] {change.get('id', f'change-{index:04d}')}")
        add_mixed(
            [
                ("위치: ", False),
                (str(change.get("location", "") or "(unknown)"), True),
                (" / 종류: ", False),
                (str(change.get("edit_class", "") or operation), True),
            ]
        )
        add("판단할 것: " + decision_prompt(change, operation))
        add("내 추천/근거: " + (review_reason_text(change) or "(reason 없음)"))
        reading_basis = str(change.get("reading_basis", "") or "")
        if reading_basis:
            add("읽은 근거: " + reading_basis)
        add_mixed([("승인 시 변화: ", False), (approve_effect(change, operation, context), True)])
        add("반려 시: 원문 유지")
        add_mixed([("제안 표시: ", False), (marker_preview(change, operation, context), True)])
        add("체크: [  ] 승인   [  ] 반려   [  ] 수정 후 승인")
        add("원문 문맥")
        add("앞문맥: " + (context.get("before") or "(앵커 앞문맥 없음)"))
        add("대상/앵커: " + (context.get("target") or str(change.get("find", ""))))
        add("뒷문맥: " + (context.get("after") or "(앵커 뒷문맥 없음)"))
        if issue:
            add("주의: " + issue["message"])
        add()

    add("끝. 이 HWPX는 중간 판단표이며 최종 원고로 사용하지 않습니다.")
    return lines


def infer_operation(change: dict[str, Any]) -> str:
    operation = str(change.get("operation", "")).strip()
    if operation:
        return operation
    return "delete" if change.get("replace") == "" else "replace"


def decision_prompt(change: dict[str, Any], operation: str) -> str:
    edit_class = str(change.get("edit_class", "")).lower()
    if operation == "delete":
        return "삭제해도 정보 손실이 없는 중복/리캡인지, 합본 기준으로 빼는 게 맞는지 판단."
    if operation in {"insert_before", "insert_after"}:
        return "추가 문장이 장면 연결, 회차 분량, 감정선을 보강하면서 새 설정을 만들지 않는지 판단."
    if "slop" in edit_class:
        return "AI-slop 신호(반복, 추상 강도어, 균질한 문장 리듬)를 줄이되 원문 톤을 과하게 바꾸지 않는지 판단."
    if "bridge" in edit_class:
        return "브리지가 앞뒤 회차의 인과를 자연스럽게 잇는지 판단."
    return "원문 의도 가능성이 남는 적극 편집인지, 승인해도 되는지 판단."


def approve_effect(change: dict[str, Any], operation: str, context: dict[str, str]) -> str:
    replace = normalize_inline(str(change.get("replace", "")))
    target = context.get("target") or normalize_inline(str(change.get("find", "")))
    if operation == "delete":
        return f"아래 대상 삭제: {target}"
    if operation == "insert_before":
        return f"앵커 앞에 추가: {replace}"
    if operation == "insert_after":
        return f"앵커 뒤에 추가: {replace}"
    return f"{target} -> {replace}"


def marker_preview(change: dict[str, Any], operation: str, context: dict[str, str]) -> str:
    return f"ⓐⓐ({aa_opinion_text(change, operation)})"


def context_for_change(
    source_text: str,
    change: dict[str, Any],
    *,
    window_chars: int,
) -> tuple[dict[str, str], dict[str, Any] | None]:
    find = str(change.get("find", ""))
    if not find:
        return {}, {"field": "find", "message": "find anchor is empty"}
    positions = find_occurrences(source_text, find)
    if not positions:
        return {}, {"field": "find", "message": "anchor not found in source text"}
    occurrence = int(change.get("occurrence") or 1)
    if occurrence < 1 or occurrence > len(positions):
        return (
            {},
            {
                "field": "occurrence",
                "message": "occurrence is outside anchor match count",
                "matches": len(positions),
            },
        )

    start = positions[occurrence - 1]
    end = start + len(find)
    return (
        {
            "before": normalize_inline(source_text[max(0, start - window_chars) : start]),
            "target": normalize_inline(source_text[start:end]),
            "after": normalize_inline(source_text[end : end + window_chars]),
        },
        None,
    )


def find_occurrences(text: str, needle: str) -> list[int]:
    positions: list[int] = []
    start = 0
    while True:
        index = text.find(needle, start)
        if index < 0:
            return positions
        positions.append(index)
        start = index + max(len(needle), 1)


def normalize_inline(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def chunk_text(text: str, limit: int = LINE_CHARS) -> list[str]:
    text = sanitize_xml_text(text)
    if len(text) <= limit:
        return [text]
    chunks: list[str] = []
    current = text
    while len(current) > limit:
        split_at = current.rfind(" ", 0, limit)
        if split_at < max(40, limit // 3):
            split_at = limit
        chunks.append(current[:split_at].strip())
        current = current[split_at:].strip()
    if current:
        chunks.append(current)
    return chunks


def sanitize_xml_text(text: str) -> str:
    return "".join(
        ch
        for ch in text
        if ch in "\t\n\r" or ord(ch) >= 0x20
    )


def write_hwpx(output_path: Path, lines: list[list[ReviewRun]], *, title: str) -> None:
    section_xml, preview_text = build_section_xml(lines)
    files = {
        "mimetype": b"application/hwp+zip",
        "version.xml": version_xml().encode("utf-8"),
        "META-INF/container.xml": container_xml().encode("utf-8"),
        "META-INF/container.rdf": container_rdf().encode("utf-8"),
        "META-INF/manifest.xml": manifest_xml().encode("utf-8"),
        "settings.xml": settings_xml().encode("utf-8"),
        "Preview/PrvText.txt": preview_text.encode("utf-8"),
        "Contents/content.hpf": content_hpf(title).encode("utf-8"),
        "Contents/header.xml": header_xml().encode("utf-8"),
        "Contents/section0.xml": section_xml.encode("utf-8"),
    }
    with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("mimetype", files.pop("mimetype"), compress_type=zipfile.ZIP_STORED)
        for name, data in files.items():
            archive.writestr(name, data)


def build_section_xml(lines: list[list[ReviewRun]]) -> tuple[str, str]:
    paras: list[str] = []
    preview: list[str] = []
    vert = 0
    for index, runs in enumerate(lines):
        body = ""
        if index == 0:
            body += section_properties_run()
        if not runs:
            body += f'<hp:run charPrIDRef="{BLACK_CHARPR}"/>'
            preview.append("")
        else:
            body += "".join(render_run(run) for run in runs)
            preview.append("".join(run.text for run in runs))
        line_count = estimate_line_count(preview[-1])
        line_segments = "" if HWPX_RENDERER_OWNS_LAYOUT else line_seg_array(vert, line_count)
        paras.append(
            (
                f'<hp:p id="{index}" paraPrIDRef="0" styleIDRef="0" pageBreak="0" '
                f'columnBreak="0" merged="0">{body}{line_segments}</hp:p>'
            )
        )
        if not HWPX_RENDERER_OWNS_LAYOUT:
            vert += LINE_HEIGHT * line_count
    return section_root_start() + "".join(paras) + "</hs:sec>", "\n".join(preview)


def estimate_line_count(text: str) -> int:
    if not text:
        return 1
    return max(1, (len(text) + HWPX_CHARS_PER_LINE - 1) // HWPX_CHARS_PER_LINE)


def render_run(run: ReviewRun) -> str:
    text = xml_escape(sanitize_xml_text(run.text), quote=False)
    return f'<hp:run charPrIDRef="{run.char_pr}"><hp:t>{text}</hp:t></hp:run>'


def line_seg_array(vert: int, line_count: int) -> str:
    segments = []
    for line_index in range(line_count):
        textpos = line_index * HWPX_CHARS_PER_LINE
        line_vert = vert + (line_index * LINE_HEIGHT)
        segments.append(
            f'<hp:lineseg textpos="{textpos}" vertpos="{line_vert}" '
            f'vertsize="{LINE_SEG_TEXT_HEIGHT}" textheight="{LINE_SEG_TEXT_HEIGHT}" '
            f'baseline="{LINE_SEG_BASELINE}" spacing="{LINE_SEG_SPACING}" horzpos="0" '
            f'horzsize="{HWPX_TEXT_WIDTH}" flags="393216"/>'
        )
    return "<hp:linesegarray>" + "".join(segments) + "</hp:linesegarray>"


def section_root_start() -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>'
        '<hs:sec xmlns:ha="http://www.hancom.co.kr/hwpml/2011/app" '
        'xmlns:hp="http://www.hancom.co.kr/hwpml/2011/paragraph" '
        'xmlns:hp10="http://www.hancom.co.kr/hwpml/2016/paragraph" '
        'xmlns:hs="http://www.hancom.co.kr/hwpml/2011/section" '
        'xmlns:hc="http://www.hancom.co.kr/hwpml/2011/core" '
        'xmlns:hh="http://www.hancom.co.kr/hwpml/2011/head" '
        'xmlns:hhs="http://www.hancom.co.kr/hwpml/2011/history" '
        'xmlns:hm="http://www.hancom.co.kr/hwpml/2011/master-page" '
        'xmlns:hpf="http://www.hancom.co.kr/schema/2011/hpf" '
        'xmlns:dc="http://purl.org/dc/elements/1.1/" '
        'xmlns:opf="http://www.idpf.org/2007/opf/" '
        'xmlns:ooxmlchart="http://www.hancom.co.kr/hwpml/2016/ooxmlchart" '
        'xmlns:hwpunitchar="http://www.hancom.co.kr/hwpml/2016/HwpUnitChar" '
        'xmlns:epub="http://www.idpf.org/2007/ops" '
        'xmlns:config="urn:oasis:names:tc:opendocument:xmlns:config:1.0">'
    )


def section_properties_run() -> str:
    return (
        f'<hp:run charPrIDRef="{BLACK_CHARPR}">'
        '<hp:secPr id="" textDirection="HORIZONTAL" spaceColumns="1134" tabStop="8000" '
        'tabStopVal="4000" tabStopUnit="HWPUNIT" outlineShapeIDRef="1" '
        'memoShapeIDRef="1" textVerticalWidthHead="0" masterPageCnt="0">'
        '<hp:grid lineGrid="0" charGrid="0" wonggojiFormat="0"/>'
        '<hp:startNum pageStartsOn="BOTH" page="0" pic="0" tbl="0" equation="0"/>'
        '<hp:visibility hideFirstHeader="0" hideFirstFooter="0" hideFirstMasterPage="0" '
        'border="SHOW_ALL" fill="SHOW_ALL" hideFirstPageNum="0" hideFirstEmptyLine="0" '
        'showLineNumber="0"/>'
        '<hp:lineNumberShape restartType="0" countBy="0" distance="0" startNumber="0"/>'
        f'<hp:pagePr landscape="WIDELY" width="{HWPX_PAGE_WIDTH}" '
        f'height="{HWPX_PAGE_HEIGHT}" gutterType="LEFT_ONLY">'
        f'<hp:margin header="{HWPX_MARGIN_HEADER}" footer="{HWPX_MARGIN_FOOTER}" '
        f'gutter="{HWPX_MARGIN_GUTTER}" left="{HWPX_MARGIN_LEFT}" '
        f'right="{HWPX_MARGIN_RIGHT}" top="{HWPX_MARGIN_TOP}" '
        f'bottom="{HWPX_MARGIN_BOTTOM}"/></hp:pagePr>'
        '<hp:footNotePr><hp:autoNumFormat type="DIGIT" userChar="" prefixChar="" '
        'suffixChar=")" supscript="0"/><hp:noteLine length="-1" type="SOLID" '
        'width="0.12 mm" color="#000000"/><hp:noteSpacing betweenNotes="283" '
        'belowLine="567" aboveLine="850"/><hp:numbering type="CONTINUOUS" newNum="1"/>'
        '<hp:placement place="EACH_COLUMN" beneathText="0"/></hp:footNotePr>'
        '<hp:endNotePr><hp:autoNumFormat type="DIGIT" userChar="" prefixChar="" '
        'suffixChar=")" supscript="0"/><hp:noteLine length="-1" type="SOLID" '
        'width="0.12 mm" color="#000000"/><hp:noteSpacing betweenNotes="0" belowLine="567" '
        'aboveLine="850"/><hp:numbering type="CONTINUOUS" newNum="1"/>'
        '<hp:placement place="END_OF_DOCUMENT" beneathText="0"/></hp:endNotePr>'
        '<hp:pageBorderFill type="BOTH" borderFillIDRef="1" textBorder="PAPER" '
        'headerInside="0" footerInside="0" fillArea="PAPER">'
        '<hp:offset left="1417" right="1417" top="1417" bottom="1417"/>'
        '</hp:pageBorderFill>'
        '</hp:secPr><hp:ctrl><hp:colPr id="" type="NEWSPAPER" layout="LEFT" colCount="1" '
        'sameSz="1" sameGap="0"/></hp:ctrl></hp:run>'
    )


def header_xml() -> str:
    fontface_langs = ["HANGUL", "LATIN", "HANJA", "JAPANESE", "OTHER", "SYMBOL", "USER"]
    fontfaces = "".join(fontface(lang) for lang in fontface_langs)
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>'
        '<hh:head xmlns:ha="http://www.hancom.co.kr/hwpml/2011/app" '
        'xmlns:hp="http://www.hancom.co.kr/hwpml/2011/paragraph" '
        'xmlns:hp10="http://www.hancom.co.kr/hwpml/2016/paragraph" '
        'xmlns:hs="http://www.hancom.co.kr/hwpml/2011/section" '
        'xmlns:hc="http://www.hancom.co.kr/hwpml/2011/core" '
        'xmlns:hh="http://www.hancom.co.kr/hwpml/2011/head" '
        'xmlns:hhs="http://www.hancom.co.kr/hwpml/2011/history" '
        'xmlns:hm="http://www.hancom.co.kr/hwpml/2011/master-page" '
        'xmlns:hpf="http://www.hancom.co.kr/schema/2011/hpf" '
        'xmlns:dc="http://purl.org/dc/elements/1.1/" '
        'xmlns:opf="http://www.idpf.org/2007/opf/" '
        'xmlns:ooxmlchart="http://www.hancom.co.kr/hwpml/2016/ooxmlchart" '
        'xmlns:hwpunitchar="http://www.hancom.co.kr/hwpml/2016/HwpUnitChar" '
        'xmlns:epub="http://www.idpf.org/2007/ops" '
        'xmlns:config="urn:oasis:names:tc:opendocument:xmlns:config:1.0" '
        'version="1.4" secCnt="1">'
        '<hh:beginNum page="1" footnote="1" endnote="1" pic="1" tbl="1" equation="1"/>'
        '<hh:refList>'
        f'<hh:fontfaces itemCnt="7">{fontfaces}</hh:fontfaces>'
        '<hh:borderFills itemCnt="2"><hh:borderFill id="1" threeD="0" shadow="0" '
        'centerLine="NONE" breakCellSeparateLine="0"><hh:slash type="NONE" Crooked="0" '
        'isCounter="0"/><hh:backSlash type="NONE" Crooked="0" isCounter="0"/>'
        '<hh:leftBorder type="NONE" width="0.1 mm" color="#000000"/>'
        '<hh:rightBorder type="NONE" width="0.1 mm" color="#000000"/>'
        '<hh:topBorder type="NONE" width="0.1 mm" color="#000000"/>'
        '<hh:bottomBorder type="NONE" width="0.1 mm" color="#000000"/>'
        '<hh:diagonal type="SOLID" width="0.1 mm" color="#000000"/>'
        '</hh:borderFill><hh:borderFill id="2" threeD="0" shadow="0" centerLine="NONE" '
        'breakCellSeparateLine="0"><hh:slash type="NONE" Crooked="0" isCounter="0"/>'
        '<hh:backSlash type="NONE" Crooked="0" isCounter="0"/>'
        '<hh:leftBorder type="NONE" width="0.1 mm" color="#000000"/>'
        '<hh:rightBorder type="NONE" width="0.1 mm" color="#000000"/>'
        '<hh:topBorder type="NONE" width="0.1 mm" color="#000000"/>'
        '<hh:bottomBorder type="NONE" width="0.1 mm" color="#000000"/>'
        '<hh:diagonal type="SOLID" width="0.1 mm" color="#000000"/>'
        '<hc:fillBrush><hc:winBrush faceColor="none" hatchColor="#FF000000" alpha="0"/>'
        '</hc:fillBrush></hh:borderFill></hh:borderFills>'
        '<hh:charProperties itemCnt="2">'
        f'{char_pr(BLACK_CHARPR, "#000000")}{char_pr(BLUE_CHARPR, BLUE)}'
        '</hh:charProperties>'
        '<hh:tabProperties itemCnt="1"><hh:tabPr id="0" autoTabLeft="0" autoTabRight="1"/>'
        '</hh:tabProperties>'
        '<hh:numberings itemCnt="1"><hh:numbering id="1" start="1"/>'
        '</hh:numberings>'
        '<hh:paraProperties itemCnt="1"><hh:paraPr id="0" tabPrIDRef="0" condense="0" '
        'fontLineHeight="0" snapToGrid="1" suppressLineNumbers="0" checked="0">'
        '<hh:align horizontal="JUSTIFY" vertical="BASELINE"/>'
        '<hh:heading type="NONE" idRef="0" level="0"/>'
        '<hh:breakSetting breakLatinWord="KEEP_WORD" breakNonLatinWord="BREAK_WORD" '
        'widowOrphan="0" keepWithNext="0" keepLines="0" pageBreakBefore="0" '
        'lineWrap="BREAK"/>'
        '<hh:autoSpacing eAsianEng="0" eAsianNum="0"/>'
        '<hp:switch><hp:case hp:required-namespace="http://www.hancom.co.kr/hwpml/2016/HwpUnitChar">'
        '<hh:margin><hc:intent value="0" unit="HWPUNIT"/><hc:left value="0" unit="HWPUNIT"/>'
        '<hc:right value="0" unit="HWPUNIT"/><hc:prev value="0" unit="HWPUNIT"/>'
        '<hc:next value="0" unit="HWPUNIT"/></hh:margin>'
        '<hh:lineSpacing type="PERCENT" value="160" unit="HWPUNIT"/></hp:case><hp:default>'
        '<hh:margin><hc:intent value="0" unit="HWPUNIT"/><hc:left value="0" unit="HWPUNIT"/>'
        '<hc:right value="0" unit="HWPUNIT"/><hc:prev value="0" unit="HWPUNIT"/>'
        '<hc:next value="0" unit="HWPUNIT"/></hh:margin>'
        '<hh:lineSpacing type="PERCENT" value="160" unit="HWPUNIT"/></hp:default></hp:switch>'
        '<hh:border borderFillIDRef="2" offsetLeft="0" offsetRight="0" offsetTop="0" '
        'offsetBottom="0" connect="0" ignoreMargin="0"/>'
        '</hh:paraPr></hh:paraProperties>'
        '<hh:styles itemCnt="1"><hh:style id="0" type="PARA" name="바탕글" engName="Normal" '
        'paraPrIDRef="0" charPrIDRef="0" nextStyleIDRef="0" langID="1042" lockForm="0"/>'
        '</hh:styles>'
        '</hh:refList></hh:head>'
    )


def fontface(lang: str) -> str:
    return (
        f'<hh:fontface lang="{lang}" fontCnt="3"><hh:font id="0" face="바탕" '
        'type="TTF" isEmbedded="0"><hh:typeInfo familyType="FCAT_GOTHIC" weight="6" '
        'proportion="0" contrast="0" strokeVariation="1" armStyle="1" letterform="1" '
        'midline="1" xHeight="1"/></hh:font><hh:font id="1" face="함초롬돋움" '
        'type="TTF" isEmbedded="0"><hh:typeInfo familyType="FCAT_GOTHIC" weight="6" '
        'proportion="4" contrast="0" strokeVariation="1" armStyle="1" letterform="1" '
        'midline="1" xHeight="1"/></hh:font><hh:font id="2" face="함초롬바탕" '
        'type="TTF" isEmbedded="0"><hh:typeInfo familyType="FCAT_GOTHIC" weight="6" '
        'proportion="4" contrast="0" strokeVariation="1" armStyle="1" letterform="1" '
        'midline="1" xHeight="1"/></hh:font></hh:fontface>'
    )


def char_pr(char_id: str, color: str) -> str:
    return (
        f'<hh:charPr id="{char_id}" height="{HWPX_FONT_HEIGHT}" '
        f'textColor="{color}" shadeColor="none" '
        'useFontSpace="0" useKerning="0" symMark="NONE" borderFillIDRef="2">'
        '<hh:fontRef hangul="2" latin="2" hanja="2" japanese="2" other="2" symbol="2" user="2"/>'
        '<hh:ratio hangul="100" latin="100" hanja="100" japanese="100" other="100" '
        'symbol="100" user="100"/>'
        '<hh:spacing hangul="0" latin="0" hanja="0" japanese="0" other="0" symbol="0" user="0"/>'
        '<hh:relSz hangul="100" latin="100" hanja="100" japanese="100" other="100" '
        'symbol="100" user="100"/>'
        '<hh:offset hangul="0" latin="0" hanja="0" japanese="0" other="0" symbol="0" user="0"/>'
        '<hh:underline type="NONE" shape="SOLID" color="#000000"/>'
        '<hh:strikeout shape="NONE" color="#000000"/>'
        '<hh:outline type="NONE"/>'
        '<hh:shadow type="NONE" color="#B2B2B2" offsetX="10" offsetY="10"/>'
        '<hh:emboss enabled="0"/>'
        '<hh:engrave enabled="0"/>'
        '<hh:supscript enabled="0"/>'
        '<hh:subscript enabled="0"/>'
        '</hh:charPr>'
    )


def content_hpf(title: str) -> str:
    safe_title = xml_escape(sanitize_xml_text(title), quote=True)
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>'
        '<opf:package xmlns:opf="http://www.idpf.org/2007/opf/" version="" '
        'unique-identifier="" id=""><opf:metadata>'
        f'<opf:title>{safe_title}</opf:title><opf:language>ko</opf:language>'
        '<opf:meta name="creator" content="text">novel-qc-loop</opf:meta>'
        '<opf:meta name="subject" content="text">editorial review</opf:meta>'
        '<opf:meta name="description" content="text">AA decision review</opf:meta>'
        '<opf:meta name="lastsaveby" content="text">Codex</opf:meta>'
        '<opf:meta name="CreatedDate" content="text">2026-05-15T00:00:00Z</opf:meta>'
        '<opf:meta name="ModifiedDate" content="2026-05-15T00:00:00Z">'
        '2026-05-15T00:00:00Z</opf:meta>'
        '<opf:meta name="date" content="text">2026-05-15</opf:meta>'
        '</opf:metadata><opf:manifest>'
        '<opf:item id="header" href="Contents/header.xml" media-type="application/xml" />'
        '<opf:item id="settings" href="settings.xml" media-type="application/xml" />'
        '<opf:item id="section0" href="Contents/section0.xml" media-type="application/xml" />'
        '</opf:manifest><opf:spine><opf:itemref idref="header" />'
        '<opf:itemref idref="section0" /></opf:spine></opf:package>'
    )


def version_xml() -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>'
        '<hv:HCFVersion xmlns:hv="http://www.hancom.co.kr/hwpml/2011/version" '
        'tagetApplication="WORDPROCESSOR" major="5" minor="1" micro="0" buildNumber="1" '
        'os="1" xmlVersion="1.4" application="Hancom Office Hangul" appVersion="11"/>'
    )


def settings_xml() -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>'
        '<ha:HWPApplicationSetting xmlns:ha="http://www.hancom.co.kr/hwpml/2011/app" '
        'xmlns:config="urn:oasis:names:tc:opendocument:xmlns:config:1.0">'
        '<ha:CaretPosition listIDRef="0" paraIDRef="0" pos="0"/>'
        '</ha:HWPApplicationSetting>'
    )


def container_xml() -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>'
        '<ocf:container xmlns:ocf="urn:oasis:names:tc:opendocument:xmlns:container" '
        'xmlns:hpf="http://www.hancom.co.kr/schema/2011/hpf"><ocf:rootfiles>'
        '<ocf:rootfile full-path="Contents/content.hpf" '
        'media-type="application/hwpml-package+xml"/>'
        '<ocf:rootfile full-path="Preview/PrvText.txt" media-type="text/plain"/>'
        '<ocf:rootfile full-path="META-INF/container.rdf" media-type="application/rdf+xml"/>'
        '</ocf:rootfiles></ocf:container>'
    )


def container_rdf() -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>'
        '<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">'
        '<rdf:Description rdf:about=""><pkg:hasPart '
        'xmlns:pkg="http://www.hancom.co.kr/hwpml/2016/meta/pkg#" '
        'rdf:resource="Contents/header.xml"/></rdf:Description>'
        '<rdf:Description rdf:about="Contents/header.xml"><rdf:type '
        'rdf:resource="http://www.hancom.co.kr/hwpml/2016/meta/pkg#HeaderFile"/>'
        '</rdf:Description><rdf:Description rdf:about=""><pkg:hasPart '
        'xmlns:pkg="http://www.hancom.co.kr/hwpml/2016/meta/pkg#" '
        'rdf:resource="Contents/section0.xml"/></rdf:Description>'
        '<rdf:Description rdf:about="Contents/section0.xml"><rdf:type '
        'rdf:resource="http://www.hancom.co.kr/hwpml/2016/meta/pkg#SectionFile"/>'
        '</rdf:Description><rdf:Description rdf:about=""><rdf:type '
        'rdf:resource="http://www.hancom.co.kr/hwpml/2016/meta/pkg#Document"/>'
        '</rdf:Description></rdf:RDF>'
    )


def manifest_xml() -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>'
        '<odf:manifest xmlns:odf="urn:oasis:names:tc:opendocument:xmlns:manifest:1.0"/>'
    )
