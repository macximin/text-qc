# novel-qc-loop

여러 웹소설 원고를 같은 기준으로 검수, 교정, 보고, export하기 위한 canonical 루프입니다. 이 저장소는 사람이 직접 원고를 맡기기 전에 LLM이 같은 기준으로 반복 감리할 수 있게 만든 **LLM-facing 하네스 체계**입니다.

이 repo에는 **루프 엔진, 문서, 템플릿, 스키마**만 둡니다. 실제 원고, HWP/HWPX/PDF, 작가별 결과물은 `workspace/`, `runs/`, `초기 원고(input)/`, `최종 원고(output)/` 아래에 두고 기본적으로 git에 올리지 않습니다. 두 원고 폴더는 `.gitkeep`으로 구조만 커밋하고, 내부 산출물과 원고 파일은 ignore합니다.

## 목표

- 여러 작품을 같은 검수 루프에 올릴 수 있게 한다.
- 작품별 원고/리포트/교정안/export를 섞지 않는다.
- `1차 전역 감리 -> 적대적 감리 -> human-facing 보고서 -> 교정안 -> 최종 export` 흐름을 표준화한다.
- LLM이 바로 읽고 실행할 수 있는 `llm-facing` 작업 지시, 체크리스트, 3-pass 감리 브리프를 산출한다.
- 다른 사람도 같은 폴더 규칙과 manifest만 알면 실행할 수 있게 한다.

## 빠른 시작

```powershell
cd C:\Users\wjjo\Desktop\novel-qc-loop
$env:PYTHONPATH = ".\src"
python -m novel_qc_loop intake --input "C:\path\to\manuscript.txt" --mode full --genre "무협" --audience "성인 독자" --analyze
python -m novel_qc_loop init-work --slug sample-title --title "샘플 작품" --genre "판타지" --audience "일반 독자" --platform "플랫폼명"
python -m novel_qc_loop start-run --work canaria --kind global-audit
python -m novel_qc_loop analyze-run --run-root "workspace\sample-title\runs\RUN_ID"
python -m novel_qc_loop validate-changes --changes "workspace\sample-title\runs\RUN_ID\corrections\changes.json"
python -m novel_qc_loop validate-submission --run-root "workspace\sample-title\runs\RUN_ID"
python -m novel_qc_loop validate-report --run-root "workspace\sample-title\runs\RUN_ID"
python -m novel_qc_loop render-reaudit-report --run-root "workspace\sample-title\runs\RUN_ID"
python -m novel_qc_loop render-author-final-report --run-root "workspace\sample-title\runs\RUN_ID" --pdf
python -m novel_qc_loop export-report-pdf --report "workspace\sample-title\runs\RUN_ID\human-facing\author_final_report.md"
python -m novel_qc_loop inspect-epub-package --input "C:\path\to\epub_folder" --output-dir "workspace\sample-title\runs\RUN_ID\evidence\package"
python -m novel_qc_loop list-works
python -m novel_qc_loop portfolio-status
python -m novel_qc_loop inspect-text --input "C:\path\to\manuscript.txt"
```

## 기본 구조

```text
docs/                 운영 문서
inbox/                초기 원고함, git ignore
초기 원고(input)/     로컬 초기 원고 투입 폴더, 구조만 commit
최종 원고(output)/    로컬 최종 원고/납품 후보 폴더, 구조만 commit
templates/            보고서/감리/교정 템플릿
schemas/              manifest/issue/report JSON schema
scripts/              현장 실행용 얇은 래퍼와 HWPX 도구
src/novel_qc_loop/    재사용 가능한 루프 코드
examples/anonymized/  익명 샘플만 허용
workspace/            실제 작품별 작업 공간, git ignore
runs/                 임시 전체 실행 로그, git ignore
```

`초기 원고(input)/`와 `최종 원고(output)/`는 사람이 파일을 넣고 꺼내기 쉬운 로컬 편의 폴더입니다. git에는 `.gitkeep`만 남기며, 그 안의 원고, 교정본, PDF, HWPX, export 산출물은 커밋하지 않습니다. 공유해야 하는 것은 원고 본문이 아니라 재현 가능한 하네스 코드, 템플릿, 스키마, 운영 문서입니다.

## 작품 단위

각 작품은 `workspace/{work_slug}` 아래에 독립적으로 생성됩니다.

```text
workspace/canaria/
  manifest.json
  inputs/
  extracted/
  runs/
  reports/
  corrections/
  exports/
  archive/
```

`manifest.json`에는 작품 제목, 장르, 대상 독자, 플랫폼, 원본 위치, 운영 메모를 둡니다. 원고 본문은 manifest에 넣지 않습니다.

## Intake Harness

가장 쉬운 흐름은 `inbox/initial_manuscripts/`에 원고를 넣고 intake를 돌리는 것입니다.

```powershell
.\scripts\novel-qc-loop.ps1 intake-inbox --mode full
```

