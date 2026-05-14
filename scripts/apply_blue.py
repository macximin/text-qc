"""
HWPX 파란색 수정 표시 스크립트
용도: HWPX 파일에서 지정한 텍스트를 파란색(#0000FF)으로 바꿔 새 파일로 저장

사용법:
  # 단일 교체 (마커 없이 교정문만 파란색)
  python3 apply_blue.py --input 원본.hwpx --output 수정본.hwpx --find "원래 텍스트" --replace "수정 텍스트"

  # 여러 교체 (JSON 파일)
  python3 apply_blue.py --input 원본.hwpx --output 수정본.hwpx --changes changes.json

  # 텍스트만 읽기 (수정 없이)
  python3 apply_blue.py --input 원본.hwpx --read-only

changes.json 형식:
  [
    {"operation": "replace", "find": "반증", "replace": "방증", "marker": "ⓐ"},
    {"operation": "delete", "find": "반복 문장", "replace": "", "marker": "ⓐⓐ"},
    {"operation": "insert_after", "find": "앵커 문장.", "replace": " 추가 문장.", "marker": "ⓐⓐ"},
    {"find": "반증", "replace": "방증"}  # operation 생략 시 replace, replace가 빈 문자열이면 delete
  ]
"""

import zipfile
import re
import json
import argparse
import os
import sys
from html import escape as xml_escape
from xml.etree import ElementTree as ET


SECTION_RE = re.compile(r'^Contents/section(\d+)\.xml$')
ALLOWED_OPERATIONS = {"replace", "delete", "insert_before", "insert_after"}


def section_sort_key(name):
    match = SECTION_RE.match(name)
    return int(match.group(1)) if match else 0


def get_section_names(files):
    """HWPX 본문 section XML 목록을 문서 순서대로 반환."""
    names = [name for name in files if SECTION_RE.match(name)]
    return sorted(names, key=section_sort_key)


def read_hwpx_text(filepath):
    """HWPX 본문 section 전체에서 텍스트 추출."""
    with zipfile.ZipFile(filepath, 'r') as z:
        names = sorted(
            [name for name in z.namelist() if SECTION_RE.match(name)],
            key=section_sort_key,
        )
        paragraphs = []
        for name in names:
            root = ET.fromstring(z.read(name))
            for elem in root.iter():
                if elem.tag.endswith('}p') or elem.tag == 'p':
                    text = ''.join(elem.itertext()).strip()
                    if text:
                        paragraphs.append(text)
        if paragraphs:
            return '\n'.join(paragraphs)

        if "Preview/PrvText.txt" in z.namelist():
            with z.open('Preview/PrvText.txt') as f:
                return f.read().decode('utf-8', errors='ignore')

    return ""


def read_all_files(filepath):
    """HWPX 내부 파일 전체 읽기"""
    files = {}
    with zipfile.ZipFile(filepath, 'r') as z:
        for name in z.namelist():
            files[name] = z.read(name)
    return files


def get_max_charpr_id(header_xml):
    """header.xml에서 현재 최대 charPr id 반환"""
    ids = re.findall(r'<hh:charPr id="(\d+)"', header_xml)
    return max(int(i) for i in ids) if ids else 0


def add_blue_charpr(header_xml, base_id, blue_id):
    """
    base_id charPr를 복사해서 blue_id로 파란색 버전 추가.
    itemCnt도 1 증가시킴.
    """
    # base_id charPr 전체 블록 추출
    pattern = rf'<hh:charPr id="{base_id}".*?</hh:charPr>'
    match = re.search(pattern, header_xml, re.DOTALL)
    if not match:
        raise ValueError(f"charPr id={base_id}를 header.xml에서 찾을 수 없습니다.")

    original_block = match.group(0)

    # 파란색 버전 생성
    blue_block = original_block.replace(f'id="{base_id}"', f'id="{blue_id}"')
    blue_block = re.sub(r'textColor="[^"]*"', 'textColor="#0000FF"', blue_block)

    # charProperties 블록의 맨 끝에 삽입 (id 순서와 position 순서 일치시키기 위함)
    # 한글 Office는 charPr를 position 순서로 읽는 경향이 있어서 id=N 블록은 N번째 위치에 있어야 함
    header_xml = header_xml.replace('</hh:charProperties>', blue_block + '</hh:charProperties>', 1)

    # charProperties의 itemCnt만 1 증가 (fontfaces 등 다른 itemCnt 건드리지 않기)
    header_xml = re.sub(
        r'(<hh:charProperties itemCnt=")(\d+)(")',
        lambda m: f'{m.group(1)}{int(m.group(2)) + 1}{m.group(3)}',
        header_xml,
        count=1
    )

    return header_xml


