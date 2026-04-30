# Intake Harness

초기 원고를 넣으면 작품 폴더와 run 폴더를 자동 생성하는 하네스입니다.

## 단일 파일 intake

```powershell
.\scripts\novel-qc-loop.ps1 intake `
  --input "C:\path\to\manuscript.txt" `
  --mode full `
  --genre "장르명" `
  --audience "대상 독자" `
  --platform "플랫폼명"
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
      inspection.json
    llm-facing/
      task_brief.md
      handoff_checklist.md
    human-facing/
      one_page_report.md
    corrections/
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
