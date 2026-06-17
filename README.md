# novel-qc-loop

여러 웹소설 원고를 같은 기준으로 검수, 교정, 보고, export하기 위한 canonical 루프입니다. 이 저장소는 사람이 직접 원고를 맡기기 전에 LLM이 같은 기준으로 반복 감리할 수 있게 만든 **LLM-facing 하네스 체계**입니다.

이 repo에는 **루프 엔진, 문서, 템플릿, 스키마**만 둡니다. 실제 원고, HWP/HWPX/PDF, 작가별 결과물은 `workspace/`, `runs/`, `초기 원고(input)/`, `최종 원고(output)/` 아래에 두고 기본적으로 git에 올리지 않습니다. 두 원고 폴더는 `.gitkeep`으로 구조만 커밋하고, 내부 산출물과 원고 파일은 ignore합니다.

이 하네스는 완제품 SaaS나 단일 정답 워크플로가 아니라, 웹소설 QC/교정 루프를 재현 가능하게 시작하기 위한 표준 출발점입니다. 작품 장르, 플랫폼 제출 규칙, 편집팀의 우선순위, 작가와의 합의 기준에 맞춰 템플릿, 감리 축, 교정 marker, 보고서 문구를 커스터마이징해서 사용할 것을 권장합니다.

## 목표

- 여러 작품을 같은 검수 루프에 올릴 수 있게 한다.
- 작품별 원고/리포트/교정안/export를 섞지 않는다.
- `정합성 검사`를 `primary 3회 -> blind 3개 lane x 3회 -> total 정합성 리포트 -> 적대적 감리 3회`인 1개 `consistency_3x3_unit`으로 표준화한다.
- `정합성 검사 3번`처럼 횟수가 붙으면 얕은 pass 3개가 아니라 `consistency_3x3_unit` 전체를 3회 반복한다.
- LLM이 바로 읽고 실행할 수 있는 `llm-facing` 작업 지시, 체크리스트, 3-pass 감리 브리프를 산출한다.
- 다른 사람도 같은 폴더 규칙과 manifest만 알면 실행할 수 있게 한다.

## 빠른 시작

