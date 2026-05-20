from __future__ import annotations


REVIEW_AXES: tuple[dict[str, str], ...] = (
    {"axis": "verisimilitude_continuity", "label": "핍진성/작중 인과 연속성"},
    {"axis": "timeline_continuity", "label": "작중 시간축 연속성"},
    {"axis": "numeric_carryover", "label": "숫자/금액 carryover"},
    {"axis": "title_role_drift", "label": "인물/직함 drift"},
    {"axis": "era_validation", "label": "외부 고증/시대감 후보"},
    {"axis": "replay_vs_escalation", "label": "replay vs escalation"},
    {"axis": "front_back_bridge", "label": "앞뒤 화 브리지"},
    {"axis": "character_consistency", "label": "캐릭터성/관계 일관성"},
    {"axis": "state_regression", "label": "사건 상태 회귀"},
    {"axis": "submission_hygiene", "label": "송고 위생"},
    {"axis": "reader_facing_polish", "label": "독자-facing 표현/문장"},
    {"axis": "non_reader_facing_notes", "label": "비독자-facing 내부 메모"},
)

EXCLUDED_REVIEW_SCOPES: tuple[dict[str, str], ...] = (
    {
        "scope": "ethics_line",
        "label": "윤리선/도덕성 판단",
        "rule": "윤리선은 하네스 판단 대상이 아니다. 정합성, 핍진성, 명시적 인과, 장면 정보 전달만 본다.",
    },
)

AUTHOR_INTENT_PROTECTION_RULE = (
    "원작 의도 보호가 우선이다. 하네스는 정합성 근거 없이 죄책감, 기부, 피해자 지원, 제보, "
    "독자 반감 완화, 최소 완충 같은 도덕/수용성 보강을 제안하지 않는다. "
    "이런 제안은 사용자가 별도로 요청했거나 원문에 이미 있는 요소의 정본/수치/상태를 맞출 때만 허용한다."
)

AI_GENERATED_TEXT_CONTINUITY_RULE = (
    "AI 작성 또는 AI 작성 의심 원고에서는 명시 표지 없는 시간 역류, 장면 접합, 중복 리캡, "
    "정보 상태 회귀를 작가 의도나 회상 장치로 구제하지 않는다. "
    "본문에 회상/며칠 전/다시 떠올림 같은 장치가 없으면 기본값은 AI 시간축 스플라이스 오류다."
)

CANONICAL_NAME_ALIAS_RULE = (
    "동일 인물, 기업, 기관으로 정본을 확정한 고유명사는 대표 표기 하나로 통일한다. "
    "약칭, 이니셜, 실명/가명 병기는 자동 허용하지 않고, 시세판, 기사 헤드라인, 괄호 설명처럼 "
    "장면 기능이 명확할 때만 원문 앵커와 함께 ⓐⓐ 예외 후보로 올린다."
)

PASS_NAMES: tuple[str, ...] = ("pass1", "pass2", "pass3")

PRIMARY_REVIEW_LANE = "primary"
BLIND_REVIEWERS: tuple[str, ...] = ("blind_agent_1", "blind_agent_2", "blind_agent_3")
REVIEW_LANES: tuple[str, ...] = (PRIMARY_REVIEW_LANE, *BLIND_REVIEWERS)

TOTAL_CONSISTENCY_REPORT_NAME = "total_consistency_report.md"
NUMBERED_ONE_PAGE_REPORT_NAME = "1차_one_page_report.md"
HARNESS_ADVERSARIAL_AUDIT_NAME = "harness_adversarial_audit_3pass.md"

DEFAULT_CONSISTENCY_UNIT_COUNT = 1
CONSISTENCY_CHECK_UNIT_ID = "consistency_3x3_unit"
CONSISTENCY_CHECK_UNIT_SUMMARY = (
    "정합성 검사 1회는 primary 3-pass, blind 3개 lane x 3-pass, "
    "total consistency report, total report 대상 adversarial 3-pass까지 포함한다."
)
CONSISTENCY_REPETITION_RULE = (
    "`정합성 검사`라고만 하면 1 consistency_3x3_unit을 뜻한다. "
    "`정합성 검사 3번`처럼 횟수를 지정하면 얕은 pass 3개가 아니라 "
    "consistency_3x3_unit 전체를 지정 횟수만큼 반복한다."
)

NTH_REPORT_VISIBLE_PRIORITIES: tuple[str, ...] = ("P0", "P1", "P2", "P3")
NTH_REPORT_CUMULATIVE_RULE = (
    "N차_one_page_report는 직전 차수 이후 새 항목만 쓰지 않고, P0-P3 전체 항목을 누적 장부로 유지한다. "
    "해결, 강등, 철회, 유보, 작가 판단 필요 항목도 삭제하지 않고 상태를 갱신하며, "
    "특정 등급이 0건이면 0건임을 명시한다."
)

REPAIRABILITY_VALUES: tuple[str, ...] = (
    "local_fixable",
    "structural_fixable",
    "needs_author_decision",
    "irreconcilable_premise",
    "webnovel_allowance",
)

DISPOSITION_VALUES: tuple[str, ...] = (
    "editable_conflict",
    "accepted_world_premise",
    "genre_hyperbole_allowance",
    "hard_carryover_conflict",
    "external_fact_soft",
    "needs_author_decision",
)

HARD_CARRYOVER_KINDS: tuple[str, ...] = (
    "date",
    "date_with_weekday",
    "absolute_date",
    "relative_time",
    "time",
    "money",
    "percent",
    "title_or_role",
    "kin_title",
    "state_carryover",
)

PREMISE_POLICY_SUMMARY = (
    "세계관 안에서 세운 제도/기술/경제 규칙은 전제로 수용하되, "
    "맥락 없이 던진 시대 불가능 설정은 worldbuilding gap으로 분리한다. "
    "웹소설식 과장과 허세는 허용하지만 숫자, 금액, 시간, 지분, 완료/미완료 상태 carryover는 엄격히 본다. "
    "동일 고유명사로 확정한 대상의 약칭/이니셜/실명 병기는 의도라고 자동 허용하지 않고 정본 통일을 우선한다. "
    "윤리선/도덕성 평가는 하네스의 알 바가 아니며, 재난/사전인지 장면도 원작 의도 보존을 우선하고 "
    "정합성, 핍진성, 명시적 인과, 장면 정보 전달만 판단한다."
)
