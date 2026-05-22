from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .workspace import decode_text_bytes


@dataclass(slots=True)
class AiSlopSignal:
    signal_type: str
    line: int
    text: str
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class AiSlopScanResult:
    input_path: str
    total: int
    counts: dict[str, int]
    examples: list[dict[str, Any]]
    output_path: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


AI_SLOP_PATTERNS: tuple[tuple[str, re.Pattern[str], str], ...] = (
    (
        "chapter_end_meta",
        re.compile(r"\(제\s*\d+\s*화\s*끝\)"),
        "회차 끝 메타 표식은 독자-facing 본문이 아니라 산출물 잔재일 가능성이 높다.",
    ),
    (
        "part_end_meta",
        re.compile(r"\(파트\s*\d+\s*완결\)|\(.*?완결\s*\)"),
        "파트/완결 괄호 표식은 본문 외부 메타 정보일 수 있다.",
    ),
    (
        "legacy_name_parenthetical",
        re.compile(r"[A-Za-z가-힣0-9·]+\(구\s*[^)\n]{1,30}\)"),
        "현재명 뒤 구명을 괄호로 붙이는 표면은 반복되면 설명 주석형 AI-slop이 될 수 있다.",
    ),
    (
        "english_parenthetical_gloss",
        re.compile(r"[A-Za-z][A-Za-z0-9 ,.!?'\-…]{2,80}\([가-힣][^)\n]{1,60}\)"),
        "영어 대사/표현 뒤 한국어 괄호 번역은 문장 리듬을 깨는 주석형 잔재일 수 있다.",
    ),
    (
        "placeholder_surface",
        re.compile(r"(?<![A-Za-z0-9가-힣])[A-D]사(?=$|[\s,.;:!?)]|[은는이가을를과와도에의])|20XX|XX년|OOO|○○"),
        "A/B/C사, XX년, OOO류 표면은 비독자-facing placeholder일 수 있다.",
    ),
    (
        "internal_memo_surface",
        re.compile(r"TODO|FIXME|검수자|편집자\s*메모|작가\s*메모|내부\s*메모|수정\s*필요"),
        "작업자 메모 또는 내부 검수 흔적일 수 있다.",
    ),
    (
        "ai_tool_surface",
        re.compile(r"ChatGPT|GPT-|AI-slop|ai-slop|인공지능이\s*작성"),
        "도구명 또는 AI 작성 흔적이 본문에 남은 후보일 수 있다.",
    ),
)


def scan_ai_slop_text(text: str, *, max_examples_per_type: int = 5) -> AiSlopScanResult:
    counts: dict[str, int] = {}
    examples: list[dict[str, Any]] = []
    lines = text.splitlines()

    for signal_type, pattern, reason in AI_SLOP_PATTERNS:
        signal_count = 0
        example_count = 0
        for line_number, line in enumerate(lines, start=1):
            if not pattern.search(line):
                continue
            matches = pattern.findall(line)
            signal_count += len(matches) if matches else 1
            if example_count < max_examples_per_type:
                examples.append(
                    AiSlopSignal(
                        signal_type=signal_type,
                        line=line_number,
                        text=line.strip(),
                        reason=reason,
                    ).to_dict()
                )
                example_count += 1
        counts[signal_type] = signal_count

    return AiSlopScanResult(
        input_path="",
        total=sum(counts.values()),
        counts=counts,
        examples=examples,
    )


def scan_ai_slop_file(
    input_path: Path,
    *,
    output_path: Path | None = None,
    max_examples_per_type: int = 5,
) -> AiSlopScanResult:
    text = decode_text_bytes(input_path.read_bytes())
    result = scan_ai_slop_text(text, max_examples_per_type=max_examples_per_type)
    result.input_path = str(input_path)

    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        lines = [json.dumps(item, ensure_ascii=False) for item in result.examples]
        output_path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
        result.output_path = str(output_path)
    return result
