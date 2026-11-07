Return {"cases": [...]}; each case:
{"name": "<unique>",
 "files": {"form_check.json": <object or "INVALID">, "wd_log.json": <object>, "plan.json": <object>, "verify.json": <object>},   // only the files present
 "expect": null | {"ats": <string or null>, "url": "<string>", "n_rows": <int>,
                   "rows": [{"index": <int>, "question": "...", "planned": <any>, "page": <any>, "ok": true|false, "required": true|false, "source": "..."}]},  // check a few rows only
 "spec_quote": "<sentence>", "ambiguous": false}
Write ~18 cases: each file kind, nesting, precedence, ok rules, empty files, invalid JSON.
