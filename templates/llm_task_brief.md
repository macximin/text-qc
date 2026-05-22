# LLM Task Brief

작품: `{{title}}` (`{{work_slug}}`)
Run: `{{run_id}}`
모드: `{{mode}}` / `{{run_kind}}`
Gate profile: `{{gate_profile}}` / `{{gate_profile_label}}`

`{{gate_profile_summary}}`

## 권위 계층

1. 코드 권위: `novel_qc_loop.protocol`의 gate profile과 하네스 계약 상수.
2. Run 권위: 이 run의 `run_manifest.json`에 기록된 `gate_profile`과 artifact 경로.
3. 제출 권위: `evidence/submission/manual_review_submission.json`의 완료 상태.
4. 납품 권위: `validate-report`를 통과한 `human-facing` 보고서와 최종 후보본.

작업 범위는 gate profile을 따른다. `delivery`가 아닌 profile에서는 full 납품 gate를 임의로 끌어오지 않는다.

## 입력

- 원본 경로: `{{source_path}}`
- 내부 NAS root: `{{internal_nas_root}}`
- 추출 텍스트: `{{extracted_text_path}}`
- 감리 큐: `{{manual_review_queue_path}}`
- 감리 제출 파일: `{{manual_review_submission_path}}`
- 장르/독자/플랫폼: `{{genre}} / {{audience}} / {{platform}}`

## 먼저 실행할 하네스

```powershell
.\scripts\novel-qc-loop.ps1 analyze-run --run-root "{{run_root}}"
```

이 명령은 작중 핍진성 후보, 날짜/시간/금액/직함/송고 위생/회차 반복/AI 티 후보를 `evidence/` 아래에 만든다. 자동 evidence는 판정이 아니라 감리 후보로만 사용한다.

감리 완료 후:

```powershell
.\scripts\novel-qc-loop.ps1 validate-submission --run-root "{{run_root}}"
.\scripts\novel-qc-loop.ps1 validate-report --run-root "{{run_root}}"
```

`validate-report`는 납품 profile에서 필수다. `proofread`, `correction`, `editorial`, `consistency` profile에서는 보고서가 필요한 경우에만 별도 산출물로 검증한다.

## 작업 원칙