def find_charpr_id_for_text(section_xml, text):
    """특정 텍스트를 감싸는 run의 charPrIDRef 반환"""
    # 텍스트가 포함된 run 블록 찾기
    escaped = re.escape(text)
    pattern = rf'<hp:run charPrIDRef="(\d+)"><hp:t>[^<]*{escaped}[^<]*</hp:t></hp:run>'
    match = re.search(pattern, section_xml)
    if match:
        return int(match.group(1))

    # 정확히 일치하는 버전
    pattern2 = rf'<hp:run charPrIDRef="(\d+)"><hp:t>{escaped}</hp:t></hp:run>'
    match2 = re.search(pattern2, section_xml)
    if match2:
        return int(match2.group(1))

    return None


def apply_change(section_xml, change, blue_id):
    """section_xml에서 find_text를 찾아 교정을 적용.

    change 딕셔너리 형식:
      - find (필수): 원문에서 찾을 텍스트
      - replace (필수): 교정된 텍스트
      - operation (선택): replace/delete/insert_before/insert_after
      - marker (선택): "ⓐ" 또는 "ⓐⓐ" — 지정 시 본문에 ⓐ{원문|교정} 마커 삽입
                      (교정문 부분만 파란색, 마커와 원문 부분은 검정)
                      미지정 시 기존 동작: 교정문만 파란색으로 단순 교체

    수정된 부분만 파란색이 되도록 run을 [before|changed(blue)|after] 형태로 분할한다.
    """
    find_text = change['find']
    replace_text = change['replace']
    marker = change.get('marker', '')
    operation = change.get('operation') or ('delete' if replace_text == '' else 'replace')
    if operation not in ALLOWED_OPERATIONS:
        return section_xml, False

    safe_find_text = xml_escape(find_text, quote=False)
    safe_replace_text = xml_escape(replace_text, quote=False)

    run_pattern = re.compile(r'<hp:run charPrIDRef="(\d+)"><hp:t>([^<]*)</hp:t></hp:run>')

    for m in run_pattern.finditer(section_xml):
        base_id = m.group(1)
        text = m.group(2)

        # 이미 마커 처리된 run은 건너뛴다 (중첩 방지)
        # - 파란색 run: 이전 교정에서 생성된 교정문
        # - 마커 prefix: "ⓐ{...|" 또는 "ⓐⓐ{...|" 를 포함하는 run
        # - 마커 suffix: "}" 로 시작하는 run
        if int(base_id) == blue_id:
            continue
        if 'ⓐ{' in text or 'ⓐⓐ{' in text:
            continue
        if text == '}':
            continue

        idx = text.find(find_text)
        if idx < 0:
            continue

        before = text[:idx]
        anchor = text[idx:idx + len(find_text)]
        after = text[idx + len(find_text):]

        if operation in {'replace', 'delete'} and marker:
            # 마커 모드: "ⓐ{원문|" (검정) + "교정문" (파랑) + "}" (검정)
            full_before = before + f'{marker}{{{safe_find_text}|'
            blue_part = safe_replace_text
            full_after = '}' + after
        elif operation in {'replace', 'delete'}:
            full_before = before
            blue_part = safe_replace_text
            full_after = after
        elif operation == 'insert_after' and marker:
            # 추가 마커: "앵커ⓐ{|" (검정) + "추가문" (파랑) + "}" (검정)
            full_before = before + anchor + f'{marker}{{|'
            blue_part = safe_replace_text
            full_after = '}' + after
        elif operation == 'insert_after':
            full_before = before + anchor
            blue_part = safe_replace_text
            full_after = after
        elif operation == 'insert_before' and marker:
            full_before = before + f'{marker}{{|'
            blue_part = safe_replace_text
            full_after = '}' + anchor + after
        else:
            full_before = before
            blue_part = safe_replace_text
            full_after = anchor + after

        parts = []
        if full_before:
            parts.append(f'<hp:run charPrIDRef="{base_id}"><hp:t>{full_before}</hp:t></hp:run>')
        if blue_part or marker:
            parts.append(f'<hp:run charPrIDRef="{blue_id}"><hp:t>{blue_part}</hp:t></hp:run>')
        if full_after:
            parts.append(f'<hp:run charPrIDRef="{base_id}"><hp:t>{full_after}</hp:t></hp:run>')

        new_block = ''.join(parts)
        section_xml = section_xml[:m.start()] + new_block + section_xml[m.end():]
        return section_xml, True

    return section_xml, False


def save_hwpx(files, output_path):
    """파일 딕셔너리를 HWPX(ZIP)로 저장"""
    section_count = len(get_section_names(files))
    if section_count and 'Contents/header.xml' in files:
        header_xml = files['Contents/header.xml'].decode('utf-8')
        header_xml = re.sub(r'secCnt="\d+"', f'secCnt="{section_count}"', header_xml, count=1)
        files['Contents/header.xml'] = header_xml.encode('utf-8')

    with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zout:
        if 'mimetype' in files:
            zout.writestr('mimetype', files['mimetype'], compress_type=zipfile.ZIP_STORED)
        for name, data in files.items():
            if name == 'mimetype':
                continue
            zout.writestr(name, data)


