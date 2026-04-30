from __future__ import annotations

import re
import shutil
import zipfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .submission import write_manual_review_scaffold
from .workspace import create_run, create_work, inspect_text, read_json, safe_slug, write_json


SUPPORTED_INPUT_SUFFIXES = {".txt", ".md", ".hwpx"}
GENERIC_TITLE_HINTS = {
    "0_합본",
    "합본",
    "원고",
    "초기 원고",
    "initial",
    "manuscript",
    "draft",
    "source",
}


@dataclass(slots=True)
class IntakeResult:
    title: str
    slug: str
    mode: str
    work_root: str
    run_root: str
    original_path: str
    extracted_text_path: str
    one_page_report_path: str
    llm_task_brief_path: str
    final_manuscript_path: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def read_source_text(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in {".txt", ".md"}:
        return path.read_text(encoding="utf-8", errors="replace")
    if suffix == ".hwpx":
        with zipfile.ZipFile(path, "r") as archive:
            try:
                return archive.read("Preview/PrvText.txt").decode("utf-8", errors="replace")
            except KeyError as exc:
                raise ValueError(f"HWPX preview text not found: {path}") from exc
    raise ValueError(f"unsupported input type: {path.suffix}")


def infer_title(path: Path, text: str) -> str:
    stem = path.stem.strip()
    cleaned_stem = _clean_title_candidate(stem)
    if cleaned_stem and cleaned_stem.lower() not in GENERIC_TITLE_HINTS:
        return cleaned_stem

    for raw_line in text.splitlines()[:80]:
        line = _clean_title_candidate(raw_line)
        if not line:
            continue
        if re.fullmatch(r"ⓚ?\d{1,4}", line):
            continue
        if 2 <= len(line) <= 60 and not line.endswith((".", "다", "요", "죠")):
            return line

    return cleaned_stem or "untitled-work"


def _clean_title_candidate(value: str) -> str:
    text = str(value or "").strip()
    text = re.sub(r"^#{1,6}\s*", "", text)
    text = re.sub(r"^ⓚ\d{3}\s*", "", text)
    text = re.sub(r"\[[^\]]*\]|\([^)]*\)", "", text)
    text = text.replace("_", " ").replace("-", " ")
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"\b(final|draft|source|manuscript)\b", "", text, flags=re.IGNORECASE).strip()
    text = re.sub(r"(최종|수정\s*완|수정본|원고|합본|초기\s*원고)", "", text).strip()
    return re.sub(r"\s+", " ", text)


def unique_slug(workspace_root: Path, preferred: str) -> str:
    base = safe_slug(preferred)
    candidate = base
    idx = 2
    while (workspace_root / candidate).exists():
        candidate = f"{base}-{idx}"
        idx += 1
    return candidate


def mode_to_run_kind(mode: str) -> str:
    normalized = safe_slug(mode)
    aliases = {
        "audit": "global-audit",
        "검수": "global-audit",
        "correction": "correction-pass",
        "교정": "correction-pass",
        "full": "full-qc-correction",
        "전체": "full-qc-correction",
    }
    return aliases.get(normalized, normalized or "global-audit")


def render_template(template: str, values: dict[str, Any]) -> str:
    rendered = template
    for key, value in values.items():
        rendered = rendered.replace("{{" + key + "}}", str(value))
    return rendered


