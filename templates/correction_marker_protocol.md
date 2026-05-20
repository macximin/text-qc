# 교정 마커 프로토콜

작품: `{{title}}` (`{{work_slug}}`)
Run: `{{run_id}}`

## 마커

- `ⓐ`: 확정 교정. 명백한 오타, 문법, 띄어쓰기, 조사 오류.
- `ⓐⓐ`: 작가 판단 요청. 문체, 말투, 고유명사, 의도 가능성이 있는 표현.

단순 맞춤법, 띄어쓰기, 문장 호흡은 `ⓐ` 자동승인으로 본다. 판단용 검수본에서는 교정문을 파란색으로 보여 주고, 최종 원고 적용본과는 분리한다.

## 인라인 표기

```text
ⓐ{원문|교정문}
ⓐⓐ{원문|후보문장}[판단: 판단 근거]
ⓐ{삭제할 말|}
ⓐ{|추가할 말}
ⓐⓐ{삭제할 말|}[판단: 삭제 판단 근거]
ⓐⓐ{|추가할 말}[판단: 추가 판단 근거]
```

`ⓐⓐ`는 원문을 바로 치환하지 않는 판단 항목이지만, `ⓐ`와 같은 `{원문|후보}` 비교 구조를 쓴다. `replace`에는 승인 시 본문에 들어갈 수 있는 문장, 문단, 삭제/추가 후보를 넣고, 판단 근거는 `reason`에 남긴다.

삭제 확정 교정은 교정문을 비운다.

```text
ⓐ{삭제할 말|}
```

## 고유명사 정본/약칭

동일 인물, 기업, 기관으로 정본이 확정된 고유명사는 대표 표기 하나로 통일한다. 약칭, 이니셜, 실명/가명 병기는 자동으로 의도 처리하지 않는다.

- 단순 혼용: `ⓐ{약칭 또는 오기|정본}` 후보.
- 시세판, 기사 헤드라인, 괄호 설명처럼 축약 장면 기능이 명확한 경우: `ⓐⓐ{약칭|정본 또는 유지 후보}[판단: 축약 기능 근거]`.
- 별도 설정 회사나 동명이인은 정본 통일 대상이 아니다. 앞뒤 문맥으로 같은 대상인지 확인한다.

## changes.json 형식

`operation`을 생략하면 기본값은 `replace`다. `replace`가 빈 문자열이면 `delete`로 해석한다. 추가는 `find`를 위치 앵커로 쓰고, `replace`에 추가할 문장을 넣는다.

```json
[
  {
    "id": "chg-0001",
    "operation": "replace",
    "severity": "P2",
    "status": "proposed",
    "marker": "ⓐ",
    "find": "원문",
    "replace": "교정문",
    "reason": "명백한 오탈자",
    "location": "ep_0001"
  },
  {
    "id": "edit-0002",
    "operation": "delete",
    "severity": "P2",
    "status": "proposed",
    "marker": "ⓐⓐ",
    "find": "삭제할 반복 문장",
    "replace": "",
    "reason": "직전 문단과 동일한 정보 반복",
    "location": "ep_0001"
  },
  {
    "id": "edit-0003",
    "operation": "insert_after",
    "severity": "P1",
    "status": "needs-author",
    "marker": "ⓐⓐ",
    "find": "앵커 문장.",
    "replace": " 빠진 인과를 잇는 추가 문장.",
    "reason": "장면 전환의 인과 브리지 보강",
    "location": "ep_0001"
  }
]
```

허용 operation:

- `replace`: 원문을 교정문/편집문으로 치환.
- `delete`: 원문 삭제. `replace`는 빈 문자열.
- `insert_before`: `find` 앵커 앞에 `replace` 텍스트 추가.
- `insert_after`: `find` 앵커 뒤에 `replace` 텍스트 추가.

## 문맥형 오타

패턴형 오탈자가 아니라 앞뒤 문맥을 읽어야 보이는 오기는 `edit_class=contextual_typo`로 올린다.

필수 필드:

- `reading_basis`: 앞뒤 문맥상 왜 오기인지.
- `context_before` / `context_after` / `context_window` / `evidence_snippet` 중 하나 이상.
- `reason`: 변경 이유.

`ⓐ`로 확정하려면 `confidence_percent`가 95 이상이어야 한다. 작가 의도 가능성이 남으면 `ⓐⓐ`로 둔다.

문맥 확인용 파일 생성:

```powershell
.\scripts\novel-qc-loop.ps1 render-change-contexts --run-root "{{run_root}}"
.\scripts\novel-qc-loop.ps1 render-change-contexts --run-root "{{run_root}}" --contextual-only
```

## 검증

```powershell
.\scripts\novel-qc-loop.ps1 validate-changes --changes "workspace\...\corrections\changes.json"
```

## 판단용 마커 검수본

편집자 모드에서는 HWPX 흐름을 기본으로 쓰지 않는다. 먼저 MD 마커 검수본을 만들어 사람이 `ⓐ`/`ⓐⓐ`를 직접 보고 판단할 수 있게 한다.

```powershell
.\scripts\novel-qc-loop.ps1 render-marked-manuscript-md --run-root "{{run_root}}" --loop-label loop_01
.\scripts\novel-qc-loop.ps1 render-marked-manuscript-hwpx --run-root "{{run_root}}" --loop-label loop_01
.\scripts\novel-qc-loop.ps1 apply-changes-text --run-root "{{run_root}}"
.\scripts\novel-qc-loop.ps1 apply-changes-text --run-root "{{run_root}}" --accept-aa
```

HWPX 파란색 표시는 별도 납품 요구가 있을 때만 사용한다.

```powershell
python scripts/apply_blue.py --input 원본.hwpx --output 수정본.hwpx --changes changes.json
```

최종 승인 후:

```powershell
python scripts/apply_blue.py --input 수정본.hwpx --output 최종본.hwpx --finalize
```

기본값은 `ⓐ`만 승인하고 `ⓐⓐ`는 원문 복원한다. `ⓐⓐ`도 일괄 승인하려면 `--accept-aa`를 붙인다.

## 금지

- `ⓐⓐ`를 작가 승인 없이 확정 교정으로 처리하지 않는다.
- HWPX 중간 검토본에서 `ⓐⓐ`를 원문에 바로 반영하지 않는다. 다만 `ⓐⓐ{원문|후보문장}[판단: ...]`처럼 원문과 실제 후보문장은 반드시 함께 보이게 둔다.
- 원본 파일을 덮어쓰지 않는다.
- 대화문 말투를 오탈자처럼 확정 교정하지 않는다.
- 고유명사는 첫 등장 기준과 불일치할 때만 판단 요청으로 올린다.
- 적극 편집은 기본적으로 `ⓐⓐ`로 올리고 승인 전 최종 반영하지 않는다.
