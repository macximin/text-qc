# LLM-facing Handoff Checklist

## 반드시 남길 산출물

- `llm-facing/global_audit_raw.md`: 내부용 원문 기반 검수.
- `llm-facing/adversarial_audit_3pass.md`: 적대적 감리 3회.
- `llm-facing/correction_plan.md`: 교정안과 우선순위.
- `human-facing/one_page_report.md`: 작가/편집자-facing 1장 보고서.
- `final_manuscript/final_manuscript.txt`: 최종 원고 후보.

## 금지

- 원본 파일 덮어쓰기.
- 근거 없는 문제 제기.
- human-facing 보고서에 내부 프롬프트, 모델명, 실행 로그 노출.
- `ⓐⓐ` 항목을 작가 승인 없이 확정 교정처럼 처리.

## 완료 조건

- P0/P1/P2가 분리되어 있다.
- human-facing 보고서가 1장 분량으로 압축되어 있다.
- 최종 원고 후보 위치가 명확하다.
- 다음 작업자가 `run_manifest.json`과 이 폴더만 보고 이어받을 수 있다.

