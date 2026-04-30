# Intake Harness

초기 원고를 넣으면 작품 폴더와 run 폴더를 자동 생성하는 하네스입니다.

## 단일 파일 intake

```powershell
.\scripts\novel-qc-loop.ps1 intake `
  --input "C:\path\to\manuscript.txt" `
  --mode full `
  --genre "장르명" `
  --audience "대상 독자" `
  --platform "플랫폼명" `
  --analyze
```

지원 형식:

- `.txt`
- `.md`
- `.hwpx` (`Preview/PrvText.txt` 기준 추출)

## 초기 원고함 intake

`inbox/initial_manuscripts/`에 원고 파일을 넣고 실행합니다.

```powershell
.\scripts\novel-qc-loop.ps1 intake-inbox --mode full
```

자동 증거 추출까지 바로 수행하려면:

```powershell
.\scripts\novel-qc-loop.ps1 intake-inbox --mode full --analyze
```

각 파일마다 제목을 유추하고, `workspace/{work_slug}` 아래에 독립 작업 공간을 만듭니다.

## 자동 생성 구조

```text
workspace/{work_slug}/
  manifest.json
  inputs/original/
    원본 파일
  extracted/
    source.txt
  runs/{run_id}/
    run_manifest.json
    evidence/
      episodes/
      inspection.json
      facts/
      review/
      submission/
        manual_review_queue.jsonl
        manual_review_submission.json
    llm-facing/
      task_brief.md
      handoff_checklist.md
      adversarial_3pass_brief.md
    human-facing/
      one_page_report.md
    corrections/
      marker_protocol.md
      changes.json
    final_manuscript/
      README.md
      final_manuscript.txt
    exports/
```

## 제목 유추

우선순위:

1. `--title`로 지정한 제목
2. 파일명에서 `합본`, `원고`, `최종`, `수정본` 같은 작업어 제거
3. 파일명이 너무 일반적이면 본문 첫 80줄 안의 제목 후보
4. 그래도 없으면 `untitled-work`

## 모드

- `audit` / `검수`: 검수 중심
- `correction` / `교정`: 교정 중심
- `full` / `전체`: 검수, 적대적 감리, 교정안, human-facing 보고서, 최종 원고 후보까지

## Human-facing 보고서

기본 보고서는 `human-facing/one_page_report.md` 하나입니다.

중간 분석, 긴 체크리스트, 모델에게 넘길 지시는 `llm-facing/`에 둡니다. 작가/편집자에게 바로 보여줄 문서는 기본적으로 1장만 유지합니다.

## 감리 제출물

`--analyze`를 붙이면 다음 파일이 함께 준비됩니다.

- `evidence/facts/timeline_summary.json`: 시간 표현이 몰린 회차 후보.
- `evidence/facts/character_title_matrix.json`: 인물/직함 drift 후보.
- `evidence/review/bridge_review_candidates.jsonl`: 앞뒤 화 연결 후보.
- `evidence/submission/manual_review_queue.jsonl`: 3-pass x 감리 축 작업 큐.
- `evidence/submission/manual_review_submission.json`: 최종 감리자가 채워 넣는 제출 파일.

감리 완료 후에는 아래 명령으로 구조를 확인합니다.

```powershell
.\scripts\novel-qc-loop.ps1 validate-submission --run-root "workspace\{work}\runs\{run_id}"
```
