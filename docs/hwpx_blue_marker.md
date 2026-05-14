# HWPX 파란색 교정 표시

`scripts/apply_blue.py`는 HWPX 파일의 특정 텍스트를 교정문으로 바꾸고, 교정문 부분만 파란색으로 표시합니다.

## 변경 JSON

```json
[
  {"operation": "replace", "find": "반증", "replace": "방증", "marker": "ⓐ"},
  {"operation": "delete", "find": "반복 문장", "replace": "", "marker": "ⓐⓐ"},
  {"operation": "insert_after", "find": "앵커 문장.", "replace": " 추가 문장.", "marker": "ⓐⓐ"}
]
```

허용 operation:

- `replace`: `find`를 `replace`로 치환
- `delete`: `find` 삭제, `replace`는 빈 문자열
- `insert_before`: `find` 앵커 앞에 `replace` 추가
- `insert_after`: `find` 앵커 뒤에 `replace` 추가

추가 작업에서도 `find`는 실제 원문에서 찾을 수 있는 앵커여야 합니다.

## 적용

```powershell
python scripts/apply_blue.py --input 원본.hwpx --output 수정본.hwpx --changes changes.json
```

## 최종 정리

```powershell
python scripts/apply_blue.py --input 수정본.hwpx --output 최종본.hwpx --finalize
```

기본값은 다음과 같습니다.

- `ⓐ`: 마커와 원문 제거, 교정문 유지
- `ⓐⓐ`: 원문 복원

`ⓐⓐ`도 일괄 승인하려면:

```powershell
python scripts/apply_blue.py --input 수정본.hwpx --output 최종본.hwpx --finalize --accept-aa
```
