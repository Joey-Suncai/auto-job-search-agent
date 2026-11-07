A JSON array. Each case is one of:
{"name": str, "fn": "slot_kind", "slot_name": str, "label": str, "expect": "resume|cover_letter|transcript|other_file"}
{"name": str, "fn": "file_slots", "plan": {"fields": [{"key": str, "label": str, "type": "file|text|combo", "required": bool}]},
 "files": [file names present in the folder], "answers": {object written as answers.json, or null for no file},
 "expect": [{"key": str, "kind": str, "required": bool, "file": str or null}]}
{"name": str, "fn": "missing_file_slots", "plan": {...same...}, "files": [...], "answers": {...} or null, "expect": [keys of the missing slots]}
{"name": str, "fn": "after_submit", "confirmed": bool, "code_page": bool, "before": [{"field","msg"}], "after": [{"field","msg"}],
 "expect": {"status": str, "fields": [str]}}
Each case also has "quote": the spec sentence it tests. Spread the cases: ~10 slot_kind (incl. the Viking label quoted in the
spec, a combined resume+cover letter, a lone "Transcript", "Unofficial transcript (PDF)", a label with no document word,
"Writing sample", standard names with odd labels), ~8 file_slots (answers.json file exists / missing / sub-path / text value,
resume and cover letter PDFs present or not, transcript present, upper-case .PDF), ~5 missing_file_slots, ~7 after_submit.
