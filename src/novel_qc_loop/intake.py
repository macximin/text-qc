from __future__ import annotations

import posixpath
import re
import shutil
import zipfile
from html import unescape
from urllib.parse import unquote
from xml.etree import ElementTree as ET
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .package_qc import collect_epub_paths, inspect_epub_packages, natural_path_sort_key, write_epub_package_qc
from .submission import write_manual_review_scaffold
from .workspace import create_run, create_work, decode_text_bytes, inspect_text, read_json, read_text_auto, safe_slug, write_json


SUPPORTED_INPUT_SUFFIXES = {".txt", ".text", ".md", ".markdown", ".hwpx", ".epub"}
EPUB_BODY_MEDIA_TYPES = {"application/xhtml+xml", "text/html", "application/xml", "text/xml"}
EPUB_NON_BODY_HINTS = {
    "cover",
    "copyright",
    "landmarks",
    "nav",
    "navigation",
    "notes",
    "titlepage",
    "title-page",
    "toc",
}
EPUB_BLOCK_TAGS = {
    "address",
    "article",
    "aside",
    "blockquote",
    "br",
    "div",
    "figcaption",
    "figure",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "hr",
    "li",
    "p",
    "pre",
    "section",
    "table",
    "td",
    "th",
    "tr",
}
EPUB_SKIP_TAGS = {"head", "script", "style", "svg", "nav", "header", "footer", "aside"}
GENERIC_TITLE_HINTS = {
    "0",
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
    editorial_brief_path: str
    final_manuscript_path: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def read_source_text(path: Path) -> str:
    if path.is_dir():
        return read_epub_collection_text(path)
    suffix = path.suffix.lower()
    if suffix in {".txt", ".text", ".md", ".markdown"}:
        return read_text_auto(path)
    if suffix == ".hwpx":
        return read_hwpx_text(path)
    if suffix == ".epub":
        return read_epub_text(path)
    raise ValueError(f"unsupported input type: {path.suffix}")


def read_epub_collection_text(path: Path) -> str:
    epub_paths = collect_epub_paths(path)
    if not epub_paths:
        raise ValueError(f"EPUB files not found in folder: {path}")
    parts = []
    for index, epub_path in enumerate(epub_paths, start=1):
        body = read_epub_text(epub_path).strip()
        if not body:
            continue
        if not begins_with_chapter_marker(body):
            body = f"{index}화\n{body}"
        parts.append(body)
    if not parts:
        raise ValueError(f"EPUB body text not found in folder: {path}")
    return "\n\n".join(parts)


def begins_with_chapter_marker(text: str) -> bool:
    head = "\n".join(text.splitlines()[:5])
    return bool(
        re.search(
            r"(?im)^\s*(?:ⓚ\d{1,4}|(?:제\s*)?\d{1,4}\s*(?:화|회|장|편|챕터|chapter|ep(?:isode)?)|(?:chapter|ep(?:isode)?)\s*\d{1,4})",
            head,
        )
    )


def read_hwpx_text(path: Path) -> str:
    with zipfile.ZipFile(path, "r") as archive:
        section_names = sorted(
            [name for name in archive.namelist() if re.match(r"^Contents/section\d+\.xml$", name)],
            key=lambda name: int(re.search(r"section(\d+)\.xml$", name).group(1)),
        )
        paragraphs: list[str] = []
        for name in section_names:
            root = ET.fromstring(archive.read(name))
            for elem in root.iter():
                if local_name(elem.tag) == "p":
                    text = "".join(elem.itertext()).strip()
                    if text:
                        paragraphs.append(text)
        if paragraphs:
            return "\n".join(paragraphs)

        if "Preview/PrvText.txt" in archive.namelist():
            preview = decode_text_bytes(archive.read("Preview/PrvText.txt")).strip()
            if preview:
                return preview

        text_parts: list[str] = []
        for name in sorted(archive.namelist()):
            if not name.lower().endswith(".xml"):
                continue
            xml = decode_text_bytes(archive.read(name))
            text_parts.extend(unescape(match) for match in re.findall(r"<hp:t[^>]*>(.*?)</hp:t>", xml, flags=re.DOTALL))
        if text_parts:
            return "\n".join(part.strip() for part in text_parts if part.strip())
    raise ValueError(f"HWPX text not found: {path}")


def read_epub_text(path: Path) -> str:
    with zipfile.ZipFile(path, "r") as archive:
        opf_path = find_epub_opf_path(archive)
        manifest, spine = read_epub_manifest_and_spine(archive, opf_path)
        body_paths = select_epub_body_paths(manifest, spine, strict=True)
        if not body_paths:
            body_paths = select_epub_body_paths(manifest, spine, strict=False)

        text_parts = []
        for item_path in body_paths:
            if item_path not in archive.namelist():
                continue
            doc_text = extract_body_text(decode_text_bytes(archive.read(item_path)))
            if doc_text:
                text_parts.append(doc_text)

        if text_parts:
            return "\n\n".join(text_parts)
    raise ValueError(f"EPUB body text not found: {path}")


def find_epub_opf_path(archive: zipfile.ZipFile) -> str:
    names = archive.namelist()
    if "META-INF/container.xml" in names:
        container = ET.fromstring(archive.read("META-INF/container.xml"))
        for elem in container.iter():
            if local_name(elem.tag) == "rootfile":
                full_path = elem.attrib.get("full-path")
                if full_path:
                    return full_path
    for name in names:
        if name.lower().endswith(".opf"):
            return name
    raise ValueError("EPUB OPF package file not found")


def read_epub_manifest_and_spine(archive: zipfile.ZipFile, opf_path: str) -> tuple[dict[str, dict[str, str]], list[str]]:
    package = ET.fromstring(archive.read(opf_path))
    opf_dir = posixpath.dirname(opf_path)
    manifest: dict[str, dict[str, str]] = {}
    spine: list[str] = []
    for elem in package.iter():
        tag = local_name(elem.tag)
        if tag == "item":
            item_id = elem.attrib.get("id")
            href = elem.attrib.get("href")
            if not item_id or not href:
                continue
            manifest[item_id] = {
                "href": epub_join(opf_dir, href),
                "media_type": elem.attrib.get("media-type", ""),
                "properties": elem.attrib.get("properties", ""),
                "id": item_id,
            }
        elif tag == "itemref":
            idref = elem.attrib.get("idref")
            if idref:
                spine.append(idref)
    return manifest, spine


def select_epub_body_paths(manifest: dict[str, dict[str, str]], spine: list[str], *, strict: bool) -> list[str]:
    paths: list[str] = []
    for idref in spine:
        item = manifest.get(idref)
        if not item:
            continue
        media_type = item.get("media_type", "")
        if media_type and media_type not in EPUB_BODY_MEDIA_TYPES:
            continue
        if "nav" in item.get("properties", "").split():
            continue
        href = item.get("href", "")
        if strict and is_epub_non_body_path(href, item.get("id", "")):
            continue
        paths.append(href)
    return paths


def is_epub_non_body_path(href: str, item_id: str) -> bool:
    target = f"{href}/{item_id}".lower()
    stem = Path(unquote(posixpath.basename(href))).stem.lower()
    return stem in EPUB_NON_BODY_HINTS or any(f"/{hint}" in target or f"{hint}." in target for hint in EPUB_NON_BODY_HINTS)


def epub_join(base_dir: str, href: str) -> str:
    clean_href = unquote(href.split("#", 1)[0])
    return posixpath.normpath(posixpath.join(base_dir, clean_href))


def extract_body_text(document: str) -> str:
    try:
        root = ET.fromstring(document.encode("utf-8"))
        body = first_descendant(root, "body")
        if body is None:
            return ""
        chunks: list[str] = []
        append_element_text(body, chunks)
        return normalize_extracted_text("".join(chunks))
    except ET.ParseError:
        return extract_body_text_fallback(document)


def first_descendant(root: ET.Element, tag_name: str) -> ET.Element | None:
    for elem in root.iter():
        if local_name(elem.tag) == tag_name:
            return elem
    return None


def append_element_text(elem: ET.Element, chunks: list[str]) -> None:
    tag = local_name(elem.tag)
    if tag in EPUB_SKIP_TAGS:
        return
    if tag in EPUB_BLOCK_TAGS:
        chunks.append("\n")
    if elem.text:
        chunks.append(elem.text)
    for child in list(elem):
        append_element_text(child, chunks)
        if child.tail:
            chunks.append(child.tail)
    if tag in EPUB_BLOCK_TAGS:
        chunks.append("\n")


def extract_body_text_fallback(document: str) -> str:
    match = re.search(r"<body\b[^>]*>(.*?)</body>", document, flags=re.IGNORECASE | re.DOTALL)
    if not match:
        return ""
    body = match.group(1)
    body = re.sub(r"<(?:script|style|nav|header|footer|aside)\b.*?</(?:script|style|nav|header|footer|aside)>", "", body, flags=re.IGNORECASE | re.DOTALL)
    body = re.sub(r"<(?:p|div|section|article|h[1-6]|li|br|tr|td|th|blockquote)\b[^>]*>", "\n", body, flags=re.IGNORECASE)
    body = re.sub(r"<[^>]+>", "", body)
    return normalize_extracted_text(body)


def normalize_extracted_text(text: str) -> str:
    lines = []
    for line in unescape(text).splitlines():
        cleaned = re.sub(r"\s+", " ", line).strip()
        if cleaned:
            lines.append(cleaned)
    return "\n".join(lines)


def local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].lower()


