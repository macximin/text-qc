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
.\scripts\novel-qc-loop.ps1 apply-changes-text --run-root "workspace\{work}\runs\{run_id}"
.\scripts\novel-qc-loop.ps1 apply-changes-text --run-root "workspace\{work}\runs\{run_id}" --accept-aa
```

## 원칙

- 원본은 덮어쓰지 않는다.
- 대화문 말투는 함부로 고치지 않는다.
- 고유명사는 첫 등장 기준으로 본다.
- 일관성 문제는 바로 확정하지 말고 `ⓐⓐ`로 올린다.
- 작가 승인 전 `ⓐⓐ`는 최종 반영하지 않는다.
- 없는 설정, 없는 감정선, 없는 사건을 편집자가 새로 발명하지 않는다.

## HWPX

HWPX는 교정 납품/표시가 필요할 때만 `scripts/apply_blue.py`로 파란색 변경 표시를 적용합니다. 편집자 모드 기본 작업에는 사용하지 않습니다.

구버전 `.hwp`는 직접 XML 조작이 어렵습니다. 가능하면 `.hwpx`로 변환한 뒤 처리합니다.
