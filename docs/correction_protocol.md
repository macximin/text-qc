# 교정 프로토콜

이 문서는 `업무자동화_ssot/교정`에서 쓰던 실전 규칙을 text-qc에 맞게 일반화한 것입니다.

## 두 종류의 교정

### 확정 교정 `ⓐ`

명백한 오류입니다.

- 오탈자
- 띄어쓰기
- 조사 오류
- 문장부호 오류
- 명백한 단어 오기

### 작가 판단 `ⓐⓐ`

의도일 수 있습니다.

- 인물 말투
- 고유명사
- 문체 선택
- 세계관 용어
- 논쟁 가능한 표현

## 적극 편집자 모드

편집자 모드는 맞춤법 교정이 아니라 문장 단위 윤문과 정합성 보강입니다. 작품의 기대 품질이 AI-slop일 수 있음을 전제로 보고, 반복 문장, 비슷한 반응, 추상 감정어 남발, 단조로운 문장 리듬, 빠진 인과 브리지를 적극적으로 고칩니다.

허용 작업:

- `replace`: 문장 또는 문단 일부 치환
- `delete`: 중복, 군더더기, 의미 없는 재방송 삭제
- `insert_before`: 앵커 앞에 누락된 주어, 정황, 브리지 추가
- `insert_after`: 앵커 뒤에 누락된 반응, 인과, 연결 문장 추가

추가는 빈 위치에 넣지 않습니다. `find`에는 실제 원문에서 찾을 수 있는 앵커 문장을 넣고, `replace`에는 추가할 문장을 넣습니다.

적극 편집은 기본적으로 `ⓐⓐ`입니다. 의미와 말투를 거의 건드리지 않는 확실한 정리만 `ⓐ`로 둡니다.

편집자 모드에서는 HWP/HWPX 파란줄을 기본 산출물로 쓰지 않습니다. `changes.json`을 plain text에 적용해 `final_manuscript/editorial_candidate.txt`와 `corrections/editorial_diff.md`를 만들고, 그 diff를 보고 승인/반려합니다.

`edit_class=ai_slop_cleanup`은 사람이 바로 알 수 있게 `reason`과 HWPX 의견에 `AI-slop 신호:`를 직접 표시합니다. 반복 표현, 추상 강도어, 빈 감탄, 균질한 문장 리듬 중 무엇을 줄이는지 밝히고, 단순히 "압축", "덜어냄"으로만 쓰지 않습니다.

`insert_before`/`insert_after`의 `find`는 가능하면 회차 제목이나 소제목이 아니라 실제 본문 문장을 앵커로 잡습니다. 불가피하게 회차 헤더를 앵커로 잡은 경우에도 중간 검토용 HWPX는 `ⓐⓐ` 의견을 헤더 줄에 붙이지 않고 별도 문단으로 분리합니다.

```powershell
.\scripts\novel-qc-loop.ps1 render-marked-manuscript-hwpx --run-root "workspace\{work}\runs\{run_id}" --loop-label loop_01
.\scripts\novel-qc-loop.ps1 apply-changes-text --run-root "workspace\{work}\runs\{run_id}"
.\scripts\novel-qc-loop.ps1 apply-changes-text --run-root "workspace\{work}\runs\{run_id}" --accept-aa
```

`render-marked-manuscript-hwpx`는 루프 중간 확인용 산출물입니다. 원문 순서 그대로 `ⓐ{원문|수정}`과 `ⓐⓐ(의견: ... / 제안: ...)`을 삽입한 검토본이며, 파란색은 제안문이나 의견을 뜻합니다. `ⓐⓐ`는 모두 의견 메모로만 표시하고 원문을 치환하지 않습니다. 이 파일도 최종 원고 적용본은 아닙니다.

표식 카운트는 `ⓐ` 교정과 `ⓐⓐ` 판단을 분리합니다. `ⓐ{` 단순 문자열 카운트는 `ⓐⓐ{...}`를 오인할 수 있으므로 금지하고, 렌더 명령의 `marker_counts`와 `rendered_marker_counts`를 기준으로 보고합니다.

동일한 `find`를 여러 occurrence로 나누어 적용하는 경우, `apply-changes-text`는 모든 anchor를 원본 좌표에서 먼저 해석한 뒤 뒤쪽 변경부터 적용합니다. 따라서 occurrence 1을 먼저 치환해 occurrence 2가 사라지는 순차 적용 오류를 피합니다.

적용 뒤에는 다시 정합성 평가를 합니다. 해결된 항목, 새로 생긴 항목, 회귀 항목, 잔여 리스크를 `llm-facing/consistency_correction_loop.md`에 남기고, 만족 기준을 통과한 뒤에만 최종 개선 보고서에서 해결 완료로 씁니다.

최종 개선 보고서에는 루프별 개선 이력과 누락 금지 이슈를 남깁니다. 중복 회차, 정본 선택, 문맥형 오타, AI-slop 정리처럼 작업 중 사람이 판단한 핵심 항목은 해결/보류/작가 판단 상태가 보고서에 반드시 보여야 합니다.

## 표면 교정 루프

편집자 모드가 끝난 후보본은 곧바로 최종고로 보지 않습니다. 별도 `proofread-pass`를 열어 오탈자, 띄어쓰기, 문장부호, 송고용 표기만 다시 읽습니다.

표면 교정 루프의 범위:

- 명백한 오탈자: `피난 주 -> 피난 중`, `숙식간 -> 순식간`, `정도록 -> 정도로`, `고았다 -> 고왔다`.
- 명백한 띄어쓰기: `말하지마요 -> 말하지 마요`, `책임의무게 -> 책임의 무게`.
- 송고용 표기: `거 같다 -> 것 같다`, 직선 따옴표/세 점 대신 `“”`, `‘’`, `…`.
- 저위험 문장 다듬기: 이중 피동, 같은 문장 안의 불필요한 단어 반복.