```powershell
cd C:\Users\wjjo\Desktop\novel-qc-loop
$env:PYTHONPATH = ".\src"
python -m novel_qc_loop intake --input "C:\path\to\manuscript.txt" --mode full --genre "무협" --audience "성인 독자" --analyze
python -m novel_qc_loop intake --input "C:\path\to\manuscript.txt" --mode editor --analyze
python -m novel_qc_loop init-work --slug sample-title --title "샘플 작품" --genre "판타지" --audience "일반 독자" --platform "플랫폼명"
python -m novel_qc_loop start-run --work canaria --kind global-audit
python -m novel_qc_loop analyze-run --run-root "workspace\sample-title\runs\RUN_ID"
python -m novel_qc_loop validate-changes --changes "workspace\sample-title\runs\RUN_ID\corrections\changes.json"
python -m novel_qc_loop render-change-contexts --run-root "workspace\sample-title\runs\RUN_ID" --contextual-only
python -m novel_qc_loop render-marked-manuscript-md --run-root "workspace\sample-title\runs\RUN_ID" --loop-label loop_01
python -m novel_qc_loop render-marked-manuscript-hwpx --run-root "workspace\sample-title\runs\RUN_ID" --loop-label loop_01
python -m novel_qc_loop apply-changes-text --run-root "workspace\sample-title\runs\RUN_ID" --accept-aa
python -m novel_qc_loop validate-submission --run-root "workspace\sample-title\runs\RUN_ID"
python -m novel_qc_loop validate-report --run-root "workspace\sample-title\runs\RUN_ID"
python -m novel_qc_loop validate-report --report "workspace\sample-title\runs\RUN_ID\human-facing\final_improvement_report.md"
python -m novel_qc_loop render-reaudit-report --run-root "workspace\sample-title\runs\RUN_ID"
python -m novel_qc_loop render-author-final-report --run-root "workspace\sample-title\runs\RUN_ID" --pdf
python -m novel_qc_loop export-report-pdf --report "workspace\sample-title\runs\RUN_ID\human-facing\author_final_report.md"
python -m novel_qc_loop inspect-epub-package --input "C:\path\to\epub_folder" --output-dir "workspace\sample-title\runs\RUN_ID\evidence\package"
python -m novel_qc_loop list-works
python -m novel_qc_loop portfolio-status
python -m novel_qc_loop inspect-text --input "C:\path\to\manuscript.txt"
python -m unittest discover -s tests -v
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

내부 NAS 원본 root는 `\\172.16.10.120\소설사업부\판무팀_ssot`입니다. 하네스는 이 경로를 원본 참조 root로만 사용하고, 원본 파일은 직접 수정하지 않습니다. intake 이후 작업은 run 내부의 `inputs/original/`, `extracted/`, `final_manuscript/`, `corrections/` 산출물에서 진행합니다.

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

지원 입력은 `.txt`, `.text`, `.md`, `.markdown`, `.hwp`, `.hwpx`, `.epub` 및 지원 원고 파일이 들어 있는 폴더입니다. `.hwp`는 PATH의 `hwp5proc xml`을 우선 사용해 HWP `LINE_BREAK`를 실제 줄바꿈으로 보존한 뒤 텍스트를 추출하고, 실패하면 `hwp5txt`로 fallback합니다. EPUB은 OPF spine의 본문 XHTML만 읽고 metadata/nav/toc/cover 계열은 제외합니다. EPUB 파일 또는 폴더를 넣으면 `evidence/package/epub_package_qc.*`에 언어, UUID 중복, 파일명 규칙 같은 패키지 QC도 함께 남깁니다. 텍스트 인코딩은 UTF-8/CP949/EUC-KR/UTF-16 계열을 자동 감지하고, 회차 표기는 `ⓚ001`, `ⓚ제1화`, Markdown 제목, `제1화`, `001화`, `1장`, `Episode 1` 계열을 우선 인식합니다.

intake는 회차 표기와 같은 줄의 소제목 마커를 `ⓚ`로 통일합니다. `# 제1화`, `#001 소제목`, `제1화 소제목`처럼 `#`이 쓰였거나 마커가 빠진 회차 헤더는 `ⓚ...`로 정규화하고, 숫자 없는 Markdown 제목만 있는 원고는 순서대로 `ⓚ제N화 제목`을 붙입니다. 폴더/EPUB 묶음에서 회차 헤더가 아예 없으면 `ⓚ제N화`를 붙입니다. 본문 안의 독립 소제목은 회차 헤더로 확정되지 않으면 자동으로 고치지 않습니다.

송고 기본 형식은 `ⓚ` 회차/소제목 마커, 제목 아래 빈 줄 3줄, 대사-대사 붙임, 지문-지문 붙임, 대사와 지문 사이 빈 줄 1줄입니다. 직선 따옴표 `""`/`''`는 쓰지 않고 곡선 따옴표 `“”`/`‘’`를 기본으로 씁니다. `inspect-text`와 `analyze-run`은 이 규칙을 `manuscript_format_*` 카운트와 `evidence/review/manuscript_format_flags.jsonl`에 남기며, `normalize-manuscript-format` 명령으로 기본 형식을 적용할 수 있습니다.

하네스는 제목을 유추하고, 작품 폴더와 run 폴더를 만들고, 다음 산출물을 자동 생성합니다.

- `llm-facing/task_brief.md`
- `llm-facing/handoff_checklist.md`
- `llm-facing/adversarial_3pass_brief.md`
- `llm-facing/consistency_rounds/primary_pass*.md`
- `llm-facing/blind_reviews/blind_agent_*_pass*.md`
- `llm-facing/total_consistency_report.md`
- `llm-facing/adversarial_audit_3pass.md`
- `llm-facing/harness_adversarial_audit_3pass.md`
- `llm-facing/episode_deep_dive_brief.md`
- `llm-facing/episode_deep_dive.md`
- `llm-facing/consistency_report.md`
- `llm-facing/editorial_pass_brief.md`
- `llm-facing/contextual_typo_brief.md`
- `llm-facing/correction_plan.md`
- `llm-facing/consistency_correction_loop.md`
- `human-facing/1차_one_page_report.md`
- `human-facing/final_improvement_report.md`
- `human-facing/*_marked_manuscript.hwpx`
- `final_manuscript/final_manuscript.txt`
- `evidence/inspection.json`
- `evidence/episodes/*.txt`
- `evidence/facts/*.jsonl`
- `evidence/facts/chapter_subtitles.jsonl`
- `evidence/facts/timeline_summary.json`
- `evidence/facts/character_title_matrix.json`
- `evidence/review/*.jsonl`
- `evidence/review/chapter_length_flags.jsonl`
- `evidence/review/subtitle_consistency_flags.jsonl`
- `evidence/review/verisimilitude_candidates.jsonl`
- `evidence/review/narrative_allowances.jsonl`
- `evidence/review/ai_slop_signals.json`
- `evidence/review/contextual_typo_candidates.jsonl`
- `evidence/submission/submission_gate.json`
- `evidence/submission/manual_review_queue.jsonl`
- `evidence/submission/manual_review_submission.json`
- `evidence/package/epub_package_qc.json`
- `evidence/package/epub_package_qc.md`

