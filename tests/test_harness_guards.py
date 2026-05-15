from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from novel_qc_loop.analyze import contextual_typo_rows_for_line  # noqa: E402
from novel_qc_loop.corrections import validate_change_item  # noqa: E402
from novel_qc_loop.reports import validate_final_improvement_report_shape  # noqa: E402
from novel_qc_loop.workspace import find_chapter_markers, normalize_chapter_heading_line  # noqa: E402


class HarnessGuardTests(unittest.TestCase):
    def test_k_heading_does_not_swallow_first_body_line(self) -> None:
        text = "ⓚ제1화\n완벽한 11자의 틈새.\n다음 줄\n"
        markers = find_chapter_markers(text)

        self.assertEqual(1, len(markers))
        self.assertEqual("ⓚ제1화", text[markers[0]["start"] : markers[0]["end"]])
        self.assertNotIn("완벽한 11자의 틈새", text[markers[0]["start"] : markers[0]["end"]])

    def test_chapter_heading_spacing_is_canonicalized(self) -> None:
        self.assertEqual("ⓚ제18화", normalize_chapter_heading_line("ⓚ제 18화"))
        self.assertEqual("ⓚ제18화 소제목", normalize_chapter_heading_line("# 제 18화 - 소제목"))

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


if __name__ == "__main__":
    unittest.main()
