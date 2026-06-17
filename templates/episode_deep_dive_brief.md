# Episode Deep Dive Brief

작품: `{{title}}` (`{{work_slug}}`)
Run: `{{run_id}}`
모드: `{{mode}}` / `{{run_kind}}`

## 목적

이 단계는 `consistency_first_editorial_gate`입니다. 편집자 모드로 문장을 고치기 전에, 전역 3-pass 감리에서 잡힌 후보를 회차별로 직접 읽고 정합성 판단으로 닫습니다.

자동 evidence는 출발점일 뿐입니다. `regex`, `glob`, `rg` 검색은 후보 위치를 찾는 데만 최소로 쓰고, `episodes/*.txt`, `source.txt`, 앞뒤 회차, 관련 facts/review 후보를 사람이 읽어서 장면의 원인, 결과, 정보 보유 상태, 감정선, 회차 경계 리듬을 확인합니다.

회차별 딥다이브는 전역 컨텍스트 스캔 이후에만 시작합니다. 전역 스캔 전에는 앞쪽을 고칠지 뒤쪽을 고칠지 확정하지 않고, 수정 비용이 낮은 방향을 찾기 위한 지도부터 만듭니다.

판정은 `수정 가능한 충돌`, `세계관 전제`, `장르적 과장/허세`, `hard carryover`, `작가 판단 필요`, `로컬 수정 불가 전제`를 분리합니다. 세계관 안에서 이미 세운 제도/기술/경제 규칙은 전제로 수용하고, 이후 자기모순만 감시합니다. 반대로 맥락 없이 던진 시대 불가능 설정은 로컬 교정으로 해결 가능한 척하지 말고 작가 판단/전제 보강으로 분리합니다.

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

윤리선/도덕성 평가는 딥다이브 판단 대상이 아닙니다. 재난/사전인지/응징/수익화 장면은 정합성, 핍진성, 명시적 인과, 장면 정보 전달만 확인합니다. 정합성 근거 없는 죄책감, 기부, 피해자 지원, 제보, 독자 반감 완화, 최소 완충 제안은 원작 의도 침해로 봅니다.

AI 작성 또는 AI 작성 의심 원고에서는 명시 표지 없는 시간 역류, 장면 접합, 중복 리캡, 정보 상태 회귀를 회상 장치로 구제하지 않습니다. 회상/며칠 전/다시 떠올림 같은 표지가 없으면 AI 시간축 스플라이스 오류로 봅니다.
`(제 80화 끝)` 같은 회차 끝 메타, `현재명(구 옛이름)` 식 괄호 주석, 영어 뒤 괄호 번역, A사/XX년 placeholder, 내부 메모형 표면은 AI-slop 후보로 별도 기록합니다. 명백하면 수정 후보로 올리되, 장면 안의 문서/대사/시스템 UI일 수 있으면 삭제하지 않고 watchlist에 둡니다.
- 리플레이 후보: `evidence/review/replay_candidates.jsonl`
- 송고 위생 후보: `evidence/review/hygiene_flags.jsonl`
- 감리 제출 파일: `{{manual_review_submission_path}}`

## 사전 리스크 체크리스트

- AI 작성/AI-slop 가능성: 반복 리캡, 장면 접합, 시간 역류, 정보 상태 회귀, 균질한 문장 리듬을 확인합니다.
- glossary 미정렬 가능성: 고유명사와 약칭은 직접 근거 전까지 정본 보류로 둡니다.
- 정합성/중복 문제 가능성: 중복 회차, 중복 리캡, 사건 상태 회귀, 앞뒤 화 브리지 결손을 우선 확인합니다.
- 인간 검수자 내부 메모 잔존 가능성: 대괄호, 괄호 대안문, 슬래시 병기, 비독자-facing 코멘트를 분류합니다.
- 화수 표기/분할 이상 가능성: HWP 추출 후 회차 번호 누락, 중복 번호, 검수자 삭제로 인한 gap, oversized merged episode를 먼저 닫습니다.
- AI-slop 메타 표면: 회차 끝 표식, 괄호형 구명/번역 주석, placeholder, 내부 메모는 `policy_watchlist` 또는 `style_watchlist`로 분리해 기록하고 전역 일괄 삭제하지 않습니다.

## 진행 순서

1. HWP 추출/회차 분할 무결성을 먼저 확인합니다.
2. `adversarial_audit_3pass.md`의 확정/유보/강등 항목을 읽습니다.
3. 후보가 걸린 회차를 먼저 읽고, 그 앞뒤 회차를 같이 봅니다.
4. 각 회차가 공백 포함 `{{minimum_chapter_chars}}`자 이상인지 확인합니다. 미달 회차는 정본 후보에서 강하게 감점하고, 삭제/병합/브리지 필요성을 따로 적습니다.
5. 소제목 유무가 섞이면 `evidence/facts/chapter_subtitles.jsonl`과 `evidence/review/subtitle_consistency_flags.jsonl`을 확인합니다. 소제목은 무단 수정하지 않고, 더 적은 쪽에 `ⓐⓐ(의견: ...)`으로 삭제 후보 또는 기존 소제목과 유사한 추가 후보를 남깁니다.
6. 중복 회차가 있으면 `base_episode`, 파일명 범위, 도입/결말/사건 spine, 회차별 분량을 비교합니다.
7. 각 회차에 대해 아래 항목을 `llm-facing/episode_deep_dive.md`에 남깁니다.
8. 숫자, 금액, 시간, 지분, 직함, 완료/미완료 상태는 `story_state_before`와 `story_state_after`를 모두 적습니다.
9. `scan-ai-slop` 후보가 있으면 회차 문맥으로 독자-facing 여부를 확인합니다.
10. 최종적으로 편집에 넘길 항목만 `llm-facing/consistency_report.md`에 요약합니다.

검색으로 같은 표현을 더 찾았더라도, 전체 치환이나 전역 정합성 결론은 하지 않습니다. 각 occurrence가 놓인 장면의 정보 상태와 독자 이해 흐름을 따로 판단합니다.

## 회차별 기록 형식

```markdown
## EP 000

- 읽은 범위:
- 공백 포함 글자수:
- 사건 spine:
- 인물/정보 상태:
- 시간/장소 상태:
- 앞 회차 연결:
- 다음 회차 연결:
- 자동 후보 검토:
- 반례/방어 가능성:
- 판정 유형:
- 수정 가능성:
- 비독자-facing 메모:
- 최종 판단:
- 편집 넘김 여부:
```

## 중복 회차 판단 기준

- 완전 동일 중복: 뒤쪽 또는 파일명 범위에서 벗어난 블록을 `ⓐ(삭제)` 후보로 넘길 수 있습니다.
- 비동일 중복: 먼저 정본 선택을 `ⓐⓐ` 판단으로 기록합니다.
- 회차별 공백 포함 글자수는 `{{minimum_chapter_chars}}`자 이상이어야 합니다. 한쪽만 기준을 만족하면 기준 만족본을 우선 정본 후보로 두되, 앞뒤 정합성이 깨지는 반례가 있으면 보류합니다.
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
