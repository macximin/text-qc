# 하네스 상태 점검: 95% 재감리 보고서 대응

점검일: 2026-04-30  
대상 저장소: `C:\Users\wjjo\Desktop\novel-qc-loop`

## 결론

초기 상태의 하네스는 `evidence 후보 생성 + 수동 감리 스캐폴드 + 최소 human report lint` 수준이었다. 방금 수준의 95% 확신 재감리 보고서를 안정적으로 내려면 부족했다.

이번 고도화 후에는 다음이 가능하다.

- EPUB 파일 또는 EPUB 폴더를 직접 intake할 수 있다.
- EPUB 폴더 intake 시 원본 EPUB 53개를 run workspace 아래로 복사해 재현성을 확보한다.
- EPUB 패키지 QC가 `evidence/package/epub_package_qc.json` 및 `.md`로 생성된다.
- `manual_review_submission.json` findings에 `decision`, `confidence_percent`, `evidence_snippet`, `counter_evidence`, `original_priority`, `final_priority`를 남길 수 있다.
- `decision=확정` 항목은 완료 검증 시 95% 이상 confidence와 근거가 필요하다.
- `render-reaudit-report` 명령으로 확정/강등/철회/유보를 분리한 human-facing 재감리 보고서를 생성할 수 있다.
- `render-author-final-report` 명령으로 항목별 `위치/원문 근거/문제/근거/해석/수정 방향`을 갖춘 작가전달용 상세 보고서를 생성할 수 있다.
- `render-author-final-report --pdf` 또는 `export-report-pdf`로 Markdown 보고서를 PDF로 변환할 수 있다.

## 남은 현실적 한계

하네스가 의미 오류를 완전 자동으로 발견하는 것은 아니다. 날짜, 금액, 브리지, 시대감, 위생 후보는 자동 생성하지만, 동양화재 공매도 같은 핵심 산식 보강 필요 여부를 확정/강등 판단하는 단계는 여전히 수동 감리 또는 LLM 감리자가 `manual_review_submission.json`에 구조화해서 넣어야 한다.

즉 현재 상태는 `의미 오류 자동 판정기`가 아니라 `재감리 결과를 검증 가능한 형태로 수집하고, 작가전달용 보고서와 PDF까지 산출하는 하네스`다. 이건 현장 사용에는 맞는 방향이다. 자동 후보를 그대로 믿지 않고, 확정/강등/철회를 분리해 남기는 구조가 생겼기 때문이다.

## 검증한 명령

```powershell
$env:PYTHONPATH='.\src'
python -m compileall src
python -m novel_qc_loop --help
python -m novel_qc_loop inspect-epub-package --input "\\172.16.10.120\소설사업부\판무팀_ssot\02_연재\재벌 멱살 잡는 투자 천재(큰손)\연재이펍" --output-dir "workspace\_repro_reaudit\package_qc_latest"
python -m novel_qc_loop intake --input "\\172.16.10.120\소설사업부\판무팀_ssot\02_연재\재벌 멱살 잡는 투자 천재(큰손)\연재이펍" --workspace workspace --templates templates --mode full --title "EPUB 폴더 인입 회귀 2" --slug "epub-folder-repro-copy" --genre "현대판타지" --audience "웹소설 독자" --platform "연재 EPUB" --analyze
python -m novel_qc_loop validate-submission --submission "workspace\_repro_reaudit\manual_review_submission.json"
python -m novel_qc_loop render-reaudit-report --run-root "workspace\qc-confidence-repro\runs\20260430_155944__full-qc-correction" --submission "workspace\_repro_reaudit\manual_review_submission.json" --output "workspace\_repro_reaudit\reaudit_report.md" --title "재감리 렌더러 회귀 보고서" --source-label "샘플 원문"
python -m novel_qc_loop validate-report --report "workspace\_repro_reaudit\reaudit_report.md"
python -m novel_qc_loop render-author-final-report --run-root "workspace\qc-confidence-repro\runs\20260430_155944__full-qc-correction" --submission "workspace\_repro_reaudit\manual_review_submission.json" --output "workspace\_repro_reaudit\author_final_report.md" --title "작가전달용 최종검수보고서 회귀" --source-label "샘플 원문"
python -m novel_qc_loop export-report-pdf --report "workspace\_repro_reaudit\author_final_report.md" --output "workspace\_repro_reaudit\author_final_report.pdf"
python -m novel_qc_loop render-author-final-report --run-root "workspace\qc-confidence-repro\runs\20260430_155944__full-qc-correction" --submission "workspace\_repro_reaudit\manual_review_submission.json" --output "workspace\_repro_reaudit\author_final_report_with_pdf.md" --title "작가전달용 최종검수보고서 PDF 회귀" --source-label "샘플 원문" --pdf "workspace\_repro_reaudit\author_final_report_with_pdf.pdf"
```

## 확인된 산출물

- `workspace\_repro_reaudit\reaudit_report.md`: 재감리 보고서 렌더링 검증 통과.
- `workspace\_repro_reaudit\author_final_report.md`: 작가전달용 상세 보고서 렌더링 검증 통과.
- `workspace\_repro_reaudit\author_final_report.pdf`: 작가전달용 상세 보고서 PDF 변환 검증 통과.
- `workspace\_repro_reaudit\package_qc_latest\epub_package_qc.md`: EPUB 패키지 QC 생성.
- `workspace\epub-folder-repro-copy\inputs\original\연재이펍\*.epub`: 원본 EPUB 53개 복사 확인.
- `workspace\epub-folder-repro-copy\runs\20260430_161353__full-qc-correction\evidence\package\epub_package_qc.md`: run 내부 패키지 QC 생성.

## 적대적 감리 반영 내역

- 구버전 completed submission 호환성: 새 confidence 규칙은 재감리 필드가 있는 finding에만 적용되도록 조정.
- 커스텀 `--submission` 렌더링 게이트: 렌더링한 submission과 gate에 기록하는 submission이 일치하도록 수정.
- EPUB 폴더 재현성: 원본 EPUB을 `inputs/original/{folder}` 아래로 복사하도록 수정.
- EPUB 정렬: lexicographic 정렬 대신 natural sort로 `1, 2, 10` 순서를 보장.
- 빈 EPUB 폴더: 성공처럼 보이지 않고 오류를 반환하도록 수정.
- inbox EPUB 폴더: `intake-inbox`에서도 EPUB 폴더를 처리하도록 수정.
- 빈 재감리 보고서: finding이 없으면 렌더링을 거부하도록 수정.

## 사용 권장 흐름

1. EPUB 폴더 또는 원고를 intake한다.
2. `analyze-run`으로 evidence를 만든다.
3. 감리자가 3-pass로 `manual_review_submission.json`을 채운다.
4. `validate-submission`으로 95% 확정 항목의 confidence/evidence를 검증한다.
5. `render-reaudit-report`로 human-facing 재감리 보고서를 만든다.
6. 작가 전달용 상세본이 필요하면 `render-author-final-report --pdf`로 Markdown/PDF를 만든다.
7. `validate-report`로 placeholder, 내부 작업어, 주장-근거 쌍을 확인한다.
