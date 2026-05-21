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

AUTHORITY_LAYERS: tuple[dict[str, str], ...] = (
    {
        "layer": "protocol_constants",
        "authority": "code",
        "rule": "하네스 계약의 최종 권위는 novel_qc_loop.protocol의 상수와 gate profile 정의다.",
    },
    {
        "layer": "run_manifest",
        "authority": "run",
        "rule": "개별 run은 run_manifest.json의 gate_profile과 artifacts를 실행 권위로 삼는다.",
    },
    {
        "layer": "manual_review_submission",
        "authority": "submission",
        "rule": "감리 완료 여부는 manual_review_submission.json을 gate profile에 맞춰 검증한다.",
    },
    {
        "layer": "human_facing_report",
        "authority": "delivery",
        "rule": "외부 전달 권위는 validate-report를 통과한 human-facing 보고서와 최종 후보본이다.",
    },
)

GATE_PROFILE_DELIVERY = "delivery"
GATE_PROFILE_CONSISTENCY = "consistency"
GATE_PROFILE_EDITORIAL = "editorial"
GATE_PROFILE_CORRECTION = "correction"
GATE_PROFILE_PROOFREAD = "proofread"

GATE_PROFILE_ORDER: tuple[str, ...] = (
    GATE_PROFILE_PROOFREAD,
    GATE_PROFILE_CORRECTION,
    GATE_PROFILE_EDITORIAL,
    GATE_PROFILE_CONSISTENCY,
    GATE_PROFILE_DELIVERY,
)

FULL_REVIEW_AXIS_IDS: tuple[str, ...] = tuple(item["axis"] for item in REVIEW_AXES)
SURFACE_REVIEW_AXIS_IDS: tuple[str, ...] = (
    "submission_hygiene",
    "reader_facing_polish",
)
EDITORIAL_REVIEW_AXIS_IDS: tuple[str, ...] = (
    "replay_vs_escalation",
    "front_back_bridge",
    "character_consistency",
    "submission_hygiene",
    "reader_facing_polish",
    "non_reader_facing_notes",
)

GATE_PROFILE_DEFINITIONS: dict[str, dict[str, object]] = {
    GATE_PROFILE_PROOFREAD: {
        "level": 1,
        "label": "표면 교정/송고 위생",
        "required_axes": SURFACE_REVIEW_AXIS_IDS,
        "require_primary_passes": False,
        "require_blind_reviews": False,
        "require_total_report": False,
        "require_adversarial_passes": False,
        "require_consistency_repetition": False,
        "require_delivery_report": False,
        "summary": "오탈자, 띄어쓰기, 문장부호, 송고 위생만 닫는 가벼운 gate.",
    },
    GATE_PROFILE_CORRECTION: {
        "level": 2,
        "label": "교정안 작성/마커 검수",
        "required_axes": (*SURFACE_REVIEW_AXIS_IDS, "non_reader_facing_notes"),
        "require_primary_passes": False,
        "require_blind_reviews": False,
        "require_total_report": False,
        "require_adversarial_passes": False,
        "require_consistency_repetition": False,
        "require_delivery_report": False,
        "summary": "ⓐ/ⓐⓐ 교정안과 판단 근거를 준비하되 full consistency gate는 요구하지 않는다.",
    },
    GATE_PROFILE_EDITORIAL: {
        "level": 3,
        "label": "적극 편집 후보",
        "required_axes": EDITORIAL_REVIEW_AXIS_IDS,
        "require_primary_passes": True,
        "require_blind_reviews": False,
        "require_total_report": False,
        "require_adversarial_passes": False,
        "require_consistency_repetition": False,
        "require_delivery_report": False,
        "summary": "편집자 모드 진입 전 최소 정합성 장부를 요구하되 blind 3x3 납품 gate는 요구하지 않는다.",
    },
    GATE_PROFILE_CONSISTENCY: {
        "level": 4,
        "label": "전 회차 정합성 감리",
        "required_axes": FULL_REVIEW_AXIS_IDS,
        "require_primary_passes": True,
        "require_blind_reviews": True,
        "require_total_report": True,
        "require_adversarial_passes": True,
        "require_consistency_repetition": True,
        "require_delivery_report": False,
        "summary": "정합성 검사 단위 전체를 닫지만 외부 납품 보고서는 별도 gate로 둔다.",
    },
    GATE_PROFILE_DELIVERY: {
        "level": 5,
        "label": "납품/최종 제출",
        "required_axes": FULL_REVIEW_AXIS_IDS,
        "require_primary_passes": True,
        "require_blind_reviews": True,
        "require_total_report": True,
        "require_adversarial_passes": True,
        "require_consistency_repetition": True,
        "require_delivery_report": True,
        "summary": "기존 full gate. 모든 정합성 감리와 human-facing 보고서 검증을 요구한다.",
    },
}

GATE_PROFILE_ALIASES: dict[str, str] = {
    "audit": GATE_PROFILE_CONSISTENCY,
    "global-audit": GATE_PROFILE_CONSISTENCY,
    "검수": GATE_PROFILE_CONSISTENCY,
    "consistency": GATE_PROFILE_CONSISTENCY,
    "정합성": GATE_PROFILE_CONSISTENCY,
    "full": GATE_PROFILE_DELIVERY,
    "full-qc-correction": GATE_PROFILE_DELIVERY,
    "delivery": GATE_PROFILE_DELIVERY,
    "전체": GATE_PROFILE_DELIVERY,
    "납품": GATE_PROFILE_DELIVERY,
    "correction": GATE_PROFILE_CORRECTION,
    "correction-pass": GATE_PROFILE_CORRECTION,
    "교정": GATE_PROFILE_CORRECTION,
    "editor": GATE_PROFILE_EDITORIAL,
    "editorial": GATE_PROFILE_EDITORIAL,
    "editorial-pass": GATE_PROFILE_EDITORIAL,
    "편집": GATE_PROFILE_EDITORIAL,
    "편집자": GATE_PROFILE_EDITORIAL,
    "proofread": GATE_PROFILE_PROOFREAD,
    "proofread-pass": GATE_PROFILE_PROOFREAD,
    "표면교정": GATE_PROFILE_PROOFREAD,
}


def normalize_gate_profile(value: object) -> str:
    key = str(value or "").strip().lower().replace("_", "-")
    return GATE_PROFILE_ALIASES.get(key, key if key in GATE_PROFILE_DEFINITIONS else GATE_PROFILE_DELIVERY)


def gate_profile_definition(value: object) -> dict[str, object]:
    return GATE_PROFILE_DEFINITIONS[normalize_gate_profile(value)]


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
