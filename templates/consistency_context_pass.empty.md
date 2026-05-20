# Consistency Context Pass

작품: `{{title}}` (`{{work_slug}}`)
Run: `{{run_id}}`
Lane: `{{review_lane}}`
Pass: `{{pass_name}}`

## 원칙

- 이 파일은 전 회차 정합성/맥락 장부와 충돌 후보를 한 번 독립적으로 닫기 위한 내부 산출물입니다.
- `정합성 검사`의 기본 단위는 이 pass 하나가 아니라 `consistency_3x3_unit` 전체입니다. 사용자가 N번을 요청하면 이 단위 전체를 N회 반복합니다.
- `regex`, `glob`, `rg`는 후보 수집과 위치 확인에만 최소로 씁니다. 판단은 원고 본문, 앞뒤 문단, 앞뒤 회차 직접 독해로 닫습니다.
- 블라인드 lane은 다른 lane의 결과를 읽지 않고 작성합니다.
- 세계관 안에서 세운 제도/기술/경제 규칙은 전제로 수용합니다. 맥락 없이 던진 시대 불가능 설정은 worldbuilding gap 또는 작가 판단 필요로 분리합니다.
- 웹소설식 과장과 허세는 허용하되, 숫자/금액/시간/지분/직함/완료 상태 carryover는 엄격히 봅니다.
- 비독자-facing 내부 메모, 정본 선택 보류, 작가 판단 필요 항목도 삭제하지 말고 별도 메모합니다.

## 전 회차 정합성/맥락 장부

| 회차 | 사건 spine | 인물/정보 상태 | 시간/장소 상태 | 숫자/금액/지분 상태 | 앞뒤 연결 | 메모 |
|---|---|---|---|---|---|---|

## 충돌 후보

| 우선순위 | 위치 | 주장 | 근거 | 반례/방어 | 판정 유형 | 수정 가능성 | 다음 액션 |
|---|---|---|---|---|---|---|---|

판정 유형은 `editable_conflict`, `accepted_world_premise`, `genre_hyperbole_allowance`, `hard_carryover_conflict`, `external_fact_soft`, `needs_author_decision` 중 하나로 둡니다.

수정 가능성은 `local_fixable`, `structural_fixable`, `needs_author_decision`, `irreconcilable_premise`, `webnovel_allowance` 중 하나로 둡니다.

## 비독자-facing 메모

- 내부 메모/작업 흔적:
- 작가 확인 필요:
- 정본 선택 보류:
- 삭제 금지/원형 보존:

## 다음 pass로 넘길 질문

- 확정 후보:
- 반례가 남은 후보:
- 전 회차 장부에서 비어 있는 상태:
