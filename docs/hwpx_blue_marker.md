# HWPX 파란색 교정 표시

`scripts/apply_blue.py`는 HWPX 파일의 특정 텍스트를 교정문으로 바꾸고, 교정문 부분만 파란색으로 표시합니다.

## 변경 JSON

```json
[
  {"find": "반증", "replace": "방증", "marker": "ⓐ"},
  {"find": "오랜만", "replace": "오래간만", "marker": "ⓐⓐ"}
]
```

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

