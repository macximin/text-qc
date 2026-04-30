# {{title}} 검수 요약

작품: `{{work_slug}}`  
Run: `{{run_id}}`  
모드: `{{mode}}`  
장르/독자/플랫폼: `{{genre}} / {{audience}} / {{platform}}`

## 한줄 판정

초기 원고가 intake되었고, 아래 기준으로 검수/교정 대기 상태입니다.

## 기본 지표

- 전체 글자 수: {{char_count}}
- 공백 제외 글자 수: {{chars_no_space}}
- 감지된 회차 수: {{chapter_count}}
- 120자 이상 긴 줄: {{long_lines_120}}
- 200자 이상 벽돌 줄: {{long_lines_200}}

<!-- AUTO:AI_SLOP_START -->
## AI 티 점검

- 분석 전: `--analyze` 실행 후 AI 문체 신호 기반 추정치가 자동 반영됩니다.
<!-- AUTO:AI_SLOP_END -->

## 우선 확인할 것

1. 말이 되는가: 시간, 장소, 인물, 수치가 앞뒤로 맞는지 확인.
2. 읽히는가: 모바일에서 긴 줄과 벽돌 단락이 숨을 막지 않는지 확인.
3. 독자에게 먹히는가: 장르/플랫폼/대상 독자 기준으로 기대 충족과 납득 근거가 보이는지 확인.
4. 교정 가능한가: 확정 교정(`ⓐ`)과 작가 판단(`ⓐⓐ`)을 분리.

## 다음 액션

- LLM/에이전트는 `llm-facing/task_brief.md`를 먼저 읽고 작업.
- 내부 감리 결과는 `llm-facing/`에 남김.
- 작가/편집자에게 보여줄 최종 보고서는 이 1장 형식을 기준으로 `human-facing/`에 정리.
- 최종 원고 후보는 `final_manuscript/final_manuscript.txt`에 반영.
