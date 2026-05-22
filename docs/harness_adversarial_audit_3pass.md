# Harness Adversarial Audit 3-Pass

대상: 최종 납품 하네스 개선분

범위:

- 기본 산출물 TXT / HTML 누적 마감 보고서
- `scan-ai-slop` 스캐너
- `render-final-delivery --report-density closing_full`
- glossary SSOT 요약
- `blocking_hold` / `policy_watchlist` / `style_watchlist` 분리
- 이전 final delivery 해시 비교와 재봉인 표시

## 1차: API/회귀 감리

판정: blocking 없음.

확인:

- 기존 `render-final-delivery` 호출은 `--report-density`를 생략해도 `closing_full` 기본값으로 동작한다.
- `FinalDeliveryResult`는 새 필드를 추가하지만 기존 핵심 필드(`manuscript_txt_path`, `human_report_html_path`, `manifest_path`, `source_final_delivery_match`)를 유지한다.
- QC JSONL status vocabulary에 `blocking_hold`, `policy_watchlist`, `style_watchlist`, `reseal_required`, `sealed`가 추가되어 새 ledger가 validate에서 막히지 않는다.
- `scan-ai-slop`은 읽기 중심 명령이며, `--output`을 줄 때만 JSONL 예시 파일을 쓴다.

잔여 리스크:

- 하네스가 설치 패키지로 실행되지 않은 로컬 환경에서는 `python -m novel_qc_loop.cli`에 `PYTHONPATH=src`가 필요하다. 기존 `scripts/novel-qc-loop.ps1` 경로를 쓰면 이 문제는 우회된다.

## 2차: 보고서 진실성/과장 감리

판정: blocking 없음.

확인:

- 최종 보고서는 `blocking_hold`와 watchlist를 분리해, 보존 정책이나 판단 유보를 출고 차단처럼 과장하지 않는다.
- AI-slop 스캐너는 "확정 오류"가 아니라 "후보 표면"으로 기록한다. 보고서 문구도 명백한 후보는 수정, 맥락 의존 후보는 watchlist로 둔다.
- glossary SSOT가 없을 때는 "연결된 glossary JSONL이 없다"고 표시하며, 없는 근거를 만들어내지 않는다.
- 이전 패키지와 현재 TXT 해시가 다르면 stale로 표시하지만, 현재 패키지는 새 manifest와 함께 다시 봉인된 것으로 표시한다.

잔여 리스크:

- AI-slop 패턴은 보수적 후보 탐지다. 작중 문서/대사/시스템 UI 표면까지 자동 삭제하면 안 되며, 회차별 문맥 확인이 필요하다.

## 3차: 운영 흐름/누락 감리

판정: blocking 없음.

확인:

- 하네스 문서와 템플릿에 전역 스캔 우선, AI-slop 스캔, 최종 TXT/HTML 산출물, `closing_full` 보고서 기본값을 반영했다.
- final delivery manifest에 report scope/density, hold summary, AI-slop summary, glossary summary, reseal summary가 함께 남는다.
- 테스트는 최종 보고서 기본 형식, AI-slop 탐지, hold/watchlist 분리, previous package stale, glossary 렌더링을 고정한다.
- 전체 테스트 결과는 `30 passed`다.

잔여 리스크:

- 실제 대형 원고에서 glossary JSONL 스키마가 다양하면 일부 필드가 요약에서 비어 보일 수 있다. canonical/canon/term, policy/verdict/status, aliases/allowed_surface_forms 계열은 처리하지만 완전히 다른 키 이름은 별도 매핑이 필요하다.

## 최종 판정

하네스 개선분은 현재 테스트 기준 통과. 최종 납품 기본 흐름은 TXT 원고, HTML 누적 마감 보고서, JSON manifest, AI-slop 후보 스캔, glossary/hold/reseal 요약을 포함하도록 승격됐다.
