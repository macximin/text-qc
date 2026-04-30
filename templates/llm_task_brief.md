# LLM Task Brief

작품: `{{title}}` (`{{work_slug}}`)
Run: `{{run_id}}`
모드: `{{mode}}` / `{{run_kind}}`

## 입력

- 원본 경로: `{{source_path}}`
- 추출 텍스트: `{{extracted_text_path}}`
- 감리 큐: `{{manual_review_queue_path}}`
- 감리 제출 파일: `{{manual_review_submission_path}}`
- 장르/독자/플랫폼: `{{genre}} / {{audience}} / {{platform}}`

## 먼저 실행할 하네스

```powershell
.\scripts\novel-qc-loop.ps1 analyze-run --run-root "{{run_root}}"
```

이 명령은 날짜/시간/금액/직함/송고 위생/회차 반복/AI 티 후보를 `evidence/` 아래에 만든다. 자동 evidence는 판정이 아니라 감리 후보로만 사용한다.

감리 완료 후:

```powershell
.\scripts\novel-qc-loop.ps1 validate-submission --run-root "{{run_root}}"
.\scripts\novel-qc-loop.ps1 validate-report --run-root "{{run_root}}"
```

## 작업 원칙

- 원본 파일은 절대 덮어쓰지 않는다.
- 검수와 교정을 분리한다.
- 내부 분석은 `llm-facing/`에 둔다.
- 작가/편집자에게 보여줄 보고서는 `human-facing/one_page_report.md`를 기본 1장으로 유지한다.
- human-facing 보고서는 한국어로 쓰고, 모든 핵심 판단에 `주장`과 `근거`를 함께 둔다.
- 근거 없는 주장은 최종 보고서에 올리지 않는다.
- 최종 원고 후보는 `final_manuscript/final_manuscript.txt`에 둔다.

## 모드별 목표

### audit / 검수

- P0/P1/P2를 분리한다.
- 문제마다 근거를 붙인다.
- "맞냐 틀리냐"보다 독자가 어떻게 읽을지를 설명한다.

### correction / 교정

- 확정 교정은 `ⓐ`.
- 작가 판단 요청은 `ⓐⓐ`.
- 변경 근거를 남긴다.

### full / 전체

1. 1차 전역 감리
2. 적대적 감리 3회
3. 교정안
4. human-facing 1장 보고서
5. 최종 원고 후보

## 기본 지표

- 전체 글자 수: {{char_count}}
- 공백 제외 글자 수: {{chars_no_space}}
- 회차 수: {{chapter_count}}
- 120자 이상 줄: {{long_lines_120}}
- 200자 이상 줄: {{long_lines_200}}
