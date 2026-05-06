from __future__ import annotations

import re
from typing import Any


BRACKETED_LINE_RE = re.compile(r"^\s*\[(?P<body>[^\]\n]{1,160})\]\s*$")

AUTHORIAL_MARKER_TERMS = (
    "TODO",
    "TBD",
    "FIXME",
    "작가",
    "편집",
    "교정",
    "검수",
    "수정",
    "삭제",
    "추가",
    "확인",
    "메모",
    "보강",
    "복선",
    "설정",
    "나중에",
    "여기",
    "장면",
    "대사",
    "묘사",
    "삽입",
    "정리",
)

STORYWORLD_CONTEXT_TERMS = (
    "뉴스",
    "속보",
    "헤드라인",
    "로이터",
    "블룸버그",
    "외신",
    "통신사",
    "단말기",
    "터미널",
    "화면",
    "모니터",
    "자막",
    "텍스트",
    "알림",
    "전광판",
    "문자",
    "메시지",
    "보고서",
    "브리핑",
    "기사",
    "신문",
    "방송",
    "앵커",
    "공시",
    "차트",
    "HTS",
    "호가창",
    "로그",
)

STORYWORLD_HEADLINE_TERMS = (
    "미국",
    "중국",
    "일본",
    "한국",
    "유럽",
    "UN",
    "WTI",
    "원유",
    "유가",
    "금리",
    "환율",
    "달러",
    "주가",
    "지수",
    "시장",
    "모기지",
    "연체율",
    "가격",
    "하락세",
    "상승세",
    "계약",
    "정부",
    "대통령",
    "발표",
    "선언",
    "공시",
    "긴급",
    "속보",
)


def classify_bracketed_line(lines: list[str], index: int, *, radius: int = 3) -> dict[str, Any] | None:
    """Classify a bracket-only line without flattening storyworld UI into author notes."""

    line = lines[index]
    match = BRACKETED_LINE_RE.match(line)
    if not match:
        return None

    body = match.group("body").strip()
    before = nearest_nonempty_lines(lines, index, radius=radius, direction=-1)
    after = nearest_nonempty_lines(lines, index, radius=radius, direction=1)
    context = "\n".join((*before, *after))
    body_upper = body.upper()
    context_upper = context.upper()

    authorial_terms = [
        term
        for term in AUTHORIAL_MARKER_TERMS
        if term in body or term.upper() in body_upper or term in context
    ]
    if authorial_terms:
        return {
            "classification": "authorial_or_editing_note",
            "blocks_submission": True,
            "confidence": "high",
            "reason": "대괄호 안팎에 작가/편집 메모성 단서가 있습니다.",
            "matched_terms": authorial_terms[:5],
            "body": body,
        }

    context_terms = [
        term
        for term in STORYWORLD_CONTEXT_TERMS
        if term in context or term.upper() in context_upper
    ]
    headline_terms = [
        term
        for term in STORYWORLD_HEADLINE_TERMS
        if term in body or term.upper() in body_upper
    ]
    looks_like_headline = len(headline_terms) >= 2 or (
        len(headline_terms) >= 1 and bool(re.search(r"[.。]|상승|하락|급등|급락|발표|선언", body))
    )

    if context_terms or looks_like_headline:
        reason = "주변 문맥 또는 문장 형태가 작중 뉴스/단말기/문서 표기에 가깝습니다."
        confidence = "high" if context_terms else "medium"
        return {
            "classification": "storyworld_artifact",
            "blocks_submission": False,
            "confidence": confidence,
            "reason": reason,
            "matched_terms": [*context_terms[:4], *headline_terms[:4]],
            "body": body,
        }

    return {
        "classification": "possible_stage_cue",
        "blocks_submission": True,
        "confidence": "medium",
        "reason": "대괄호 한 줄이지만 작중 UI/문서 표기로 볼 문맥 단서가 부족합니다.",
        "matched_terms": [],
        "body": body,
    }


def nearest_nonempty_lines(
    lines: list[str],
    index: int,
    *,
    radius: int,
    direction: int,
) -> list[str]:
    rows: list[str] = []
    cursor = index + direction
    while 0 <= cursor < len(lines) and len(rows) < radius:
        line = lines[cursor].strip()
        if line:
            rows.append(line)
        cursor += direction
    if direction < 0:
        rows.reverse()
    return rows


def classify_bracketed_lines(text: str) -> list[dict[str, Any]]:
    lines = text.splitlines()
    rows: list[dict[str, Any]] = []
    for index, line in enumerate(lines):
        result = classify_bracketed_line(lines, index)
        if not result:
            continue
        rows.append(
            {
                **result,
                "line": index + 1,
                "context": line.strip()[:260],
            }
        )
    return rows
