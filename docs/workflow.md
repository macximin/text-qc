# 표준 작업 흐름

## 0. 작품 등록

```powershell
.\scripts\novel-qc-loop.ps1 init-work `
  --slug canaria `
  --title "카나리아" `
  --genre "장르명" `
  --audience "대상 독자" `
  --platform "플랫폼명" `
  --source "C:\path\to\origin"
```

## 1. 원고 수집/추출

원본 HWP/HWPX/PDF/TXT는 `workspace/{work}/inputs`에 둘 수 있지만, git에는 올리지 않습니다.

추출 텍스트는 `workspace/{work}/extracted`에 저장합니다.

권장 방식은 intake harness입니다.

```powershell
.\scripts\novel-qc-loop.ps1 intake --input "C:\path\to\manuscript.txt" --mode full --analyze
```

`--mode`는 기본 gate profile을 정합니다. 필요하면 `--gate-profile`로 명시합니다.

- `proofread`: 표면 교정/송고 위생만 닫습니다.
- `correction`: `ⓐ`/`ⓐⓐ` 교정안과 마커 검수본을 닫습니다.
- `editorial`: 적극 편집 후보에 필요한 최소 정합성 장부를 닫습니다.
- `consistency`: full consistency unit을 닫되 납품 보고서는 별도입니다.
- `delivery`: 기존 full 납품 gate입니다.

권위 순서는 `protocol.py` 코드 정의 -> `run_manifest.json`의 `gate_profile` -> `manual_review_submission.json` -> `human-facing` 납품 보고서입니다.

초기 원고함 일괄 처리:

```powershell
.\scripts\novel-qc-loop.ps1 intake-inbox --mode full --analyze
```

## 2. 1차 전역 감리

목표는 빠르게 치명상을 찾는 것입니다.

먼저 evidence를 생성합니다.

```powershell
.\scripts\novel-qc-loop.ps1 analyze-run --run-root "workspace\{work}\runs\{run_id}"
```

- 말이 되는가
- 시간/장소/인물/수치가 깨지지 않았는가
- 화당 기준 분량, 즉 공백 제외 4000자를 넘는가
- 장르 톤을 크게 해치는 표현이 있는가
- 독자가 억지 전개라고 느낄 지점이 있는가

## 3. 적대적 감리 3회

Pass 1: 구조/연속성

- 앞뒤 화 연결
- 인물 동기
- 시간 점프
- 정보 공개 순서

Pass 2: 독자-facing

- 모바일 호흡
- 대화 밀도
- 장르 기대를 해치지 않는 명시적 인과
- 독자가 앞뒤 정보를 따라갈 수 있는 근거

Pass 3: AI 티/문체

- 과잉 비유
- 과잉 감탄
- 반복 표현
- 불필요한 거창함

완료 후 `evidence/submission/manual_review_submission.json`을 채우고 검증합니다. `delivery`와 `consistency` profile의 완료 상태는 primary 정합성/맥락 장부 3회, blind 3개 lane x 3회, `llm-facing/total_consistency_report.md`, 통합본 대상 적대적 감리 3회가 모두 채워져야 합니다. 이 전체 묶음이 1개 `consistency_3x3_unit`이고, `정합성 검사 3번`은 이 묶음을 세 번 반복한다는 뜻입니다.

```powershell
.\scripts\novel-qc-loop.ps1 validate-submission --run-root "workspace\{work}\runs\{run_id}"
```

## 4. 교정안 작성과 반복 재평가

교정은 검수와 분리합니다.

