# Harness Efficiency Gate Profile Audit - 2026-05-21

## 목표

하네스가 모든 작업에 full 납품 gate를 요구해 과도하게 느려지는 문제를 줄이고, 권위 순서를 `protocol.py` -> `run_manifest.json` -> `manual_review_submission.json` -> `human-facing` 납품 보고서로 정렬한다.

## Pass 1. 문서/템플릿 모순 공격

- 공격 질문: `editorial`, `correction`, `proofread`처럼 가벼운 profile에서도 오래된 문서 문장이 primary/blind/total/adversarial full gate를 강제하지 않는가.
- 발견: `intake_harness.md`, `harness_contract.md`, `workflow.md`, LLM 템플릿 일부가 여전히 "편집자 모드=full gate 이후"처럼 읽혔다.
- 조치: `gate_profile`별 권위를 문서와 템플릿에 명시하고, full gate 언어는 `delivery`/`consistency` profile로 한정했다.
- 판정: 통과. `required_for_gate=true`와 `manual_review_submission.json`의 workflow requirements가 profile별 필수 범위를 정한다.

## Pass 2. 가벼운 profile 큐 공격

- 공격 질문: `correction`/`proofread` profile은 full pass를 요구하지 않으므로 큐가 전부 skipped처럼 보이지 않는가.
- 발견: primary/blind/total/adversarial 행은 skip 처리됐지만, profile 필수 축을 수행하라는 양성 큐 행이 없었다.
- 조치: `profile_axis_review` 행을 추가해 가벼운 profile에서도 실제 필수 축 점검을 큐에 노출했다.
- 판정: 통과. `correction` profile 큐는 `profile_axis_review`만 필수이고 primary/blind는 skipped로 표시된다.

## Pass 3. 실행 경로/납품 blocker 공격

- 공격 질문: `correction --analyze` 실행 시 최종 보고서 부재가 여전히 납품 blocker로 들어오는가.
- 실행 확인: `intake --mode correction --analyze` 결과에서 intake/analyze/manifest 모두 `gate_profile=correction`이었다.
- 실행 확인: `submission_gate.json` blocker는 `chapter_under_minimum_chars`, `manual_review_axes_not_complete`, `manual_review_not_complete`만 남고, `human_report_missing`류 납품 blocker는 생기지 않았다.
- 추가 조치: `validate-report --run-root`도 `manual_review_submission.json`의 `require_delivery_report`가 true일 때만 수동감리 완료를 납품 조건으로 묶는다.
- 판정: 통과. 비납품 profile은 보고서가 있을 때만 보고서 검증을 참고하며, 납품 보고서를 필수 blocker로 끌어오지 않는다.

## 결론

효율화는 full gate를 제거한 것이 아니라 profile 계층으로 격리한 것이다. `delivery` profile은 기존 납품 안전성을 유지하고, `consistency`는 정합성 감리만 닫고, `editorial`/`correction`/`proofread`는 필요한 축만 빠르게 닫는다. 새 run의 실제 권위는 항상 `run_manifest.json`의 `gate_profile`이다.