def finalize_markers(section_xml, accept_aa=False):
    """본문에 삽입된 ⓐ/ⓐⓐ 마커를 일괄 정리한다.

    처리 규칙:
      - ⓐ: 항상 strip — 마커와 원문 제거, 교정문(파란색) 유지
      - ⓐⓐ:
          accept_aa=True  → ⓐ와 동일 (strip, 교정문 유지)
          accept_aa=False → 원문 복원 — 마커와 교정문 제거, 원문을 검정으로 되돌림

    마커 구조: [검정 run: "...ⓐ{원문|" or "...ⓐⓐ{원문|"]
               [파란 run: "교정문"]
               [검정 run: "}..."]
    """
    # 마커 세 개 run을 매칭하는 패턴
    pattern = re.compile(
        r'<hp:run charPrIDRef="(\d+)"><hp:t>([^<]*?)(ⓐⓐ|ⓐ)\{([^|<]*)\|</hp:t></hp:run>'
        r'<hp:run charPrIDRef="(\d+)"><hp:t>([^<]*)</hp:t></hp:run>'
        r'<hp:run charPrIDRef="(\d+)"><hp:t>\}([^<]*)</hp:t></hp:run>'
    )

    stats = {'alpha_stripped': 0, 'alphaalpha_accepted': 0, 'alphaalpha_rejected': 0}

    while True:
        m = pattern.search(section_xml)
        if not m:
            break

        prefix_id = m.group(1)
        prefix_text = m.group(2)
        marker_type = m.group(3)
        original = m.group(4)
        blue_run_id = m.group(5)
        correction = m.group(6)
        suffix_id = m.group(7)
        suffix_text = m.group(8)

        reject = (marker_type == 'ⓐⓐ' and not accept_aa)

        parts = []
        if reject:
            # 원문 복원: 앞·원문·뒤를 하나의 검정 run으로 병합
            merged = prefix_text + original + suffix_text
            if merged:
                parts.append(f'<hp:run charPrIDRef="{prefix_id}"><hp:t>{merged}</hp:t></hp:run>')
            stats['alphaalpha_rejected'] += 1
        else:
            # accept (strip marker, keep correction in blue)
            if prefix_text:
                parts.append(f'<hp:run charPrIDRef="{prefix_id}"><hp:t>{prefix_text}</hp:t></hp:run>')
            parts.append(f'<hp:run charPrIDRef="{blue_run_id}"><hp:t>{correction}</hp:t></hp:run>')
            if suffix_text:
                parts.append(f'<hp:run charPrIDRef="{suffix_id}"><hp:t>{suffix_text}</hp:t></hp:run>')
            if marker_type == 'ⓐ':
                stats['alpha_stripped'] += 1
            else:
                stats['alphaalpha_accepted'] += 1

        new_block = ''.join(parts)
        section_xml = section_xml[:m.start()] + new_block + section_xml[m.end():]

    return section_xml, stats


