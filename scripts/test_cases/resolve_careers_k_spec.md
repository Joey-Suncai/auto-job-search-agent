# resolve_careers resume file (JSA-129)

A long `--report out.json` run keeps a resume file `out.json.part.jsonl` so that killing it and running the same command
again only processes what is left.

## The file
- One JSON object per line. Line 1 is the header `{"key": K}`, where K is the run key.
- Every later line is one of:
  - `{"t": "comp", "c": company, "s": systems, "site": site, "note": note, "reason": reason}` — a company whose site work is finished.
  - `{"t": "render", "site": site, "s": systems, "note": note}` — a site rendered in headless Chrome.
  - `{"t": "row", "id": row_id, "r": result}` — a row whose result is decided.
- `systems` is a list of `[system, ident]` pairs. An ident is a string, or (for Workday) a list of strings; when read back,
  a list ident becomes a tuple, a string ident stays a string.

## Run key — `run_key(args)`
- The key is the run's command-line arguments joined with single spaces, in their original order, with every `--fresh`
  argument left out. Nothing else is dropped.

## Opening — `Checkpoint(path, key, fresh)`
- path None → no file is read or written; nothing is resumed.
- The file is used only when it exists, `fresh` is false, and its first readable line has `"key"` equal to `key`.
  Then every comp / render / row line is loaded:
  - `comp[company] = (systems, site, note, reason)` (reason "" when missing),
  - `render[site] = (systems, note)`,
  - `rows[row_id] = result`.
  A line that is not valid JSON (for example the last line, cut off when the run was killed) is skipped; the other lines still count.
  Lines with an unknown `t` are ignored. A resumed file is rewritten with its valid lines only (in order), so later appends start on a clean line. When the same company / site / row appears twice, the later line wins.
- Otherwise (no file, a different key, an empty file, or `fresh`) nothing is loaded and the file is started over:
  it then contains only the header line for `key`.
- `resumed()` = number of companies + rendered sites + rows loaded.

## Writing — `put(obj)`
- Appends `obj` as one JSON line (with a path); does nothing without a path.

## Finishing — `done()`
- Deletes the file once the report has been written (no error when it is already gone or path is None).

## Rows to resolve — `targets(jobs)`
- A row is kept when all hold: its `url` is an aggregator link (contains `jobright.ai/jobs/info/`, or `joinhandshake.com`,
  or `linkedin.com/jobs/view/` / `linkedin.com/comm/jobs/view/`, case-insensitive); it has no (or an empty) `ats_url`;
  its `elig` is `可投` or `待核实`; and its `ats_unresolved` does not start with `spot-check:` (a match a reviewer
  rejected is never tried again). Other `ats_unresolved` texts do not matter. Order is kept.
