# LLM-facing Handoff Checklist

## 반드시 남길 산출물

- `llm-facing/global_audit_raw.md`: 내부용 원문 기반 검수.
- `llm-facing/consistency_rounds/primary_pass1.md` 등 primary 3회: 전 회차 정합성/맥락 장부와 충돌 후보.
- `llm-facing/blind_reviews/blind_agent_1_pass1.md` 등 blind 3개 lane x 3회: 서로 블라인드인 독립 감리.
- `llm-facing/total_consistency_report.md`: primary/blind 결과 통합본.
- `llm-facing/adversarial_audit_3pass.md`: 적대적 감리 3회.
- `llm-facing/harness_adversarial_audit_3pass.md`: 하네스 계약 변경 또는 계층화 변경 자체에 대한 적대적 감리 3회.
- `llm-facing/episode_deep_dive.md`: 회차별 수동 맥락 독해.
- `llm-facing/consistency_report.md`: 편집자 모드 진입 전 정합성 판정.
- `llm-facing/editorial_pass_brief.md`: 적극 편집자 모드 기준.
- `llm-facing/contextual_typo_brief.md`: 문맥형 오타 판단 기준.
- `llm-facing/correction_plan.md`: 교정안과 우선순위.
- `llm-facing/consistency_correction_loop.md`: 정합성 평가와 교정 반복 기록.
- `evidence/submission/manual_review_submission.json`: 감리 제출용 구조화 결과.
- `human-facing/1차_one_page_report.md`: 작가/편집자-facing 1차 SSOT 보고서.
- `human-facing/N차_one_page_report.md`: P0-P3 전체를 누적 표시하는 최신 SSOT 보고서. N차에는 신규 항목만이 아니라 이전 차수 항목의 현재 상태도 남긴다.
- `human-facing/final_improvement_report.md`: 반복 루프 이후 최종 개선 요약.
- `corrections/editorial_diff.md`: 편집자 모드 텍스트 적용 diff.
- `corrections/change_contexts.md`: 문맥형 오타/변경 후보의 주변 문맥.
- `final_manuscript/final_manuscript.txt`: 최종 원고 후보.
- `evidence/review/chapter_length_flags.jsonl`: 공백 제외 4000자 미만 회차 후보.

## 금지

- 원본 파일 덮어쓰기.
- 내부 NAS 원본을 직접 수정하거나 이동.
- 근거 없는 문제 제기.
- 주장만 있고 근거가 없는 최종 보고서 작성.
- human-facing 보고서에 내부 프롬프트, 모델명, 실행 로그 노출.
- `ⓐⓐ` 항목을 작가 승인 없이 확정 교정처럼 처리.
- 적극 편집으로 없는 설정, 없는 감정선, 없는 사건을 새로 발명.
- 편집자 모드 기본 작업을 HWP/HWPX 파란줄 산출물에 묶고 MD 판단용 마커 검수본을 생략하기.
- `regex`, `glob`, `rg` 검색 결과를 본문 독해 없이 확정 판정으로 복붙.
- 문맥형 오타를 앞뒤 문맥 근거 없이 패턴 치환처럼 일괄 처리.
- 전역 3-pass와 화별 딥다이브 없이 자동 evidence만 보고 적극 편집 후보 작성.
- 블라인드 lane이 서로의 결과를 읽고 작성.
- total report 없이 적대적 감리를 먼저 수행.
- 사용자가 `정합성 검사 N번`이라고 했는데 N개의 full `consistency_3x3_unit`이 아니라 pass N개로 축소.
- 하네스 계약 변경 뒤 하네스 자체 적대감리를 생략.
- 세계관 전제/장르적 허세로 방어된 항목을 P0/P1 확정 충돌처럼 제출.
- 정본 선택 전 비동일 중복 회차를 확정 삭제.
- 삭제 후 남는 회차가 공백 제외 4000자 미만인데도 정본 삭제를 확정.
- 교정 후 재평가 없이 최종 보고서에 해결 완료라고 작성.

## 완료 조건

- P0/P1/P2가 분리되어 있고, P0/P1은 확정/95% 이상/직접 근거/반례 없음/작중 핍진성 영향 조건을 충족한다.
- 패턴 검색은 후보 수집으로만 쓰였고, 최종 판단에는 앞뒤 문단/회차 독해 근거가 붙어 있다.
- 외부 고증 항목은 작중 행동·상태·인과를 깨는 경우와 단순 보강 후보가 분리되어 있다.
- `manual_review_submission.json`의 3-pass와 감리 축 상태가 채워져 있다.
- primary 3-pass, blind 3개 lane x 3-pass, total consistency report, adversarial 3-pass가 완료 상태다.
- `정합성 검사 N번` 요청 시 `consistency_repetition_contract.requested_unit_count=N`이고, 완료 unit도 N개다.
- `validate-submission` 결과가 남아 있고 통과 상태다.
- `validate-report` 결과가 남아 있고 통과 상태다.
- human-facing 보고서가 1장 분량으로 압축되어 있다.
- human-facing 보고서가 한국어 작가/편집자-facing이며, 주장-근거 쌍을 갖춘다.
- human-facing N차 보고서가 P0/P1/P2/P3를 모두 보여주고, 각 항목의 최초 차수와 현재 상태를 누적식으로 유지한다.
- `changes.json`의 적극 편집 후보가 replace/delete/insert_before/insert_after 중 하나로 구조화되어 있다.
- 적극 편집 후보는 `episode_deep_dive.md`와 `consistency_report.md`의 근거를 참조한다.
- `consistency_report.md`의 편집자 모드 진입 가능 여부가 `가능`으로 바뀌어 있다.
- 공백 제외 4000자 미만 회차는 결락/중복/분할 오류 여부가 닫혀 있다.
- `consistency_correction_loop.md`에 각 iteration의 해결/신규/회귀/잔여 리스크가 남아 있다.
- 최종 개선 보고서는 Before/After, 개선 근거, 잔여 리스크를 축별로 분리하고, 납품 대상으로 쓰기 전 `validate-report --report`로 별도 검증한다.
- `edit_class=contextual_typo` 항목은 reading_basis와 앞뒤 문맥 근거를 갖춘다.
- 문맥형 `ⓐ` 교정은 대체 해석과 그 해석을 버린 이유가 남아 있다.
- 중복 회차, 정본 선택, 문맥형 오타처럼 논의된 핵심 이슈는 최종 보고서의 `누락 금지 이슈`에 상태가 적혀 있다.
- 편집자 모드 적용본은 plain text 후보본과 Markdown diff로 확인할 수 있다.
- 최종 원고 후보 위치가 명확하다.
- 다음 작업자가 `run_manifest.json`과 이 폴더만 보고 이어받을 수 있다.