def infer_title(path: Path, text: str) -> str:
    stem = path.stem.strip()
    cleaned_stem = _clean_title_candidate(stem)
    if cleaned_stem and not is_generic_title_candidate(cleaned_stem, stem):
        return cleaned_stem

    for raw_line in text.splitlines()[:80]:
        line = _clean_title_candidate(raw_line)
        if not line:
            continue
        if re.fullmatch(r"ⓚ?\d{1,4}", line):
            continue
        if is_chapter_title_candidate(line):
            continue
        if 2 <= len(line) <= 60 and not line.endswith((".", "다", "요", "죠")):
            return line

    return cleaned_stem or "untitled-work"


def _clean_title_candidate(value: str) -> str:
    text = str(value or "").strip()
    text = re.sub(r"^#{1,6}\s*", "", text)
    text = re.sub(r"^(?:제목|작품명|타이틀|title)\s*[:：]\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"^ⓚ\d{3}\s*", "", text)
    text = re.sub(r"\[[^\]]*\]|\([^)]*\)", "", text)
    text = text.replace("_", " ").replace("-", " ")
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"\b(final|draft|source|manuscript)\b", "", text, flags=re.IGNORECASE).strip()
    text = re.sub(r"(최종|수정\s*완|수정본|원고|합본|초기\s*원고)", "", text).strip()
    return re.sub(r"\s+", " ", text)


