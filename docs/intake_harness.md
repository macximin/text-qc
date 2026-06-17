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

`--mode`는 gate profile을 함께 정합니다. `full`은 `delivery`, `audit`은 `consistency`, `editor`는 `editorial`, `correction`은 `correction`, `proofread`는 `proofread` profile입니다. 필요하면 `--gate-profile proofread|correction|editorial|consistency|delivery`로 명시합니다. 새 run의 실제 권위는 `run_manifest.json`의 `gate_profile`입니다.

지원 형식:

- `.txt`
- `.text`
- `.md`
- `.markdown`
- `.hwp` (`hwp5proc xml` 우선, 실패 시 `hwp5txt` fallback. HWP `LINE_BREAK`는 실제 줄바꿈으로 보존)
- `.hwpx` (`Preview/PrvText.txt` 우선, 없으면 HWPX XML 본문 fallback)
- `.epub` (OPF spine 기준 본문 XHTML만 추출, metadata/nav/toc/cover는 제외)

텍스트 인코딩은 UTF-8/UTF-8 BOM/CP949/EUC-KR/UTF-16 계열을 자동 감지합니다.

내부 NAS 원본 root:

```text
\\172.16.10.120\소설사업부\판무팀_ssot
```

이 경로는 원본 참조 root입니다. 원본은 직접 수정하지 않고, intake가 만든 run 내부 산출물을 수정 대상으로 삼습니다.

감지하는 회차 표기:

- `ⓚ001`, `ⓚ제1화`
- Markdown 제목: `# 1화`
- 번호형 제목: `제1화`, `001화`, `1장`, `Episode 1`

intake는 회차 헤더 마커를 `ⓚ`로 통일합니다. `# 제1화`, `#001 소제목`, `제1화 소제목`처럼 `#`이 쓰였거나 마커가 빠진 회차 표기/같은 줄 소제목은 `ⓚ...`로 정규화합니다. 숫자 없는 Markdown 제목만 있는 원고는 순서대로 `ⓚ제N화 제목`을 붙입니다. 폴더 또는 EPUB 묶음에서 개별 파일에 회차 헤더가 없으면 `ⓚ제N화`를 붙입니다. 본문 안의 독립 소제목은 회차 헤더로 확정되지 않으면 자동 변경하지 않습니다.

송고 기본 형식은 `ⓚ` 회차/소제목 마커, 제목 아래 빈 줄 3줄, 대사-대사 붙임, 지문-지문 붙임, 대사와 지문 사이 빈 줄 1줄입니다. 직선 따옴표 `""`/`''`는 곡선 따옴표 `“”`/`‘’`로 정리합니다. `analyze-run`은 위반 항목을 `evidence/review/manuscript_format_flags.jsonl`에 남기고 submission gate의 `manuscript_format_policy_violations` blocker로 올립니다.

## 초기 원고함 intake

`inbox/initial_manuscripts/`에 원고 파일을 넣고 실행합니다.

```powershell
.\scripts\novel-qc-loop.ps1 intake-inbox --mode full
```

자동 증거 추출까지 바로 수행하려면:

```powershell
.\scripts\novel-qc-loop.ps1 intake-inbox --mode full --analyze
```

각 파일 또는 지원 원고 파일이 들어 있는 폴더마다 제목을 유추하고, `workspace/{work_slug}` 아래에 독립 작업 공간을 만듭니다.

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
      consistency_rounds/
      blind_reviews/
      total_consistency_report.md
      adversarial_audit_3pass.md
      harness_adversarial_audit_3pass.md
      episode_deep_dive_brief.md
      episode_deep_dive.md
      consistency_report.md
      correction_plan.md
      consistency_correction_loop.md
    human-facing/
      1차_one_page_report.md
      final_improvement_report.md
    corrections/
      marker_protocol.md
      changes.json
    final_manuscript/
      README.md
      final_manuscript.txt
    final_delivery/
      v1_final_approved_package/
        *_final_approved.txt
        *_final_human_report.html
        delivery_manifest.json
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
- `editor` / `편집`: 적극 편집자 모드. 중복 삭제, 문장 윤문, 빠진 브리지 추가, AI 티 완화까지 포함
- `full` / `전체`: primary 정합성 3회, blind 3개 lane x 3회, total 정합성 리포트, 적대적 감리, 교정안, human-facing 보고서, 최종 원고 후보까지

