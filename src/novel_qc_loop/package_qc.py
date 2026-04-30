from __future__ import annotations

import json
import re
import zipfile
from collections import Counter
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET


def inspect_epub_packages(input_path: Path) -> dict[str, Any]:
    input_path = input_path.resolve()
    epub_paths = collect_epub_paths(input_path)
    items = [inspect_one_epub(path) for path in epub_paths]
    language_counter = Counter()
    identifier_counter = Counter()
    title_counter = Counter()
    filename_styles = Counter()
    invalid_items = []
    for item in items:
        if not item.get("valid_zip"):
            invalid_items.append(item["path"])
        language_counter.update(tuple(item.get("languages") or [""]))
        identifier_counter.update(tuple(item.get("identifiers") or [""]))
        title_counter.update(tuple(item.get("titles") or [""]))
        filename_styles[item.get("filename_style", "unknown")] += 1

    duplicate_identifiers = [
        {"identifier": identifier, "count": count}
        for identifier, count in identifier_counter.items()
        if identifier and count > 1
    ]
    language_values = [key for key in language_counter if key]
    unique_languages = sorted(language_values)
    mixed_filename_style = len([key for key, count in filename_styles.items() if key and count]) >= 2

    findings = []
    if invalid_items:
        findings.append(
            {
                "priority": "P0",
                "category": "package",
                "claim": "일부 EPUB이 ZIP으로 열리지 않습니다.",
                "evidence": f"{len(invalid_items)}개 파일 실패",
                "confidence": 99,
            }
        )
    if unique_languages == ["en"]:
        findings.append(
            {
                "priority": "P1",
                "category": "metadata",
                "claim": "모든 EPUB의 dc:language가 en입니다.",
                "evidence": f"{len(items)}개 EPUB 모두 language=en",
                "confidence": 99,
                "fix_hint": "한국어 납품이면 ko 또는 납품처 지정 locale로 수정합니다.",
            }
        )
    if duplicate_identifiers:
        top = duplicate_identifiers[0]
        findings.append(
            {
                "priority": "P1",
                "category": "metadata",
                "claim": "EPUB 식별자 UUID가 중복됩니다.",
                "evidence": f"{top['identifier']} = {top['count']}개 파일",
                "confidence": 99,
                "fix_hint": "회차별 고유 dc:identifier를 부여합니다.",
            }
        )
    if mixed_filename_style:
        findings.append(
            {
                "priority": "P3",
                "category": "naming",
                "claim": "EPUB 파일명 규칙이 섞여 있습니다.",
                "evidence": ", ".join(f"{key}:{count}" for key, count in filename_styles.items()),
                "confidence": 99,
                "fix_hint": "납품 규격에 맞춰 파일명 패턴을 통일합니다.",
            }
        )

    return {
        "schema_version": "epub_package_qc.v1",
        "input_path": str(input_path),
        "epub_count": len(items),
        "items": items,
        "summary": {
            "valid_zip_count": sum(1 for item in items if item.get("valid_zip")),
            "mimetype_ok_count": sum(1 for item in items if item.get("mimetype_ok")),
            "language_counter": dict(language_counter),
            "identifier_counter": dict(identifier_counter),
            "title_counter": dict(title_counter),
            "filename_style_counter": dict(filename_styles),
            "duplicate_identifiers": duplicate_identifiers,
            "mixed_filename_style": mixed_filename_style,
        },
        "findings": findings,
    }


def collect_epub_paths(input_path: Path) -> list[Path]:
    if input_path.is_dir():
        paths = sorted(
            (path for path in input_path.iterdir() if path.is_file() and path.suffix.lower() == ".epub"),
            key=natural_path_sort_key,
        )
        if not paths:
            raise ValueError(f"EPUB files not found in folder: {input_path}")
        return paths
    if input_path.is_file() and input_path.suffix.lower() == ".epub":
        return [input_path]
    raise ValueError(f"EPUB file or folder expected: {input_path}")


def natural_path_sort_key(path: Path) -> list[Any]:
    parts = re.split(r"(\d+)", path.name.lower())
    return [int(part) if part.isdigit() else part for part in parts]


