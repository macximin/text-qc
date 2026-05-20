# Harness Contract

이 문서는 `text-qc`가 생성하는 run 폴더의 표준 계약입니다.

## 목표

초기 원고를 넣으면, 사람이든 LLM이든 같은 위치에서 같은 파일을 보고 이어받을 수 있어야 합니다.

내부 NAS 원본 root는 `\\172.16.10.120\소설사업부\판무팀_ssot`입니다. 이 경로는 원본 참조 root이며, run 내부 하네스는 원본을 복사/추출한 산출물만 수정 대상으로 삼습니다.

## 표준 run 구조

```text
runs/{run_id}/
  run_manifest.json
  evidence/
    episodes/
      001.txt
      002.txt
    inspection.json
    facts/
      chapter_metrics.jsonl
      absolute_dates.jsonl
      relative_times.jsonl
      dates.jsonl
      dates_with_weekday.jsonl
      times.jsonl
      money.jsonl
      percents.jsonl
      ages.jsonl
      titles.jsonl
      kin_titles.jsonl
      speaker_cues.jsonl
      inline_author_memos.jsonl
      inline_paren_errors.jsonl
      timeline_summary.json
      character_title_matrix.json
    review/
      verisimilitude_candidates.jsonl
      hygiene_flags.jsonl
      narrative_allowances.jsonl
      ai_slop_signals.json
      replay_candidates.jsonl
      bridge_review_candidates.jsonl
      chapter_length_flags.jsonl
      era_review_candidates.jsonl
    package/
      epub_package_qc.json
      epub_package_qc.md
    submission/
      submission_gate.json
      manual_review_queue.jsonl
      manual_review_submission.json
  llm-facing/
    task_brief.md
    handoff_checklist.md
    adversarial_3pass_brief.md
    consistency_rounds/
      primary_pass1.md
      primary_pass2.md
      primary_pass3.md
    blind_reviews/
      blind_agent_1_pass1.md
      ...
    total_consistency_report.md
    adversarial_audit_3pass.md
    harness_adversarial_audit_3pass.md
    episode_deep_dive_brief.md
    global_audit_raw.md
    adversarial_audit_3pass.md
    episode_deep_dive.md
    consistency_report.md
    correction_plan.md
    consistency_correction_loop.md
  human-facing/
    1차_one_page_report.md
    final_improvement_report.md
    reaudit_report.md
    author_final_report.md
    author_final_report.pdf
  corrections/
    marker_protocol.md
    changes.json
  final_manuscript/
    README.md
    final_manuscript.txt
  exports/
```

## Evidence

`evidence/`는 LLM이 먼저 읽어야 하는 기계 생성 후보입니다.

- `inspection.json`: 분량, 줄 길이, 회차 수, 마크다운/무대지문 기초 지표.
- `episodes/*.txt`: 회차별 텍스트. 전역 감리 중 특정 회차를 바로 열기 위한 분할본.
- `facts/*.jsonl`: 날짜, 시간, 상대 시간, 금액, 퍼센트, 나이, 직함, 친족 호칭, 화자 cue 후보.
- `facts/chapter_subtitles.jsonl`: 회차별 소제목 유무, 소제목 텍스트, 본문 offset.
- `facts/timeline_summary.json`: 시간 표현이 몰린 회차 후보.
- `facts/character_title_matrix.json`: 한 인물이 여러 직함/호칭으로 잡히는 drift 후보.
- `review/verisimilitude_candidates.jsonl`: 작중 행동/상태/인과 충돌 후보. 같은 시점에서 수행/미수행이 함께 잡히거나 상태 전환어가 있는 줄을 우선 큐로 남깁니다.
- `review/hygiene_flags.jsonl`: 작가 메모, 교정 마커, HTML 엔티티, 무대지문 등 송고 위생 후보. 단, 작중 뉴스/단말기/문서 표기로 방어 가능한 대괄호 문장은 blocker로 올리지 않습니다.
- `review/narrative_allowances.jsonl`: 자동 탐지에 걸렸지만 소설적 허용 또는 작중 UI/문서 표기로 판단해 blocker에서 제외한 후보와 그 근거.
- `review/replay_candidates.jsonl`: 회차 경계 반복 후보.
- `review/bridge_review_candidates.jsonl`: 회차 앞뒤 브리지 약화 후보.
- `review/chapter_length_flags.jsonl`: 공백 제외 4000자 미만 회차 후보.
- `review/subtitle_consistency_flags.jsonl`: 소제목이 있다가 없다가 하는 형식 불균형 후보.
- `review/era_review_candidates.jsonl`: 시대감/현대어/장르 톤 후보.
- `review/ai_slop_signals.json`: 반복 반응/추상어/AI 티 후보.
- `package/epub_package_qc.*`: EPUB 파일/폴더 입력 시 언어, 식별자, 파일명 규칙, OPF 기본 메타데이터 확인 결과.
- `submission/submission_gate.json`: 송고 보류/검토 가능 여부를 기계적으로 요약.
- `submission/manual_review_queue.jsonl`: primary 3-pass, blind 3개 lane x 3-pass, total report, adversarial 3-pass 작업 큐.
- `submission/manual_review_submission.json`: 사람이 완료한 감리 결과. 완료 상태는 primary/blind/total/adversarial workflow가 모두 채워져야 통과합니다.