- 원본 파일은 절대 덮어쓰지 않는다.
- 검수와 교정을 분리한다.
- 내부 분석은 `llm-facing/`에 둔다.
- 기호는 보존하고, 삭제가 필요하면 먼저 정합성 근거를 남긴다.
- 회차별 공백 제외 글자수는 `{{minimum_chapter_chars_no_space}}`자 이상을 강한 원칙으로 본다.
- 소제목은 무단 수정하지 않는다. 유무가 불균형하면 더 적은 쪽에 `ⓐⓐ(의견: ...)`으로 삭제 후보 또는 기존 소제목과 유사한 추가 후보를 남긴다.
- 정합성 평가는 교정 전후에 반복한다. 각 반복은 `llm-facing/consistency_correction_loop.md`에 남긴다.
- 작가/편집자에게 보여줄 보고서는 `human-facing/1차_one_page_report.md`를 1차 SSOT로 유지한다. n차 갱신은 `N차_one_page_report.md`로 만들고, 구형 `one_page_report.md`는 만들지 않는다.
- n차 보고서는 직전 차수 이후 새 항목만 쓰지 않는다. P0-P3 전체를 누적 장부로 보여주고, 해결/강등/철회/유보/작가 판단 필요 항목도 삭제하지 말고 상태만 갱신한다.
- 특정 등급이 아직 없으면 보고서에서 생략하지 말고 “현재 장부화된 P0 항목 없음”처럼 등급별 0건임을 명시한다.
- `regex`, `glob`, `rg`는 파일 찾기와 후보 수집에만 최소로 쓴다. 확정 판단은 원고 본문, 앞뒤 문단, 앞뒤 회차를 직접 읽어서 내린다.
- 문맥형 오타는 패턴 치환이 아니라 앞뒤 문맥을 읽고 판단한다.
- `정합성 검사`라고만 하면 전 회차 정합성/맥락 장부와 충돌 후보 리포트의 1개 `consistency_3x3_unit`을 뜻한다.
- 1개 `consistency_3x3_unit`은 primary 3회, blind 3개 lane x 3회, total report, total report 대상 적대적 감리 3회를 포함한다.
- `정합성 검사 3번`처럼 횟수를 지정하면 얕은 pass 3개가 아니라 `consistency_3x3_unit` 전체를 3회 반복한다.
- blind lane은 서로의 결과를 읽지 않는다. blind 결과는 `llm-facing/total_consistency_report.md`로 통합한 뒤, 그 통합본을 대상으로 적대적 감리 3회를 수행한다.
- 하네스 계약 자체가 바뀌면 `llm-facing/harness_adversarial_audit_3pass.md`로 하네스 자체를 3-pass 적대감리한다.
- 편집자 모드가 끝난 뒤에는 별도 `proofread-pass`를 실행해 오탈자, 띄어쓰기, 문장부호, 송고용 표기만 다시 훑는다.
- human-facing 보고서는 한국어로 쓰고, 모든 핵심 판단에 `주장`과 `근거`를 함께 둔다.
- 근거 없는 주장은 최종 보고서에 올리지 않는다.
- human-facing N차 보고서에는 누적 P0-P3 장부를 두고, 최초 차수, 현재 상태, 주장, 근거, 처리 방향을 함께 쓴다.
- `delivery` profile의 최종 보고서는 `validate-submission`이 통과된 뒤 `validate-report`까지 통과해야 제출 가능하다.
- P0/P1은 최종 감리에서 확정, 95% 이상 확신, 직접 근거, 미해결 반례 없음, 작중 핍진성 영향이 모두 맞는 항목만 사용한다.
- 날짜/요일/영업일 같은 외부 고증은 작중 행동·상태·인과가 깨지는 경우에만 강한 이슈로 올린다.
- 세계관 안에서 세운 제도/기술/경제 규칙은 전제로 수용한다. 맥락 없이 던진 시대 불가능 설정은 worldbuilding gap 또는 작가 판단 필요로 분리한다.
- 윤리선/도덕성 평가는 하네스의 알 바가 아니다. 원작 의도 보호가 우선이며, 정합성 근거 없이 죄책감, 기부, 피해자 지원, 제보, 독자 반감 완화, 최소 완충 같은 도덕/수용성 보강을 제안하지 않는다. 재난, 사전인지, 응징, 수익화 장면도 정합성, 핍진성, 명시적 인과, 장면 정보 전달만 본다.
- AI 작성 또는 AI 작성 의심 원고에서는 명시 표지 없는 시간 역류, 장면 접합, 중복 리캡, 정보 상태 회귀를 작가 의도나 회상 장치로 구제하지 않는다. 본문에 회상/며칠 전/다시 떠올림 같은 장치가 없으면 기본값은 AI 시간축 스플라이스 오류다.
- 웹소설식 과장과 허세는 허용하되, 숫자/금액/시간/지분/직함/완료 상태 carryover는 엄격히 본다.
- 독자-facing하지 않은 내부 메모, 정본 선택 보류, 작가 확인용 질문도 삭제하지 말고 내부 장부에 남긴다.
- 최종 원고 후보는 `final_manuscript/final_manuscript.txt`에 둔다.
- 최종 승인 패키지는 `render-final-delivery`로 만든다. 기본 납품 원고는 TXT, 기본 human-facing 보고서는 HTML이다.

## 전역 컨텍스트 스캔 우선

HWP 계열, AI 작성 의심, glossary 미정렬, 중복/화수 이상 가능성이 있는 원고는 회차별 수정 전에 전역 컨텍스트 스캔을 먼저 수행한다.

전역 스캔은 수정 지시가 아니다. 목적은 앞/뒤 모순 분포, 정본 후보, 수정 비용이 낮은 방향을 찾는 지도 작성이다. 10화 단위 검수와 본문 수정은 이 지도가 생긴 뒤 시작한다.

전역 스캔 최소 축:

- HWP 추출/회차 분할 무결성
- glossary/고유명사/실명·가명/약칭 분포
- 시간축/상대시간/사건 상태 carryover
- 돈/수익률/계좌/지분 carryover
- 중복 회차/중복 리캡/앞뒤 화 브리지
- 내부 메모/대안문/슬래시 병기/비독자-facing 흔적
- AI-slop 신호: 반복, 장면 접합, 정보 상태 회귀, 균질 리듬

## 사전 리스크 체크리스트

이 체크리스트는 확정 사실이 아니라 초기 감리 가설이다. 각 항목은 직접 근거를 확인하기 전까지 `blocked` 또는 `needs_human`으로 둔다.

- AI 작성/AI-slop 가능성: 반복 리캡, 장면 접합, 시간 역류, 정보 상태 회귀, 균질한 문장 리듬을 먼저 의심한다.
- glossary 미정렬 가능성: 고유명사, 실명/가명, 약칭/이니셜은 전역 치환하지 않는다. 직접 근거가 생길 때까지 정본 보류로 둔다.
- 정합성/중복 문제 가능성: 중복 회차, 중복 리캡, 사건 상태 회귀, 앞뒤 화 브리지 결손을 root gate로 먼저 본다.
- 인간 검수자 내부 메모 잔존 가능성: 대괄호, 괄호 대안문, 슬래시 병기, 비독자-facing 코멘트는 삭제 전 내부 메모인지 장면 장치인지 분리한다.
- 화수 표기/분할 이상 가능성: HWP 계열 추출에서는 회차 번호 누락, 중복 번호, 검수자 삭제로 인한 gap, oversized merged episode를 내용 검수 전 먼저 닫는다.

