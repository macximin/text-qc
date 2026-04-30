from __future__ import annotations


REVIEW_AXES: tuple[dict[str, str], ...] = (
    {"axis": "timeline_continuity", "label": "시간축/달력 연속성"},
    {"axis": "numeric_carryover", "label": "숫자/금액 carryover"},
    {"axis": "title_role_drift", "label": "인물/직함 drift"},
    {"axis": "era_validation", "label": "시대 검증/고증 축"},
    {"axis": "replay_vs_escalation", "label": "replay vs escalation"},
    {"axis": "front_back_bridge", "label": "앞뒤 화 브리지"},
    {"axis": "character_consistency", "label": "캐릭터성/관계 일관성"},
    {"axis": "state_regression", "label": "사건 상태 회귀"},
    {"axis": "submission_hygiene", "label": "송고 위생"},
    {"axis": "reader_facing_polish", "label": "독자-facing 표현/문장"},
)

PASS_NAMES: tuple[str, ...] = ("pass1", "pass2", "pass3")