지원 입력은 `.txt`, `.text`, `.md`, `.markdown`, `.hwpx`, `.epub` 및 EPUB 파일이 들어 있는 폴더입니다. EPUB은 OPF spine의 본문 XHTML만 읽고 metadata/nav/toc/cover 계열은 제외합니다. EPUB 파일 또는 폴더를 넣으면 `evidence/package/epub_package_qc.*`에 언어, UUID 중복, 파일명 규칙 같은 패키지 QC도 함께 남깁니다. 텍스트 인코딩은 UTF-8/CP949/EUC-KR/UTF-16 계열을 자동 감지하고, 회차 표기는 `ⓚ001`, Markdown 제목, `제1화`, `001화`, `1장`, `Episode 1` 계열을 우선 인식합니다.

하네스는 제목을 유추하고, 작품 폴더와 run 폴더를 만들고, 다음 산출물을 자동 생성합니다.

- `llm-facing/task_brief.md`
- `llm-facing/handoff_checklist.md`
- `llm-facing/adversarial_3pass_brief.md`
- `human-facing/one_page_report.md`
- `final_manuscript/final_manuscript.txt`
- `evidence/inspection.json`
- `evidence/episodes/*.txt`
- `evidence/facts/*.jsonl`
- `evidence/facts/timeline_summary.json`
- `evidence/facts/character_title_matrix.json`
- `evidence/review/*.jsonl`
- `evidence/review/verisimilitude_candidates.jsonl`
- `evidence/review/narrative_allowances.jsonl`
- `evidence/review/ai_slop_signals.json`
- `evidence/submission/submission_gate.json`
- `evidence/submission/manual_review_queue.jsonl`
- `evidence/submission/manual_review_submission.json`
- `evidence/package/epub_package_qc.json`
- `evidence/package/epub_package_qc.md`

`ai_slop_signals.json`에는 "AI로 쓴 확률"처럼 읽히는 자동 추정치가 들어가지만, 이는 포렌식 판정이 아니라 반복 표현/문장 리듬/추상어 밀도 기반의 **AI 티 위험도**입니다. 같은 값은 `human-facing/one_page_report.md`의 `AI 티 점검` 섹션에도 자동 반영됩니다.

하네스는 자동 후보를 곧바로 확정 오류로 보지 않습니다. 다만 우선순위는 외부 고증보다 작중 핍진성에 둡니다. `오늘 했다`고 쓴 행동이 뒤에서 `오늘 하지 않았다`로 뒤집히거나, 완료된 사건/정산/권한 상태가 원인 없이 회귀하는 문제를 가장 먼저 봅니다. 날짜/요일/은행 영업일 같은 외부 고증은 작중 행동 결과를 흔들 때만 강한 이슈가 됩니다. 작중 뉴스 자막, 로이터/블룸버그 단말기 문구, 문서/보고서 표기, 장르적 과장처럼 소설적 허용으로 방어 가능한 항목은 blocker에서 제외하고 `evidence/review/narrative_allowances.jsonl`에 근거를 남깁니다.

## LLM-facing 하네스

`llm-facing/` 산출물은 LLM이 다음 작업을 이어받기 위한 내부 작업면입니다. 여기에는 `task_brief.md`, `handoff_checklist.md`, `adversarial_3pass_brief.md`가 들어가며, 감리자는 이 문서를 기준으로 전역 감리, 적대적 재감리, 최종 감리의 3-pass를 수행합니다.

LLM-facing 문서는 작가에게 그대로 전달하지 않습니다. 원고 판단, 후보 evidence, 반례, 수동 감리 상태를 모아 LLM과 편집자가 검토하는 중간층이며, 외부 전달물은 `human-facing/` 보고서와 승인된 `final_manuscript/`만 사용합니다.

## 핵심 원칙

- 원본 원고는 보존한다.
- 자동 변환은 검수/리포트 보조에만 쓰고, 문장 의미를 바꾸는 교정은 사람이 확인한다.
- 검수와 교정은 분리한다. 검수는 문제와 근거를 남기고, 교정은 변경안과 승인 상태를 남긴다.
- 리포트는 내부용 raw 판정과 작가/편집자-facing 보고서를 분리한다.
- 최종 보고서는 한국어 human-facing 문서여야 하며, 모든 핵심 판단에는 주장과 근거를 함께 둔다.
- 최종 보고서는 `manual_review_submission.json` 감리 완료와 `validate-submission` 통과 전에는 제출 가능 상태가 될 수 없다.
- P0/P1은 최종 감리에서 확정, 확신도 95% 이상, 직접 근거 있음, 미해결 반례 없음, 작중 핍진성 영향이 모두 충족된 항목만 사용한다.
- 외부 고증 후보는 작중 행동·상태·인과를 깨뜨리는 경우와 단순 보강 후보를 분리한다.
- HWPX 교정 표시는 파란색 변경 표기를 표준으로 둔다.

## 교정 규칙

