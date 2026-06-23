import argparse
import datetime
import re
import sys
from pathlib import Path
from urllib.request import urlopen

CURRENT_YEAR = datetime.date.today().year

# Named groups: start, list (comma-separated extras), end (range), open (open-ended dash)
YEAR_CAPTURE = r'(?P<start>\d{4})(?:(?P<list>(?:\s*,\s*\d{4})+)|-(?P<end>\d{4})|(?P<open>-))?'

# Comment character by file extension
COMMENT_CHARS = {
    '.py': '#', '.sh': '#', '.bash': '#', '.zsh': '#', '.r': '#',
    '.rb': '#', '.pl': '#', '.yaml': '#', '.yml': '#', '.toml': '#',
    '.ini': '#', '.cfg': '#', '.conf': '#',
    '.js': '//', '.ts': '//', '.java': '//', '.c': '//', '.cpp': '//',
    '.h': '//', '.cs': '//', '.go': '//', '.rs': '//',
}

# Matches the first (C) copyright line regardless of holder; year required
ANY_COPYRIGHT_PATTERN = re.compile(
    rf'\(C\)\s+Copyright\s+{YEAR_CAPTURE}\s+(?P<found_holder>[^\n]+)',
)

# Same but with the year block optional (used in --no-year mode)
ANY_COPYRIGHT_PATTERN_NO_YEAR = re.compile(
    rf'\(C\)\s+Copyright\s+(?:{YEAR_CAPTURE}\s+)?(?P<found_holder>[^\n]+)',
)


def get_comment_char(path):
    return COMMENT_CHARS.get(Path(path).suffix.lower(), '#')


def build_pattern(holder, no_year=False):
    if no_year:
        # Accept the notice with or without a year in the file
        return re.compile(rf'Copyright\s+(?:{YEAR_CAPTURE}\s+)?{re.escape(holder)}')
    return re.compile(rf'Copyright\s+{YEAR_CAPTURE}\s+{re.escape(holder)}')


def year_is_current(m):
    if m.group('open'):
        return True
    if m.group('list'):
        last_year = int(re.findall(r'\d{4}', m.group('list'))[-1])
        return last_year >= CURRENT_YEAR
    end = m.group('end')
    return int(end if end else m.group('start')) >= CURRENT_YEAR


def updated_year_str(m):
    if m.group('list'):
        last_year = int(re.findall(r'\d{4}', m.group('list'))[-1])
        if last_year >= CURRENT_YEAR:
            return m.group('start') + m.group('list')
        return m.group('start') + m.group('list') + f', {CURRENT_YEAR}'
    start = m.group('start')
    if int(start) == CURRENT_YEAR:
        return start
    return f'{start}-{CURRENT_YEAR}'


def update_year_in_content(content, m):
    new_year = updated_year_str(m)
    if m.group('list'):
        year_end = m.end('list')
    elif m.group('end'):
        year_end = m.end('end')
    elif m.group('open'):
        year_end = m.end('open')
    else:
        year_end = m.end('start')
    return content[:m.start('start')] + new_year + content[year_end:]


def load_license_text(source):
    if source.startswith(('http://', 'https://')):
        with urlopen(source) as resp:
            return resp.read().decode('utf-8').rstrip('\n')
    return Path(source).read_text(encoding='utf-8').rstrip('\n')


def extract_license_from_file(content, comment_char):
    lines = content.splitlines()
    in_block = False

    for i, line in enumerate(lines):
        if not in_block:
            if '(C)' in line or 'Copyright' in line:
                in_block = True
            continue
        license_lines = []
        for subsequent in lines[i:]:
            stripped = subsequent.strip()
            if not stripped:
                break
            if stripped.startswith(comment_char):
                license_lines.append(stripped[len(comment_char):].lstrip())
            else:
                break
        return '\n'.join(license_lines) if license_lines else None

    return None


def format_as_comments(text, comment_char):
    lines = []
    for line in text.splitlines():
        lines.append(f'{comment_char} {line}' if line.strip() else comment_char)
    return '\n'.join(lines)


def add_notice(path, years, holder, license_text=None):
    """Insert a copyright notice. Pass years=None to omit the year."""
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()

    comment_char = get_comment_char(path)
    if years:
        copyright_line = f'{comment_char} (C) Copyright {years} {holder}.\n'
    else:
        copyright_line = f'{comment_char} (C) Copyright {holder}.\n'

    if license_text is None:
        license_text = extract_license_from_file(content, comment_char)

    notice = copyright_line
    if license_text:
        notice += f'{comment_char}\n'
        notice += format_as_comments(license_text, comment_char) + '\n'
    notice += '\n'

    lines = content.splitlines(keepends=True)
    insert_at = 0
    if lines and (lines[0].startswith('#!') or lines[0].startswith('# -*-')):
        insert_at = 1
        if lines[0].startswith('#!') and len(lines) > 1 and lines[1].startswith('# -*-'):
            insert_at = 2

    new_content = ''.join(lines[:insert_at]) + notice + ''.join(lines[insert_at:])
    with open(path, 'w', encoding='utf-8') as f:
        f.write(new_content)


