# 반복/다작품 루프

## 핵심 명령

초기 원고함 일괄 intake:

```powershell
.\scripts\novel-qc-loop.ps1 intake-inbox --mode full
```

증거 파일까지 즉시 생성:

```powershell
.\scripts\novel-qc-loop.ps1 intake-inbox --mode full --analyze
```

단일 원고 intake:

```powershell
.\scripts\novel-qc-loop.ps1 intake --input "C:\path\to\manuscript.txt" --mode full --analyze
```

작품 목록:

```powershell
.\scripts\novel-qc-loop.ps1 list-works
```

작품별 run 목록:

```powershell
.\scripts\novel-qc-loop.ps1 list-runs --work canaria
```

전체 포트폴리오 상태:

```powershell
.\scripts\novel-qc-loop.ps1 portfolio-status
```

기계가 읽을 JSON:

```powershell
.\scripts\novel-qc-loop.ps1 portfolio-status --json
```

## 작품 10개를 동시에 운영하는 감각

각 작품은 `manifest.json`으로 정체성을 가집니다.

- 장르
- 대상 독자
- 플랫폼
- 원본 경로
- 운영 메모

각 검수는 `run_manifest.json`으로 상태를 가집니다.

- run 종류
- 생성 시각
- source text
- 단계별 pending/done
- evidence/report/export 위치

이 구조 덕분에 다음 질문을 IDE에서 바로 할 수 있습니다.

- 지금 어떤 작품이 대기 중인가?
- 마지막 run이 어디에서 멈췄나?
- 한 작품만 계속 파고 있는가, 전체 포트폴리오를 균형 있게 보고 있는가?
- 같은 P2 폴리싱 문제가 여러 작품에서 반복되는가?

## 권장 run 종류

- `global-audit`: 전역 검수. P0/P1 치명상 우선.
- `adversarial-audit`: 독자/심사자 관점 3회 감리.
- `ai-slop-scan`: 특정 장르 취향을 강제하지 않고 AI 티, 반복 표현, 말투 균질화를 점검.
- `correction-pass`: `ⓐ`/`ⓐⓐ` 교정안 생성.
- `editorial-pass`: 적극 편집자 모드. replace/delete/insert_before/insert_after 기반 윤문, 중복 삭제, 브리지 추가. HWP/HWPX 대신 text 후보본과 Markdown diff를 사용.
- `export-pass`: PDF/HWPX/HTML 산출과 확인.

## 자동 evidence 생성

```powershell
.\scripts\novel-qc-loop.ps1 analyze-run --run-root "workspace\{work}\runs\{run_id}"
```

생성물:

- `evidence/facts/dates.jsonl`
- `evidence/facts/absolute_dates.jsonl`
- `evidence/facts/relative_times.jsonl`
- `evidence/facts/ages.jsonl`
- `evidence/facts/times.jsonl`
- `evidence/facts/money.jsonl`
- `evidence/facts/percents.jsonl`
- `evidence/facts/titles.jsonl`
- `evidence/facts/kin_titles.jsonl`
- `evidence/facts/timeline_summary.json`
- `evidence/facts/character_title_matrix.json`
- `evidence/review/hygiene_flags.jsonl`
- `evidence/review/replay_candidates.jsonl`
- `evidence/review/bridge_review_candidates.jsonl`
- `evidence/review/era_review_candidates.jsonl`
- `evidence/review/ai_slop_signals.json`
- `evidence/submission/submission_gate.json`
- `evidence/submission/manual_review_queue.jsonl`
- `evidence/submission/manual_review_submission.json`

감리 제출 검증:

```powershell
.\scripts\novel-qc-loop.ps1 validate-submission --run-root "workspace\{work}\runs\{run_id}"
```

## 팀 운영 규칙

- 한 사람이 한 run을 끝까지 책임진다.
- 원고 원본은 `inputs/`에 두고 수정하지 않는다.
- 추출본과 교정본은 `extracted/`, `corrections/`, `exports/`에 분리한다.
- 최종 보고서는 `runs/{run_id}/final_reports/`에 둔다.
- 팀 공통으로 재사용할 발견은 `docs/patterns` 계열 문서로 승격한다.

## 모델 독립성

이 루프는 특정 모델에 묶이지 않습니다.

중요한 것은 모델 이름이 아니라 산출물이 다음 계약을 지키는가입니다.

- manifest를 읽었는가
- 원본을 보존했는가
- 문제에 근거를 붙였는가
- 내부 감리와 human-facing 보고서를 분리했는가
- 다음 run이 이어받을 수 있게 상태를 남겼는가