`ai_slop_signals.json`에는 "AI로 쓴 확률"처럼 읽히는 자동 추정치가 들어가지만, 이는 포렌식 판정이 아니라 반복 표현/문장 리듬/추상어 밀도 기반의 **AI 티 위험도**입니다. 같은 값은 `human-facing/1차_one_page_report.md`의 `AI 티 점검` 섹션에도 자동 반영됩니다.

하네스는 자동 후보를 곧바로 확정 오류로 보지 않습니다. 다만 우선순위는 외부 고증보다 작중 핍진성에 둡니다. `오늘 했다`고 쓴 행동이 뒤에서 `오늘 하지 않았다`로 뒤집히거나, 완료된 사건/정산/권한 상태가 원인 없이 회귀하는 문제를 가장 먼저 봅니다. 날짜/요일/은행 영업일 같은 외부 고증은 작중 행동 결과를 흔들 때만 강한 이슈가 됩니다. 작중 뉴스 자막, 로이터/블룸버그 단말기 문구, 문서/보고서 표기, 장르적 과장처럼 소설적 허용으로 방어 가능한 항목은 blocker에서 제외하고 `evidence/review/narrative_allowances.jsonl`에 근거를 남깁니다. 세계관 안에서 세운 제도/기술/경제 규칙은 전제로 수용하고, 맥락 없이 던진 시대 불가능 설정은 `needs_author_decision` 또는 `irreconcilable_premise`로 분리합니다. 숫자, 금액, 시간, 지분, 직함, 완료/미완료 상태 carryover는 장르적 허세보다 엄격하게 봅니다.

윤리선/도덕성 평가는 하네스의 알 바가 아닙니다. 원작 의도 보호가 우선이며, 재난, 사전인지, 응징, 수익화 장면도 주인공을 도덕적으로 재판하지 않습니다. 정합성 근거 없이 죄책감, 기부, 피해자 지원, 제보, 독자 반감 완화, 최소 완충 같은 도덕/수용성 보강을 제안하지 않습니다. 하네스는 정합성, 핍진성, 명시적 인과, 장면 정보 전달만 봅니다.

AI 작성 또는 AI 작성 의심 원고에서는 명시 표지 없는 시간 역류, 장면 접합, 중복 리캡, 정보 상태 회귀를 작가 의도나 회상 장치로 구제하지 않습니다. 본문에 회상/며칠 전/다시 떠올림 같은 장치가 없으면 기본값은 AI 시간축 스플라이스 오류입니다.

## LLM-facing 하네스

`llm-facing/` 산출물은 LLM이 다음 작업을 이어받기 위한 내부 작업면입니다. 여기에는 `task_brief.md`, `handoff_checklist.md`, `adversarial_3pass_brief.md`, `episode_deep_dive_brief.md`가 들어가며, 감리자는 이 문서를 기준으로 primary 전 회차 정합성/맥락 장부 3회, blind 3개 lane x 3회, total 정합성 리포트, 적대적 감리 3회와 화별 수동 딥다이브를 수행합니다. blind lane은 서로의 결과를 읽지 않는 독립 감리로 취급합니다. 하네스 계약 자체가 바뀌면 `llm-facing/harness_adversarial_audit_3pass.md`로 하네스 자체를 3-pass 감리합니다.

LLM-facing 문서는 작가에게 그대로 전달하지 않습니다. 원고 판단, 후보 evidence, 반례, 수동 감리 상태를 모아 LLM과 편집자가 검토하는 중간층이며, 외부 전달물은 `human-facing/` 보고서와 승인된 `final_manuscript/`만 사용합니다.

## 전역 적대적 3-pass 이후 갱신