Evidence는 판정이 아니라 후보입니다. 최종 판단은 `llm-facing` 감리와 `human-facing` 보고서에서 수행합니다. 우선순위는 외부 고증보다 작중 핍진성입니다. `오늘 했다`고 쓴 행동이 뒤에서 `오늘 하지 않았다`로 뒤집히거나, 이미 완료된 사건/정산/권한 상태가 원인 없이 회귀하는 문제를 먼저 봅니다. 날짜/요일/영업일 같은 외부 고증은 작중 행동 결과나 독자 이해를 실제로 깨뜨릴 때만 강한 이슈로 올립니다. 자동 탐지는 소설적 허용을 감안해 작중 뉴스, 단말기 자막, 문서/보고서 표기, 고의적 플래시백, 장르적 과장으로 방어 가능한 항목을 곧바로 오류로 승격하지 않습니다. 이런 항목은 가능하면 `narrative_allowances.jsonl` 또는 수동 감리의 `counter_evidence`에 남겨 추적합니다. 세계관 안에서 세운 제도/기술/경제 규칙은 전제로 수용하고, 맥락 없이 던진 시대 불가능 설정은 작가 판단 또는 전제 보강으로 분리합니다. 숫자/금액/시간/지분/직함/완료 상태 carryover는 장르적 허세보다 엄격하게 봅니다.

윤리선/도덕성 평가는 하네스 판단 대상이 아닙니다. 원작 의도 보호가 우선이며, 하네스는 주인공을 윤리적으로 재판하지 않습니다. 재난/사전인지/응징/수익화 장면도 정합성 근거 없이 죄책감, 기부, 피해자 지원, 제보, 독자 반감 완화, 최소 완충 같은 도덕/수용성 보강을 제안하지 않습니다. 하네스는 정합성, 핍진성, 명시적 인과, 장면 정보 전달만 봅니다.

AI 작성 또는 AI 작성 의심 원고에서는 명시 표지 없는 시간 역류, 장면 접합, 중복 리캡, 정보 상태 회귀를 작가 의도나 회상 장치로 구제하지 않습니다. 본문에 회상/며칠 전/다시 떠올림 같은 장치가 없으면 기본값은 AI 시간축 스플라이스 오류입니다.

## LLM-facing

`llm-facing/`은 내부 작업자와 AI 에이전트가 읽는 폴더입니다. 길어도 됩니다.

반드시 남길 것:

- 전역 검수 raw
- primary 전 회차 정합성/맥락 장부 3-pass
- blind 3개 lane x 3-pass
- total consistency report
- total report 이후 적대적 감리 3-pass
- 하네스 계약 변경 시 harness adversarial audit 3-pass
- 화별 수동 딥다이브
- 편집자 모드 진입 전 정합성 리포트
- 적극 편집자 모드 브리프와 편집안
- 교정안
- 반례 탐색 메모

## Human-facing

`human-facing/1차_one_page_report.md`는 기본적으로 1장 SSOT입니다. 이후 갱신은 `N차_one_page_report.md`로 차수만 올립니다.

N차 보고서는 직전 차수 이후 신규 항목만 적는 문서가 아닙니다. P0-P3 전체 항목을 누적 장부로 보여주며, 이전 차수의 항목은 삭제하지 않고 현재 상태만 갱신합니다. 해결, 강등, 철회, 유보, 작가 판단 필요 항목도 누락하지 않습니다. 특정 등급이 아직 없으면 해당 등급을 생략하지 말고 0건임을 명시합니다.

원칙:

