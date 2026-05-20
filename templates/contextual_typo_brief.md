# Contextual Typo Brief

작품: `{{title}}` (`{{work_slug}}`)
Run: `{{run_id}}`

## 목적

이 브리프는 패턴형 오탈자가 아니라, 앞뒤 문맥을 읽어야만 보이는 오기와 단어 혼입을 처리하기 위한 기준입니다. 단어 하나가 사전상 가능해 보여도 장면, 행동 연쇄, 지시 대상, 인물 기억, 물건 상태와 맞지 않으면 문맥형 오타 후보로 올립니다.

## 먼저 읽을 범위

- `regex`, `glob`, `rg` 검색은 후보를 찾는 데만 씁니다. 검색 결과가 곧 오탈자 판정은 아닙니다.
- 해당 문장만 보지 말고 최소 앞뒤 1-3문단을 읽습니다.
- 회차 경계, 장면 전환, 직전 대화 상대, 현재 들고 있는 물건, 직전 행동 결과를 확인합니다.
- 같은 단어가 여러 번 나오면 자동 치환하지 말고, 해당 occurrence의 문맥만 판단합니다.

## changes.json 작성

문맥형 오타는 `edit_class`를 `contextual_typo`로 둡니다. 반드시 `reading_basis`와 문맥 근거를 남깁니다. `ⓐ`로 확정할 때는 가능한 다른 해석과 그 해석을 버린 이유까지 적습니다.

```json
{
  "id": "ctx-typo-0001",
  "operation": "replace",
  "severity": "P2",
  "status": "needs-author",
  "marker": "ⓐⓐ",
  "find": "문맥상 어긋난 원문",
  "replace": "문맥상 맞는 후보",
  "reason": "앞뒤 행동 연쇄상 단어가 어긋남",
  "location": "ep_0001",
  "edit_class": "contextual_typo",
  "context_before": "직전 문맥 요약 또는 원문 일부",
  "context_after": "직후 문맥 요약 또는 원문 일부",
  "reading_basis": "왜 이 단어가 문맥상 오기인지",
  "alternative_interpretation": "작가가 의도했을 수 있는 다른 해석",
  "rejection_basis": "그 해석보다 교정안이 안전한 이유",
  "confidence_percent": 90
}
```

`ⓐ`로 확정하려면 `confidence_percent`가 95 이상이어야 합니다. 95 미만이거나 작가 의도 가능성이 남으면 `ⓐⓐ`로 둡니다.

## 문맥 추출

```powershell
.\scripts\novel-qc-loop.ps1 render-change-contexts --run-root "{{run_root}}"
.\scripts\novel-qc-loop.ps1 render-change-contexts --run-root "{{run_root}}" --contextual-only
```

결과는 `corrections/change_contexts.md`에 생성됩니다. 이 파일에서 실제 앞뒤 문맥을 확인한 뒤 `reading_basis`, `context_before`, `context_after`를 채웁니다.

## 판단 예시

- 인물이 방금 휴대폰을 집어 들었는데 다음 문장에서 `검을 켰다`처럼 물건이 섞이면 문맥형 오타 후보입니다.
- 직전까지 형을 부르던 인물이 같은 대화에서 갑자기 `아버지`라고 하면 호칭 drift 또는 문맥형 오타 후보입니다.
- 앞뒤 문맥상 `문을 잠갔다`가 맞는데 `문을 잠갔다가 열었다`의 생략인지, 실제로 `문을 열었다`가 맞는지는 장면 전환을 읽고 판단합니다.
- `11자의 틈새`처럼 가능한 형상 해석이 있는 경우, 수식 대상이 `펜촉`인지 `틈새`인지 확인합니다. `틈새`를 수식한다면 `일자형 틈새`가 더 안전하다는 식으로 반례 처리 근거를 남깁니다.

## 금지

- 단어가 낯설다는 이유만으로 문맥형 오타라고 단정하지 않습니다.
- 작가의 반복 리듬, 인물 말버릇, 장르적 과장을 자동 오타로 취급하지 않습니다.
- 앞뒤 문맥 근거 없이 대량 치환하지 않습니다.
