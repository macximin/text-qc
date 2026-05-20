# Harness Adversarial Audit 3-Pass

작품: `{{title}}` (`{{work_slug}}`)
Run: `{{run_id}}`

## 목적

이 문서는 원고가 아니라 하네스 자체를 공격적으로 점검하기 위한 내부 산출물입니다. 새 계약, 템플릿, validator, gate가 실제 운영 언어와 어긋나지 않는지 3회 검산합니다.

## Pass 1. 계약/용어 공격

- `정합성 검사`가 항상 `consistency_3x3_unit`으로 해석되는가:
- `정합성 검사 N번`이 N개의 full 3x3 unit으로 기록되는가:
- primary 3-pass, blind 3개 lane x 3-pass, total report, adversarial 3-pass가 누락 없이 연결되는가:
- human-facing 보고서와 llm-facing 내부 산출물 경계가 지켜지는가:

## Pass 2. Gate/스키마 공격

- `manual_review_submission.json` 완료 조건이 실제로 workflow 누락을 막는가:
- `submission_gate.json` blocker가 모호하지 않은가:
- n차 one-page report 선택이 manifest/최신 차수와 충돌하지 않는가:
- 오래된 run에 새 필드를 병합해도 기존 수동 메모를 지우지 않는가:

## Pass 3. 현장 오용 공격

- 자동 evidence가 본문 독해 없이 확정 이슈로 승격될 여지가 있는가:
- 세계관 전제/장르적 허세가 P0/P1 확정 오류로 잘못 유지될 여지가 있는가:
- 윤리선/도덕성 판단이 정합성·핍진성·명시적 인과 판단으로 위장되어 들어올 여지가 있는가:
- 죄책감, 기부, 피해자 지원, 제보, 독자 반감 완화, 최소 완충 같은 원작 의도 개입이 하네스 기본값으로 들어올 여지가 있는가:
- AI 작성 의심 원고의 시간 역류를 작가 의도/회상 장치로 과보호할 여지가 있는가:
- 숫자/금액/시간/지분/직함/완료 상태 carryover가 장르적 허용으로 흐려질 여지가 있는가:
- 비독자-facing 메모가 human-facing 보고서에 과노출되거나 반대로 소실될 여지가 있는가:

## 최종 판정

- 하네스 계약 보강 필요:
- 템플릿 보강 필요:
- validator 보강 필요:
- 현장 운영 메모:
