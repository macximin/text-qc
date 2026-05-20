from __future__ import annotations

import html
import re
from collections import defaultdict
from typing import Any


TEMPORAL_ANCHOR_RE = re.compile(
    r"(?P<raw>(?:\d{4}년\s*)?\d{1,2}월\s*\d{1,2}일|"
    r"\d{1,2}:\d{2}|"
    r"오늘|금일|당일|어제|내일|다음 날|그날|같은 날|방금|조금 전|잠시 후|며칠 후|"
    r"그날 밤|그날 오전|그날 오후|새벽|아침|정오|저녁|밤|하루 뒤|이튿날)"
)
NEGATION_RE = re.compile(
    r"않|안\s|못|없(?:다|었다|었|고|는|어|음|을|다면|지만|지)|금지|거부|불가|중단|철회|취소|보류|미수행|미완|아직"
)
AFFIRMATION_RE = re.compile(r"했|했다|마쳤|완료|끝냈|확인|승인|서명|시작|유지|넣|눌렀|받았|보냈|만났|나섰|들어갔")
PLAN_RE = re.compile(r"해야\s*했|해야\s*한다|하려|할 생각|할 계획|예정|준비|기다리|필요")
HARD_AFFIRMATION_RE = re.compile(r"마쳤|완료|끝냈|확인했다|승인|서명|눌렀|넣었|받았|보냈|만났")
STATE_TRACE_RE = re.compile(r"이미|아직|더 이상|처음|다시|결국|마침내|한 번도|단 한")

ACTION_PATTERNS: tuple[tuple[str, str, re.Pattern[str]], ...] = (
    ("report", "보고/연락 상태", re.compile(r"보고|연락|통화|전화|회선")),
    ("trade_order", "주문/포지션 상태", re.compile(r"매수|매도|청산|주문|포지션|계약|호가|진입")),
    ("approval", "승인/결재 상태", re.compile(r"승인|결재|허가|가승인|본승인|한도")),
    ("signing", "서명/문서 처리", re.compile(r"서명|신청서|해지|서류|계약서")),
    ("money_flow", "자금 이동/분리", re.compile(r"이체|송금|입금|출금|현금화|분리|동결|자금")),
    ("visit_movement", "방문/외출/복귀", re.compile(r"방문|외출|나섰|나갔|돌아|들어갔|빠져나왔")),
    ("meeting", "만남/상담/대화", re.compile(r"만났|상담|대화|대면|불렀|호출")),
    ("knowledge", "인지/확인 상태", re.compile(r"알았|몰랐|확인|기억|눈치|파악")),
)


def extract_verisimilitude_candidates(chapters: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen_conflicts: set[tuple[str, str, int, int]] = set()

    for chapter in chapters:
        episode = str(chapter.get("episode") or "")
        lines = str(chapter.get("text") or "").splitlines()
        anchor = {"value": "episode_start", "line": 1}
        traces: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)

        for index, raw_line in enumerate(lines, start=1):
            line = html.unescape(raw_line.strip())
            if not line:
                continue
            anchor_match = TEMPORAL_ANCHOR_RE.search(line)
            if anchor_match:
                anchor = {"value": anchor_match.group("raw"), "line": index}

            actions = classify_action_line(line)
            polarity = classify_polarity(line)
            if actions and polarity in {"affirmed", "negated"}:
                for action_key, action_label in actions:
                    trace = {
                        "episode": episode,
                        "line": index,
                        "anchor_value": anchor["value"],
                        "anchor_line": anchor["line"],
                        "action_key": action_key,
                        "action_label": action_label,
                        "polarity": polarity,
                        "context": line[:260],
                    }
                    opposite = "negated" if polarity == "affirmed" else "affirmed"
                    bucket = f"{episode}:{anchor['value']}"
                    for prior in traces.get((bucket, action_key, opposite), [])[-3:]:
                        if abs(index - int(prior["line"])) > 160:
                            continue
                        conflict_key = (action_key, bucket, int(prior["line"]), index)
                        if conflict_key in seen_conflicts:
                            continue
                        seen_conflicts.add(conflict_key)
                        rows.append(build_conflict_row(prior, trace, bucket))
                    traces[(bucket, action_key, polarity)].append(trace)

            if should_emit_state_trace(line, actions):
                rows.append(
                    {
                        "kind": "state_trace_checkpoint",
                        "axis": "verisimilitude_continuity",
                        "episode": episode,
                        "line": index,
                        "temporal_anchor": anchor["value"],
                        "action_labels": [label for _, label in actions],
                        "context": line[:260],
                        "strictness": "hard_carryover",
                        "disposition_hint": "hard_carryover_conflict",
                        "allowance_check_required": True,
                        "repairability_hint": "local_fixable",
                        "priority_hint": "P1 후보는 아님. 뒤에서 상태가 뒤집히는지 수동 감리",
                        "review_hint": (
                            "이미/아직/더 이상/처음/다시 같은 상태 전환어가 있는 줄입니다. "
                            "이후 장면에서 같은 행동이나 상태가 반대로 서술되는지 확인합니다."
                        ),
                    }
                )

    return dedupe_rows(rows)


def classify_action_line(line: str) -> list[tuple[str, str]]:
    hits = []
    for key, label, pattern in ACTION_PATTERNS:
        if pattern.search(line):
            hits.append((key, label))
    return hits


def classify_polarity(line: str) -> str:
    negated = bool(NEGATION_RE.search(line))
    affirmed = bool(AFFIRMATION_RE.search(line))
    planned = bool(PLAN_RE.search(line)) and not HARD_AFFIRMATION_RE.search(line)
    if planned:
        return "planned"
    if negated and not affirmed:
        return "negated"
    if affirmed and not negated:
        return "affirmed"
    if negated and affirmed:
        return "mixed"
    return "unknown"


def should_emit_state_trace(line: str, actions: list[tuple[str, str]]) -> bool:
    if not actions:
        return False
    return bool(STATE_TRACE_RE.search(line) or TEMPORAL_ANCHOR_RE.search(line))


def build_conflict_row(first: dict[str, Any], second: dict[str, Any], bucket: str) -> dict[str, Any]:
    return {
        "kind": "possible_internal_action_conflict",
        "axis": "verisimilitude_continuity",
        "episode": second["episode"],
        "temporal_bucket": bucket,
        "action_key": second["action_key"],
        "action_label": second["action_label"],
        "first_line": first["line"],
        "second_line": second["line"],
        "first_polarity": first["polarity"],
        "second_polarity": second["polarity"],
        "evidence": [first["context"], second["context"]],
        "confidence": "medium",
        "strictness": "hard_carryover",
        "disposition_hint": "hard_carryover_conflict",
        "allowance_check_required": True,
        "repairability_hint": "local_fixable",
        "priority_hint": "수동 확인 후 실제 충돌이면 P0/P1 우선 후보",
        "review_hint": (
            "같은 작중 시점/장면 안에서 수행 상태와 미수행 상태가 함께 잡힌 후보입니다. "
            "화자, 조건, 대상이 같은지 확인하고 같다면 외부 고증보다 우선합니다."
        ),
    }


def dedupe_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    deduped = []
    seen: set[tuple[Any, ...]] = set()
    for row in rows:
        key = (
            row.get("kind"),
            row.get("episode"),
            row.get("line") or row.get("first_line"),
            row.get("second_line"),
            row.get("action_key"),
            row.get("context") or tuple(row.get("evidence") or []),
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(row)
    return deduped
