# 교정 마커 프로토콜

작품: `{{title}}` (`{{work_slug}}`)
Run: `{{run_id}}`

## 마커

- `ⓐ`: 확정 교정. 명백한 오타, 문법, 띄어쓰기, 조사 오류.
- `ⓐⓐ`: 작가 판단 요청. 문체, 말투, 고유명사, 의도 가능성이 있는 표현.

## 인라인 표기

```text
ⓐ{원문|교정문}
ⓐⓐ{원문|대안}
```

삭제는 교정문을 비운다.

```text
ⓐ{삭제할 말|}
```

## changes.json 형식

```json
[
  {
    "id": "chg-0001",
    "severity": "P2",
    "status": "proposed",
    "marker": "ⓐ",
    "find": "원문",
    "replace": "교정문",
    "reason": "명백한 오탈자",
    "location": "ep_0001"
  }
]
```

## 검증

```powershell
.\scripts\novel-qc-loop.ps1 validate-changes --changes "workspace\...\corrections\changes.json"
```

## HWPX 파란색 적용

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
- 원본 파일을 덮어쓰지 않는다.
- 대화문 말투를 오탈자처럼 확정 교정하지 않는다.
- 고유명사는 첫 등장 기준과 불일치할 때만 판단 요청으로 올린다.