편집자 모드는 `gate_profile`에 맞는 정합성 우선 편집 게이트를 거칩니다. `delivery`/`consistency` profile은 primary 정합성 3-pass, blind 3개 lane x 3-pass, `llm-facing/total_consistency_report.md`, 적대적 감리 3-pass까지 닫습니다. `editorial` profile은 `manual_review_queue.jsonl`의 `required_for_gate=true` 항목과 `llm-facing/consistency_report.md`의 편집 진입 판정을 우선합니다. full 묶음 전체가 1개 `consistency_3x3_unit`이며, 사용자가 `정합성 검사 3번`이라고 하면 이 묶음을 세 번 반복합니다.

회차별 공백 포함 글자수는 4000자 이상을 강한 원칙으로 둡니다. `inspection.json`과 `facts/chapter_metrics.jsonl`에는 기준과 회차별 충족 여부가 남고, 미달 회차는 `evidence/review/chapter_length_flags.jsonl`과 `submission_gate.json`에 blocker 후보로 남습니다.

편집자 모드는 HWP/HWPX를 기본 작업물로 쓰지 않습니다. `corrections/changes.json`을 plain text에 적용해 `final_manuscript/editorial_candidate.txt`와 `corrections/editorial_diff.md`를 생성합니다. 중간 확인이 필요하면 `render-marked-manuscript-md`로 원문 순서 그대로 기호가 들어간 MD 검수본을 생성합니다. 한글 검토나 납품 요구가 있으면 `render-marked-manuscript-hwpx`도 함께 생성합니다.

최종 승인 패키지는 `render-final-delivery`가 생성합니다. 기본 납품 원고는 TXT이고, 기본 human-facing 보고서는 HTML입니다. 최종 보고서 기본 밀도는 `closing_full`이며, 누적 마감 보고서에는 정책 판정, glossary SSOT, AI-slop 표면, hold/watchlist 분리, 검증/재봉인 상태가 들어갑니다. 최종 패키징 전에는 `scan-ai-slop`으로 메타 표식, 괄호 주석, placeholder, 내부 메모형 표면을 별도 확인합니다.

정합성 평가와 교정은 반복합니다. `llm-facing/correction_plan.md`에 교정 batch를 만들고, 적용 후 `llm-facing/consistency_correction_loop.md`에 해결/신규/회귀/잔여 리스크를 남깁니다. 최종 개선은 `human-facing/final_improvement_report.md`에 Before/After와 근거 중심으로 정리합니다.

문맥형 오타 확인은 `render-change-contexts`로 `corrections/change_contexts.md`를 만든 뒤 진행합니다. `edit_class=contextual_typo` 변경안은 앞뒤 문맥 근거와 `reading_basis`를 가져야 합니다.

## Human-facing 보고서

기본 빠른 보고서는 `human-facing/1차_one_page_report.md` 하나입니다. n차 보고서는 `N차_one_page_report.md`로 차수만 올립니다. 반복 루프 이후 최종 개선 요약은 `human-facing/final_improvement_report.md`에 둡니다.

N차 보고서는 누적식입니다. 직전 차수 이후 신규 항목만 쓰지 않고 P0-P3 전체를 계속 보여주며, 각 항목의 최초 차수와 현재 상태를 갱신합니다. 해결, 강등, 철회, 유보, 작가 판단 필요 항목도 삭제하지 않습니다. 특정 등급이 아직 없으면 해당 등급을 생략하지 말고 0건이라고 씁니다.

중간 분석, 긴 체크리스트, 모델에게 넘길 지시는 `llm-facing/`에 둡니다. 작가/편집자에게 바로 보여줄 문서는 기본적으로 1장만 유지합니다.

## 감리 제출물

`--analyze`를 붙이면 다음 파일이 함께 준비됩니다.

- `evidence/facts/timeline_summary.json`: 시간 표현이 몰린 회차 후보.
- `evidence/facts/character_title_matrix.json`: 인물/직함 drift 후보.
- `evidence/review/chapter_length_flags.jsonl`: 공백 포함 4000자 미만 회차 후보.
- `evidence/review/bridge_review_candidates.jsonl`: 앞뒤 화 연결 후보.
- `evidence/submission/manual_review_queue.jsonl`: profile별 작업 큐. `required_for_gate=true`인 행이 이 run에서 실제 필수 작업입니다.
- `evidence/submission/manual_review_submission.json`: 최종 감리자가 채워 넣는 제출 파일. 완료 조건은 `gate_profile`의 required axes/workflow를 따릅니다. `delivery`/`consistency` profile에서는 primary/blind/total/adversarial 묶음과 `consistency_repetition_contract`를 닫습니다.

감리 완료 후에는 아래 명령으로 구조를 확인합니다.

```powershell
.\scripts\novel-qc-loop.ps1 validate-submission --run-root "workspace\{work}\runs\{run_id}"
```