- 내부 로그를 노출하지 않는다.
- 모델명/프롬프트/실행 흔적을 쓰지 않는다.
- 한국어 작가/편집자-facing 문장으로 쓴다.
- 모든 핵심 판단은 `주장`과 `근거`를 함께 둔다.
- 근거 없는 주장은 최종 보고서에 올리지 않는다.
- N차 보고서에는 누적 P0-P3 장부를 두고, 각 항목의 최초 차수, 현재 상태, 주장, 근거, 처리 방향을 함께 쓴다.
- 문제, 근거, 독자 리스크, 수정 방향만 남긴다.
- 작가전달용 최종 보고서는 항목별로 `위치`, `원문 근거`, `문제`, `근거`, `해석`, `수정 방향`을 포함한다.
- 해석 여지가 있거나 반례가 있는 항목은 P0/P1로 강하게 올리지 않고 P2/P3 보강 권고로 낮춘다.
- P0/P1은 최종 감리에서 `확정`, `confidence_percent >= 95`, 직접 근거 있음, 미해결 `counter_evidence` 없음, 작중 핍진성 영향이 모두 충족된 항목만 사용한다.
- 외부 고증 후보는 `story_internal_impact`가 명확하지 않으면 P2/P3 또는 유보로 둔다.
- `accepted_world_premise`, `genre_hyperbole_allowance`, `external_fact_soft`로 방어한 항목은 P0/P1 확정 충돌로 제출하지 않는다.

최종 보고서는 `validate-report`를 통과해야 합니다. `--run-root` 기준 검증은 한국어 비율, 내부 작업어 노출, placeholder, 주장-근거 쌍뿐 아니라 `manual_review_submission.json`이 감리 완료/검증 상태인지도 확인합니다.

```powershell
.\scripts\novel-qc-loop.ps1 validate-report --run-root "workspace\...\runs\..."
```

## Corrections

교정은 `ⓐ`와 `ⓐⓐ`를 분리합니다.

- `ⓐ`: 확정 교정
- `ⓐⓐ`: 작가 판단 요청

`changes.json`은 항상 `validate-changes`를 통과해야 합니다.

```powershell
.\scripts\novel-qc-loop.ps1 validate-changes --changes "workspace\...\corrections\changes.json"
```

변경 operation은 `replace`, `delete`, `insert_before`, `insert_after`를 허용합니다. 추가 작업에서도 `find`는 실제 원문 앵커이며, `replace`가 추가될 문장입니다. 적극 편집자 모드의 윤문, 중복 삭제, 인과 브리지 추가는 기본적으로 `ⓐⓐ`로 올리고 승인 전 확정 반영하지 않습니다.

편집자 모드는 HWP/HWPX를 기본 작업물로 쓰지 않습니다. `apply-changes-text`가 `final_manuscript/editorial_candidate.txt`와 `corrections/editorial_diff.md`를 생성합니다. 다만 루프 중간 확인을 위해 `render-marked-manuscript-md`로 `human-facing/*_marked_manuscript.md`를 만들고, 필요하면 `render-marked-manuscript-hwpx`로 `human-facing/*_marked_manuscript.hwpx`도 만들 수 있습니다. 이 검수본은 원문 순서 그대로 `ⓐ{원문|수정}`과 `ⓐⓐ{원문|후보문장}[판단: ...]`을 삽입한 판단용 산출물이며 원고 적용본이 아닙니다. 단순 맞춤법/띄어쓰기/문장 호흡은 `ⓐ` 자동승인으로 파란 교정문을 표시합니다. `ⓐⓐ`는 승인 전 원문에 반영하지 않지만, `ⓐ`와 같은 `{원문|후보}` 비교 구조로 보여 줍니다. HWPX 파란줄 납품본은 별도 납품 요구가 있을 때만 사용합니다.

표식 수는 `ⓐ` 교정과 `ⓐⓐ` 판단을 분리해 보고합니다. `ⓐ{` 단순 문자열 검색은 `ⓐⓐ{...}` 내부를 함께 잡을 수 있으므로 카운트 근거로 쓰지 않습니다.

소제목은 무단 수정하지 않습니다. 소제목 유무가 회차마다 불균형하면 하네스는 있는 회차 수와 없는 회차 수를 세고, 더 적은 쪽에만 `ⓐⓐ(의견: ...)`을 붙입니다. 소제목 있는 회차가 소수이면 삭제 후보 의견, 소제목 없는 회차가 소수이면 기존 소제목 톤과 길이에 맞춘 추가 후보 의견으로 남깁니다.

문맥형 오타는 `edit_class=contextual_typo`로 표시합니다. 이 항목은 `reading_basis`와 앞뒤 문맥 근거(`context_before`, `context_after`, `context_window`, `evidence_snippet` 중 하나)를 가져야 하며, `ⓐ` 확정은 `confidence_percent >= 95`일 때만 허용합니다. `render-change-contexts`는 변경 후보 주변 원문을 `corrections/change_contexts.md`로 렌더링합니다.

