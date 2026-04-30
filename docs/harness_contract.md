# Harness Contract

이 문서는 `text-qc`가 생성하는 run 폴더의 표준 계약입니다.

## 목표

초기 원고를 넣으면, 사람이든 LLM이든 같은 위치에서 같은 파일을 보고 이어받을 수 있어야 합니다.

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
      hygiene_flags.jsonl
      ai_slop_signals.json
      replay_candidates.jsonl
      bridge_review_candidates.jsonl
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
    global_audit_raw.md
    adversarial_audit_3pass.md
    correction_plan.md
  human-facing/
    one_page_report.md
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
- `facts/timeline_summary.json`: 시간 표현이 몰린 회차 후보.
- `facts/character_title_matrix.json`: 한 인물이 여러 직함/호칭으로 잡히는 drift 후보.
- `review/hygiene_flags.jsonl`: 작가 메모, 교정 마커, HTML 엔티티, 무대지문 등 송고 위생 후보.
- `review/replay_candidates.jsonl`: 회차 경계 반복 후보.
- `review/bridge_review_candidates.jsonl`: 회차 앞뒤 브리지 약화 후보.
- `review/era_review_candidates.jsonl`: 시대감/현대어/장르 톤 후보.
- `review/ai_slop_signals.json`: 반복 반응/추상어/AI 티 후보.
- `package/epub_package_qc.*`: EPUB 파일/폴더 입력 시 언어, 식별자, 파일명 규칙, OPF 기본 메타데이터 확인 결과.
- `submission/submission_gate.json`: 송고 보류/검토 가능 여부를 기계적으로 요약.
- `submission/manual_review_queue.jsonl`: 3-pass x 감리 축 작업 큐.
- `submission/manual_review_submission.json`: 사람이 완료한 감리 결과.

Evidence는 판정이 아니라 후보입니다. 최종 판단은 `llm-facing` 감리와 `human-facing` 보고서에서 수행합니다.

## LLM-facing

`llm-facing/`은 내부 작업자와 AI 에이전트가 읽는 폴더입니다. 길어도 됩니다.

반드시 남길 것:

- 전역 검수 raw
- 적대적 감리 3-pass
- 교정안
- 반례 탐색 메모

## Human-facing

`human-facing/one_page_report.md`는 기본적으로 1장입니다.

원칙:

- 내부 로그를 노출하지 않는다.
- 모델명/프롬프트/실행 흔적을 쓰지 않는다.
- 한국어 작가/편집자-facing 문장으로 쓴다.
- 모든 핵심 판단은 `주장`과 `근거`를 함께 둔다.
- 근거 없는 주장은 최종 보고서에 올리지 않는다.
- 문제, 근거, 독자 리스크, 수정 방향만 남긴다.
- 작가전달용 최종 보고서는 항목별로 `위치`, `원문 근거`, `문제`, `근거`, `해석`, `수정 방향`을 포함한다.
- 해석 여지가 있거나 반례가 있는 항목은 P0/P1로 강하게 올리지 않고 P2/P3 보강 권고로 낮춘다.

최종 보고서는 `validate-report`를 통과해야 합니다. 이 검증은 한국어 비율, 내부 작업어 노출, placeholder, 주장-근거 쌍을 확인합니다.

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

감리 제출 파일은 `validate-submission`으로 확인합니다. `--run-root`를 쓰면 `submission_gate.json`의 `manual_review` 상태도 함께 갱신됩니다.

`findings`에는 95% 재감리를 위한 선택 필드를 둘 수 있습니다.

- `decision`: `확정`, `강등`, `철회`, `유보`
- `confidence_percent`: 0-100 정수. `확정`은 95 이상이어야 합니다.
- `evidence_snippet`: 작가/편집자-facing 보고서에 바로 쓸 수 있는 근거 문장.
- `counter_evidence`: 강등/철회 판단의 반례 또는 방어 가능한 해석.
- `original_priority`, `final_priority`: P0-P3 우선순위 변경 이력.

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