전역 감리와 적대적 감리 3회를 끝낸 뒤에는 루프 자체가 바뀌었는지 확인하고, 바뀐 경우 이 README를 갱신합니다. 특히 새 명령, 새 산출물, 새 validator 조건, 새 편집/교정 marker, 새 gate가 생겼다면 커밋 전에 README의 빠른 시작, 산출물 목록, 핵심 원칙, 관련 모드 설명을 함께 고칩니다.

작품별 판단이나 특정 원고의 이슈는 README에 쓰지 않습니다. 그런 내용은 해당 run의 `llm-facing/`, `human-facing/`, `corrections/`, `evidence/submission/`에 남깁니다. README는 하네스 운영법과 재현 가능한 계약만 담습니다.

## 핵심 원칙

- 원본 원고는 보존한다.
- 자동 변환은 검수/리포트 보조에만 쓰고, 문장 의미를 바꾸는 교정은 사람이 확인한다.
- 검수와 교정은 분리한다. 검수는 문제와 근거를 남기고, 교정은 변경안과 승인 상태를 남긴다.
- `regex`, `glob`, `rg` 같은 패턴 검색은 파일 찾기와 1차 후보 수집용으로만 최소 사용한다. 최종 판정은 원고 본문, 앞뒤 문단, 앞뒤 회차를 직접 읽고 내린다.
- 리포트는 내부용 raw 판정과 작가/편집자-facing 보고서를 분리한다.
- 최종 보고서는 한국어 human-facing 문서여야 하며, 모든 핵심 판단에는 주장과 근거를 함께 둔다.
- 최종 보고서는 `manual_review_submission.json` 감리 완료와 `validate-submission` 통과 전에는 제출 가능 상태가 될 수 없다.
- `manual_review_submission.json` 완료 상태는 primary 3-pass, blind 3개 lane x 3-pass, total consistency report, adversarial 3-pass가 모두 채워져야 통과한다.
- `manual_review_submission.json`의 `consistency_repetition_contract`는 `정합성 검사 N번` 요청을 기록한다. N이 2 이상이면 완료 unit도 N개여야 한다.
- 회차별 공백 포함 글자수는 4000자 이상을 강한 원칙으로 본다. 4000자 미만 회차는 결락, 중복, 분할 오류, 정본 선택 보류 후보로 먼저 검토한다.
- 정합성 평가와 교정은 반복 루프다. `정합성 평가 -> 교정/편집 batch -> 후보본 적용 -> 정합성 재평가`를 만족 기준까지 반복하고, 각 iteration의 해결/신규/회귀 항목을 남긴다.
- P0/P1은 최종 감리에서 확정, 확신도 95% 이상, 직접 근거 있음, 미해결 반례 없음, 작중 핍진성 영향이 모두 충족된 항목만 사용한다.
- 외부 고증 후보는 작중 행동·상태·인과를 깨뜨리는 경우와 단순 보강 후보를 분리한다.
- 웹소설식 허세와 과장은 결함이 아니며, 반복/독해 실패/수치 또는 상태 carryover 훼손이 있을 때만 수정 후보로 둔다.
- 판단용 마커 검수본은 MD를 기본으로 두고, HWPX 교정 표시는 별도 납품 또는 한글 검토가 필요할 때 사용한다.

## 교정 규칙

이 하네스는 검수뿐 아니라 교정도 할 수 있습니다. 다만 교정은 감리 evidence와 분리해 `corrections/changes.json`에 변경안으로 남기고, 승인된 변경만 `final_manuscript/`나 HWPX export에 반영합니다.