def expand_paths(paths, extensions):
    """Expand directory arguments to individual files, skipping hidden directories."""
    result = []
    for path in paths:
        p = Path(path)
        if p.is_dir():
            for f in sorted(p.rglob('*')):
                if not f.is_file():
                    continue
                if any(part.startswith('.') for part in f.relative_to(p).parts):
                    continue
                suffix = f.suffix.lower()
                if extensions is not None:
                    if suffix in extensions:
                        result.append(str(f))
                elif suffix in COMMENT_CHARS:
                    result.append(str(f))
        else:
            result.append(path)
    return result


def main():
    parser = argparse.ArgumentParser(
        description="Check and optionally add/update copyright notices in source files."
    )
    parser.add_argument('--years', default=str(CURRENT_YEAR),
                        help='Year(s) for new notices (YYYY, YYYY-, YYYY-YYYY, or YYYY,YYYY,...). '
                             'Default: current year. Ignored when --no-year is set.')
    parser.add_argument('--holder', default='The copyright holder',
                        help='Copyright holder name')
    parser.add_argument('--add', action='store_true',
                        help='Add missing notices and update stale years instead of reporting')
    parser.add_argument('--no-year', action='store_true',
                        help='Omit the year from copyright notices; do not check year staleness')
    parser.add_argument('--ignore-stale', action='store_true',
                        help='Do not fail on stale copyright years')
    parser.add_argument('--extensions', metavar='EXT[,EXT...]',
                        help='Only check files with these extensions, comma-separated (e.g. .py,.js)')
    parser.add_argument('--license', metavar='FILE_OR_URL',
                        help='Path or URL to a plain-text license block (no comment characters)')
    parser.add_argument('files', nargs='+', help='Files or directories to check')
    args = parser.parse_args()

    extensions = None
    if args.extensions:
        extensions = {e.strip() if e.strip().startswith('.') else f'.{e.strip()}'
                      for e in args.extensions.split(',')}

    license_text = None
    if args.license:
        license_text = load_license_text(args.license)

    pattern = build_pattern(args.holder, no_year=args.no_year)
    any_pat = ANY_COPYRIGHT_PATTERN_NO_YEAR if args.no_year else ANY_COPYRIGHT_PATTERN
    failed = False

    for path in expand_paths(args.files, extensions):
        if extensions and Path(path).suffix.lower() not in extensions:
            continue

        try:
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
        except (OSError, UnicodeDecodeError):
            continue

        any_m = any_pat.search(content)
        m = pattern.search(content)

        # Holder mismatch: there's a (C) copyright block but it doesn't match our holder
        holder_mismatch = (
            any_m is not None
            and (m is None or not (any_m.start() <= m.start() <= any_m.end()))
        )

        if holder_mismatch:
            found_holder = any_m.group('found_holder').rstrip('. \t')
            if args.add:
                if args.no_year:
                    replacement = f'(C) Copyright {args.holder}.'
                else:
                    new_year = updated_year_str(any_m)
                    replacement = f'(C) Copyright {new_year} {args.holder}.'
                new_content = content[:any_m.start()] + replacement + content[any_m.end():]
                with open(path, 'w', encoding='utf-8') as f:
                    f.write(new_content)
                print(f'Fixed copyright holder in {path}.')
            else:
                print(f'Wrong copyright holder in {path}: '
                      f'found "{found_holder}", expected "{args.holder}".')
                failed = True

        elif not m:
            if args.add:
                years = None if args.no_year else args.years
                add_notice(path, years, args.holder, license_text)
                print(f'Added copyright notice to {path}.')
            else:
                print(f'Copyright notice missing in {path}.')
                if not args.no_year:
                    print(f'Expected: Copyright {args.years} {args.holder}')
                failed = True

        elif not args.no_year and not args.ignore_stale and not year_is_current(m):
            new_year = updated_year_str(m)
            if args.add:
                new_content = update_year_in_content(content, m)
                with open(path, 'w', encoding='utf-8') as f:
                    f.write(new_content)
                print(f'Updated copyright year to {new_year} in {path}.')
            else:
                print(f'Copyright year is stale in {path}.')
                print(f'Expected end year {CURRENT_YEAR}, found: {m.group(0)}')
                failed = True

    sys.exit(1 if failed else 0)


if __name__ == '__main__':
    main()