## Consistency-Correction Loop

정합성 평가와 교정은 단발 작업이 아닙니다. 하네스는 `consistency_correction_loop`를 기준으로 아래 순서를 반복합니다.

1. 정합성 평가에서 확정/유보/강등 항목을 분리한다.
2. `llm-facing/correction_plan.md`에 교정 batch를 만든다.
3. `corrections/changes.json`을 검증하고 `render-marked-manuscript-md`로 원문형 기호 적용 MD 검수본을 생성한다. 납품 또는 한글 검토가 필요하면 `render-marked-manuscript-hwpx`도 추가 생성한다.
4. 승인 범위에 맞춰 plain text 후보본에 적용한다.
5. 같은 회차와 앞뒤 회차를 다시 읽어 정합성 재평가를 한다.
6. 해결된 항목, 새로 생긴 항목, 회귀 항목, 잔여 리스크를 `llm-facing/consistency_correction_loop.md`에 남긴다.
7. 만족 기준을 통과할 때까지 다음 batch를 반복한다.

만족 기준은 P0/P1 정합성 이슈가 해결 또는 작가 판단 보류로 분리되고, 중복/정본 선택과 회차별 공백 제외 4000자 기준이 닫히며, 재평가에서 새 P0/P1 회귀가 없는 상태입니다.

`human-facing/final_improvement_report.md`는 반복 루프가 닫힌 뒤 작성합니다. 이 문서는 내부 작업 로그가 아니라 Before/After, 개선 근거, 잔여 리스크, 작가 판단 항목을 한국어 편집자-facing으로 정리합니다.

`validate-report --run-root`는 manifest 또는 최신 `N차_one_page_report.md`를 검증합니다. 기본 1차 SSOT는 `human-facing/1차_one_page_report.md`입니다. 최종 개선 보고서를 납품 대상으로 쓸 때는 파일을 직접 지정합니다.

```powershell
.\scripts\novel-qc-loop.ps1 validate-report --report "workspace\...\runs\...\human-facing\final_improvement_report.md"
```

## Consistency-First Editorial Gate

편집자 모드는 전역 감리 직후 바로 실행하지 않습니다. `consistency_first_editorial_gate`를 통과한 뒤 실행합니다.

필수 순서:

1. primary 전 회차 정합성/맥락 장부와 충돌 후보를 3회 작성한다.
2. blind 3개 lane이 서로의 결과를 읽지 않고 각 3회 작성한다.
3. `llm-facing/total_consistency_report.md`에 확정/강등/유보/전제 수용/장르 허용을 통합한다.
4. 통합본을 대상으로 `llm-facing/adversarial_audit_3pass.md`에 적대적 감리 3회를 남긴다.
5. `llm-facing/episode_deep_dive.md`에 회차별 수동 독해를 남긴다. 자동 evidence만 복사하지 않고 앞뒤 회차와 장면 맥락을 직접 확인한다.
6. `llm-facing/consistency_report.md`에 편집자 모드로 넘길 항목과 보류 항목을 분리한다.
7. 그 뒤에만 `corrections/changes.json`에 적극 편집 후보를 작성한다.

1-4번이 1개 `consistency_3x3_unit`입니다. 사용자가 `정합성 검사`라고만 말하면 이 단위를 1회 수행합니다. `정합성 검사 3번`처럼 횟수를 지정하면 1-4번 전체를 3회 반복하며, `manual_review_submission.json`의 `consistency_repetition_contract.requested_unit_count`를 해당 횟수로 둡니다.

`episode_deep_dive.md` 또는 `consistency_report.md`가 비어 있거나 `작성 필요` 상태이면 게이트 미통과입니다. `consistency_report.md`의 편집자 모드 진입 가능 여부가 `가능`으로 명시된 뒤에만 적극 편집 후보를 작성합니다.

기호 보존이 기본값입니다. `ⓚ`, 대괄호 UI, 회차 제목, 특수기호는 삭제하지 않고, 송고 위생 문제인지 작중 장치인지 먼저 판정합니다. 단, 회차 표기 또는 같은 줄 소제목의 마커가 `#`이거나 빠져 있으면 intake에서 `ⓚ`로 통일합니다. 숫자 없는 Markdown 제목만 있는 원고는 순서대로 `ⓚ제N화 제목`을 붙이고, 폴더/EPUB 묶음에서 회차 헤더가 없으면 `ⓚ제N화`를 붙입니다. 본문 안의 독립 소제목은 회차 헤더로 확정되지 않으면 자동 변경하지 않습니다.