- `ⓐ`: 확정 교정. 오탈자, 띄어쓰기, 조사, 문장부호, 명백한 단어 오기처럼 작가 의도 가능성이 낮은 오류에만 쓴다.
- `ⓐⓐ`: 작가 판단 요청. 인물 말투, 고유명사, 문체 선택, 세계관 용어, 논쟁 가능한 표현처럼 의도 가능성이 있는 항목에 쓴다.
- `operation=replace`: 원문을 교정문 또는 편집문으로 바꾼다.
- `operation=delete`: 원문을 삭제한다. `replace`는 빈 문자열로 둔다.
- `operation=insert_before` / `insert_after`: `find`를 위치 앵커로 삼아 `replace` 텍스트를 앞/뒤에 추가한다.
- 원본 파일은 덮어쓰지 않는다. `inputs/original/`은 보존하고, 최종 후보는 `final_manuscript/` 또는 `최종 원고(output)/`에 둔다.
- 대화문 말투와 캐릭터성은 오탈자처럼 확정 교정하지 않는다.
- 고유명사는 첫 등장과 설정 기준을 확인한 뒤, 불일치 가능성이 있으면 `ⓐⓐ`로 올린다.
- 활자 표준은 `“”`, `‘’`, `…`입니다. 직선 따옴표 `""`, `''`와 세 점 `...`은 송고용 기본값으로 보지 않고, `normalize-typography` 또는 `contextual_typo_candidates.jsonl` 후보로 정리합니다.
- 작가 승인 전 `ⓐⓐ`는 최종 반영하지 않는다. `scripts/apply_blue.py`의 기본 동작도 `ⓐ`만 승인하고 `ⓐⓐ`는 원문 복원하는 쪽이다.
- 교정안은 `validate-changes`를 통과해야 하며, `find`와 `replace`가 같거나 marker가 `ⓐ`/`ⓐⓐ`/빈 값 외이면 실패로 본다.
- 사람이 판단하는 검수본에는 마커가 보여야 한다. 단순 맞춤법/띄어쓰기/문장 호흡은 `ⓐ` 자동승인으로 보고 파란 교정문을 표시하며, 정합성/고증/맥락 수정은 `ⓐ`, 인간 판단이 필요한 항목은 `ⓐⓐ`로 표시한다.

## 편집자 모드

`--mode editor` 또는 `--mode 편집`은 맞춤법 교정이 아니라 적극 편집 단계입니다. 작품의 기대 품질이 AI-slop에 가까울 수 있음을 전제로, 중복 문장, 단조로운 리듬, 추상 감정어 반복, 빠진 인과 브리지, 모바일 가독성 문제를 문장 단위로 고칩니다.

편집자 모드는 `consistency_first_editorial_gate` 뒤에만 실행합니다. 순서는 `primary 정합성 3-pass -> blind 3개 lane x 3-pass -> total 정합성 리포트 -> 적대적 감리 3-pass -> 화별 수동 딥다이브 -> 정합성 리포트 -> 편집자 모드`입니다. 자동 evidence는 후보일 뿐이며, `llm-facing/episode_deep_dive.md`와 `llm-facing/consistency_report.md`에 수동 맥락 독해와 최종 판단이 남은 항목만 `corrections/changes.json`으로 넘깁니다.

기호 보존이 기본값입니다. `ⓚ`, 대괄호 UI, 회차 제목, 특수기호는 삭제하지 않고, 송고 위생 문제인지 작중 장치인지 먼저 판정합니다. 다만 회차 표기 또는 같은 줄 소제목의 마커가 `#`이거나 빠져 있으면 intake에서 `ⓚ`로 통일합니다. 중복 회차가 완전 동일하면 `ⓐ(삭제)` 후보가 될 수 있지만, 비동일 중복은 먼저 `ⓐⓐ(정본 선택)`으로 판단하고 정본 결정 뒤 비정본 블록을 `ⓐ(삭제)` 후보로 올립니다. 정본 후보는 공백 포함 4000자 이상이어야 하며, 삭제 후 남는 회차가 4000자 미만이면 삭제 확정이 아니라 결락/추가/정본 선택 보류로 둡니다.

소제목은 무단 수정하지 않습니다. 회차별 소제목 유무가 들쭉날쭉하면 `evidence/facts/chapter_subtitles.jsonl`과 `evidence/review/subtitle_consistency_flags.jsonl`에 카운트를 남기고, 더 적은 쪽에만 `ⓐⓐ(의견: ...)`을 붙입니다. 소제목 있는 회차가 소수이면 삭제 후보 의견, 소제목 없는 회차가 소수이면 기존 소제목 톤과 길이를 참고한 추가 후보 의견으로 둡니다.

이 모드에서는 삭제와 추가도 정상 작업입니다. 다만 글을 새로 쓰는 단계는 아니므로 플롯, 인물의 결정, POV, 사건 결과, 세계관 사실은 원문 근거 없이 발명하지 않습니다. 말투/문체/장면 호흡을 건드리는 변경은 기본적으로 `ⓐⓐ`로 올려 작가 또는 편집자 승인 후 반영합니다.

