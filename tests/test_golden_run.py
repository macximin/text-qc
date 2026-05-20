from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from novel_qc_loop.analyze import analyze_run  # noqa: E402
from novel_qc_loop.workspace import read_text_auto  # noqa: E402


FIXTURE = ROOT / "tests" / "fixtures" / "golden_manuscript.txt"


class GoldenRunTests(unittest.TestCase):
    def test_analyze_run_golden_manuscript_keeps_guard_signals(self) -> None:
        with tempfile.TemporaryDirectory(prefix="novel-qc-golden-") as temp_dir:
            run_root = Path(temp_dir) / "golden-work" / "runs" / "run1"
            run_root.mkdir(parents=True)
            source_path = run_root / "source.txt"
            source_path.write_text(read_text_auto(FIXTURE), encoding="utf-8")
            (run_root / "run_manifest.json").write_text(
                json.dumps(
                    {
                        "source_text_path": str(source_path),
                        "artifacts": {},
                        "stages": {},
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            result = analyze_run(run_root=run_root)

            candidates = read_jsonl(Path(result.contextual_typo_candidates_path))
            subtypes = {row["subtype"] for row in candidates}
            self.assertIn("numeric_shape_homograph", subtypes)
            self.assertIn("surface_typo", subtypes)
            self.assertIn("surface_spacing", subtypes)
            self.assertIn("ascii_ellipsis", subtypes)
            self.assertIn("quote_balance", subtypes)

            by_value = {row["value"]: row for row in candidates}
            self.assertEqual("일자형 틈새", by_value["11자의 틈새"]["suggested_replace"])
            self.assertEqual("순식간", by_value["숙식간"]["suggested_replace"])
            self.assertEqual("피난 중", by_value["피난 주"]["suggested_replace"])
            self.assertEqual("책임의 무게", by_value["책임의무게"]["suggested_replace"])
            self.assertEqual("말하지 마요", by_value["말하지마요"]["suggested_replace"])

            episode_018 = (run_root / "evidence" / "episodes" / "018.txt").read_text(encoding="utf-8")
            self.assertIn("양쪽으로 벌어진 슬릿을 맞췄다.", episode_018)
            self.assertIn("완벽한 11자의 틈새.", episode_018)

            gate = json.loads(Path(result.submission_gate_path).read_text(encoding="utf-8"))
            self.assertEqual(len(candidates), gate["contextual_typo_candidate_count"])

            submission = json.loads(Path(result.manual_review_submission_path).read_text(encoding="utf-8"))
            self.assertIn("blind_reviews", submission)
            self.assertIn("total_consistency_report", submission)
            self.assertIn("adversarial_passes", submission)
            self.assertIn("non_reader_facing_notes", submission)

            manifest = json.loads((run_root / "run_manifest.json").read_text(encoding="utf-8"))
            self.assertIn("contextual_typo_candidates_path", manifest["artifacts"])
            self.assertTrue(Path(manifest["artifacts"]["contextual_typo_candidates_path"]).exists())


def read_jsonl(path: Path) -> list[dict[str, object]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


if __name__ == "__main__":
    unittest.main()
