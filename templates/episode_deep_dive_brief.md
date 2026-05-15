# Episode Deep Dive Brief

작품: `{{title}}` (`{{work_slug}}`)
Run: `{{run_id}}`
모드: `{{mode}}` / `{{run_kind}}`

## 목적

이 단계는 `consistency_first_editorial_gate`입니다. 편집자 모드로 문장을 고치기 전에, 전역 3-pass 감리에서 잡힌 후보를 회차별로 직접 읽고 정합성 판단으로 닫습니다.

자동 evidence는 출발점일 뿐입니다. `episodes/*.txt`, `source.txt`, 앞뒤 회차, 관련 facts/review 후보를 사람이 읽어서 장면의 원인, 결과, 정보 보유 상태, 감정선, 회차 경계 리듬을 확인합니다.

## 기호 보존

- `ⓚ`, `ⓐ`, `ⓐⓐ`, 대괄호 UI, 회차 제목, 원문 특수기호를 임의 삭제하지 않습니다.
- 기호가 송고 위생 문제인지, 작중 UI/시스템/문서 표기인지 먼저 판정합니다.
- 삭제나 이동이 필요하면 `changes.json`이 아니라 먼저 `llm-facing/episode_deep_dive.md`와 `llm-facing/consistency_report.md`에 근거를 남깁니다.

## 입력물

- 추출 텍스트: `{{extracted_text_path}}`
- 회차 분할: `evidence/episodes/`
- inspection: `evidence/inspection.json`
- chapter metrics: `evidence/facts/chapter_metrics.jsonl`
- 회차 분량 플래그: `evidence/review/chapter_length_flags.jsonl`
- 정합성 후보: `evidence/review/verisimilitude_candidates.jsonl`
- 회차 경계 후보: `evidence/review/bridge_review_candidates.jsonl`
- 리플레이 후보: `evidence/review/replay_candidates.jsonl`
- 송고 위생 후보: `evidence/review/hygiene_flags.jsonl`
- 감리 제출 파일: `{{manual_review_submission_path}}`

## 진행 순서

1. `adversarial_audit_3pass.md`의 확정/유보/강등 항목을 읽습니다.
2. 후보가 걸린 회차를 먼저 읽고, 그 앞뒤 회차를 같이 봅니다.
3. 각 회차가 공백 제외 `{{minimum_chapter_chars_no_space}}`자 이상인지 확인합니다. 미달 회차는 정본 후보에서 강하게 감점하고, 삭제/병합/브리지 필요성을 따로 적습니다.
4. 소제목 유무가 섞이면 `evidence/facts/chapter_subtitles.jsonl`과 `evidence/review/subtitle_consistency_flags.jsonl`을 확인합니다. 소제목은 무단 수정하지 않고, 더 적은 쪽에 `ⓐⓐ(의견: ...)`으로 삭제 후보 또는 기존 소제목과 유사한 추가 후보를 남깁니다.
5. 중복 회차가 있으면 `base_episode`, 파일명 범위, 도입/결말/사건 spine, 회차별 분량을 비교합니다.
6. 각 회차에 대해 아래 항목을 `llm-facing/episode_deep_dive.md`에 남깁니다.
7. 최종적으로 편집에 넘길 항목만 `llm-facing/consistency_report.md`에 요약합니다.

## 회차별 기록 형식

```markdown
## EP 000

- 읽은 범위:
- 공백 제외 글자수:
- 사건 spine:
- 인물/정보 상태:
- 시간/장소 상태:
- 앞 회차 연결:
- 다음 회차 연결:
- 자동 후보 검토:
- 반례/방어 가능성:
- 최종 판단:
- 편집 넘김 여부:
```

## 중복 회차 판단 기준

- 완전 동일 중복: 뒤쪽 또는 파일명 범위에서 벗어난 블록을 `ⓐ(삭제)` 후보로 넘길 수 있습니다.
- 비동일 중복: 먼저 정본 선택을 `ⓐⓐ` 판단으로 기록합니다.
- 회차별 공백 제외 글자수는 `{{minimum_chapter_chars_no_space}}`자 이상이어야 합니다. 한쪽만 기준을 만족하면 기준 만족본을 우선 정본 후보로 두되, 앞뒤 정합성이 깨지는 반례가 있으면 보류합니다.
- 양쪽 모두 기준 미달이면 삭제로 해결하지 않습니다. 결락, 분할 오류, 누락 회차, 브리지/추가 필요성을 먼저 판단합니다.
- 정본 결정 후 비정본 블록 삭제는 `ⓐ(삭제)` 후보로 넘길 수 있습니다.
- 삭제본에만 있는 좋은 문장은 자동 병합하지 않습니다. 필요하면 별도 `ⓐⓐ(이식 후보)`로 분리합니다.

## 편집자 모드 진입 조건

편집자 모드는 아래가 모두 채워진 뒤에만 실행합니다.

- `llm-facing/adversarial_audit_3pass.md`
- `llm-facing/episode_deep_dive.md`
- `llm-facing/consistency_report.md`
- `evidence/submission/manual_review_submission.json`

이 조건이 비어 있으면 `corrections/changes.json`에 적극 편집 후보를 만들지 않습니다.
