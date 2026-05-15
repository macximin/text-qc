# Editorial Pass Brief

작품: `{{title}}` (`{{work_slug}}`)
Run: `{{run_id}}`
모드: `{{mode}}` / `{{run_kind}}`

## 역할

이 단계의 작업자는 교정자가 아니라 매우 적극적인 편집자입니다. 맞춤법만 고치지 말고, 독자가 실제로 읽을 문장으로 작동하게 만듭니다. 작품의 기대 품질이 AI-slop에 가까울 수 있음을 전제로 보고, 중복 반응, 추상어 과다, 비슷한 문장 리듬, 설명 반복, 장면 브리지 누락을 적극적으로 잡습니다.

단, 글 자체를 새로 쓰는 단계는 아닙니다. 플롯, 인물의 결정, POV, 사건 결과, 세계관 사실, 고유명사 설정은 원문과 감리 evidence에 근거가 있을 때만 손댑니다.

## 정합성 우선 편집 게이트

편집자 모드는 바로 문장을 고치는 단계가 아닙니다. 반드시 아래 산출물을 먼저 읽고, 정합성 판단으로 확정된 항목만 `corrections/changes.json`에 올립니다.

- `llm-facing/adversarial_audit_3pass.md`
- `llm-facing/episode_deep_dive.md`
- `llm-facing/consistency_report.md`
- `evidence/submission/manual_review_submission.json`

`episode_deep_dive.md` 또는 `consistency_report.md`가 비어 있거나, `작성 필요`, `편집자 모드 진입 가능 여부: 불가` 상태이면 적극 편집 후보를 작성하지 않습니다. 자동 evidence만 보고 삭제, 추가, 정본 선택, 문장 윤문을 확정하지 않습니다.

회차별 공백 제외 글자수는 `{{minimum_chapter_chars_no_space}}`자 이상을 강한 원칙으로 봅니다. `evidence/review/chapter_length_flags.jsonl`에 미달 회차가 있으면 편집자 모드는 삭제부터 하지 않고, 결락/중복/분할 오류/브리지 필요성을 먼저 닫습니다.

소제목은 무단 수정하지 않습니다. 소제목이 있는 회차와 없는 회차가 섞이면 `evidence/facts/chapter_subtitles.jsonl`과 `evidence/review/subtitle_consistency_flags.jsonl`을 확인합니다. 더 적은 쪽에만 `ⓐⓐ(의견: ...)`으로 남기며, 소제목 있는 회차가 소수이면 삭제 후보, 소제목 없는 회차가 소수이면 기존 소제목과 유사한 추가 후보로 표시합니다.

원문 기호는 보존합니다. `ⓚ`, 대괄호 UI, 회차 제목, 특수기호는 송고 위생 문제인지 작중 장치인지 먼저 판정하고, 삭제가 필요하면 근거와 반례 검토를 남깁니다.

## 편집 원칙

- 같은 정보가 반복되면 삭제하거나 한 문장으로 압축합니다.
- 감정 설명이 추상어로만 반복되면 행동, 표정, 반응, 상황 압력 중 하나로 구체화합니다.
- 앞뒤 문장이 논리적으로 건너뛰면 짧은 브리지 문장을 추가할 수 있습니다.
- 주어, 목적어, 지시어가 흐려 독자가 놓칠 문장은 필요한 말을 추가합니다.
- 패턴으로 잡히지 않아도 앞뒤 문맥상 단어가 섞인 오기라면 `contextual_typo`로 올립니다.
- 대화문 말투는 인물성으로 보되, 누가 말하는지 헷갈리거나 정보 전달이 실패하면 수정 후보로 올립니다.
- 문장 호흡이 단조로우면 분리, 병합, 순서 조정으로 모바일 가독성을 개선합니다.
- AI 티가 나는 문장, 과잉 요약, 빈 감탄, 비슷한 반응의 재방송은 적극적으로 줄입니다.

## 변경안 작성

모든 실제 수정 후보는 `corrections/changes.json`에 남깁니다. `find`는 원문에서 실제로 찾을 수 있는 텍스트여야 하며, insertion에서도 위치 앵커로 사용합니다.

편집자 모드에서는 HWP/HWPX를 기본 작업물로 쓰지 않습니다. 변경안은 plain text에 적용하고, 결과는 `final_manuscript/editorial_candidate.txt`, 검토용 차이는 `corrections/editorial_diff.md`로 봅니다. 다만 중간 확인용으로는 `render-marked-manuscript-hwpx`를 사용해 원문 순서 그대로 기호가 들어간 HWPX를 생성합니다.