## 모드별 목표

### audit / 검수

- P0/P1/P2를 분리한다.
- 문제마다 근거를 붙인다.
- "맞냐 틀리냐"보다 독자가 어떻게 읽을지를 설명한다.
- `오늘 했다`와 `오늘 하지 않았다`, 완료된 사건의 원인 없는 회귀, 이미 안다는 정보의 재발견처럼 작중 연속성이 깨지는 항목을 최우선으로 본다.
- 소설적 허용이나 대체 해석으로 방어 가능한 항목은 P2/P3 또는 유보로 낮춘다.
- 검색으로 걸린 줄은 시작점일 뿐이다. 같은 회차의 장면 흐름과 앞뒤 회차의 상태 변화를 읽기 전에는 정합성 오류로 확정하지 않는다.

### correction / 교정

- 확정 교정은 `ⓐ`.
- 작가 판단 요청은 `ⓐⓐ`.
- 변경 근거를 남긴다.
- 삭제는 `operation=delete`, 추가는 `operation=insert_before` 또는 `operation=insert_after`로 남긴다.
- 추가 작업에서도 `find`는 빈 문자열이 아니라 삽입 위치를 잡는 앵커 문장이어야 한다.
- 문맥형 오타는 `edit_class=contextual_typo`로 두고 `reading_basis`와 앞뒤 문맥 근거를 남긴다.
- 문맥형 오타를 `ⓐ`로 확정하려면 `confidence_percent`가 95 이상이어야 한다.
- 문맥형 `ⓐ`에는 가능한 대체 해석과 그 해석을 버린 이유를 함께 남긴다.

### editor / 편집

- 교정자가 아니라 매우 적극적인 편집자로 작업한다.
- `delivery`/`consistency` profile에서는 `adversarial_audit_3pass`, `episode_deep_dive`, `consistency_report` 이후에만 실행한다.
- `editorial` profile에서는 `manual_review_queue.jsonl`의 `required_for_gate=true` 항목과 `consistency_report`의 진입 판정을 우선한다.
- 작품의 기대 품질이 AI-slop일 수 있음을 전제로, 중복 문장, 단조로운 문장 리듬, 추상 감정어 반복, 빠진 인과 브리지를 적극적으로 고친다.
- 필요하면 문장 단위 치환, 삭제, 추가를 모두 제안한다.
- 적극 편집은 기본적으로 `ⓐⓐ`로 올리고, 작가 승인 전 최종 원고에 확정 반영하지 않는다.
- 편집자 모드에서는 HWP/HWPX를 기본 작업물로 쓰지 않고, `apply-changes-text`로 텍스트 후보본과 Markdown diff를 만든다.
- 문맥형 오타 후보는 `render-change-contexts`로 주변 문맥을 뽑은 뒤 판단한다.
- 세부 기준은 `llm-facing/editorial_pass_brief.md`를 따른다.

### full / 전체

1. primary 전 회차 정합성/맥락 장부 + 충돌 후보 3회
2. blind_agent_1/2/3이 서로 블라인드인 상태로 각 3회
3. `llm-facing/total_consistency_report.md` 통합
4. 통합 리포트 대상 적대적 감리 3회
5. 화별 수동 딥다이브
6. 편집자 모드 윤문/정합성 편집안
7. 정합성 평가 -> 교정 -> 정합성 재평가 반복 루프
8. 표면 교정 루프
9. `human-facing/1차_one_page_report.md`와 최종 개선 보고서
10. 최종 원고 후보
11. `render-final-delivery`로 TXT 원고와 HTML 최종 보고서 패키징

위 1-4번이 1개 `consistency_3x3_unit`입니다. 사용자가 "정합성 검사 3번"이라고 말하면 1-4번을 세 번 수행하고, `manual_review_submission.json`의 `consistency_repetition_contract.requested_unit_count`를 3으로 둡니다.

## 기본 지표

- 전체 글자 수: {{char_count}}
- 공백 제외 글자 수: {{chars_no_space}}
- 회차 수: {{chapter_count}}
- 회차 최소 기준: 공백 제외 {{minimum_chapter_chars_no_space}}자
- 기준 미달 회차: {{under_min_chapter_chars_no_space_summary}}
- 120자 이상 줄: {{long_lines_120}}
- 200자 이상 줄: {{long_lines_200}}
