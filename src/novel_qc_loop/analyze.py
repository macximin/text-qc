from __future__ import annotations

import html
import json
import re
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .submission import validate_manual_review_submission, write_manual_review_scaffold
from .workspace import inspect_text, read_json, write_json, write_jsonl


AI_SLOP_TERMS = (
    "그야말로",
    "말 그대로",
    "순식간에",
    "한순간",
    "어느새",
    "숨을 삼켰다",
    "마른침",
    "입을 열었다",
    "시선을 돌렸다",
    "고개를 끄덕였다",
    "침묵이 내려앉았다",
    "완벽한",
    "거대한",
    "차가운",
    "서늘한",
    "압도적인",
)

GENERIC_HYGIENE_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("author_note_marker", re.compile(r"(?m)^\s*@\S+|@\s*(?:부연|추가|메모|수정|확인)")),
    ("slash_swap_marker", re.compile(r"/[^/\n]{1,80}\([^)\n]{1,80}\)/")),
    ("html_entity", re.compile(r"&(?:nbsp|lt|gt|amp|quot|apos|#\d+);")),
    ("markdown_header", re.compile(r"(?m)^#{1,6}\s+\S+")),
    ("stage_cue", re.compile(r"(?m)^\[[^\]\n]{1,160}\]\s*$")),
    ("strike_marker", re.compile(r"<s>.*?</s>|~~[^~]+~~")),
    ("correction_marker", re.compile(r"ⓐⓐ?\{[^|{}]*\|[^{}]*\}")),
)

ABSOLUTE_DATE_RE = re.compile(r"(?P<raw>(?:\d{4}년\s*)?\d{1,2}월\s*\d{1,2}일|\d{4}[./-]\d{1,2}[./-]\d{1,2})")
RELATIVE_TIME_RE = re.compile(r"(?P<raw>오늘|내일|어제|다음 날|그날 밤|며칠 후|몇 시간 후|잠시 후|한 달 후|이틀 뒤|사흘 뒤|보름 뒤|일 년 후)")
DATE_RE = re.compile(
    r"(?P<raw>(?:\d{4}년\s*)?\d{1,2}월\s*\d{1,2}일|"
    r"\d{4}[./-]\d{1,2}[./-]\d{1,2}|"
    r"(?:오늘|내일|어제|다음 날|그날 밤|며칠 후|몇 시간 후|잠시 후|한 달 후|이틀 뒤|사흘 뒤|보름 뒤|일 년 후))"
)
DATE_WITH_WEEKDAY_RE = re.compile(
    r"(?P<raw>(?:\d{4}년\s*)?\d{1,2}월\s*\d{1,2}일\s*(?:월|화|수|목|금|토|일)요일)"
)
TIME_RE = re.compile(r"(?P<raw>(?:오전|오후|새벽|정오|자정)\s*\d{1,2}시(?:\s*\d{1,2}분)?|\d{1,2}:\d{2})")
MONEY_RE = re.compile(r"(?P<raw>\d+(?:\.\d+)?\s*(?:억|조|만|천만|백만)?\s*(?:원|달러|위안|엔|냥|관|전))")
PERCENT_RE = re.compile(r"(?P<raw>\d+(?:\.\d+)?\s*%|\d+(?:\.\d+)?\s*퍼센트)")
TITLE_RE = re.compile(r"(?P<raw>[가-힣A-Za-z0-9]{2,20}\s*(?:회장|대표|팀장|부장|과장|실장|장로|궁주|맹주|소저|공자|도련님|사부|스승|PB))")
AGE_RE = re.compile(r"(?P<raw>\d{1,3}\s*세|약관|이립|불혹|지천명|환갑|고희)")
KIN_TITLE_RE = re.compile(r"(?P<raw>[가-힣A-Za-z0-9]{1,20}\s*(?:아버지|어머니|부친|모친|숙부|숙모|형님|누님|오라버니|동생|사촌|정혼자|장인|장모|사위|며느리|할아버지|할머니))")
SPEAKER_CUE_RE = re.compile(r"(?P<raw>[가-힣A-Za-z0-9]{2,20}(?:이|가|은|는)?\s*(?:말했다|물었다|중얼거렸다|외쳤다|답했다|웃었다|고개를 끄덕였다))")
INLINE_AUTHOR_MEMO_RE = re.compile(r"(?m)(?P<raw>@\s*(?:부연|추가|메모|수정|확인)[^\n]*|^\s*@\S+[^\n]*)")
INLINE_PAREN_ERROR_RE = re.compile(r"(?P<raw>/[^/\n]{1,80}\([^)\n]{1,80}\)/|//[^/\n]{1,120}//)")
ERA_CANDIDATE_RE = re.compile(
    r"(?P<raw>스마트폰|핸드폰|인터넷|온라인|브리핑|쇼|퍼즐|레이저|스파크|타이밍|스위치|스포일러|콤비|갑질|독고다이)"
)
ROLE_SUFFIXES = (
    "회장",
    "대표",
    "팀장",
    "부장",
    "과장",
    "실장",
    "장로",
    "궁주",
    "맹주",
    "소저",
    "공자",
    "도련님",
    "사부",
    "스승",
    "PB",
)


