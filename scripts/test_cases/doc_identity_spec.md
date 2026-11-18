# Spec: instruction files must not hold an identity value (JSA-415)

Two pure functions in `scripts/test_doc_identity.py`.

`is_doc_file(path)` — True for the instruction-type files that agents read, False for everything else. Paths are
repo-relative with `/`. True: any `*.md` file; `ops/CLAUDE.md`; any file under `docs/agent/`; any `SKILL.md`.
False (even if `.md`): any path with a segment `test`, `test_cases` or `fixtures`; a basename starting with `test_`;
`config/fixtures/**`. Non-doc extensions (`.py`, `.js`, `.json`, `.csv`) are False unless under `docs/agent/`.

`identity_hits(text, values)` — `values` is a dict name→string (the fictional identity). Returns the sorted list of NAMES
(never the values) whose value occurs in `text`. Matching is case-insensitive. A value of 5 or more characters, or one
containing a non-letter (digit, `@`, `.`, `_`, space, `-`, `/`), matches as a plain substring. A value that is purely
letters and shorter than 5 characters (a first name, a last name, a nickname) matches only as a whole word
(letters on both sides do not count: "Doe" does not match in "Doerr" or "Dodoes"; "Doe" matches in "Mr. Doe," ).
Empty values are ignored. A text with no hit returns [].