허용 표기와 문체 판단이 섞이는 항목은 스타일 시트가 없으면 자동 일괄 치환하지 않습니다. `해주다`, `굳어있다`, `추천해주세요`처럼 붙여 쓰기 허용이나 대사 리듬이 얽힌 항목은 별도 스타일 루프나 `ⓐⓐ` 판단으로 남깁니다.

산출물은 편집자 모드와 분리합니다. 예: `corrections/loop_06_proofread_changes.json`, `corrections/loop_06_proofread_diff.md`, `final_manuscript/loop_06_proofread_candidate.txt`, `human-facing/loop_06_proofread_marked_manuscript.hwpx`.

## 문맥형 오타

문맥형 오타는 정규식이나 단어 목록만으로 잡지 않습니다. 해당 문장 앞뒤를 읽고, 장면의 물건, 행동 연쇄, 호칭, 지시 대상, 직전 상태와 맞지 않는 단어를 후보로 올립니다.

`changes.json`에서는 `edit_class=contextual_typo`를 사용합니다.

필수:

- `reading_basis`: 앞뒤 문맥상 왜 오기인지.
- `context_before` / `context_after` / `context_window` / `evidence_snippet` 중 하나 이상.
- `reason`: 변경 이유.
- `ⓐ` 확정 교정이면 `alternative_interpretation`, `counter_evidence`, `rejected_interpretation`, `rejection_basis` 중 하나 이상. 즉, 가능한 다른 해석을 확인했고 왜 버렸는지 남깁니다.

문맥형 오타를 `ⓐ`로 확정하려면 `confidence_percent`가 95 이상이어야 합니다. 확신이 부족하거나 작가 의도 가능성이 있으면 `ⓐⓐ`로 둡니다.

예: `11자의 틈새`는 두 갈래 펜촉이 숫자 11처럼 보인다는 의도 가능성이 있습니다. 그러나 수식 대상이 `펜촉`이 아니라 `틈새`이고, 주변 문맥이 슬릿/모세관/이리듐 팁 정렬이면 `일자형 틈새`가 더 자연스럽습니다. 이런 경우 보고서에는 "숫자 11이 틀림"으로 단정하지 말고, "대체 해석은 검토했으나 수식 대상 기준으로 일자형이 안전하다"까지 씁니다.

```powershell
.\scripts\novel-qc-loop.ps1 render-change-contexts --run-root "workspace\{work}\runs\{run_id}"
.\scripts\novel-qc-loop.ps1 render-change-contexts --run-root "workspace\{work}\runs\{run_id}" --contextual-only
```

## 원칙

- 원본은 덮어쓰지 않는다.
- 대화문 말투는 함부로 고치지 않는다.
- 고유명사는 첫 등장 기준으로 본다.
- 소제목은 함부로 고치지 않는다. 소제목 유무가 회차마다 불균형하면 더 적은 쪽에만 `ⓐⓐ(의견: ...)`을 붙여 삭제 후보 또는 기존 소제목과 유사한 추가 후보로 남긴다.
- 일관성 문제는 바로 확정하지 말고 `ⓐⓐ`로 올린다.
- 작가 승인 전 `ⓐⓐ`는 최종 반영하지 않는다.
- 없는 설정, 없는 감정선, 없는 사건을 편집자가 새로 발명하지 않는다.

## HWPX

HWPX는 두 용도로만 사용합니다.

- 루프 중간 검토본: `render-marked-manuscript-hwpx`로 `human-facing/*_marked_manuscript.hwpx`를 생성합니다. 이는 원문형 기호 적용본이며 최종 원고 적용본이 아닙니다.
- 교정 납품/표시: 필요할 때만 `scripts/apply_blue.py`로 파란색 변경 표시를 적용합니다.

루프 중간 검토본의 기본 편집용지는 A4 세로입니다. 여백은 위쪽 20mm, 머리말 15mm, 왼쪽 30mm, 오른쪽 30mm, 제본 0mm, 꼬리말 15mm, 아래쪽 15mm로 둡니다.

문단 모양은 양쪽 정렬, 왼쪽/오른쪽 여백 0pt, 첫 줄 보통, 줄 간격 160%, 문단 위/아래 0pt, 편집 용지 줄 격자 사용, 한글 줄 나눔 글자 단위, 영어 줄 나눔 단어 단위를 기본값으로 둡니다. 글자 모양은 20pt, 함초롬바탕, 장평 100%, 자간 0%, 검정색을 기본값으로 두고 파란 제안/의견만 `#0000FF`로 표시합니다.

생성 HWPX의 내부 XML은 한글에서 저장한 네이티브 HWPX 본문 스타일을 기준으로 맞춥니다. A4 수치, `pagePr`, 본문 `borderFill`, 기본 글꼴 테이블, 20pt 함초롬바탕 참조 ID가 한글 생성본과 다르면 같은 dialog 값이어도 화면 줄배치가 달라질 수 있습니다. 루프 중간 검토본은 `hp:linesegarray`를 생성하지 않고 한글 렌더러가 문단을 재조판하게 둡니다. `linesegarray`는 문단 내용이 아니라 줄 위치 캐시에 가까우므로 하네스가 추정값을 쓰면 양쪽 정렬에서 단어 사이 공백이 과하게 벌어질 수 있습니다.

구버전 `.hwp`는 intake에서 `hwp5txt`로 텍스트 추출까지 지원합니다. 다만 직접 XML 조작이나 파란색 변경 표시는 어렵기 때문에 납품용 표시가 필요하면 가능하면 `.hwpx`로 변환한 뒤 처리합니다.