def is_generic_title_candidate(cleaned: str, original: str) -> bool:
    lowered = cleaned.lower()
    raw_lowered = str(original or "").lower()
    if lowered in GENERIC_TITLE_HINTS:
        return True
    if re.fullmatch(r"\d{1,4}", cleaned) and re.search(r"(합본|원고|draft|source|manuscript)", raw_lowered):
        return True
    return False


def is_chapter_title_candidate(value: str) -> bool:
    return bool(
        re.fullmatch(
            r"(?:제\s*)?\d{1,4}\s*(?:화|회|장|편|챕터|chapter|ep(?:isode)?)(?:[\s.:：_\-].*)?",
            value,
            flags=re.IGNORECASE,
        )
    )


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
        "editor": "editorial-pass",
        "editorial": "editorial-pass",
        "편집": "editorial-pass",
        "편집자": "editorial-pass",
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
    is_epub_collection = input_path.is_dir()
    if is_epub_collection and not any(
        item.is_file() and item.suffix.lower() == ".epub" for item in input_path.iterdir()
    ):
        raise ValueError(f"unsupported input folder: {input_path}")
    if not is_epub_collection and input_path.suffix.lower() not in SUPPORTED_INPUT_SUFFIXES:
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
    if input_path.is_dir():
        collection_dir = original_dir / input_path.name
        collection_dir.mkdir(parents=True, exist_ok=True)
        copied_items = []
        for item in collect_epub_paths(input_path):
            destination = collection_dir / item.name
            shutil.copy2(item, destination)
            copied_items.append({"name": item.name, "path": str(destination), "size": destination.stat().st_size})
        original_path = original_dir / "epub_collection_manifest.json"
        epub_items = [
            {"name": item.name, "path": str(item.resolve()), "size": item.stat().st_size}
            for item in collect_epub_paths(input_path)
        ]
        write_json(
            original_path,
            {
                "schema_version": "epub_collection_manifest.v1",
                "source_folder": str(input_path),
                "epub_count": len(epub_items),
                "items": epub_items,
                "copied_folder": str(collection_dir),
                "copied_items": copied_items,
            },
        )
    else:
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
    package_qc_paths: dict[str, Path] = {}
    if input_path.is_dir() or input_path.suffix.lower() == ".epub":
        package_qc = inspect_epub_packages(input_path)
        package_qc_paths = write_epub_package_qc(package_qc, run_root / "evidence" / "package")

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
    editorial_brief_path = run_root / "llm-facing" / "editorial_pass_brief.md"
    correction_protocol_path = run_root / "corrections" / "marker_protocol.md"
    changes_path = run_root / "corrections" / "changes.json"
    final_readme_path = run_root / "final_manuscript" / "README.md"
    final_manuscript_path = run_root / "final_manuscript" / "final_manuscript.txt"

    _render_file(templates_root / "llm_task_brief.md", llm_task_brief_path, values)
    _render_file(templates_root / "human_facing_one_page.md", one_page_report_path, values)
    _render_file(templates_root / "llm_handoff_checklist.md", checklist_path, values)
    _render_file(templates_root / "adversarial_3pass_brief.md", adversarial_brief_path, values)
    _render_file(templates_root / "editorial_pass_brief.md", editorial_brief_path, values)
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
        "editorial_brief_path": str(editorial_brief_path),
        "correction_protocol_path": str(correction_protocol_path),
        "changes_path": str(changes_path),
        "manual_review_queue_path": str(manual_paths["queue_path"]),
        "manual_review_submission_path": str(manual_paths["submission_path"]),
        "final_manuscript_path": str(final_manuscript_path),
    }
    if package_qc_paths:
        run_manifest["artifacts"]["epub_package_qc_json_path"] = str(package_qc_paths["json_path"])
        run_manifest["artifacts"]["epub_package_qc_markdown_path"] = str(package_qc_paths["markdown_path"])
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
        editorial_brief_path=str(editorial_brief_path),
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
    for path in sorted(inbox_root.iterdir(), key=natural_path_sort_key):
        if path.name.startswith("."):
            continue
        if path.is_dir():
            if not any(item.is_file() and item.suffix.lower() == ".epub" for item in path.iterdir()):
                continue
        elif not path.is_file() or path.suffix.lower() not in SUPPORTED_INPUT_SUFFIXES:
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
