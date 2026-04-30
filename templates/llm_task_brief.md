# LLM Task Brief

작품: `{{title}}` (`{{work_slug}}`)
Run: `{{run_id}}`
모드: `{{mode}}` / `{{run_kind}}`

## 입력

- 원본 경로: `{{source_path}}`
- 추출 텍스트: `{{extracted_text_path}}`
- 장르/독자/플랫폼: `{{genre}} / {{audience}} / {{platform}}`

## 작업 원칙

- 원본 파일은 절대 덮어쓰지 않는다.
- 검수와 교정을 분리한다.
- 내부 분석은 `llm-facing/`에 둔다.
- 작가/편집자에게 보여줄 보고서는 `human-facing/one_page_report.md`를 기본 1장으로 유지한다.
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