- 확정 교정: `ⓐ`
- 작가 판단 요청: `ⓐⓐ`
- 변경 근거는 `corrections/changes.json`에 남깁니다.
- 적극 편집자 모드에서는 `replace`, `delete`, `insert_before`, `insert_after`로 문장 단위 윤문과 브리지 추가까지 구조화합니다.
- 추가 작업의 `find`는 빈 값이 아니라 실제 원문 위치를 잡는 앵커입니다.
- 편집자 모드 적용본은 HWP/HWPX가 아니라 `apply-changes-text`로 plain text 후보본과 Markdown diff를 만듭니다.
- 중간 확인용 판단본은 `render-marked-manuscript-md`로 원문 순서 그대로 기호를 삽입한 MD 검수본을 만듭니다. 한글 검토나 납품 요구가 있으면 `render-marked-manuscript-hwpx`도 함께 만듭니다.
- `delivery`/`consistency` profile의 편집자 모드는 primary 정합성 3-pass, blind 3개 lane x 3-pass, total 정합성 리포트, 적대적 감리 3-pass, 화별 수동 딥다이브, 정합성 리포트 이후에만 실행합니다. `editorial` profile은 `manual_review_queue.jsonl`의 `required_for_gate=true` 항목과 `consistency_report` 진입 판정을 따릅니다.
- 세계관 안에서 세운 제도/기술/경제 규칙은 전제로 수용하고, 맥락 없이 던진 시대 불가능 설정은 작가 판단 또는 전제 보강으로 분리합니다.
- 웹소설식 허세와 과장은 결함이 아니며, 숫자/금액/시간/지분/직함/완료 상태 carryover는 엄격히 봅니다.
- 중복 회차 정본 선택에서는 공백 제외 4000자 이상을 강한 원칙으로 삼고, 삭제 후 남는 회차가 4000자 미만이면 삭제 확정 대신 결락/추가/보류로 둡니다.
- 문맥형 오타는 `edit_class=contextual_typo`로 올리고, `reading_basis`와 앞뒤 문맥 근거를 남깁니다.
- 교정 적용 후 같은 회차와 앞뒤 회차를 다시 읽고, 해결/신규/회귀/잔여 리스크를 분리합니다.
- 이 반복은 만족 기준을 통과할 때까지 `llm-facing/consistency_correction_loop.md`에 누적합니다.

```powershell
.\scripts\novel-qc-loop.ps1 render-change-contexts --run-root "workspace\{work}\runs\{run_id}" --contextual-only
.\scripts\novel-qc-loop.ps1 render-marked-manuscript-md --run-root "workspace\{work}\runs\{run_id}" --loop-label loop_01
.\scripts\novel-qc-loop.ps1 render-marked-manuscript-hwpx --run-root "workspace\{work}\runs\{run_id}" --loop-label loop_01
.\scripts\novel-qc-loop.ps1 apply-changes-text --run-root "workspace\{work}\runs\{run_id}"
.\scripts\novel-qc-loop.ps1 apply-changes-text --run-root "workspace\{work}\runs\{run_id}" --accept-aa
```

## 5. human-facing 보고서와 최종 개선 보고서

내부 감리 결과를 작가/편집자가 읽을 수 있게 바꿉니다.

- "틀렸다"보다 "독자가 이렇게 읽을 수 있다"를 우선합니다.
- 한국어 작가/편집자-facing 문장으로 씁니다.
- 모든 핵심 판단은 `주장`과 `근거`를 함께 씁니다.
- 문제, 근거, 리스크, 수정 방향을 분리합니다.
- 원문 위치, 원문 인용, 수치, 반복 횟수, 앞뒤 문맥 중 하나 이상을 근거로 남깁니다.
- 가능한 경우 비유를 붙여 체감되게 설명합니다.
- 최종 개선 보고서는 Before/After, 개선 근거, 잔여 리스크, 작가 판단 항목을 분리합니다.

최종 전달 전에는 보고서도 검증합니다.

```powershell
.\scripts\novel-qc-loop.ps1 validate-report --run-root "workspace\{work}\runs\{run_id}"
.\scripts\novel-qc-loop.ps1 validate-report --report "workspace\{work}\runs\{run_id}\human-facing\final_improvement_report.md"
```

## 6. export

최종 승인 후 기본 납품 산출물은 TXT 원고와 human-facing HTML 보고서입니다. 최종 보고서는 기본 `closing_full` 누적 마감 보고서이며, 정책 판정, glossary SSOT, AI-slop 표면, hold/watchlist 분리, 검증/재봉인 상태를 함께 표시합니다.

```powershell
.\scripts\novel-qc-loop.ps1 scan-ai-slop --input "workspace\{work}\runs\{run_id}\final_manuscript\final_manuscript.txt" --output "workspace\{work}\runs\{run_id}\consistency_integrity\ai_slop_scan.jsonl"
.\scripts\novel-qc-loop.ps1 render-final-delivery --run-root "workspace\{work}\runs\{run_id}" --version v1
```

기본 출력은 `final_delivery/v1_final_approved_package/`에 생성됩니다. 패키지에는 최종 원고 TXT, 두괄식 HTML 보고서, `delivery_manifest.json`이 포함됩니다.

필요에 따라 추가 Markdown, PDF, HWPX를 생성합니다.

HWPX 교정 표시가 필요하면 `scripts/apply_blue.py`를 사용합니다. 편집자 모드의 기본 export는 text/Markdown diff입니다.
