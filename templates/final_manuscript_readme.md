# Final Manuscript Folder

이 폴더는 최종 원고 후보를 두는 위치입니다.

기본 파일:

- `final_manuscript.txt`
- `editorial_candidate.txt` (편집자 모드 적용 후보본, 필요 시 생성)

intake 직후에는 추출 원고가 그대로 복사되어 있습니다. 검수/교정 이후 승인된 변경만 반영해서 최종 후보로 갱신합니다.

편집자 모드에서는 HWP/HWPX가 아니라 plain text 후보본을 우선 사용합니다.

```powershell
.\scripts\novel-qc-loop.ps1 apply-changes-text --run-root "{{run_root}}"
.\scripts\novel-qc-loop.ps1 apply-changes-text --run-root "{{run_root}}" --accept-aa
```

검토용 diff는 `corrections/editorial_diff.md`에 생성됩니다.

원본은 `inputs/original/`에 보존되어야 하며, 이 폴더의 파일만 수정 대상으로 삼습니다.
