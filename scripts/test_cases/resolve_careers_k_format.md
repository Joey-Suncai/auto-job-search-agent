Return {"cases": [...]}. Each case is one of:

1. {"name": "...", "fn": "run_key", "args": {"argv": [str, ...]}, "expect": str, "spec_quote": "...", "ambiguous": false}

2. {"name": "...", "fn": "checkpoint",
    "args": {"file_lines": [str, ...] or null,   // raw text lines already in the file (null = no file); a line may be invalid JSON
             "no_path": bool,                     // true = path None
             "key": str, "fresh": bool,
             "puts": [object, ...]},              // put() calls made after opening
    "expect": {"comp": {company: [systems, site, note, reason]},   // systems as [[system, ident], ...]; a tuple ident written as a list
               "render": {site: [systems, note]},
               "rows": {row_id: result},
               "resumed": int,
               "file_after": [object, ...] or null}  // every line of the file after the puts, parsed as JSON (null = no file)
    "spec_quote": "...", "ambiguous": false}

3. {"name": "...", "fn": "systems_back", "args": {"systems": [[system, ident], ...]},
    "expect": [[system, ident, "tuple" | "str"], ...], "spec_quote": "...", "ambiguous": false}

4. {"name": "...", "fn": "targets", "args": {"jobs": [{"id": str, "url": str, "ats_url"?: str, "elig": str, "ats_unresolved"?: str}, ...]},
    "expect": [id, ...], "spec_quote": "...", "ambiguous": false}

Write 30 cases: targets 6 (spot-check rejected skipped, other unresolved reason kept, 不可投 dropped, non-aggregator url dropped, empty ats_url kept, case of the url), run_key 5 (with / without --fresh, several --fresh, order kept), systems_back 3, checkpoint 16 (no file,
matching key, other key, fresh, empty file, truncated last line, unknown t, duplicate company — later wins, no_path with
puts, missing reason, puts after resume appended, puts after a key mismatch start from the header).
