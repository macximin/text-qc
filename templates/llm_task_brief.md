# LLM Task Brief

작품: `{{title}}` (`{{work_slug}}`)
Run: `{{run_id}}`
모드: `{{mode}}` / `{{run_kind}}`

## 입력

- 원본 경로: `{{source_path}}`
- 내부 NAS root: `{{internal_nas_root}}`
- 추출 텍스트: `{{extracted_text_path}}`
- 감리 큐: `{{manual_review_queue_path}}`
- 감리 제출 파일: `{{manual_review_submission_path}}`
- 장르/독자/플랫폼: `{{genre}} / {{audience}} / {{platform}}`

## 먼저 실행할 하네스

```powershell
.\scripts\novel-qc-loop.ps1 analyze-run --run-root "{{run_root}}"
```

이 명령은 작중 핍진성 후보, 날짜/시간/금액/직함/송고 위생/회차 반복/AI 티 후보를 `evidence/` 아래에 만든다. 자동 evidence는 판정이 아니라 감리 후보로만 사용한다.

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
- 문맥형 오타는 패턴 치환이 아니라 앞뒤 문맥을 읽고 판단한다.
- human-facing 보고서는 한국어로 쓰고, 모든 핵심 판단에 `주장`과 `근거`를 함께 둔다.
- 근거 없는 주장은 최종 보고서에 올리지 않는다.
- 최종 보고서는 `validate-submission`이 통과된 뒤 `validate-report`까지 통과해야 제출 가능하다.
- P0/P1은 최종 감리에서 확정, 95% 이상 확신, 직접 근거, 미해결 반례 없음, 작중 핍진성 영향이 모두 맞는 항목만 사용한다.
- 날짜/요일/영업일 같은 외부 고증은 작중 행동·상태·인과가 깨지는 경우에만 강한 이슈로 올린다.
- 최종 원고 후보는 `final_manuscript/final_manuscript.txt`에 둔다.

## 모드별 목표

### audit / 검수

- P0/P1/P2를 분리한다.
- 문제마다 근거를 붙인다.
- "맞냐 틀리냐"보다 독자가 어떻게 읽을지를 설명한다.
- `오늘 했다`와 `오늘 하지 않았다`, 완료된 사건의 원인 없는 회귀, 이미 안다는 정보의 재발견처럼 작중 연속성이 깨지는 항목을 최우선으로 본다.
- 소설적 허용이나 대체 해석으로 방어 가능한 항목은 P2/P3 또는 유보로 낮춘다.

### correction / 교정

- 확정 교정은 `ⓐ`.
- 작가 판단 요청은 `ⓐⓐ`.
- 변경 근거를 남긴다.
- 삭제는 `operation=delete`, 추가는 `operation=insert_before` 또는 `operation=insert_after`로 남긴다.
- 추가 작업에서도 `find`는 빈 문자열이 아니라 삽입 위치를 잡는 앵커 문장이어야 한다.
- 문맥형 오타는 `edit_class=contextual_typo`로 두고 `reading_basis`와 앞뒤 문맥 근거를 남긴다.
- 문맥형 오타를 `ⓐ`로 확정하려면 `confidence_percent`가 95 이상이어야 한다.

### editor / 편집

- 교정자가 아니라 매우 적극적인 편집자로 작업한다.
- 작품의 기대 품질이 AI-slop일 수 있음을 전제로, 중복 문장, 단조로운 문장 리듬, 추상 감정어 반복, 빠진 인과 브리지를 적극적으로 고친다.
- 필요하면 문장 단위 치환, 삭제, 추가를 모두 제안한다.
- 적극 편집은 기본적으로 `ⓐⓐ`로 올리고, 작가 승인 전 최종 원고에 확정 반영하지 않는다.
- 편집자 모드에서는 HWP/HWPX를 기본 작업물로 쓰지 않고, `apply-changes-text`로 텍스트 후보본과 Markdown diff를 만든다.
- 문맥형 오타 후보는 `render-change-contexts`로 주변 문맥을 뽑은 뒤 판단한다.
- 세부 기준은 `llm-facing/editorial_pass_brief.md`를 따른다.

### full / 전체

1. 1차 전역 감리
2. 적대적 감리 3회
3. 편집자 모드 윤문/정합성 편집안
4. 교정안
5. human-facing 1장 보고서
6. 최종 원고 후보

## 기본 지표

- 전체 글자 수: {{char_count}}
- 공백 제외 글자 수: {{chars_no_space}}
- 회차 수: {{chapter_count}}
- 120자 이상 줄: {{long_lines_120}}
- 200자 이상 줄: {{long_lines_200}}
