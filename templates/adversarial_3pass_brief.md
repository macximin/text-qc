# 원고 적대적 3-pass 감리 브리프

작품: `{{title}}` (`{{work_slug}}`)
Run: `{{run_id}}`
모드: `{{mode}}`

## 미션

- `좋아 보인다`가 아니라 `어디가 틀릴 수 있는지 끝까지 의심하는 감리자`로 행동한다.
- 목표는 칭찬이 아니라 시간축 오류, 숫자 오류, 인물/직함 drift, 사건 상태 회귀, 캐릭터성 붕괴, 송고 위생 문제를 잡는 것이다.
- `문제 없음`은 기본값이 아니다. 반대로 가정하고 깨보는 것이 기본값이다.

## 필수 입력물

- 추출 텍스트: `{{extracted_text_path}}`
- inspection: `evidence/inspection.json`
- facts: `evidence/facts/`
- review candidates: `evidence/review/`
- submission gate: `evidence/submission/submission_gate.json`

## 먼저 실행할 것

```powershell
.\scripts\novel-qc-loop.ps1 analyze-run --run-root "{{run_root}}"
```

## Pass 1. 표면 팩트 감리

- 날짜, 시간, 금액, 지분율, 나이, 직함, 관계 호칭을 먼저 수집한다.
- 각 이슈는 최소 `회차`, `줄번호`, `증거 문장`, `왜 문제인지`, `수정 방향`을 남긴다.
- 사소해 보여도 일단 모은다. 나중에 지우더라도 처음엔 넓게 잡는다.
- `manual_review_queue.jsonl`의 축을 빠뜨리지 않는다.

## Pass 2. 적대적 반례 감리

- Pass 1에서 잡은 모든 항목에 대해 반대 증거를 찾는다.
- 시간축이면 앞뒤 회차를 다시 뒤져 실제 오류인지, 고의적 플래시백인지 확인한다.
- 숫자면 동일 수치가 다른 장면에서 다시 어떻게 쓰이는지 확인한다.
- 인물/직함이면 같은 이름이 다른 직함으로 불리는 장면을 모아 실제 변화인지 drift인지 판정한다.
- replay 후보면 lawful repetition과 lazy replay를 구분한다.

## Pass 3. 폐쇄 감리

- 앞선 두 패스에서 `문제 없음` 처리한 항목을 다시 의심한다.
- 최종 산출물에는 `확정 이슈`, `유보 이슈`, `근거 부족으로 보류한 의심점`을 분리한다.
- 최종 보고 전 `정말 수정 가치가 있나`를 다시 검산한다.
- 완료 후 `manual_review_submission.json`의 각 축과 pass 상태를 채운다.

```powershell
.\scripts\novel-qc-loop.ps1 validate-submission --run-root "{{run_root}}"
```

## FAIL 조건

- 회차/줄번호 없는 지적.
- 반례 탐색 없이 단정한 지적.
- 동일 이름/수치 재등장 확인 없이 내린 전역 결론.
- `문제 없음`인데 어떤 축을 확인했는지 목록이 없는 보고.
- 자동 evidence를 복붙하고 끝내는 보고.

## 최소 산출물

- `llm-facing/global_audit_raw.md`
- `llm-facing/adversarial_audit_3pass.md`
- `evidence/submission/manual_review_submission.json`
- `human-facing/one_page_report.md`
