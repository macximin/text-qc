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
- 화당 기준 분량을 넘는가
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
- 장르 기대와 독자 납득
- 독자가 납득할 근거

Pass 3: AI 티/문체

- 과잉 비유
- 과잉 감탄
- 반복 표현
- 불필요한 거창함

완료 후 `evidence/submission/manual_review_submission.json`을 채우고 검증합니다.

```powershell
.\scripts\novel-qc-loop.ps1 validate-submission --run-root "workspace\{work}\runs\{run_id}"
```

## 4. 교정안 작성

교정은 검수와 분리합니다.

- 확정 교정: `ⓐ`
- 작가 판단 요청: `ⓐⓐ`
- 변경 근거는 `corrections/changes.json`에 남깁니다.

## 5. human-facing 보고서

내부 감리 결과를 작가/편집자가 읽을 수 있게 바꿉니다.

- "틀렸다"보다 "독자가 이렇게 읽을 수 있다"를 우선합니다.
- 문제, 근거, 리스크, 수정 방향을 분리합니다.
- 가능한 경우 비유를 붙여 체감되게 설명합니다.

## 6. export

필요에 따라 Markdown, HTML, PDF, HWPX를 생성합니다.

HWPX 교정 표시가 필요하면 `scripts/apply_blue.py`를 사용합니다.