이 하네스는 검수뿐 아니라 교정도 할 수 있습니다. 다만 교정은 감리 evidence와 분리해 `corrections/changes.json`에 변경안으로 남기고, 승인된 변경만 `final_manuscript/`나 HWPX export에 반영합니다.

- `ⓐ`: 확정 교정. 오탈자, 띄어쓰기, 조사, 문장부호, 명백한 단어 오기처럼 작가 의도 가능성이 낮은 오류에만 쓴다.
- `ⓐⓐ`: 작가 판단 요청. 인물 말투, 고유명사, 문체 선택, 세계관 용어, 논쟁 가능한 표현처럼 의도 가능성이 있는 항목에 쓴다.
- 원본 파일은 덮어쓰지 않는다. `inputs/original/`은 보존하고, 최종 후보는 `final_manuscript/` 또는 `최종 원고(output)/`에 둔다.
- 대화문 말투와 캐릭터성은 오탈자처럼 확정 교정하지 않는다.
- 고유명사는 첫 등장과 설정 기준을 확인한 뒤, 불일치 가능성이 있으면 `ⓐⓐ`로 올린다.
- 작가 승인 전 `ⓐⓐ`는 최종 반영하지 않는다. `scripts/apply_blue.py`의 기본 동작도 `ⓐ`만 승인하고 `ⓐⓐ`는 원문 복원하는 쪽이다.
- 교정안은 `validate-changes`를 통과해야 하며, `find`와 `replace`가 같거나 marker가 `ⓐ`/`ⓐⓐ`/빈 값 외이면 실패로 본다.

```powershell
python -m novel_qc_loop validate-changes --changes "workspace\sample-title\runs\RUN_ID\corrections\changes.json"
python scripts/apply_blue.py --input 원본.hwpx --output 수정본.hwpx --changes changes.json
python scripts/apply_blue.py --input 수정본.hwpx --output 최종본.hwpx --finalize
```

## 95% 재감리 보고서

`manual_review_submission.json`의 findings에는 `decision`, `confidence_percent`, `evidence_snippet`, `counter_evidence`, `original_priority`, `final_priority`, `story_state_before`, `story_state_after`, `story_internal_impact`를 넣을 수 있습니다. `status=complete` 제출에서는 이 최종 감리 필드가 필수입니다. P0/P1은 `decision=확정`, 95% 이상 확신, 직접 근거, 미해결 반례 없음, 작중 핍진성 영향이 모두 맞아야 완료 검증을 통과합니다. 반례나 장면상 방어가 남은 항목은 P2/P3로 낮추거나 철회/유보해야 합니다. 감리 완료 후 아래 명령으로 작가/편집자-facing 재감리 보고서를 렌더링합니다.

```powershell
python -m novel_qc_loop render-reaudit-report --run-root "workspace\sample-title\runs\RUN_ID"
```

## 작가전달용 최종 보고서

표 기반 재감리 요약이 아니라 항목별 상세 보고서가 필요하면 `render-author-final-report`를 사용합니다. 이 명령은 `manual_review_submission.json`의 findings를 바탕으로 `위치 -> 원문 근거 -> 문제 -> 근거 -> 해석 -> 수정 방향` 순서의 한국어 보고서를 생성합니다.

```powershell
python -m novel_qc_loop render-author-final-report --run-root "workspace\sample-title\runs\RUN_ID"
python -m novel_qc_loop render-author-final-report --run-root "workspace\sample-title\runs\RUN_ID" --pdf
```

기본 출력은 `human-facing/author_final_report.md`입니다. `--pdf`를 붙이면 같은 위치에 PDF도 생성합니다. 별도 Markdown 보고서를 PDF로 변환할 때는 다음 명령을 씁니다.

```powershell
python -m novel_qc_loop export-report-pdf --report "workspace\sample-title\runs\RUN_ID\human-facing\author_final_report.md"
```

등급 렌더링은 보수 기준을 따릅니다. `final_priority`가 있으면 최종 등급을 우선 사용하고, `decision=강등` 또는 `counter_evidence`가 있는 항목은 방어 가능한 해석을 보고서의 `해석`에 함께 남깁니다. P0/P1은 확정 항목만 포함하고, `decision=철회` 또는 `decision=유보` 항목은 작가전달용 최종 이슈에서 제외합니다.

## IDE-first

이 루프의 기본 사용처는 IDE입니다. 원고, manifest, run, 리포트, 교정안을 한 repo 안에서 보고 AI 에이전트와 함께 반복합니다.

추천 문서:

- `docs/ide_first_operating_model.md`
- `docs/intake_harness.md`
- `docs/harness_contract.md`
- `docs/legacy_ssot_mapping.md`
- `docs/adversarial_audit.md`
- `docs/correction_protocol.md`
- `docs/repeatable_multi_work_loop.md`
- `docs/ai_slop_signal.md`

## 현재 이식된 레거시

- `scripts/apply_blue.py`: HWPX 파란색 교정 표시 도구. 기존 `업무자동화_ssot/교정/scripts/apply_blue.py`에서 가져온다.
