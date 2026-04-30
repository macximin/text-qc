# Legacy SSOT Mapping

`novel-qc-loop`는 기존 `업무자동화_ssot`의 실전 폴더를 그대로 공개 repo에 넣지 않고, 반복 가능한 규칙으로 일반화합니다.

## 검수에서 가져온 것

참조 루트:

- `C:\Users\wjjo\Desktop\업무자동화_ssot\검수`

반영한 패턴:

- `artifacts/facts/`: 날짜, 시간, 금액, 퍼센트, 나이, 직함, 인물/호칭 후보를 JSONL로 먼저 뽑는다.
- `artifacts/review/`: replay, bridge, 시대감, 송고 위생 후보를 별도 review 후보로 둔다.
- `manual_review_queue.jsonl`: 3-pass와 감리 축을 작업 큐로 분리한다.
- `manual_review_submission.json`: 감리자가 최종 제출하는 구조화 결과를 둔다.
- `submission_gate.json`: 자동 후보와 수동 감리 완료 여부를 합쳐 송고 가능 상태를 요약한다.
- `adversarial_3pass_audit_brief.md`: "좋아 보인다"가 아니라 반례를 찾는 감리 태도를 템플릿화한다.

## 교정에서 가져온 것

참조 루트:

- `C:\Users\wjjo\Desktop\업무자동화_ssot\교정`

반영한 패턴:

- `ⓐ`: 확정 교정.
- `ⓐⓐ`: 작가 판단 요청.
- `changes.json`: `find`, `replace`, `marker`, `reason`, `location`을 남기는 교정 변경 목록.
- `scripts/apply_blue.py`: HWPX에서 교정문만 파란색으로 표시하는 도구.
- `validate-changes`: 교정 변경 목록이 최소 규격을 지키는지 확인.

## 일반화하면서 바꾼 것

- 특정 작품명/장르명에 묶인 판단은 제거한다.
- human-facing 보고서는 기본 1장으로 둔다.
- 긴 감리 로그와 중간 handoff는 `llm-facing/`과 `evidence/`에 분리한다.
- 실제 원고와 산출물은 `workspace/`에 두고 git에는 올리지 않는다.
- AI slop 검사는 특정 장르 취향 강제가 아니라 반복 반응, 추상어, 말투 균질화의 신호 점검으로 둔다.
