# 다작품 루프 아키텍처

## 핵심 분리

`novel-qc-loop`는 원고 보관소가 아니라 원고 검수 루프입니다.

- repo tracked: 코드, 템플릿, 스키마, 운영 문서
- workspace ignored: 작품 원고, 추출 텍스트, 리포트 초안, 교정안, export

이 분리를 유지해야 여러 작품을 동시에 넣어도 저작물/업무 데이터가 repo에 섞이지 않습니다.

## 계층

```text
workspace/
  {work_slug}/
    manifest.json
    inputs/
    extracted/
    runs/
      {yyyymmdd_hhmmss}__{kind}/
        run_manifest.json
        evidence/
        draft_reports/
        final_reports/
        exports/
    reports/
    corrections/
    exports/
    archive/
```

## Work Manifest

작품 단위의 고정 정보입니다.

- `slug`: 파일시스템용 작품 ID
- `title`: 작품명
- `author`: 작가명 또는 내부 식별자
- `genre`: 현대판타지, 무협, 로맨스판타지 등
- `audience`: 3040, 남성향, 여성향 등
- `platform`: 네이버 시리즈, 카카오페이지, 문피아 등
- `source_path`: 원본 위치. 본문을 직접 저장하지 않음
- `notes`: 운영 메모

## Run Manifest

검수 1회 실행 단위의 기록입니다.

- `global-audit`: 원고 전역의 P0/P1/P2 문제 탐색
- `adversarial-audit`: 독자/심사자 관점의 적대적 감리
- `correction-pass`: 교정안 생성과 승인 추적
- `editorial-pass`: 적극 편집자 모드. 문장 단위 윤문, 중복 삭제, 브리지 추가, AI 티 완화. 기본 산출물은 plain text 후보본과 Markdown diff.
- `export-pass`: PDF/HWPX/HTML export 검증

## Report 계층

리포트는 최소 3층으로 나눕니다.

1. `raw_audit`: 내부 판정. 날것의 문제, 근거, 라인, 심각도.
2. `human_facing`: 작가/편집자에게 전달 가능한 설명형 보고서.
3. `submission_ready`: 최종 송고 전 체크리스트와 잔여 리스크.

## Severity

- P0: 송고 차단. 세계관/인물/시간/수치가 깨져 독자가 즉시 이탈할 문제.
- P1: 높은 확률로 독자 신뢰를 깎는 문제. 장르 톤, 전개 억지, 주요 인물 동기 훼손.
- P2: 폴리싱. 문장 호흡, AI 티, 반복 표현, 모바일 가독성, 리포트 친절도.

P2라도 작품 전체에서 반복되면 제품 개선 이슈로 승격합니다.

## 다작품 운영 원칙

- 작품별 manifest를 먼저 만든 뒤 run을 시작합니다.
- 한 run은 한 작품만 다룹니다.
- 작품 간 표현/문제 패턴은 `docs/patterns.md` 같은 공통 문서로 승격합니다.
- 원고 원본은 절대 자동 덮어쓰기하지 않습니다.
- 교정안은 `corrections/changes.json`처럼 변경 근거와 승인 상태를 남깁니다.