@dataclass(slots=True)
class AnalysisResult:
    source_text_path: str
    inspection_path: str
    episodes_dir: str
    chapter_metrics_path: str
    absolute_dates_path: str
    relative_times_path: str
    dates_path: str
    dates_with_weekday_path: str
    times_path: str
    money_path: str
    percents_path: str
    ages_path: str
    titles_path: str
    kin_titles_path: str
    speaker_cues_path: str
    inline_author_memos_path: str
    inline_paren_errors_path: str
    era_candidates_path: str
    timeline_summary_path: str
    character_title_matrix_path: str
    hygiene_flags_path: str
    ai_slop_path: str
    replay_candidates_path: str
    bridge_candidates_path: str
    submission_gate_path: str
    manual_review_queue_path: str
    manual_review_submission_path: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def analyze_run(*, run_root: Path) -> AnalysisResult:
    manifest_path = run_root / "run_manifest.json"
    manifest = read_json(manifest_path)
    source_text_path = resolve_source_text_path(run_root, str(manifest.get("source_text_path") or ""))
    if not source_text_path.exists():
        raise FileNotFoundError(f"source_text_path not found: {source_text_path}")

    text = source_text_path.read_text(encoding="utf-8", errors="replace")
    chapters = split_chapters(text)

    episodes_dir = run_root / "evidence" / "episodes"
    facts_dir = run_root / "evidence" / "facts"
    review_dir = run_root / "evidence" / "review"
    submission_dir = run_root / "evidence" / "submission"
    episodes_dir.mkdir(parents=True, exist_ok=True)
    facts_dir.mkdir(parents=True, exist_ok=True)
    review_dir.mkdir(parents=True, exist_ok=True)
    submission_dir.mkdir(parents=True, exist_ok=True)
    write_episode_files(episodes_dir, chapters)

    inspection = inspect_text(source_text_path)
    inspection_path = run_root / "evidence" / "inspection.json"
    write_json(inspection_path, inspection.to_dict())

    chapter_metrics_path = facts_dir / "chapter_metrics.jsonl"
    write_jsonl(chapter_metrics_path, build_chapter_metrics(chapters))

    absolute_dates_path = facts_dir / "absolute_dates.jsonl"
    relative_times_path = facts_dir / "relative_times.jsonl"
    dates_path = facts_dir / "dates.jsonl"
    dates_with_weekday_path = facts_dir / "dates_with_weekday.jsonl"
    times_path = facts_dir / "times.jsonl"
    money_path = facts_dir / "money.jsonl"
    percents_path = facts_dir / "percents.jsonl"
    ages_path = facts_dir / "ages.jsonl"
    titles_path = facts_dir / "titles.jsonl"
    kin_titles_path = facts_dir / "kin_titles.jsonl"
    speaker_cues_path = facts_dir / "speaker_cues.jsonl"
    inline_author_memos_path = facts_dir / "inline_author_memos.jsonl"
    inline_paren_errors_path = facts_dir / "inline_paren_errors.jsonl"
    era_candidates_path = review_dir / "era_review_candidates.jsonl"
    timeline_summary_path = facts_dir / "timeline_summary.json"
    character_title_matrix_path = facts_dir / "character_title_matrix.json"
    absolute_date_rows = extract_regex_rows(chapters, ABSOLUTE_DATE_RE, "absolute_date")
    relative_time_rows = extract_regex_rows(chapters, RELATIVE_TIME_RE, "relative_time")
    date_rows = extract_regex_rows(chapters, DATE_RE, "date")
    date_with_weekday_rows = extract_regex_rows(chapters, DATE_WITH_WEEKDAY_RE, "date_with_weekday")
    time_rows = extract_regex_rows(chapters, TIME_RE, "time")
    money_rows = extract_regex_rows(chapters, MONEY_RE, "money")
    percent_rows = extract_regex_rows(chapters, PERCENT_RE, "percent")
    age_rows = extract_regex_rows(chapters, AGE_RE, "age")
    title_rows = extract_regex_rows(chapters, TITLE_RE, "title_or_role")
    kin_title_rows = extract_regex_rows(chapters, KIN_TITLE_RE, "kin_title")
    speaker_cue_rows = extract_regex_rows(chapters, SPEAKER_CUE_RE, "speaker_cue")
    inline_author_memo_rows = extract_regex_rows(chapters, INLINE_AUTHOR_MEMO_RE, "inline_author_memo")
    inline_paren_error_rows = extract_regex_rows(chapters, INLINE_PAREN_ERROR_RE, "inline_paren_error")
    era_candidate_rows = extract_regex_rows(chapters, ERA_CANDIDATE_RE, "era_or_modern_tone_candidate")
    write_jsonl(absolute_dates_path, absolute_date_rows)
    write_jsonl(relative_times_path, relative_time_rows)
    write_jsonl(dates_path, date_rows)
    write_jsonl(dates_with_weekday_path, date_with_weekday_rows)
    write_jsonl(times_path, time_rows)
    write_jsonl(money_path, money_rows)
    write_jsonl(percents_path, percent_rows)
    write_jsonl(ages_path, age_rows)
    write_jsonl(titles_path, title_rows)
    write_jsonl(kin_titles_path, kin_title_rows)
    write_jsonl(speaker_cues_path, speaker_cue_rows)
    write_jsonl(inline_author_memos_path, inline_author_memo_rows)
    write_jsonl(inline_paren_errors_path, inline_paren_error_rows)
    write_jsonl(era_candidates_path, era_candidate_rows)
    write_json(timeline_summary_path, build_timeline_summary(chapters, date_rows, time_rows, relative_time_rows))
    write_json(character_title_matrix_path, build_character_title_matrix(title_rows, kin_title_rows))

    hygiene_flags_path = review_dir / "hygiene_flags.jsonl"
    write_jsonl(hygiene_flags_path, extract_hygiene_flags(chapters))

    ai_slop_path = review_dir / "ai_slop_signals.json"
    write_json(ai_slop_path, build_ai_slop_summary(text))

    replay_candidates_path = review_dir / "replay_candidates.jsonl"
    write_jsonl(replay_candidates_path, build_replay_candidates(chapters))

    bridge_candidates_path = review_dir / "bridge_review_candidates.jsonl"
    write_jsonl(bridge_candidates_path, build_bridge_candidates(chapters))

    manual_paths = write_manual_review_scaffold(submission_dir)
    manual_review_queue_path = manual_paths["queue_path"]
    manual_review_submission_path = manual_paths["submission_path"]

    submission_gate_path = submission_dir / "submission_gate.json"
    write_json(
        submission_gate_path,
        build_submission_gate(
            inspection=inspection.to_dict(),
            hygiene_flags_path=hygiene_flags_path,
            replay_candidates_path=replay_candidates_path,
            bridge_candidates_path=bridge_candidates_path,
            era_candidates_path=era_candidates_path,
            manual_review_submission_path=manual_review_submission_path,
        ),
    )

    manifest.setdefault("artifacts", {})
    manifest["artifacts"].update(
        {
            "chapter_metrics_path": str(chapter_metrics_path),
            "episodes_dir": str(episodes_dir),
            "absolute_dates_path": str(absolute_dates_path),
            "relative_times_path": str(relative_times_path),
            "dates_path": str(dates_path),
            "dates_with_weekday_path": str(dates_with_weekday_path),
            "times_path": str(times_path),
            "money_path": str(money_path),
            "percents_path": str(percents_path),
            "ages_path": str(ages_path),
            "titles_path": str(titles_path),
            "kin_titles_path": str(kin_titles_path),
            "speaker_cues_path": str(speaker_cues_path),
            "inline_author_memos_path": str(inline_author_memos_path),
            "inline_paren_errors_path": str(inline_paren_errors_path),
            "era_candidates_path": str(era_candidates_path),
            "timeline_summary_path": str(timeline_summary_path),
            "character_title_matrix_path": str(character_title_matrix_path),
            "hygiene_flags_path": str(hygiene_flags_path),
            "ai_slop_path": str(ai_slop_path),
            "replay_candidates_path": str(replay_candidates_path),
            "bridge_candidates_path": str(bridge_candidates_path),
            "submission_gate_path": str(submission_gate_path),
            "manual_review_queue_path": str(manual_review_queue_path),
            "manual_review_submission_path": str(manual_review_submission_path),
        }
    )
    if isinstance(manifest.get("stages"), dict):
        manifest["stages"]["02_global_audit"] = "evidence-ready"
    write_json(manifest_path, manifest)

    return AnalysisResult(
        source_text_path=str(source_text_path),
        inspection_path=str(inspection_path),
        episodes_dir=str(episodes_dir),
        chapter_metrics_path=str(chapter_metrics_path),
        absolute_dates_path=str(absolute_dates_path),
        relative_times_path=str(relative_times_path),
        dates_path=str(dates_path),
        dates_with_weekday_path=str(dates_with_weekday_path),
        times_path=str(times_path),
        money_path=str(money_path),
        percents_path=str(percents_path),
        ages_path=str(ages_path),
        titles_path=str(titles_path),
        kin_titles_path=str(kin_titles_path),
        speaker_cues_path=str(speaker_cues_path),
        inline_author_memos_path=str(inline_author_memos_path),
        inline_paren_errors_path=str(inline_paren_errors_path),
        era_candidates_path=str(era_candidates_path),
        timeline_summary_path=str(timeline_summary_path),
        character_title_matrix_path=str(character_title_matrix_path),
        hygiene_flags_path=str(hygiene_flags_path),
        ai_slop_path=str(ai_slop_path),
        replay_candidates_path=str(replay_candidates_path),
        bridge_candidates_path=str(bridge_candidates_path),
        submission_gate_path=str(submission_gate_path),
        manual_review_queue_path=str(manual_review_queue_path),
        manual_review_submission_path=str(manual_review_submission_path),
    )


