# pre-commit-copyright-notice

A [pre-commit](https://pre-commit.com) hook that checks source files for a
copyright notice and optionally adds one when missing. Also ships as a
standalone `copyright-notice` command.

## Usage in `.pre-commit-config.yaml`

```yaml
- repo: https://github.com/b8raoult/pre-commit-copyright-notice
  rev: "0.1.0"
  hooks:
  - id: copyright-notice
    args: ["--years", "2020-2026", "--holder", "PackageName contributors"]
```

## Standalone CLI

After `pip install pre-commit-copyright-notice` the `copyright-notice` command
is available:

```bash
# Check files
copyright-notice --holder "MyOrganisation" src/

# Check a single file
copyright-notice --holder "MyOrganisation" myfile.py

# Add missing notices and fix stale years in a whole directory
copyright-notice --holder "MyOrganisation" --fix src/

# Check only Python and JavaScript files
copyright-notice --holder "MyOrganisation" --extensions .py,.js src/

# Skip files whose path matches a glob (repeat --exclude for several patterns)
copyright-notice --holder "MyOrganisation" --exclude 'docs/**/*.py' --exclude 'build/' src/

# Ignore stale years (only check that a notice exists with the right holder)
copyright-notice --holder "MyOrganisation" --ignore-stale src/

# Omit the year entirely
copyright-notice --holder "MyOrganisation" --no-year src/
```

When a **directory** is passed, the tool walks it recursively and checks every
file whose extension is in the known list (or in `--extensions` if given).
Hidden directories (names starting with `.`) are skipped automatically, as are
any files whose path matches an `--exclude` glob.

## Excluding files

`--exclude` takes a **glob pattern** (the same style as
[ruff](https://docs.astral.sh/ruff/settings/#exclude), via Rust's `globset`)
matched against each file path:

| Token | Matches |
|-------|---------|
| `*` | any run of characters **within** a single path segment (does not cross `/`) |
| `**` | any number of path segments (crosses `/`) |
| `?` | a single non-`/` character |
| `[abc]`, `[!abc]` | a character class / negated class |
| trailing `/` | the named directory **and everything under it** |

A pattern **without** a slash matches a *basename* anywhere in the tree
(`*_pb2.py` excludes `pb2` files at any depth). A pattern **with** a slash
matches that relative path under any parent directory (`docs/**/*.py`).

Give `--exclude` multiple times to exclude several patterns. In
`.pre-commit-config.yaml`, pass each as its own argument:

```yaml
- id: copyright-notice
  args:
  - "--holder=PackageName contributors"
  - "--exclude=docs/**/*.py"
  - "--exclude=build/"
```

## Options

| Option | Description |
|--------|-------------|
| `--years YEARS` | Year(s) for new notices. Accepted formats: `YYYY`, `YYYY-`, `YYYY-YYYY`, `YYYY, YYYY, ...`. Default: current year. Ignored when `--no-year` is set. |
| `--holder NAME` | Copyright holder name to check for. Default: `The copyright holder`. |
| `--fix` | Fix files in place instead of failing: insert missing notices, correct wrong holders, and update stale years. |
| `--no-year` | Omit the year from notices entirely; year staleness is never checked. |
| `--ignore-stale` | Do not fail on stale copyright years; only check that a notice is present with the correct holder. |
| `--extensions .EXT[,.EXT...]` | Comma-separated list of file extensions to check (e.g. `.py,.js`). |
| `--exclude GLOB` | Glob matched against each file path; matching files are skipped. May be given multiple times. See [Excluding files](#excluding-files). |
| `--exit-non-zero-on-fix` | Exit with a non-zero status when `--fix` changes any file. Use in pre-commit so a run that rewrote files fails the hook (and the fixed files are re-staged on the next run). |
| `--license FILE_OR_URL` | Path or URL to a plain-text license block (no comment characters). |

## Year formats

The following year formats are accepted in source files and in `--years`:

| Format | Example | Description |
|--------|---------|-------------|
| Single year | `2026` | Exact year |
| Open-ended range | `2024-` | Always considered current |
| Closed range | `2024-2026` | Start through end year |
| Comma-separated list | `2020, 2023, 2026` | Discrete years; last one checked for staleness |

The `--years` value is not matched literally — any file containing
`Copyright <any-valid-year-format> <holder>` passes. When `--fix` updates a
stale year in the file it preserves the existing format (e.g. a closed range
stays a closed range with an updated end year; a comma list gets the current
year appended).

## Behaviour

### Holder mismatch

If a file already contains a `(C) Copyright` line but with a **different**
holder, the tool fails (or fixes with `--fix`). Only the **first** `(C)`
block in the file is checked — additional blocks are ignored, as they may be
present intentionally (e.g. third-party code with a different licence header).

```
Wrong copyright holder in src/foo.py: found "Other Org", expected "MyOrganisation".
```

With `--fix` the wrong holder (and stale year, if any) is corrected in-place.

### Missing notice

```
Copyright notice missing in src/bar.py.
Expected: Copyright 2026 MyOrganisation
```

With `--fix` the notice is inserted at the top of the file (after a shebang
or encoding declaration if present), followed by a blank line.

### Stale year

```
Copyright year is stale in src/baz.py.
Expected end year 2026, found: Copyright 2024 MyOrganisation
```

With `--fix` the year is updated in-place. Pass `--ignore-stale` to suppress
this check, or `--no-year` to omit years from notices altogether.

### No-year mode (`--no-year`)

When `--no-year` is set the tool:

- Accepts files that have `(C) Copyright Holder.` (no year) **or** any
  year-bearing format — either is considered valid as long as the holder matches.
- Inserts notices without a year when `--fix` is used:
  ```
  # (C) Copyright MyOrganisation.
  ```
- Never reports or fixes stale years.

## Adding missing notices (`--fix`)

By default `--fix` exits `0` once it has rewritten the failing files. In
pre-commit you usually want the hook to **fail** on the run that made changes
(so the commit stops and the rewritten files are staged for the next attempt) —
add `--exit-non-zero-on-fix` for that behaviour. The exit status is non-zero
only when at least one file was actually changed.

The tool writes a notice at the top of each failing file (after a shebang or
encoding declaration if present), followed by a blank line:

```
# (C) Copyright 2024-2026 My Organisation.
# <license block lines, if any>

<rest of file>
```

**License block resolution order:**

1. `--license FILE_OR_URL` — load plain text from a local file or HTTP(S) URL.
2. Existing block in the file — if the file already contains a `(C)` copyright
   notice from another holder, the lines immediately following it are extracted
   and reused (comment characters are stripped and re-applied for the target
   file type).
3. No block — only the copyright line is added.

The license text must contain **no comment characters**. The tool prefixes
each line with the correct character for the file's extension:

| Extensions | Comment character |
|------------|-------------------|
| `.py` `.sh` `.bash` `.zsh` `.r` `.rb` `.pl` `.yaml` `.yml` `.toml` `.ini` `.cfg` `.conf` | `#` |
| `.js` `.ts` `.java` `.c` `.cpp` `.h` `.cs` `.go` `.rs` | `//` |
| anything else | `#` (default) |

### Example: license from a file

`LICENSE_HEADER.txt` (plain text, no comment chars):

```
This software is licensed under the terms of the MIT License.
See LICENSE for details.
```

Hook configuration:

```yaml
- repo: https://github.com/b8raoult/pre-commit-copyright-notice
  rev: "0.1.0"
  hooks:
  - id: copyright-notice
    args:
    - "--years"
    - "2024-2026"
    - "--holder"
    - "PackageName contributors"
    - "--license"
    - "LICENSE_HEADER.txt"
    - "--fix"
```

A Python file missing a notice would become:

```python
# (C) Copyright 2024-2026 PackageName contributors.
# This software is licensed under the terms of the MIT License.
# See LICENSE for details.

def foo():
    ...
```

A JavaScript file would use `//` instead of `#`.

### Example: license from a URL

```yaml
args:
- "--license"
- "https://example.com/license-header.txt"
```
