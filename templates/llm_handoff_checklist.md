# LLM-facing Handoff Checklist

## 반드시 남길 산출물

- `llm-facing/global_audit_raw.md`: 내부용 원문 기반 검수.
- `llm-facing/adversarial_audit_3pass.md`: 적대적 감리 3회.
- `llm-facing/editorial_pass_brief.md`: 적극 편집자 모드 기준.
- `llm-facing/contextual_typo_brief.md`: 문맥형 오타 판단 기준.
- `llm-facing/correction_plan.md`: 교정안과 우선순위.
- `evidence/submission/manual_review_submission.json`: 감리 제출용 구조화 결과.
- `human-facing/one_page_report.md`: 작가/편집자-facing 1장 보고서.
- `corrections/editorial_diff.md`: 편집자 모드 텍스트 적용 diff.
- `corrections/change_contexts.md`: 문맥형 오타/변경 후보의 주변 문맥.
- `final_manuscript/final_manuscript.txt`: 최종 원고 후보.

## 금지

- 원본 파일 덮어쓰기.
- 근거 없는 문제 제기.
- 주장만 있고 근거가 없는 최종 보고서 작성.
- human-facing 보고서에 내부 프롬프트, 모델명, 실행 로그 노출.
- `ⓐⓐ` 항목을 작가 승인 없이 확정 교정처럼 처리.
- 적극 편집으로 없는 설정, 없는 감정선, 없는 사건을 새로 발명.
- 편집자 모드 기본 작업을 HWP/HWPX 파란줄 산출물에 묶기.
- 문맥형 오타를 앞뒤 문맥 근거 없이 패턴 치환처럼 일괄 처리.

## 완료 조건

- P0/P1/P2가 분리되어 있고, P0/P1은 확정/95% 이상/직접 근거/반례 없음/작중 핍진성 영향 조건을 충족한다.
- 외부 고증 항목은 작중 행동·상태·인과를 깨는 경우와 단순 보강 후보가 분리되어 있다.
- `manual_review_submission.json`의 3-pass와 감리 축 상태가 채워져 있다.
- `validate-submission` 결과가 남아 있고 통과 상태다.
- `validate-report` 결과가 남아 있고 통과 상태다.
- human-facing 보고서가 1장 분량으로 압축되어 있다.
- human-facing 보고서가 한국어 작가/편집자-facing이며, 주장-근거 쌍을 갖춘다.
- `changes.json`의 적극 편집 후보가 replace/delete/insert_before/insert_after 중 하나로 구조화되어 있다.
- `edit_class=contextual_typo` 항목은 reading_basis와 앞뒤 문맥 근거를 갖춘다.
- 편집자 모드 적용본은 plain text 후보본과 Markdown diff로 확인할 수 있다.
- 최종 원고 후보 위치가 명확하다.
- 다음 작업자가 `run_manifest.json`과 이 폴더만 보고 이어받을 수 있다.
