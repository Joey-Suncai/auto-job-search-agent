Return {"cases": [...]}. Each case: {"name": str, "fn": "essay_like" | "guard_short_answers" | "apply_drafts" | "required_empty", "args": {...}, "expect": ..., "spec_quote": str, "ambiguous": false}.
- essay_like: args {"field": {key,label,type,required}}, expect bool.
- guard_short_answers: args {"fields": [...], "answers": {...}}, expect {field key: status} for every key in answers after the call.
- apply_drafts: args {"fields": [...], "answers": {...}, "drafts": {...}, "cover": str|null}, expect {"ok_keys": [keys whose answer is status ok after the call, in field order], "missing": [ids in field order]}.
- required_empty: args {"rows": [...]}, expect list of labels.
Write 26 cases: essay_like 9 (each label family, the 100-char length rule, cover_letter / summary keys, a non-textarea with an essay label, a short plain textarea like "Address"), guard_short_answers 5, apply_drafts 7 (required and optional essays, cover with and without text, an essay already answered, a non-essay unknown field), required_empty 5 (radio / select / text / file rows, whitespace, optional empty).
