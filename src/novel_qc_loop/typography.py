from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from pathlib import Path


ASCII_ELLIPSIS_RE = re.compile(r"\.{3,}")


@dataclass(slots=True)
class TypographyNormalizationResult:
    input_path: str
    output_path: str
    changed: bool
    straight_double_quotes_before: int
    straight_single_quotes_before: int
    ascii_ellipsis_before: int
    straight_double_quotes_after: int
    straight_single_quotes_after: int
    ascii_ellipsis_after: int
    unicode_ellipsis_after: int

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def normalize_korean_typography_file(*, input_path: Path, output_path: Path) -> TypographyNormalizationResult:
    source_text = input_path.read_text(encoding="utf-8")
    normalized = normalize_korean_typography(source_text)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(normalized, encoding="utf-8")
    return TypographyNormalizationResult(
        input_path=str(input_path),
        output_path=str(output_path),
        changed=source_text != normalized,
        straight_double_quotes_before=source_text.count('"'),
        straight_single_quotes_before=count_style_single_quotes(source_text),
        ascii_ellipsis_before=count_ascii_ellipsis(source_text),
        straight_double_quotes_after=normalized.count('"'),
        straight_single_quotes_after=count_style_single_quotes(normalized),
        ascii_ellipsis_after=count_ascii_ellipsis(normalized),
        unicode_ellipsis_after=normalized.count("…"),
    )


def normalize_korean_typography(text: str) -> str:
    text = normalize_ascii_ellipsis(text)
    text = normalize_straight_quotes(text)
    return text


def normalize_ascii_ellipsis(text: str) -> str:
    def replace(match: re.Match[str]) -> str:
        dot_count = len(match.group(0))
        return "…" * max(1, round(dot_count / 3))

    return ASCII_ELLIPSIS_RE.sub(replace, text)


def normalize_straight_quotes(text: str) -> str:
    result: list[str] = []
    double_open = True
    single_open = True
    for index, char in enumerate(text):
        if char == '"':
            result.append("“" if double_open else "”")
            double_open = not double_open
            continue
        if char == "'" and should_treat_single_quote_as_style_quote(text, index):
            result.append("‘" if single_open else "’")
            single_open = not single_open
            continue
        result.append(char)
    return "".join(result)


def should_treat_single_quote_as_style_quote(text: str, index: int) -> bool:
    prev_char = text[index - 1] if index > 0 else ""
    next_char = text[index + 1] if index + 1 < len(text) else ""
    return not (prev_char.isascii() and prev_char.isalpha() and next_char.isascii() and next_char.isalpha())


def count_style_single_quotes(text: str) -> int:
    return sum(1 for index, char in enumerate(text) if char == "'" and should_treat_single_quote_as_style_quote(text, index))


def count_ascii_ellipsis(text: str) -> int:
    return len(ASCII_ELLIPSIS_RE.findall(text))