회차별 공백 제외 글자수는 4000자 이상을 강한 원칙으로 둡니다. `inspection.json`, `facts/chapter_metrics.jsonl`, `review/chapter_length_flags.jsonl`, `submission_gate.json`은 이 기준과 미달 회차를 드러냅니다. 4000자 미만 회차는 결락, 중복, 분할 오류, 정본 선택 보류 후보로 먼저 검토합니다.

중복 회차는 아래 기준으로 처리합니다.

- 완전 동일 중복: 뒤쪽 또는 파일명 범위에서 벗어난 블록을 `ⓐ(삭제)` 후보로 올릴 수 있다.
- 비동일 중복: 먼저 정본 선택을 `ⓐⓐ` 판단으로 남긴다.
- 정본 후보는 공백 제외 4000자 이상이어야 한다. 삭제 후 남는 정본이 4000자 미만이면 삭제 확정 대신 결락/추가/정본 선택 보류로 둔다.
- 정본 결정 후 비정본 블록 삭제는 `ⓐ(삭제)` 후보로 올릴 수 있다.
- 삭제본에만 있는 문장 이식은 자동 병합하지 않고 `ⓐⓐ(이식 후보)`로 분리한다.

감리 제출 파일은 `validate-submission`으로 확인합니다. `--run-root`를 쓰면 `submission_gate.json`의 `manual_review` 상태도 함께 갱신됩니다. 수동 감리가 완료되지 않으면 보고서 검증과 제출 gate가 모두 막힙니다.

`findings`에는 95% 재감리를 위한 선택 필드를 둘 수 있습니다.

- `decision`: `확정`, `강등`, `철회`, `유보`
- `confidence_percent`: 0-100 정수. `확정`은 95 이상이어야 합니다.
- `evidence_snippet`: 작가/편집자-facing 보고서에 바로 쓸 수 있는 근거 문장.
- `counter_evidence`: 강등/철회 판단의 반례 또는 방어 가능한 해석.
- `original_priority`, `final_priority`: P0-P3 우선순위 변경 이력.
- `story_state_before`, `story_state_after`: 앞뒤 장면에서 확인되는 작중 상태.
- `story_internal_impact`: 외부 고증이 아니라 독자가 실제로 납득을 잃는 작중 영향.
- `repairability`: `local_fixable`, `structural_fixable`, `needs_author_decision`, `irreconcilable_premise`, `webnovel_allowance`.
- `disposition`: `editable_conflict`, `accepted_world_premise`, `genre_hyperbole_allowance`, `hard_carryover_conflict`, `external_fact_soft`, `needs_author_decision`.

`status=complete` 제출에서는 finding마다 `decision`, `confidence_percent`, `final_priority`, `fix_hint`, `reader_risk`가 필요합니다. P0/P1은 확정/95%/직접 근거/반례 없음/작중 핍진성 영향 조건을 충족해야 하며, 반례 또는 소설적 허용으로 방어 가능한 항목은 P2/P3로 강등하거나 철회/유보합니다. `hard_carryover_conflict` P0/P1은 `story_state_before`와 `story_state_after`를 모두 요구합니다.

```powershell
.\scripts\novel-qc-loop.ps1 validate-submission --run-root "workspace\...\runs\..."
```

완료된 감리 제출 파일은 재감리 보고서로 렌더링할 수 있습니다.

```powershell
.\scripts\novel-qc-loop.ps1 render-reaudit-report --run-root "workspace\...\runs\..."
```

작가/편집자에게 바로 보낼 상세 보고서는 별도 렌더러를 사용합니다. 이 보고서는 `manual_review_submission.json`의 `evidence_snippet`, `counter_evidence`, `fix_hint`, `reader_risk`, `final_priority`를 읽어 항목별 설명문을 만듭니다.

```powershell
.\scripts\novel-qc-loop.ps1 render-author-final-report --run-root "workspace\...\runs\..."
.\scripts\novel-qc-loop.ps1 render-author-final-report --run-root "workspace\...\runs\..." --pdf
```

이미 만든 Markdown 보고서만 PDF로 내보낼 수도 있습니다.

```powershell
.\scripts\novel-qc-loop.ps1 export-report-pdf --report "workspace\...\runs\...\human-facing\author_final_report.md"
```

## Stage 상태

`run_manifest.json`의 `stages`를 기준으로 이어받습니다.

```powershell
.\scripts\novel-qc-loop.ps1 mark-stage --run-root "workspace\...\runs\..." --stage 03_adversarial_audit --status done
```
