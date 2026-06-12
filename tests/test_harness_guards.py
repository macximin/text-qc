from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from novel_qc_loop.analyze import contextual_typo_rows_for_line, enrich_fact_row  # noqa: E402
from novel_qc_loop.ai_slop import scan_ai_slop_text  # noqa: E402
from novel_qc_loop.corrections import apply_changes_to_text_file, validate_change_item  # noqa: E402
from novel_qc_loop.delivery import build_final_delivery_package  # noqa: E402
from novel_qc_loop.hwpx_review import render_marked_manuscript_md  # noqa: E402
from novel_qc_loop.intake import begins_with_chapter_marker, extract_hwp5_xml_text  # noqa: E402
from novel_qc_loop.qc import render_qc_html, validate_qc_jsonl_files  # noqa: E402
from novel_qc_loop.reports import (  # noqa: E402
    validate_claim_evidence_tables,
    validate_final_improvement_report_shape,
)
from novel_qc_loop.cli import resolve_one_page_report_path  # noqa: E402
from novel_qc_loop.source_integrity import (  # noqa: E402
    build_sequence_rows,
    detect_blocked_source_issues,
    split_embedded_tail_episode_labels,
)
from novel_qc_loop.protocol import (  # noqa: E402
    AUTHOR_INTENT_PROTECTION_RULE,
    AI_GENERATED_TEXT_CONTINUITY_RULE,
    BLIND_REVIEWERS,
    CANONICAL_NAME_ALIAS_RULE,
    CONSISTENCY_CHECK_UNIT_ID,
    EXCLUDED_REVIEW_SCOPES,
    GATE_PROFILE_CONSISTENCY,
    GATE_PROFILE_CORRECTION,
    GATE_PROFILE_DELIVERY,
    NTH_REPORT_VISIBLE_PRIORITIES,
    PASS_NAMES,
)
from novel_qc_loop.submission import (  # noqa: E402
    build_empty_manual_review_submission,
    build_manual_review_queue,
    validate_manual_review_submission,
)
from novel_qc_loop.workspace import (  # noqa: E402
    find_chapter_markers,
    normalize_chapter_heading_markers,
    normalize_chapter_heading_line,
)


