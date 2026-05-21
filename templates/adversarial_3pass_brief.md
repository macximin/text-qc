# 원고 적대적 3-pass 감리 브리프

작품: `{{title}}` (`{{work_slug}}`)
Run: `{{run_id}}`
모드: `{{mode}}`

## 미션

- `좋아 보인다`가 아니라 `어디가 틀릴 수 있는지 끝까지 의심하는 감리자`로 행동한다.
- 목표는 칭찬이 아니라 핍진성 붕괴, 시간축 오류, 숫자 오류, 인물/직함 drift, 사건 상태 회귀, 캐릭터성 붕괴, 송고 위생 문제를 잡는 것이다.
- 우선순위의 중심은 외부 고증이 아니라 작중 연속성이다. 예: `오늘 했다`고 쓴 행동이 뒤에서 `오늘 하지 않았다`로 뒤집히면 날짜/영업일 고증보다 먼저 본다.
- `문제 없음`은 기본값이 아니다. 반대로 가정하고 깨보는 것이 기본값이다.
- 이 감리는 primary/blind 3x3 결과가 `llm-facing/total_consistency_report.md`로 통합된 뒤 수행한다. 통합본의 확정, 유보, 수용 전제, 장르적 허용을 공격 대상으로 삼는다.

## 필수 입력물

- 추출 텍스트: `{{extracted_text_path}}`
- 내부 NAS root: `{{internal_nas_root}}`
- inspection: `evidence/inspection.json`
- facts: `evidence/facts/`
- review candidates: `evidence/review/`
- 회차 분량 플래그: `evidence/review/chapter_length_flags.jsonl`
- verisimilitude candidates: `evidence/review/verisimilitude_candidates.jsonl`
- 통합 정합성 리포트: `llm-facing/total_consistency_report.md`
- submission gate: `evidence/submission/submission_gate.json`

## 먼저 실행할 것

```powershell
.\scripts\novel-qc-loop.ps1 analyze-run --run-root "{{run_root}}"
```

## Pass 1. 표면 팩트 감리

- `verisimilitude_candidates.jsonl`을 먼저 열어 작중 행동/상태/인과 충돌 후보를 확인한다.
- 날짜, 시간, 금액, 지분율, 나이, 직함, 관계 호칭을 먼저 수집한다.
- 회차별 공백 제외 글자수 `{{minimum_chapter_chars_no_space}}`자 미만 후보를 확인한다. 미달 회차는 결락, 중복, 분할 오류, 정본 선택 보류 후보로 본다.
- 각 이슈는 최소 `회차`, `줄번호`, `증거 문장`, `왜 문제인지`, `수정 방향`을 남긴다.
- 사소해 보여도 일단 모은다. 나중에 지우더라도 처음엔 넓게 잡는다.
- 자동 evidence는 후보일 뿐이다. 작중 뉴스/단말기/문서 표기, 고의적 플래시백, 장르적 과장처럼 소설적 허용으로 방어 가능한 항목은 곧바로 확정 오류로 올리지 말고 반례와 함께 강등 또는 유보한다.
- 윤리선/도덕성 판단은 공격 대상에서 제외한다. 재난/사전인지/응징/수익화 장면은 정합성, 핍진성, 명시적 인과, 장면 정보 전달만 공격한다.
- 정합성 근거 없는 죄책감, 기부, 피해자 지원, 제보, 독자 반감 완화, 최소 완충 제안은 원작 의도 침해로 공격한다.
- AI 작성 또는 AI 작성 의심 원고의 명시 표지 없는 시간 역류는 회상으로 구제하지 말고 AI 시간축 스플라이스 오류로 먼저 공격한다.
- `regex`, `glob`, `rg` 검색은 후보 수집과 위치 확인에만 최소로 쓴다. 검색 결과를 그대로 확정 이슈로 옮기지 말고 본문 독해로 닫는다.
- `manual_review_queue.jsonl`의 축을 빠뜨리지 않는다.
- 세계관 안에서 이미 세운 제도/기술/경제 규칙은 현실 고증으로 깨지 말고 내부 규칙으로 등록한다. 이후에는 그 내부 규칙과 자기모순이 나는지만 본다.
- 맥락 없이 시대 불가능 설정이 던져졌다면 `needs_author_decision` 또는 `irreconcilable_premise`로 분리한다. 로컬 문장 교정으로 해결 가능한 척하지 않는다.

## Pass 2. 적대적 반례 감리