def main():
    parser = argparse.ArgumentParser(description='HWPX 파란색 수정 표시 도구')
    parser.add_argument('--input', required=True, help='입력 HWPX 파일 경로')
    parser.add_argument('--output', help='출력 HWPX 파일 경로 (기본: 원본명_수정.hwpx)')
    parser.add_argument('--find', help='찾을 텍스트')
    parser.add_argument('--replace', help='바꿀 텍스트')
    parser.add_argument(
        '--operation',
        choices=sorted(ALLOWED_OPERATIONS),
        help='단일 변경 operation: replace/delete/insert_before/insert_after',
    )
    parser.add_argument('--changes', help='여러 변경사항 JSON 파일 경로')
    parser.add_argument('--read-only', action='store_true', help='텍스트만 출력하고 종료')
    parser.add_argument('--finalize', action='store_true', help='마커 정리 모드: ⓐ는 strip, ⓐⓐ는 --accept-aa/--reject-aa로 처리')
    parser.add_argument('--accept-aa', action='store_true', help='--finalize 시 ⓐⓐ도 accept (strip, 교정문 유지)')
    parser.add_argument('--reject-aa', action='store_true', help='--finalize 시 ⓐⓐ를 reject (원문 복원, 기본값)')
    args = parser.parse_args()

    if not os.path.exists(args.input):
        print(f"오류: 파일을 찾을 수 없습니다 - {args.input}")
        sys.exit(1)

    # 읽기 전용 모드
    if args.read_only:
        text = read_hwpx_text(args.input)
        print(text)
        return

    # finalize 모드
    if args.finalize:
        if args.accept_aa and args.reject_aa:
            print("오류: --accept-aa와 --reject-aa는 동시 지정 불가")
            sys.exit(1)
        accept_aa = args.accept_aa  # 기본값: False (ⓐⓐ reject)

        if not args.output:
            base, ext = os.path.splitext(args.input)
            args.output = base + '_최종' + ext

        print(f"입력: {args.input}")
        print(f"출력: {args.output}")
        print(f"ⓐⓐ 처리: {'accept (strip, 교정문 유지)' if accept_aa else 'reject (원문 복원)'}")

        files = read_all_files(args.input)
        section_names = get_section_names(files)
        if not section_names:
            print("오류: Contents/section*.xml 본문 파일을 찾을 수 없습니다.")
            sys.exit(1)

        total_stats = {'alpha_stripped': 0, 'alphaalpha_accepted': 0, 'alphaalpha_rejected': 0}
        for section_name in section_names:
            section = files[section_name].decode('utf-8')
            section, stats = finalize_markers(section, accept_aa=accept_aa)
            files[section_name] = section.encode('utf-8')
            for key, value in stats.items():
                total_stats[key] += value

        print(f"section 처리: {len(section_names)}개")
        print(f"ⓐ strip: {total_stats['alpha_stripped']}개")
        print(f"ⓐⓐ accept: {total_stats['alphaalpha_accepted']}개")
        print(f"ⓐⓐ reject: {total_stats['alphaalpha_rejected']}개")

        save_hwpx(files, args.output)
        print(f"저장 위치: {args.output}")
        return

    # 변경사항 수집
    changes = []
    if args.changes:
        with open(args.changes, 'r', encoding='utf-8') as f:
            changes = json.load(f)
    elif args.find is not None and args.replace is not None:
        change = {"find": args.find, "replace": args.replace}
        if args.operation:
            change["operation"] = args.operation
        changes = [change]
    else:
        print("오류: --find/--replace 또는 --changes 중 하나를 지정하세요.")
        sys.exit(1)

    # 출력 경로 결정
    if not args.output:
        base, ext = os.path.splitext(args.input)
        args.output = base + '_수정' + ext

    print(f"입력: {args.input}")
    print(f"출력: {args.output}")
    print(f"변경사항: {len(changes)}개")

    # 파일 읽기
    files = read_all_files(args.input)
    header = files['Contents/header.xml'].decode('utf-8')
    section_names = get_section_names(files)
    if not section_names:
        print("오류: Contents/section*.xml 본문 파일을 찾을 수 없습니다.")
        sys.exit(1)
    sections = {name: files[name].decode('utf-8') for name in section_names}

    # 파란색 charPr 추가
    max_id = get_max_charpr_id(header)
    blue_id = max_id + 1

    # 본문용 charPr를 기반으로 (보통 id=6 또는 7이 본문용)
    # 본문에서 실제로 가장 많이 쓰이는 id 찾기
    used_ids = []
    for section in sections.values():
        used_ids.extend(re.findall(r'charPrIDRef="(\d+)"', section))
    base_id = max(set(used_ids), key=used_ids.count) if used_ids else str(max_id)
    base_id = int(base_id)

    print(f"section 대상: {len(section_names)}개")
    print(f"기반 charPr id: {base_id}, 파란색 id: {blue_id}")

    try:
        header = add_blue_charpr(header, base_id, blue_id)
        print("파란색 charPr 추가 완료")
    except ValueError as e:
        print(f"오류: {e}")
        sys.exit(1)

    # 각 변경사항 적용
    success_count = 0
    for i, change in enumerate(changes):
        find_text = change['find']
        marker = change.get('marker', '')
        operation = change.get('operation') or ('delete' if change.get('replace') == '' else 'replace')
        ok = False
        matched_section = ''
        for section_name in section_names:
            updated, ok = apply_change(sections[section_name], change, blue_id)
            if ok:
                sections[section_name] = updated
                matched_section = section_name
                break
        tag = f"[{operation}/{marker}] " if marker else f"[{operation}] "
        if ok:
            print(f"[{i+1}] [OK] {tag}'{find_text[:30]}...' -> {matched_section} 파란색 적용")
            success_count += 1
        else:
            print(f"[{i+1}] [FAIL] {tag}'{find_text[:30]}...' -> 텍스트를 찾지 못함 (정확히 일치해야 함)")

    # 저장
    files['Contents/header.xml'] = header.encode('utf-8')
    for section_name, section in sections.items():
        files[section_name] = section.encode('utf-8')
    save_hwpx(files, args.output)

    print(f"\n완료: {success_count}/{len(changes)}개 적용됨")
    print(f"저장 위치: {args.output}")


if __name__ == '__main__':
    main()