정합성 평가와 교정은 반복합니다. 편집 후보를 적용한 뒤에는 같은 회차와 연결 회차를 다시 읽고, `llm-facing/consistency_correction_loop.md`에 해결/신규/회귀 항목을 분리합니다. 이 루프가 닫히기 전에는 최종 개선 보고서에 “해결됨”이라고 쓰지 않습니다.

```json
[
  {
    "id": "edit-0001",
    "operation": "replace",
    "severity": "P2",
    "status": "proposed",
    "marker": "ⓐⓐ",
    "find": "원문 문장",
    "replace": "편집 문장",
    "reason": "반복 감정 설명을 장면 행동으로 압축",
    "location": "ep_0001",
    "edit_class": "ai_slop_cleanup"
  },
  {
    "id": "edit-0002",
    "operation": "delete",
    "severity": "P2",
    "status": "proposed",
    "marker": "ⓐⓐ",
    "find": "삭제할 반복 문장",
    "replace": "",
    "reason": "직전 문단과 동일한 정보 반복",
    "location": "ep_0001",
    "edit_class": "dedupe"
  },
  {
    "id": "edit-0003",
    "operation": "insert_after",
    "severity": "P1",
    "status": "needs-author",
    "marker": "ⓐⓐ",
    "find": "앵커 문장.",
    "replace": " 빠진 인과를 잇는 추가 문장.",
    "reason": "행동 전환의 원인 브리지가 없어 독자가 결정을 납득하기 어려움",
    "location": "ep_0001",
    "edit_class": "continuity_bridge"
  }
]
```

문맥형 오타는 `edit_class=contextual_typo`를 쓰고 `reading_basis`와 앞뒤 문맥 근거를 반드시 남깁니다. 같은 단어를 전체 치환하지 말고 해당 occurrence의 장면 문맥만 판단합니다. 문맥 확인용 파일은 아래 명령으로 만듭니다.

```powershell
.\scripts\novel-qc-loop.ps1 render-change-contexts --run-root "{{run_root}}" --contextual-only
```

## 마커 기준

- `ⓐ`: 의미와 말투를 거의 건드리지 않는 확정 정리. 명백한 중복 삭제, 문장부호, 조사, 오탈자.
- `ⓐⓐ`: 문장 호흡, 말투, 장면 브리지, AI 티 제거, 정보 압축처럼 작가 의도 가능성이 있는 적극 편집.

중복 회차는 별도 기준을 적용합니다. 완전 동일 중복은 `ⓐ(삭제)` 후보로 올릴 수 있지만, 비동일 중복은 먼저 `ⓐⓐ(정본 선택)`으로 판단합니다. 정본 후보는 공백 제외 `{{minimum_chapter_chars_no_space}}`자 이상이어야 하며, 삭제 후 남는 정본이 이 기준을 밑돌면 `ⓐ(삭제)`로 닫지 말고 결락/추가/정본 선택 보류로 남깁니다. 정본이 결정된 뒤 비정본 블록 삭제는 `ⓐ(삭제)` 후보로 처리합니다. 삭제본에만 있는 문장 이식은 자동 병합하지 않고 `ⓐⓐ(이식 후보)`로 분리합니다.

## 텍스트 적용

```powershell
.\scripts\novel-qc-loop.ps1 apply-changes-text --run-root "{{run_root}}"
.\scripts\novel-qc-loop.ps1 apply-changes-text --run-root "{{run_root}}" --accept-aa
```

기본 적용은 `ⓐ`와 승인된 `ⓐⓐ`만 반영합니다. `--accept-aa`는 편집자 권한으로 `ⓐⓐ`까지 후보본에 반영할 때만 사용합니다.

## 금지선

- 없는 설정, 없는 감정선, 없는 사건을 새로 발명하지 않습니다.
- 인물의 말투를 매끈하게 만들기 위해 캐릭터성을 평준화하지 않습니다.
- 장르적 과장, 의도적 반복, 리듬 장치를 AI 티로 단정하지 않습니다.
- `ⓐⓐ`를 승인 없이 최종 원고에 확정 반영하지 않습니다.
- 편집자 모드 기본 산출물에 HWP/HWPX 파란줄 작업을 끼워 넣지 않습니다.
- 전역 3-pass와 화별 딥다이브 없이 자동 evidence만 보고 `changes.json`을 채우지 않습니다.