- Pass 1에서 잡은 모든 항목에 대해 반대 증거를 찾는다.
- 시간축이면 앞뒤 회차를 다시 뒤져 실제 오류인지, 고의적 플래시백인지 확인한다. 외부 날짜/요일/영업일은 작중 행동 결과를 뒤집을 때만 강한 이슈로 올린다.
- 송고 위생이면 `narrative_allowances.jsonl`을 확인해 작중 UI/헤드라인으로 이미 방어된 후보인지 먼저 본다.
- 숫자면 동일 수치가 다른 장면에서 다시 어떻게 쓰이는지 확인한다.
- 인물/직함이면 같은 이름이 다른 직함으로 불리는 장면을 모아 실제 변화인지 drift인지 판정한다.
- 숫자, 금액, 시간, 지분, 직함, 완료/미완료 상태는 `hard_carryover_conflict` 후보로 우선 본다. 장르적 허세나 과장으로 강등하려면 앞뒤 상태가 실제로 방어된다는 반례가 있어야 한다.
- replay 후보면 lawful repetition과 lazy replay를 구분한다.
- 중복 회차가 있으면 어느 블록을 살릴지 판단하기 전에 양쪽의 분량, 파일명 범위, 앞뒤 사건 spine을 함께 대조한다.

## Pass 3. 폐쇄 감리

- 앞선 두 패스에서 `문제 없음` 처리한 항목을 다시 의심한다.
- 최종 산출물에는 `확정 이슈`, `유보 이슈`, `근거 부족으로 보류한 의심점`을 분리한다.
- 최종 보고 전 `정말 수정 가치가 있나`를 다시 검산한다.
- 편집자 모드로 넘길 항목과 화별 딥다이브에서 다시 읽어야 할 항목을 분리한다.
- P0/P1은 최종 감리에서 `확정`, `confidence_percent >= 95`, 직접 근거 있음, 미해결 반례 없음, 작중 핍진성 영향이 모두 맞는 항목만 유지한다.
- 단순 외부 고증은 `story_internal_impact`가 분명하지 않으면 P2/P3 또는 유보로 낮춘다.
- 대체 해석, 소설적 허용, 앞뒤 문맥상 방어가 남은 항목은 P2/P3로 강등하거나 철회/유보한다.
- 웹소설식 과장과 허세 자체는 결함이 아니다. 반복, 독해 실패, 수치/상태 carryover 훼손을 만들 때만 편집 후보로 유지한다.
- 윤리선/도덕성 또는 독자 반감 완화만 문제인 항목은 finding으로 유지하지 않는다.
- 완료 후 `manual_review_submission.json`의 각 축과 pass 상태를 채운다.

```powershell
.\scripts\novel-qc-loop.ps1 validate-submission --run-root "{{run_root}}"
```

## FAIL 조건

- 회차/줄번호 없는 지적.
- 반례 탐색 없이 단정한 지적.
- 동일 이름/수치 재등장 확인 없이 내린 전역 결론.
- 외부 고증만으로 P0/P1을 올리고 작중 독자 영향 또는 상태 충돌을 설명하지 않는 보고.
- `accepted_world_premise`, `genre_hyperbole_allowance`, `external_fact_soft`로 방어한 항목을 P0/P1로 유지하는 보고.
- hard carryover P0/P1인데 `story_state_before`와 `story_state_after` 둘 다 없는 보고.
- `문제 없음`인데 어떤 축을 확인했는지 목록이 없는 보고.
- 자동 evidence를 복붙하고 끝내는 보고.
- 반례가 남은 항목을 P0/P1로 제출하는 보고.

## 최소 산출물

- `llm-facing/global_audit_raw.md`
- `llm-facing/adversarial_audit_3pass.md`
- `llm-facing/total_consistency_report.md`
- `llm-facing/episode_deep_dive.md`로 넘길 회차별 수동 독해 큐
- `llm-facing/consistency_correction_loop.md`로 넘길 재평가 대상
- `evidence/submission/manual_review_submission.json`
- `human-facing/1차_one_page_report.md`

`delivery` profile의 최종 보고서는 `validate-submission`이 통과된 뒤 `validate-report`를 통과해야 제출 가능하다. `consistency` profile은 감리 제출을 닫고, 보고서는 별도 납품 요청이 있을 때 검증한다.

`delivery`/`consistency` profile의 편집자 모드는 이 3-pass와 `llm-facing/episode_deep_dive.md`, `llm-facing/consistency_report.md`가 채워진 뒤에만 실행한다. `editorial` profile은 `manual_review_queue.jsonl`의 `required_for_gate=true` 항목과 `consistency_report.md`의 진입 판정을 우선한다. 교정 적용 뒤에는 같은 축으로 재평가하고, 해결/신규/회귀를 loop 기록에 남긴다.