def inspect_one_epub(path: Path) -> dict[str, Any]:
    item: dict[str, Any] = {
        "path": str(path),
        "name": path.name,
        "filename_style": classify_filename_style(path.name),
        "valid_zip": False,
        "mimetype_ok": False,
        "opf_path": "",
        "languages": [],
        "identifiers": [],
        "titles": [],
        "spine_count": 0,
        "hangul_internal_path_count": 0,
        "errors": [],
    }
    try:
        with zipfile.ZipFile(path, "r") as archive:
            item["valid_zip"] = True
            names = archive.namelist()
            if "mimetype" in names:
                mimetype = archive.read("mimetype").decode("ascii", errors="replace").strip()
                item["mimetype"] = mimetype
                item["mimetype_ok"] = mimetype == "application/epub+zip"
            item["hangul_internal_path_count"] = sum(1 for name in names if re.search(r"[가-힣]", name))
            opf_path = find_epub_opf_path(archive)
            item["opf_path"] = opf_path
            opf = ET.fromstring(archive.read(opf_path))
            item["languages"] = text_values(opf, "language")
            item["identifiers"] = text_values(opf, "identifier")
            item["titles"] = text_values(opf, "title")
            item["spine_count"] = sum(1 for elem in opf.iter() if local_name(elem.tag) == "itemref")
    except Exception as exc:  # noqa: BLE001 - package audit should continue across broken files.
        item["errors"].append(str(exc))
    return item


def classify_filename_style(name: str) -> str:
    stem = Path(name).stem
    if re.fullmatch(r"_?\d{1,5}", stem):
        return "numeric"
    if re.search(r"\d{1,4}\s*화", stem):
        return "title_episode"
    if re.search(r"[가-힣]", stem):
        return "korean_title"
    return "other"


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


def text_values(root: ET.Element, local_tag: str) -> list[str]:
    values = []
    for elem in root.iter():
        if local_name(elem.tag) == local_tag:
            value = "".join(elem.itertext()).strip()
            if value:
                values.append(value)
    return values


def local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].lower()


def write_epub_package_qc(payload: dict[str, Any], output_dir: Path) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "epub_package_qc.json"
    md_path = output_dir / "epub_package_qc.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    md_path.write_text(render_epub_package_qc_markdown(payload), encoding="utf-8")
    return {"json_path": json_path, "markdown_path": md_path}


def render_epub_package_qc_markdown(payload: dict[str, Any]) -> str:
    summary = payload.get("summary") or {}
    findings = payload.get("findings") or []
    lines = [
        "# EPUB 패키지 QC",
        "",
        f"- 입력: `{payload.get('input_path', '')}`",
        f"- EPUB 수: {payload.get('epub_count', 0)}",
        f"- ZIP 정상: {summary.get('valid_zip_count', 0)}",
        f"- mimetype 정상: {summary.get('mimetype_ok_count', 0)}",
        f"- language 분포: {summary.get('language_counter', {})}",
        f"- 파일명 스타일: {summary.get('filename_style_counter', {})}",
        "",
        "## 확정 이슈",
        "",
    ]
    if not findings:
        lines.append("- 패키징 메타데이터에서 자동 확정 이슈를 찾지 못했습니다.")
    else:
        lines.extend(["| 우선순위 | 문제 | 근거 | 확신 | 처리 방향 |", "|---|---|---|---:|---|"])
        for finding in findings:
            lines.append(
                "| {priority} | {claim} | {evidence} | {confidence}% | {fix_hint} |".format(
                    priority=finding.get("priority", ""),
                    claim=finding.get("claim", ""),
                    evidence=finding.get("evidence", ""),
                    confidence=finding.get("confidence", ""),
                    fix_hint=finding.get("fix_hint", ""),
                )
            )
    lines.extend(["", "## 파일별 샘플", "", "| 파일 | language | identifier | opf |", "|---|---|---|---|"])
    for item in (payload.get("items") or [])[:20]:
        lines.append(
            "| {name} | {lang} | {identifier} | {opf} |".format(
                name=item.get("name", ""),
                lang=", ".join(item.get("languages") or []),
                identifier=", ".join(item.get("identifiers") or [])[:80],
                opf=item.get("opf_path", ""),
            )
        )
    return "\n".join(lines) + "\n"