def resolve_source_text_path(run_root: Path, raw_path: str) -> Path:
    source_path = Path(raw_path).expanduser()
    if source_path.is_absolute():
        return source_path
    candidates = [
        run_root / source_path,
        run_root.parent.parent / source_path,
        Path.cwd() / source_path,
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate.resolve()
    return candidates[0]


def split_chapters(text: str) -> list[dict[str, Any]]:
    marker_matches = list(re.finditer(r"(?m)^ⓚ(\d{3})\s*$", text))
    if marker_matches:
        chapters = []
        for idx, match in enumerate(marker_matches):
            start = match.end()
            end = marker_matches[idx + 1].start() if idx + 1 < len(marker_matches) else len(text)
            chapters.append({"episode": match.group(1), "text": text[start:end], "start_offset": start})
        return chapters

    header_matches = list(re.finditer(r"(?m)^#\s+(.+?)\s*$", text))
    if header_matches:
        chapters = []
        for idx, match in enumerate(header_matches):
            start = match.end()
            end = header_matches[idx + 1].start() if idx + 1 < len(header_matches) else len(text)
            chapters.append({"episode": f"{idx + 1:03d}", "title": match.group(1), "text": text[start:end], "start_offset": start})
        return chapters

    return [{"episode": "001", "text": text, "start_offset": 0}]


def write_episode_files(episodes_dir: Path, chapters: list[dict[str, Any]]) -> None:
    for old_path in episodes_dir.glob("*.txt"):
        old_path.unlink()
    for chapter in chapters:
        episode = safe_episode_name(str(chapter["episode"]))
        (episodes_dir / f"{episode}.txt").write_text(str(chapter["text"]).strip() + "\n", encoding="utf-8")


def safe_episode_name(value: str) -> str:
    cleaned = re.sub(r"[^0-9A-Za-z가-힣_.-]+", "_", value).strip("_.-")
    return cleaned or "episode"


def build_chapter_metrics(chapters: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for chapter in chapters:
        body = str(chapter["text"])
        lines = body.splitlines()
        nonempty = [line for line in lines if line.strip()]
        rows.append(
            {
                "episode": chapter["episode"],
                "chars": len(body),
                "chars_no_space": len(re.sub(r"\s+", "", body)),
                "line_count": len(lines),
                "nonempty_line_count": len(nonempty),
                "long_lines_120": sum(1 for line in nonempty if len(line) >= 120),
                "long_lines_200": sum(1 for line in nonempty if len(line) >= 200),
                "bang_count": body.count("!"),
                "question_count": body.count("?"),
            }
        )
    return rows


def extract_regex_rows(chapters: list[dict[str, Any]], pattern: re.Pattern[str], kind: str) -> list[dict[str, Any]]:
    rows = []
    for chapter in chapters:
        lines = str(chapter["text"]).splitlines()
        for line_no, line in enumerate(lines, start=1):
            for match in pattern.finditer(line):
                rows.append(
                    {
                        "kind": kind,
                        "episode": chapter["episode"],
                        "line": line_no,
                        "value": match.group("raw"),
                        "context": line.strip()[:240],
                    }
                )
    return rows


def build_timeline_summary(
    chapters: list[dict[str, Any]],
    date_rows: list[dict[str, Any]],
    time_rows: list[dict[str, Any]],
    relative_time_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    episode_order = [str(chapter["episode"]) for chapter in chapters]
    counts: dict[str, dict[str, int]] = {
        episode: {"dates": 0, "times": 0, "relative_times": 0}
        for episode in episode_order
    }
    samples: dict[str, list[str]] = {episode: [] for episode in episode_order}
    for key, rows in (("dates", date_rows), ("times", time_rows), ("relative_times", relative_time_rows)):
        for row in rows:
            episode = str(row.get("episode") or "")
            if episode not in counts:
                counts[episode] = {"dates": 0, "times": 0, "relative_times": 0}
                samples[episode] = []
            counts[episode][key] += 1
            if len(samples[episode]) < 5:
                samples[episode].append(str(row.get("value") or ""))

    high_signal = [
        {"episode": episode, **episode_counts, "samples": samples.get(episode, [])}
        for episode, episode_counts in counts.items()
        if sum(episode_counts.values()) >= 4
    ]
    return {
        "schema_version": "timeline_summary.v1",
        "episode_count": len(episode_order),
        "total_dates": len(date_rows),
        "total_times": len(time_rows),
        "total_relative_times": len(relative_time_rows),
        "high_signal_episodes": high_signal,
        "by_episode": counts,
    }


def build_character_title_matrix(title_rows: list[dict[str, Any]], kin_title_rows: list[dict[str, Any]]) -> dict[str, Any]:
    matrix: dict[str, dict[str, Any]] = {}
    for row in title_rows + kin_title_rows:
        raw = str(row.get("value") or "").strip()
        name, role = split_name_role(raw)
        if not name or not role:
            continue
        entry = matrix.setdefault(name, {"roles": Counter(), "samples": []})
        entry["roles"][role] += 1
        if len(entry["samples"]) < 8:
            entry["samples"].append(
                {
                    "role": role,
                    "episode": row.get("episode"),
                    "line": row.get("line"),
                    "context": row.get("context"),
                }
            )

    normalized = {}
    drift_candidates = []
    for name, entry in sorted(matrix.items()):
        roles = dict(entry["roles"])
        normalized[name] = {"roles": roles, "samples": entry["samples"]}
        if len(roles) >= 2:
            drift_candidates.append({"name": name, "roles": roles, "samples": entry["samples"][:3]})
    return {
        "schema_version": "character_title_matrix.v1",
        "character_count": len(normalized),
        "drift_candidate_count": len(drift_candidates),
        "drift_candidates": drift_candidates,
        "characters": normalized,
    }


def split_name_role(raw: str) -> tuple[str, str]:
    compact = re.sub(r"\s+", "", raw)
    for suffix in sorted((*ROLE_SUFFIXES, "아버지", "어머니", "부친", "모친", "숙부", "숙모", "형님", "누님", "오라버니", "동생", "사촌", "정혼자", "장인", "장모", "사위", "며느리", "할아버지", "할머니"), key=len, reverse=True):
        if compact.endswith(suffix) and len(compact) > len(suffix):
            return compact[: -len(suffix)], suffix
    return raw, ""


def extract_hygiene_flags(chapters: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for chapter in chapters:
        lines = str(chapter["text"]).splitlines()
        for line_no, line in enumerate(lines, start=1):
            for kind, pattern in GENERIC_HYGIENE_PATTERNS:
                if pattern.search(line):
                    rows.append(
                        {
                            "kind": kind,
                            "episode": chapter["episode"],
                            "line": line_no,
                            "context": html.unescape(line.strip())[:260],
                        }
                    )
    return rows


def build_ai_slop_summary(text: str) -> dict[str, Any]:
    counts = Counter({term: text.count(term) for term in AI_SLOP_TERMS})
    counts = Counter({term: count for term, count in counts.items() if count})
    total = sum(counts.values())
    density = round(total / max(len(text) / 10000, 1), 3)
    if density >= 15:
        verdict = "High"
    elif density >= 6:
        verdict = "Medium"
    else:
        verdict = "Low"
    return {
        "verdict": verdict,
        "total_hits": total,
        "density_per_10k_chars": density,
        "top_terms": [{"term": term, "count": count} for term, count in counts.most_common(20)],
    }


def build_replay_candidates(chapters: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for prev, curr in zip(chapters, chapters[1:]):
        prev_tail = tail_signal_lines(str(prev["text"]))
        curr_head = head_signal_lines(str(curr["text"]))
        overlap = sorted(set(prev_tail) & set(curr_head))
        if not overlap:
            continue
        rows.append(
            {
                "prev_episode": prev["episode"],
                "episode": curr["episode"],
                "overlap_count": len(overlap),
                "overlap_samples": overlap[:5],
                "review_hint": "회차 경계 리캡인지 편집 잔재인지 확인",
            }
        )
    return rows


def build_bridge_candidates(chapters: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for prev, curr in zip(chapters, chapters[1:]):
        prev_tail = meaningful_tail(str(prev["text"]), limit=5)
        curr_head = meaningful_head(str(curr["text"]), limit=5)
        if not prev_tail or not curr_head:
            continue
        tail_text = " ".join(prev_tail)
        head_text = " ".join(curr_head)
        weak_signals = []
        if len(head_text) < 80:
            weak_signals.append("short_opening")
        if not re.search(r"(다음 날|그날|잠시 후|며칠 후|그 사이|이튿날|새벽|아침|정오|밤)", head_text):
            weak_signals.append("missing_time_anchor")
        if prev_tail[-1][-1:] in {"?", "!", "…"} and not any(sample[:20] in head_text for sample in prev_tail):
            weak_signals.append("cliffhanger_not_picked_up")
        if weak_signals:
            rows.append(
                {
                    "prev_episode": prev["episode"],
                    "episode": curr["episode"],
                    "signals": weak_signals,
                    "prev_tail": prev_tail,
                    "curr_head": curr_head,
                    "review_hint": "회차 사이 시간/장소/감정 브리지가 충분한지 확인",
                }
            )
    return rows


def meaningful_tail(text: str, *, limit: int) -> list[str]:
    lines = normalize_signal_lines(text.splitlines())
    return lines[-limit:]


def meaningful_head(text: str, *, limit: int) -> list[str]:
    lines = normalize_signal_lines(text.splitlines())
    return lines[:limit]


def tail_signal_lines(text: str) -> list[str]:
    return normalize_signal_lines(text.splitlines()[-20:])


def head_signal_lines(text: str) -> list[str]:
    return normalize_signal_lines(text.splitlines()[:20])


def normalize_signal_lines(lines: list[str]) -> list[str]:
    normalized = []
    for line in lines:
        text = re.sub(r"\s+", " ", line).strip()
        if len(text) < 12:
            continue
        if text in {"***", "* * *"}:
            continue
        normalized.append(text[:160])
    return normalized


def build_submission_gate(
    *,
    inspection: dict[str, Any],
    hygiene_flags_path: Path,
    replay_candidates_path: Path,
    bridge_candidates_path: Path,
    era_candidates_path: Path,
    manual_review_submission_path: Path,
) -> dict[str, Any]:
    hygiene_count = count_jsonl_rows(hygiene_flags_path)
    replay_count = count_jsonl_rows(replay_candidates_path)
    bridge_count = count_jsonl_rows(bridge_candidates_path)
    era_count = count_jsonl_rows(era_candidates_path)
    blockers = []
    if int(inspection.get("stage_cues") or 0) > 0:
        blockers.append("stage_cues_present")
    if hygiene_count > 0:
        blockers.append("hygiene_flags_present")
    manual_ready = False
    manual_review: dict[str, Any] | None = None
    if manual_review_submission_path.exists():
        try:
            validation = validate_manual_review_submission(manual_review_submission_path)
            manual_review = validation.to_dict()
            manual_ready = validation.ready_for_submission
        except json.JSONDecodeError:
            blockers.append("manual_review_submission_invalid_json")
    if not manual_ready:
        blockers.append("manual_review_not_complete")
    payload = {
        "schema_version": "submission_gate.v1",
        "ready_for_submission": not blockers,
        "status": "blocked" if blockers else "ready",
        "blockers": blockers,
        "hygiene_flag_count": hygiene_count,
        "replay_candidate_count": replay_count,
        "bridge_candidate_count": bridge_count,
        "era_candidate_count": era_count,
        "manual_review_submission_path": str(manual_review_submission_path),
        "line_quality": {
            "long_lines_120": inspection.get("long_lines_120", 0),
            "long_lines_200": inspection.get("long_lines_200", 0),
        },
    }
    if manual_review is not None:
        payload["manual_review"] = manual_review
    return payload


def count_jsonl_rows(path: Path) -> int:
    if not path.exists():
        return 0
    return sum(1 for line in path.read_text(encoding="utf-8").splitlines() if line.strip())
