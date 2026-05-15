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

```powershell
.\scripts\novel-qc-loop.ps1 render-marked-manuscript-hwpx --run-root "workspace\{work}\runs\{run_id}" --loop-label loop_01
.\scripts\novel-qc-loop.ps1 apply-changes-text --run-root "workspace\{work}\runs\{run_id}"
.\scripts\novel-qc-loop.ps1 apply-changes-text --run-root "workspace\{work}\runs\{run_id}" --accept-aa
```

`render-marked-manuscript-hwpx`는 루프 중간 확인용 산출물입니다. 원문 순서 그대로 `ⓐ{원문|수정}`과 `ⓐⓐ(의견: ... / 제안: ...)`을 삽입한 검토본이며, 파란색은 제안문이나 의견을 뜻합니다. `ⓐⓐ`는 모두 의견 메모로만 표시하고 원문을 치환하지 않습니다. 이 파일도 최종 원고 적용본은 아닙니다.

표식 카운트는 `ⓐ` 교정과 `ⓐⓐ` 판단을 분리합니다. `ⓐ{` 단순 문자열 카운트는 `ⓐⓐ{...}`를 오인할 수 있으므로 금지하고, 렌더 명령의 `marker_counts`와 `rendered_marker_counts`를 기준으로 보고합니다.

적용 뒤에는 다시 정합성 평가를 합니다. 해결된 항목, 새로 생긴 항목, 회귀 항목, 잔여 리스크를 `llm-facing/consistency_correction_loop.md`에 남기고, 만족 기준을 통과한 뒤에만 최종 개선 보고서에서 해결 완료로 씁니다.

## 문맥형 오타

문맥형 오타는 정규식이나 단어 목록만으로 잡지 않습니다. 해당 문장 앞뒤를 읽고, 장면의 물건, 행동 연쇄, 호칭, 지시 대상, 직전 상태와 맞지 않는 단어를 후보로 올립니다.

`changes.json`에서는 `edit_class=contextual_typo`를 사용합니다.

필수:

- `reading_basis`: 앞뒤 문맥상 왜 오기인지.
- `context_before` / `context_after` / `context_window` / `evidence_snippet` 중 하나 이상.
- `reason`: 변경 이유.

문맥형 오타를 `ⓐ`로 확정하려면 `confidence_percent`가 95 이상이어야 합니다. 확신이 부족하거나 작가 의도 가능성이 있으면 `ⓐⓐ`로 둡니다.

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

구버전 `.hwp`는 intake에서 `hwp5txt`로 텍스트 추출까지 지원합니다. 다만 직접 XML 조작이나 파란색 변경 표시는 어렵기 때문에 납품용 표시가 필요하면 가능하면 `.hwpx`로 변환한 뒤 처리합니다.