편집자 모드의 기본 산출물은 HWP/HWPX가 아니라 plain text입니다. `apply-changes-text`는 `corrections/changes.json`을 `final_manuscript/final_manuscript.txt`에 적용해 `final_manuscript/editorial_candidate.txt`와 `corrections/editorial_diff.md`를 만듭니다. 기본값은 `ⓐ`와 승인 상태의 `ⓐⓐ`만 반영하고, 편집자 권한으로 전체 적극 편집안을 후보본에 넣을 때는 `--accept-aa`를 붙입니다.

루프 중간 확인용으로는 MD 또는 HWPX 기호 적용 원고를 생성합니다. 이 파일은 원문 순서 그대로 `ⓐ{원문|수정}`과 `ⓐⓐ{원문|후보문장}[판단: ...]`을 삽입한 human-facing 판단용 검토본입니다. `ⓐⓐ`는 승인 전 원문에 반영하지 않지만, `ⓐ`와 같은 `{원문|후보}` 비교 구조로 보여 줍니다. 파란색은 승인 시 들어가거나 실행되는 교정문, 후보문장, 판단 사유를 뜻합니다. 클린 후보본과 판단용 마커 검수본은 항상 분리합니다.

표식 수를 셀 때는 `ⓐ` 교정과 `ⓐⓐ` 판단을 반드시 분리합니다. `ⓐ{` 문자열만 단순 검색하면 과거 산출물의 `ⓐⓐ{...}` 안쪽까지 잡힐 수 있으므로, `render-marked-manuscript-md` 또는 `render-marked-manuscript-hwpx` 출력 JSON의 `marker_counts`와 `rendered_marker_counts`를 기준으로 봅니다.

```powershell
python -m novel_qc_loop render-marked-manuscript-md --run-root "workspace\sample-title\runs\RUN_ID" --loop-label loop_01
python -m novel_qc_loop render-marked-manuscript-hwpx --run-root "workspace\sample-title\runs\RUN_ID" --loop-label loop_01
```

문맥형 오타는 패턴형 치환과 분리합니다. 앞뒤 문맥을 읽어야만 보이는 단어 혼입, 호칭 drift, 물건/행동 불일치 후보는 `evidence/review/contextual_typo_candidates.jsonl`에 자동 후보로 올리고, 확정 변경안은 `edit_class=contextual_typo`로 남기며 `reading_basis`와 `context_before`/`context_after` 같은 문맥 근거를 붙입니다. 예를 들어 `제품에+끌어안다`, 펜촉/슬릿 문맥의 `11자의 틈새`, 깨진 따옴표 균형, 직선 따옴표, `...`, `튀어 나왔다` 같은 후보는 자동 evidence가 되지만, 적용 전에는 반드시 주변 문장을 읽습니다. `regex`/`rg` 검색으로 같은 문자열을 더 찾을 수는 있어도, 전체 치환이나 확정 판단은 하지 않습니다. 문맥형 오타를 `ⓐ`로 확정하려면 `confidence_percent` 95 이상이어야 하고, `alternative_interpretation` 또는 `rejection_basis`처럼 대체 해석을 검토하고 버린 이유까지 남겨야 합니다. 의도 가능성이 남으면 `ⓐⓐ`로 둡니다.

편집자 모드 이후에는 별도 표면 교정 루프를 반드시 둡니다. 편집자 모드는 정합성, 중복 삭제, 인과 브리지, AI-slop 정리에 강하지만 오탈자/띄어쓰기/송고용 표기만 따로 훑는 단계가 아니므로, 최종 후보본에 대해 `proofread-pass`를 한 번 더 돌립니다. 이 단계는 `피난 주 -> 피난 중`, `숙식간 -> 순식간`, `고았다 -> 고왔다`, `거 같다 -> 것 같다`, `-지마요 -> -지 마요`처럼 표면 오류와 문맥형 오타를 확인하고, 변경안은 `corrections/loop_N_proofread_changes.json`과 `corrections/loop_N_proofread_diff.md`로 분리합니다. 허용 표기와 문체 판단이 섞이는 `해주다`, `굳어있다`, `추천해주세요` 계열은 스타일 시트가 없으면 일괄 치환하지 않고 잔여 판단으로 남깁니다.

```powershell
python -m novel_qc_loop normalize-typography --input "workspace\sample-title\runs\RUN_ID\final_manuscript\candidate.txt" --output "workspace\sample-title\runs\RUN_ID\final_manuscript\candidate_typography.txt"
```