class HarnessGuardTests(unittest.TestCase):
    def test_final_delivery_package_defaults_to_txt_and_human_html(self) -> None:
        with tempfile.TemporaryDirectory(prefix="novel-qc-final-delivery-") as temp_dir:
            run_root = Path(temp_dir)
            final_dir = run_root / "final_manuscript"
            final_dir.mkdir(parents=True)
            final_path = final_dir / "final_manuscript.txt"
            source_path = run_root / "source.txt"
            manuscript = "ⓚ1화\n첫 장면입니다.\n\nⓚ2화\n둘째 장면입니다.\n"
            final_path.write_text(manuscript, encoding="utf-8")
            source_path.write_text(manuscript, encoding="utf-8")
            scan_dir = run_root / "consistency_integrity" / "v100_global_consistency_drift_scan"
            scan_dir.mkdir(parents=True)
            surface_path = scan_dir / "surface.jsonl"
            surface_path.write_text(
                "\n".join(
                    [
                        json.dumps({"term": "대영증권", "count": 2}, ensure_ascii=False),
                        json.dumps({"term": "대한증권", "count": 0}, ensure_ascii=False),
                        json.dumps({"term": "SY텔레콤", "count": 1}, ensure_ascii=False),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            scan_manifest = scan_dir / "global_consistency_drift_scan_manifest_v100.json"
            scan_manifest.write_text(
                json.dumps(
                    {
                        "status": "done",
                        "scan_status": "clean",
                        "active_hold_count": 0,
                        "source_final_raw_match": True,
                        "surface_path": str(surface_path),
                        "validation_total": 3,
                        "validation_valid": 3,
                        "validation_invalid": 0,
                        "test_result": "24 passed",
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            (run_root / "run_manifest.json").write_text(
                json.dumps(
                    {
                        "work_slug": "테스트작",
                        "source_text_path": str(source_path),
                        "final_manuscript_path": str(final_path),
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            result = build_final_delivery_package(
                run_root=run_root,
                version="vtest",
                scan_manifest_path=scan_manifest,
            )

            self.assertEqual("txt", result.manuscript_format)
            self.assertEqual("html", result.report_format)
            self.assertTrue(result.source_final_delivery_match)
            self.assertEqual(2, result.episode_count)
            self.assertTrue(result.marker_sequence_clean)
            manuscript_output = Path(result.manuscript_txt_path)
            report_output = Path(result.human_report_html_path)
            self.assertEqual(".txt", manuscript_output.suffix)
            self.assertEqual(".html", report_output.suffix)
            self.assertEqual(manuscript, manuscript_output.read_text(encoding="utf-8"))
            report_text = report_output.read_text(encoding="utf-8")
            self.assertIn("전체 누적 최종 마감 보고서", report_text)
            self.assertIn("<h2>1. 요약</h2>", report_text)
            self.assertIn("<h2>2. 최종 산출물</h2>", report_text)
            self.assertIn("<h2>6. 정책 판정 상세</h2>", report_text)
            self.assertIn("<h2>8. AI-slop 전역 스캔</h2>", report_text)
            delivery_manifest = json.loads(Path(result.manifest_path).read_text(encoding="utf-8"))
            self.assertEqual("txt", delivery_manifest["default_manuscript_format"])
            self.assertEqual("html", delivery_manifest["default_report_format"])
            self.assertEqual("closing_full", delivery_manifest["report_density"])
            self.assertEqual("cumulative_final_closing_report", delivery_manifest["report_scope"])
            self.assertTrue(delivery_manifest["current_package_sealed"])
            updated_run_manifest = json.loads((run_root / "run_manifest.json").read_text(encoding="utf-8"))
            self.assertEqual("done", updated_run_manifest["final_delivery_status"])
            self.assertEqual("closing_full", updated_run_manifest["final_delivery_report_density"])

    def test_ai_slop_scanner_flags_meta_parenthetical_and_placeholders(self) -> None:
        text = "\n".join(
            [
                "ⓚ제80화",
                "(제 80화 끝)",
                "KD전자(구 한성전자)가 회의실에 걸려 있었다.",
                "Crazy Koreans(미친 한국인들)라는 말은 너무 주석 같다.",
                "A사는 TODO 메모를 남겼다.",
            ]
        )

        result = scan_ai_slop_text(text).to_dict()

        self.assertGreater(result["counts"]["chapter_end_meta"], 0)
        self.assertGreater(result["counts"]["legacy_name_parenthetical"], 0)
        self.assertGreater(result["counts"]["english_parenthetical_gloss"], 0)
        self.assertGreater(result["counts"]["placeholder_surface"], 0)
        self.assertGreater(result["counts"]["internal_memo_surface"], 0)

    def test_final_delivery_splits_policy_watchlist_from_blocking_holds(self) -> None:
        with tempfile.TemporaryDirectory(prefix="novel-qc-hold-split-") as temp_dir:
            run_root = Path(temp_dir)
            final_dir = run_root / "final_manuscript"
            final_dir.mkdir(parents=True)
            manuscript = "ⓚ제1화\n본문.\n"
            final_path = final_dir / "final_manuscript.txt"
            source_path = run_root / "source.txt"
            final_path.write_text(manuscript, encoding="utf-8")
            source_path.write_text(manuscript, encoding="utf-8")
            scan_manifest = run_root / "scan_manifest.json"
            scan_manifest.write_text(
                json.dumps(
                    {
                        "scan_status": "clean",
                        "active_hold_count": 2,
                        "hold_items_untouched": [
                            "policy_choice / 소로스 실명은 유명 실존인물이라 보존",
                            "name_policy / 모델명 보존은 독자-facing 정책 watchlist",
                        ],
                        "validation_total": 1,
                        "validation_valid": 1,
                        "validation_invalid": 0,
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            (run_root / "run_manifest.json").write_text(
                json.dumps(
                    {"source_text_path": str(source_path), "final_manuscript_path": str(final_path)},
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            result = build_final_delivery_package(
                run_root=run_root,
                version="vhold",
                scan_manifest_path=scan_manifest,
            )

            delivery_manifest = json.loads(Path(result.manifest_path).read_text(encoding="utf-8"))
            self.assertEqual(0, delivery_manifest["blocking_hold_count"])
            self.assertEqual(2, delivery_manifest["policy_watchlist_count"])
            self.assertIn("policy_watchlist", Path(result.human_report_html_path).read_text(encoding="utf-8"))

    def test_final_delivery_marks_previous_package_stale_when_hash_changes(self) -> None:
        with tempfile.TemporaryDirectory(prefix="novel-qc-reseal-") as temp_dir:
            run_root = Path(temp_dir)
            final_dir = run_root / "final_manuscript"
            final_dir.mkdir(parents=True)
            final_path = final_dir / "final_manuscript.txt"
            source_path = run_root / "source.txt"
            previous_manifest = run_root / "final_delivery" / "vold_final_approved_package" / "delivery_manifest.json"
            previous_manifest.parent.mkdir(parents=True)
            previous_manifest.write_text(
                json.dumps({"delivery_txt_sha256": "OLD", "created_at": "2026-01-01T00:00:00+00:00"}),
                encoding="utf-8",
            )
            manuscript = "ⓚ제1화\n새 본문.\n"
            final_path.write_text(manuscript, encoding="utf-8")
            source_path.write_text(manuscript, encoding="utf-8")
            (run_root / "run_manifest.json").write_text(
                json.dumps(
                    {
                        "source_text_path": str(source_path),
                        "final_manuscript_path": str(final_path),
                        "final_delivery_manifest_path": str(previous_manifest),
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            result = build_final_delivery_package(run_root=run_root, version="vnew")

            delivery_manifest = json.loads(Path(result.manifest_path).read_text(encoding="utf-8"))
            self.assertTrue(delivery_manifest["previous_delivery_stale"])
            self.assertTrue(delivery_manifest["current_package_sealed"])

    def test_glossary_summary_is_rendered_in_closing_full_report(self) -> None:
        with tempfile.TemporaryDirectory(prefix="novel-qc-glossary-") as temp_dir:
            run_root = Path(temp_dir)
            final_dir = run_root / "final_manuscript"
            final_dir.mkdir(parents=True)
            final_path = final_dir / "final_manuscript.txt"
            source_path = run_root / "source.txt"
            manuscript = "ⓚ제1화\nSY텔레콤이 움직였다.\n"
            final_path.write_text(manuscript, encoding="utf-8")
            source_path.write_text(manuscript, encoding="utf-8")
            glossary_path = run_root / "consistency_integrity" / "v1" / "glossary_current.jsonl"
            glossary_path.parent.mkdir(parents=True)
            glossary_path.write_text(
                json.dumps(
                    {
                        "canonical": "SY텔레콤",
                        "domain": "brand",
                        "policy": "가명 정본",
                        "aliases": ["선우텔레콤"],
                        "forbidden_aliases": ["KS텔레콤"],
                        "residual_forbidden_alias_counts": {"KS텔레콤": 0},
                        "reason": "선우그룹 약칭은 SY로 통일",
                    },
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )
            scan_manifest = run_root / "scan_manifest.json"
            scan_manifest.write_text(
                json.dumps(
                    {"scan_status": "clean", "active_hold_count": 0, "glossary_current_path": str(glossary_path)},
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            (run_root / "run_manifest.json").write_text(
                json.dumps(
                    {"source_text_path": str(source_path), "final_manuscript_path": str(final_path)},
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            result = build_final_delivery_package(
                run_root=run_root,
                version="vglossary",
                scan_manifest_path=scan_manifest,
            )

            report_text = Path(result.human_report_html_path).read_text(encoding="utf-8")
            self.assertIn("SY텔레콤", report_text)
            self.assertIn("가명 정본", report_text)

    def test_lightweight_qc_jsonl_validates_and_renders_html(self) -> None:
        with tempfile.TemporaryDirectory(prefix="novel-qc-jsonl-") as temp_dir:
            root = Path(temp_dir)
            ledger_path = root / "qc_ledger_EP006-015.jsonl"
            output_path = root / "qc_review.html"
            ledger_path.write_text(
                "\n".join(
                    [
                        json.dumps(
                            {
                                "record_type": "issue",
                                "id": "EP006-QC-001",
                                "episode": "006",
                                "type": "name_consistency",
                                "status": "confirmed_error",
                                "ssot_id": "CE-001",
                                "source": "대한증권",
                                "target": "대영증권",
                                "reason": "회사명 맥락상 오기",
                                "action": "replace",
                                "requires_human": False,
                            },
                            ensure_ascii=False,
                        )
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            validation = validate_qc_jsonl_files([ledger_path])
            render_result = render_qc_html(paths=[ledger_path], output_path=output_path)

            self.assertEqual(0, validation.invalid)
            self.assertEqual(1, validation.valid)
            self.assertEqual(1, render_result.total)
            self.assertIn("EP006-QC-001", output_path.read_text(encoding="utf-8"))

    def test_k_heading_does_not_swallow_first_body_line(self) -> None:
        text = "ⓚ제1화\n완벽한 11자의 틈새.\n다음 줄\n"
        markers = find_chapter_markers(text)

        self.assertEqual(1, len(markers))
        self.assertEqual("ⓚ제1화", text[markers[0]["start"] : markers[0]["end"]])
        self.assertNotIn("완벽한 11자의 틈새", text[markers[0]["start"] : markers[0]["end"]])

    def test_chapter_heading_spacing_is_canonicalized(self) -> None:
        self.assertEqual("ⓚ제18화", normalize_chapter_heading_line("ⓚ제 18화"))
        self.assertEqual("ⓚ제18화 소제목", normalize_chapter_heading_line("# 제 18화 - 소제목"))

    def test_plain_number_dot_headings_are_normalized_when_repeated(self) -> None:
        text = "126.\n첫 줄\n127.\n다음 줄\n"
        normalized = normalize_chapter_heading_markers(text)
        markers = find_chapter_markers(normalized)

        self.assertIn("ⓚ126.", normalized)
        self.assertIn("ⓚ127.", normalized)
        self.assertEqual(["126", "127"], [row["episode"] for row in markers])
        self.assertTrue(begins_with_chapter_marker(text))

    def test_source_repair_splits_only_monotonic_embedded_tail_labels(self) -> None:
        text = "\n".join(
            [
                "ⓚ제53화",
                "전 회차의 마지막 문장.54화",
                "다음 회차 첫 줄",
                "다음 회차 마지막 문장.55화",
                "세 번째 회차 첫 줄",
            ]
        )

        repaired, changes = split_embedded_tail_episode_labels(
            text,
            document_name="sample.hwp",
            next_id_start=1,
        )

        self.assertEqual(["053", "054", "055"], [row["base_episode"] for row in build_sequence_rows(repaired)])
        self.assertEqual(2, len(changes))
        self.assertNotIn("문장.54화", repaired)

    def test_hwp_xml_line_break_is_preserved_as_text_newline(self) -> None:
        xml = """<?xml version="1.0" encoding="utf-8"?>
<HwpDoc>
  <BodyText>
    <Paragraph>
      <LineSeg>
        <Text>이건 또 무슨 말이야.</Text>
        <ControlChar name="LINE_BREAK" code="10" kind="CHAR" char="&#10;" />
      </LineSeg>
      <LineSeg>
        <Text>단순한 쿠데타가 아니었단 말인가.</Text>
        <ControlChar name="PARAGRAPH_BREAK" code="13" kind="CHAR" char="&#13;" />
      </LineSeg>
    </Paragraph>
  </BodyText>
</HwpDoc>"""

        text = extract_hwp5_xml_text(xml)

        self.assertEqual("이건 또 무슨 말이야.\n단순한 쿠데타가 아니었단 말인가.", text)

    def test_source_repair_blocks_slash_tail_labels_without_flagging_plain_end_labels(self) -> None:
        text = "\n".join(
            [
                "ⓚ제101화",
                "(제 101화 끝)",
                "ⓚ제102화",
                "(제 /102화(104화)/ 끝)",
            ]
        )

        rows = detect_blocked_source_issues(text, next_id_start=1)

        self.assertEqual(["ambiguous_tail_label"], [row["operation"] for row in rows])
        self.assertEqual(4, rows[0]["line"])

    def test_numeric_gap_candidate_survives_line_break_context_loss(self) -> None:
        rows = contextual_typo_rows_for_line("019", 1, "완벽한 11자의 틈새.")

        self.assertEqual(1, len(rows))
        self.assertEqual("numeric_shape_homograph", rows[0]["subtype"])
        self.assertEqual("P3", rows[0]["severity"])
        self.assertIn("alternative_interpretation", rows[0])
        self.assertIn("rejection_basis", rows[0])

    def test_contextual_signal_cannot_bypass_change_validation(self) -> None:
        issues = validate_change_item(
            1,
            {
                "id": "ctx",
                "operation": "replace",
                "marker": "ⓐ",
                "find": "완벽한 11자의 틈새",
                "replace": "완벽한 일자형 틈새",
                "reason": "교정",
            },
        )

        fields = {str(issue.get("field")) for issue in issues}
        self.assertIn("reading_basis", fields)
        self.assertIn("context", fields)
        self.assertIn("confidence_percent", fields)
        self.assertIn("alternative_interpretation", fields)

    def test_fact_rows_mark_hard_carryover_and_soft_external_fact(self) -> None:
        money = enrich_fact_row({"kind": "money", "episode": "001", "line": 1, "value": "10억 원", "context": "10억 원"})
        era = enrich_fact_row({"kind": "era_or_modern_tone_candidate", "episode": "001", "line": 2, "value": "스마트폰", "context": "스마트폰"})

        self.assertEqual("hard_carryover", money["strictness"])
        self.assertEqual("hard_carryover_conflict", money["disposition_hint"])
        self.assertEqual("soft_external_fact", era["strictness"])
        self.assertEqual("external_fact_soft", era["disposition_hint"])

    def test_final_improvement_report_requires_nonempty_anti_omission_sections(self) -> None:
        text = "\n".join(
            [
                "# 작품 최종 개선 보고서",
                "",
                "## 루프 결과 요약",
                "",
                "## 개선 요약",
                "",
                "## 주요 해결 항목",
                "",
                "## 루프별 개선 이력",
                "",
                "| 루프 | 목적 | 새로 발견한 항목 | 적용/보류 | 개선 근거 |",
                "|---|---|---|---|---|",
                "",
                "## 누락 금지 이슈",
                "",
                "| 이슈 | 최종 상태 | 보고서 반영 문장 | 근거 |",
                "|---|---|---|---|",
                "",
            ]
        )

        issues = validate_final_improvement_report_shape(text)
        codes = [issue["code"] for issue in issues]
        self.assertEqual(["empty_final_report_section", "empty_final_report_section"], codes)

    def test_insert_inside_replacement_span_is_blocked_before_application(self) -> None:
        with tempfile.TemporaryDirectory(prefix="novel-qc-overlap-") as temp_dir:
            root = Path(temp_dir)
            source_path = root / "source.txt"
            changes_path = root / "changes.json"
            output_path = root / "edited.txt"
            diff_path = root / "diff.md"
            source_path.write_text("abcde\n", encoding="utf-8")
            changes_path.write_text(
                json.dumps(
                    [
                        {
                            "id": "replace-all",
                            "marker": "ⓐ",
                            "operation": "replace",
                            "find": "abcde",
                            "replace": "X",
                            "reason": "collapse sample span",
                        },
                        {
                            "id": "insert-inside",
                            "marker": "ⓐ",
                            "operation": "insert_after",
                            "find": "bc",
                            "replace": "Y",
                            "reason": "inner insertion",
                        },
                    ],
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            result = apply_changes_to_text_file(
                source_path=source_path,
                changes_path=changes_path,
                output_path=output_path,
                diff_path=diff_path,
            )

            self.assertEqual("X\n", output_path.read_text(encoding="utf-8"))
            self.assertEqual(1, result.applied)
            self.assertIn("insert-inside", {issue.get("id") for issue in result.issues})

    def test_insert_before_same_replacement_anchor_keeps_boundary_order(self) -> None:
        with tempfile.TemporaryDirectory(prefix="novel-qc-boundary-") as temp_dir:
            root = Path(temp_dir)
            source_path = root / "source.txt"
            changes_path = root / "changes.json"
            output_path = root / "edited.txt"
            diff_path = root / "diff.md"
            source_path.write_text("abcde\n", encoding="utf-8")
            changes_path.write_text(
                json.dumps(
                    [
                        {
                            "id": "replace-anchor",
                            "marker": "ⓐ",
                            "operation": "replace",
                            "find": "abc",
                            "replace": "X",
                            "reason": "replace sample span",
                        },
                        {
                            "id": "insert-before-anchor",
                            "marker": "ⓐ",
                            "operation": "insert_before",
                            "find": "abc",
                            "replace": "A",
                            "reason": "prefix sample span",
                        },
                        {
                            "id": "insert-after-anchor",
                            "marker": "ⓐ",
                            "operation": "insert_after",
                            "find": "abc",
                            "replace": "B",
                            "reason": "suffix sample span",
                        },
                    ],
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            result = apply_changes_to_text_file(
                source_path=source_path,
                changes_path=changes_path,
                output_path=output_path,
                diff_path=diff_path,
            )

            self.assertEqual("AXBde\n", output_path.read_text(encoding="utf-8"))
            self.assertEqual(3, result.applied)

    def test_marked_manuscript_md_shows_reader_facing_markers(self) -> None:
        with tempfile.TemporaryDirectory(prefix="novel-qc-marked-md-") as temp_dir:
            root = Path(temp_dir)
            source_path = root / "source.txt"
            changes_path = root / "changes.json"
            output_path = root / "marked.md"
            source_path.write_text("원문A 문장.\n판단 앵커.\n", encoding="utf-8")
            changes_path.write_text(
                json.dumps(
                    [
                        {
                            "id": "auto-a",
                            "marker": "ⓐ",
                            "operation": "replace",
                            "find": "원문A",
                            "replace": "교정A",
                            "reason": "단순 맞춤법 자동승인",
                            "status": "auto-approved",
                        },
                        {
                            "id": "needs-human",
                            "marker": "ⓐⓐ",
                            "operation": "replace",
                            "find": "판단 앵커",
                            "replace": "판단 후보",
                            "reason": "정본 선택 필요",
                            "status": "needs-author",
                        },
                    ],
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            result = render_marked_manuscript_md(
                source_path=source_path,
                changes_path=changes_path,
                output_path=output_path,
                include_manual_notes=False,
            )
            text = output_path.read_text(encoding="utf-8")

            self.assertIn("ⓐ{원문A|", text)
            self.assertIn("교정A", text)
            self.assertIn("ⓐⓐ{판단 앵커|", text)
            self.assertIn("판단 후보}", text)
            self.assertIn("수정 판단: 정본 선택 필요", text)
            self.assertNotIn("<span", text)
            self.assertEqual(2, result.rendered_changes)

    def test_aa_replace_must_be_applyable_candidate_not_review_memo(self) -> None:
        issues = validate_change_item(
            1,
            {
                "id": "aa-memo-only",
                "marker": "ⓐⓐ",
                "operation": "insert_after",
                "find": "앵커 문장.",
                "replace": "정본 확정 필요. 작가 판단 여부 판단 필요.",
                "reason": "판단 사유",
                "status": "needs-author",
            },
        )

        self.assertIn("replace", {str(issue.get("field")) for issue in issues})

    def test_report_table_requires_claim_when_evidence_exists(self) -> None:
        lines = [
            "| 주장 | 근거 |",
            "|---|---|",
            "|  | 18화 원문 |",
        ]

        pair_count, issues = validate_claim_evidence_tables(lines)

        self.assertEqual(0, pair_count)
        self.assertEqual(["empty_table_claim"], [issue["code"] for issue in issues])

    def test_numbered_one_page_report_is_preferred(self) -> None:
        with tempfile.TemporaryDirectory(prefix="novel-qc-report-") as temp_dir:
            run_root = Path(temp_dir) / "run"
            human_dir = run_root / "human-facing"
            human_dir.mkdir(parents=True)
            (human_dir / "one_page_report.md").write_text("legacy", encoding="utf-8")
            (human_dir / "1차_one_page_report.md").write_text("first", encoding="utf-8")
            (human_dir / "2차_one_page_report.md").write_text("second", encoding="utf-8")

            self.assertEqual(
                human_dir / "2차_one_page_report.md",
                resolve_one_page_report_path(run_root),
            )

    def test_manual_review_scaffold_includes_blind_total_and_non_reader_axis(self) -> None:
        payload = build_empty_manual_review_submission()

        self.assertIn("review_protocol", payload)
        self.assertEqual(GATE_PROFILE_DELIVERY, payload["gate_profile"])
        self.assertEqual(GATE_PROFILE_DELIVERY, payload["review_protocol"]["active_gate_profile"])
        self.assertIn("authority_layers", payload["review_protocol"])
        self.assertIn("gate_profiles", payload["review_protocol"])
        self.assertEqual(CONSISTENCY_CHECK_UNIT_ID, payload["review_protocol"]["consistency_check_unit_id"])
        self.assertEqual(list(NTH_REPORT_VISIBLE_PRIORITIES), payload["review_protocol"]["nth_report_visible_priorities"])
        self.assertIn("누적 장부", payload["review_protocol"]["nth_report_cumulative_rule"])
        self.assertEqual(CONSISTENCY_CHECK_UNIT_ID, payload["consistency_repetition_contract"]["unit_definition"])
        self.assertEqual(1, payload["consistency_repetition_contract"]["requested_unit_count"])
        self.assertIn("non_reader_facing_notes", payload)
        self.assertIn("non_reader_facing_notes", {item["axis"] for item in payload["checked_axes"]})
        self.assertEqual(set(BLIND_REVIEWERS), set(payload["blind_reviews"]))
        for reviewer in BLIND_REVIEWERS:
            self.assertEqual(set(PASS_NAMES), set(payload["blind_reviews"][reviewer]["passes"]))
        self.assertEqual(set(PASS_NAMES), set(payload["adversarial_passes"]))
        self.assertEqual("pending", payload["total_consistency_report"]["status"])

    def test_correction_gate_profile_does_not_require_full_delivery_workflow(self) -> None:
        payload = build_empty_manual_review_submission(GATE_PROFILE_CORRECTION)
        payload["status"] = "complete"
        payload["reviewer"] = "tester"
        payload["reviewed_at"] = "2026-05-21"
        payload["final_summary"] = "교정안과 판단용 마커 검수본 기준 완료"
        for axis in payload["checked_axes"]:
            if axis["axis"] in {"submission_hygiene", "reader_facing_polish", "non_reader_facing_notes"}:
                axis["status"] = "checked"
                axis["notes"] = "profile axis checked"

        result = validate_payload(payload)

        self.assertTrue(result.ready_for_submission)
        self.assertEqual(GATE_PROFILE_CORRECTION, result.gate_profile)
        self.assertEqual(0, result.required_pass_count)
        self.assertEqual(3, result.required_axis_count)

    def test_gate_profile_marks_non_required_queue_tasks_skipped(self) -> None:
        correction_rows = build_manual_review_queue(GATE_PROFILE_CORRECTION)
        consistency_rows = build_manual_review_queue(GATE_PROFILE_CONSISTENCY)

        self.assertTrue(correction_rows)
        self.assertTrue(any(row["required_for_gate"] for row in correction_rows if row["phase"] == "profile_axis_review"))
        self.assertTrue(all(row["status"] == "skipped" for row in correction_rows if row["phase"] == "primary_consistency_review"))
        self.assertFalse(any(row["required_for_gate"] for row in correction_rows if row["phase"] == "blind_consistency_review"))
        self.assertTrue(any(row["required_for_gate"] for row in consistency_rows if row["phase"] == "blind_consistency_review"))

    def test_harness_excludes_ethics_line_as_review_scope(self) -> None:
        payload = build_empty_manual_review_submission()
        excluded_scopes = {item["scope"] for item in payload["review_protocol"]["excluded_review_scopes"]}
        reviewed_axes = {item["axis"] for item in payload["checked_axes"]}

        self.assertIn("ethics_line", excluded_scopes)
        self.assertNotIn("ethics_line", reviewed_axes)
        self.assertIn("윤리선은 하네스 판단 대상이 아니다", EXCLUDED_REVIEW_SCOPES[0]["rule"])
        self.assertIn("정합성 근거 없이", payload["review_protocol"]["author_intent_protection_rule"])
        self.assertIn("독자 반감 완화", AUTHOR_INTENT_PROTECTION_RULE)
        self.assertIn("AI 시간축 스플라이스 오류", payload["review_protocol"]["ai_generated_text_continuity_rule"])
        self.assertIn("작가 의도나 회상 장치로 구제하지 않는다", AI_GENERATED_TEXT_CONTINUITY_RULE)

    def test_harness_treats_aliases_as_canonical_name_candidates(self) -> None:
        payload = build_empty_manual_review_submission()

        self.assertIn("canonical_name_alias_rule", payload["review_protocol"])
        self.assertIn("대표 표기 하나로 통일", payload["review_protocol"]["canonical_name_alias_rule"])
        self.assertIn("약칭, 이니셜, 실명/가명 병기는 자동 허용하지 않고", CANONICAL_NAME_ALIAS_RULE)
        self.assertIn("동일 고유명사", payload["review_protocol"]["premise_policy"])

    def test_complete_submission_requires_blind_total_and_adversarial_workflow(self) -> None:
        payload = build_empty_manual_review_submission()
        payload["status"] = "complete"
        payload["reviewer"] = "tester"
        payload["reviewed_at"] = "2026-05-20"
        payload["final_summary"] = "primary pass만 끝낸 상태"
        for axis in payload["checked_axes"]:
            axis["status"] = "checked"
            axis["notes"] = "checked"
        for pass_name in PASS_NAMES:
            payload["passes"][pass_name] = {
                "status": "completed",
                "notes": [f"{pass_name} done"],
                "completed_task_ids": [f"{pass_name}-all"],
            }

        with tempfile.TemporaryDirectory(prefix="novel-qc-submission-") as temp_dir:
            path = Path(temp_dir) / "manual_review_submission.json"
            path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

            result = validate_manual_review_submission(path)

        self.assertFalse(result.ready_for_submission)
        fields = {str(issue["field"]) for issue in result.issues}
        self.assertIn("total_consistency_report.status", fields)
        self.assertTrue(any(field.startswith("blind_reviews.") for field in fields))
        self.assertTrue(any(field.startswith("adversarial_passes.") for field in fields))

    def test_consistency_check_three_times_means_three_full_units(self) -> None:
        payload = complete_submission_payload()
        payload["consistency_repetition_contract"]["requested_unit_count"] = 3
        payload["consistency_repetition_contract"]["completed_unit_count"] = 1
        payload["consistency_repetition_contract"]["units"] = [
            {
                "unit_id": "unit1",
                "status": "completed",
                "total_report_path": "llm-facing/total_consistency_report.md",
                "notes": ["first unit complete"],
            }
        ]

        result = validate_payload(payload)

        self.assertFalse(result.ready_for_submission)
        self.assertIn(
            "consistency_repetition_contract.completed_unit_count",
            {str(issue["field"]) for issue in result.issues},
        )

    def test_webnovel_allowance_cannot_remain_p1_confirmed_issue(self) -> None:
        payload = complete_submission_payload()
        payload["findings"] = [
            {
                "priority": "P1",
                "status": "confirmed",
                "decision": "confirmed",
                "confidence_percent": 98,
                "original_priority": "P1",
                "final_priority": "P1",
                "category": "장르적 허세",
                "claim": "허세가 과하다",
                "rationale": "웹소설식 과장으로 방어되는 표현",
                "evidence": "원문 근거",
                "story_state_before": "이전 상태",
                "story_state_after": "이후 상태",
                "story_internal_impact": "독자 영향",
                "fix_hint": "과장 완화",
                "reader_risk": "낮음",
                "repairability": "webnovel_allowance",
                "disposition": "genre_hyperbole_allowance",
            }
        ]

        result = validate_payload(payload)

        self.assertFalse(result.ready_for_submission)
        fields = {str(issue["field"]) for issue in result.issues}
        self.assertIn("findings[1].repairability", fields)
        self.assertIn("findings[1].disposition", fields)

    def test_hard_carryover_p1_requires_before_and_after_states(self) -> None:
        payload = complete_submission_payload()
        payload["findings"] = [
            {
                "priority": "P1",
                "status": "confirmed",
                "decision": "confirmed",
                "confidence_percent": 98,
                "original_priority": "P1",
                "final_priority": "P1",
                "category": "숫자 carryover",
                "claim": "70%와 80% 완료 상태가 충돌",
                "rationale": "같은 자산 처리 상태가 뒤집힘",
                "evidence": "원문 근거",
                "story_internal_impact": "핵심 거래 상태가 흔들림",
                "fix_hint": "둘 중 하나로 통일",
                "reader_risk": "중간",
                "disposition": "hard_carryover_conflict",
                "strictness": "hard_carryover",
            }
        ]

        result = validate_payload(payload)

        self.assertFalse(result.ready_for_submission)
        fields = {str(issue["field"]) for issue in result.issues}
        self.assertIn("findings[1].story_state_before", fields)
        self.assertIn("findings[1].story_state_after", fields)


def complete_submission_payload() -> dict[str, object]:
    payload = build_empty_manual_review_submission()
    payload["status"] = "complete"
    payload["reviewer"] = "tester"
    payload["reviewed_at"] = "2026-05-20"
    payload["final_summary"] = "all workflow stages complete"
    for axis in payload["checked_axes"]:
        axis["status"] = "checked"
        axis["notes"] = "checked"
    for pass_map in (payload["passes"], payload["adversarial_passes"]):
        complete_pass_map(pass_map)
    for reviewer in BLIND_REVIEWERS:
        payload["blind_reviews"][reviewer]["status"] = "completed"
        payload["blind_reviews"][reviewer]["notes"] = [f"{reviewer} done"]
        complete_pass_map(payload["blind_reviews"][reviewer]["passes"])
    payload["total_consistency_report"] = {
        "status": "completed",
        "path": "llm-facing/total_consistency_report.md",
        "notes": ["integrated"],
    }
    return payload


def complete_pass_map(pass_map: dict[str, object]) -> None:
    for pass_name in PASS_NAMES:
        pass_map[pass_name] = {
            "status": "completed",
            "notes": [f"{pass_name} done"],
            "completed_task_ids": [f"{pass_name}-all"],
        }


def validate_payload(payload: dict[str, object]):
    with tempfile.TemporaryDirectory(prefix="novel-qc-submission-") as temp_dir:
        path = Path(temp_dir) / "manual_review_submission.json"
        path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        return validate_manual_review_submission(path)


if __name__ == "__main__":
    unittest.main()