def intake_manuscript(
    *,
    input_path: Path,
    workspace_root: Path,
    templates_root: Path,
    mode: str = "full",
    title: str = "",
    slug: str = "",
    author: str = "",
    genre: str = "",
    audience: str = "",
    platform: str = "",
    source_note: str = "",
) -> IntakeResult:
    input_path = input_path.resolve()
    if not input_path.exists():
        raise FileNotFoundError(input_path)
    if input_path.suffix.lower() not in SUPPORTED_INPUT_SUFFIXES:
        raise ValueError(f"unsupported input type: {input_path.suffix}")

    source_text = read_source_text(input_path)
    inferred_title = title.strip() or infer_title(input_path, source_text)
    work_slug = unique_slug(workspace_root, slug or inferred_title)
    work_root = create_work(
        workspace_root=workspace_root,
        slug=work_slug,
        title=inferred_title,
        author=author,
        genre=genre,
        audience=audience,
        platform=platform,
        source_path=str(input_path),
        notes=[note for note in (source_note, "created by intake harness") if note],
    )

    original_dir = work_root / "inputs" / "original"
    original_dir.mkdir(parents=True, exist_ok=True)
    original_path = original_dir / input_path.name
    shutil.copy2(input_path, original_path)

    extracted_dir = work_root / "extracted"
    extracted_dir.mkdir(parents=True, exist_ok=True)
    extracted_text_path = extracted_dir / "source.txt"
    extracted_text_path.write_text(source_text, encoding="utf-8")

    run_kind = mode_to_run_kind(mode)
    run_root = create_run(
        workspace_root=workspace_root,
        work_slug=work_slug,
        kind=run_kind,
        source_text_path=str(extracted_text_path),
        notes=[f"mode={mode}", "created by intake harness"],
    )

    inspection = inspect_text(extracted_text_path)
    write_json(run_root / "evidence" / "inspection.json", inspection.to_dict())
    manual_paths = write_manual_review_scaffold(run_root / "evidence" / "submission")

    values = {
        "title": inferred_title,
        "work_slug": work_slug,
        "run_id": run_root.name,
        "run_root": str(run_root),
        "mode": mode,
        "run_kind": run_kind,
        "genre": genre or "미지정",
        "audience": audience or "미지정",
        "platform": platform or "미지정",
        "source_path": str(input_path),
        "extracted_text_path": str(extracted_text_path),
        "char_count": inspection.char_count,
        "chars_no_space": inspection.chars_no_space,
        "chapter_count": inspection.chapter_count,
        "long_lines_120": inspection.long_lines_120,
        "long_lines_200": inspection.long_lines_200,
        "manual_review_queue_path": str(manual_paths["queue_path"]),
        "manual_review_submission_path": str(manual_paths["submission_path"]),
    }

    llm_task_brief_path = run_root / "llm-facing" / "task_brief.md"
    one_page_report_path = run_root / "human-facing" / "one_page_report.md"
    checklist_path = run_root / "llm-facing" / "handoff_checklist.md"
    adversarial_brief_path = run_root / "llm-facing" / "adversarial_3pass_brief.md"
    correction_protocol_path = run_root / "corrections" / "marker_protocol.md"
    changes_path = run_root / "corrections" / "changes.json"
    final_readme_path = run_root / "final_manuscript" / "README.md"
    final_manuscript_path = run_root / "final_manuscript" / "final_manuscript.txt"

    _render_file(templates_root / "llm_task_brief.md", llm_task_brief_path, values)
    _render_file(templates_root / "human_facing_one_page.md", one_page_report_path, values)
    _render_file(templates_root / "llm_handoff_checklist.md", checklist_path, values)
    _render_file(templates_root / "adversarial_3pass_brief.md", adversarial_brief_path, values)
    _render_file(templates_root / "correction_marker_protocol.md", correction_protocol_path, values)
    _render_file(templates_root / "correction_changes.empty.json", changes_path, values)
    _render_file(templates_root / "final_manuscript_readme.md", final_readme_path, values)
    final_manuscript_path.write_text(source_text, encoding="utf-8")

    run_manifest_path = run_root / "run_manifest.json"
    run_manifest = read_json(run_manifest_path)
    run_manifest["stages"]["01_intake"] = "done"
    run_manifest["artifacts"] = {
        "original_path": str(original_path),
        "extracted_text_path": str(extracted_text_path),
        "inspection_path": str(run_root / "evidence" / "inspection.json"),
        "one_page_report_path": str(one_page_report_path),
        "llm_task_brief_path": str(llm_task_brief_path),
        "adversarial_brief_path": str(adversarial_brief_path),
        "correction_protocol_path": str(correction_protocol_path),
        "changes_path": str(changes_path),
        "manual_review_queue_path": str(manual_paths["queue_path"]),
        "manual_review_submission_path": str(manual_paths["submission_path"]),
        "final_manuscript_path": str(final_manuscript_path),
    }
    write_json(run_manifest_path, run_manifest)

    return IntakeResult(
        title=inferred_title,
        slug=work_slug,
        mode=mode,
        work_root=str(work_root),
        run_root=str(run_root),
        original_path=str(original_path),
        extracted_text_path=str(extracted_text_path),
        one_page_report_path=str(one_page_report_path),
        llm_task_brief_path=str(llm_task_brief_path),
        final_manuscript_path=str(final_manuscript_path),
    )


def intake_inbox(
    *,
    inbox_root: Path,
    workspace_root: Path,
    templates_root: Path,
    mode: str = "full",
    genre: str = "",
    audience: str = "",
    platform: str = "",
) -> list[IntakeResult]:
    if not inbox_root.exists():
        return []

    results: list[IntakeResult] = []
    for path in sorted(inbox_root.iterdir()):
        if not path.is_file() or path.name.startswith("."):
            continue
        if path.suffix.lower() not in SUPPORTED_INPUT_SUFFIXES:
            continue
        results.append(
            intake_manuscript(
                input_path=path,
                workspace_root=workspace_root,
                templates_root=templates_root,
                mode=mode,
                genre=genre,
                audience=audience,
                platform=platform,
            )
        )
    return results


def _render_file(template_path: Path, output_path: Path, values: dict[str, Any]) -> None:
    template = template_path.read_text(encoding="utf-8")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_template(template, values), encoding="utf-8")