## 정합성-교정 반복 루프

교정은 한 번 적용하고 끝내지 않습니다. `llm-facing/consistency_correction_loop.md`에 iteration을 쌓으면서 정합성 평가와 교정을 반복합니다.

1. 정합성 평가에서 P0/P1/P2, 중복/정본, 4000자 미달, 문맥형 오타, 회차 경계 문제를 분리합니다.
2. `llm-facing/correction_plan.md`에 교정 batch를 만들고 `corrections/changes.json`에 구조화합니다.
3. `render-marked-manuscript-md`로 원문형 기호 적용 MD 검수본을 `human-facing/`에 생성합니다. 필요하면 `render-marked-manuscript-hwpx`도 함께 생성합니다.
4. `apply-changes-text`로 후보본과 diff를 생성합니다.
5. 같은 회차와 앞뒤 회차를 다시 읽어 해결, 신규, 회귀, 잔여 리스크를 분리합니다.
6. 정합성 루프가 닫힌 후보본에 대해 표면 교정 루프를 별도로 실행합니다.
7. 만족 기준을 통과하면 `human-facing/final_improvement_report.md`에 Before/After, 개선 근거, 잔여 리스크를 정리합니다.

최종 개선 보고서는 “좋아졌다”가 아니라 “무엇이 어떻게 줄었고, 무엇이 아직 작가 판단으로 남았는지”를 보여주는 문서입니다. `validate-report --report`는 최종 개선 보고서로 보이는 파일에 `루프별 개선 이력`과 `누락 금지 이슈`가 비어 있으면 실패합니다. 중복 회차, 정본 선택, 문맥형 오타처럼 작업 중 논의된 핵심 이슈는 최종 상태가 이 섹션에 남아야 합니다.

`validate-report --run-root`는 manifest 또는 최신 `N차_one_page_report.md`를 우선 검증합니다. 기본 1차 SSOT는 `human-facing/1차_one_page_report.md`입니다. 최종 개선 보고서를 납품 대상으로 쓸 때는 아래처럼 파일을 직접 지정해 별도로 검증합니다.

```powershell
python -m novel_qc_loop validate-report --report "workspace\sample-title\runs\RUN_ID\human-facing\final_improvement_report.md"
```

### 교정 예시: 띄어쓰기와 중의성

아래 예시는 모두 최종 문장이 `아버지가 방에 들어가신다`라고 가정할 때의 처리 기준입니다. 다만 `아버지가방`처럼 `아버지 가방`으로도 읽힐 수 있는 경우는 문맥이 확정되지 않으면 `ⓐⓐ`로 올립니다.

| 원문 | 기본 처리 | 교정 후보 | 판단 기준 |
|---|---|---|---|
| `아버지가방에들어가신다` | `ⓐⓐ` | `아버지가 방에 들어가신다` | `아버지가 방에`와 `아버지 가방에`가 모두 가능하므로 문맥 확인 필요. 주변 문맥상 방에 들어가는 상황이 명확하면 `ⓐ`로 승격 가능. |
| `아버지가 방에들어가신다` | `ⓐ` | `아버지가 방에 들어가신다` | `방에/들어가신다` 사이 띄어쓰기 누락이 명백함. |
| `아버지가방에 들어가신다` | `ⓐⓐ` | `아버지가 방에 들어가신다` | `아버지가 방에`인지 `아버지 가방에`인지 중의성이 남음. |
| `아버지가 방 에 들어가신다` | `ⓐ` | `아버지가 방에 들어가신다` | 조사 `에`를 앞말과 붙이는 확정 띄어쓰기 교정. |

`changes.json`에는 아래처럼 남깁니다.

```json
[
  {
    "id": "chg-0001",
    "severity": "P3",
    "status": "proposed",
    "marker": "ⓐ",
    "find": "아버지가 방에들어가신다",
    "replace": "아버지가 방에 들어가신다",
    "reason": "명백한 띄어쓰기 오류",
    "location": "ep_0001"
  },
  {
    "id": "chg-0002",
    "severity": "P3",
    "status": "needs-author",
    "marker": "ⓐⓐ",
    "find": "아버지가방에들어가신다",
    "replace": "아버지가 방에 들어가신다",
    "reason": "문맥상 '방'인지 '가방'인지 확인 필요",
    "location": "ep_0001"
  }
]
```

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
