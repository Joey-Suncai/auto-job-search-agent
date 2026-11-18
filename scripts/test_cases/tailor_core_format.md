Return a JSON array of about 14 cases about core bullets only. Two kinds, by "fn":
- {"name","why","fn":"tailor","facts":{...},"role":{...},"master":{...},"jd","title":"","expect_bullets": {entry_id: [bullet texts in final order]}}
  (master shape: {"headline","summary","skills": [],"entries": [{"entry_id","bullets": [{"text","fact_ids","competencies","bold","core"?}]}],
  "reserve": [{"entry_id","text","fact_ids","competencies","bold"}]}; fact base shape: {"entries": [{"id","org","on_resume"}],
  "facts": [{"id","entry","skills","resume_ok"}], "skills": {"true": {...}, "not_true": []}}; role shape as in the spec)
- {"name","why","fn":"tailored","facts":{...},"approved":{...},"tailored":{...},"title":null,"expect_kinds":[...]}  (kinds compared:
  core_dropped, new_sentence; a set, empty = clean)
About 8 tailor cases: a reserve bullet that would replace the lowest-weight bullet but that bullet is core → the next eligible non-core one
goes instead; every non-first bullet core → reserve skipped; core bullets moved ahead of a non-core bullet with more JD terms; several core
bullets keep their master order even when a later one holds more JD terms; non-core bullets sorted after them; an entry with "core": false
treated as non-core. Keep skills [] and headline / title empty, every term true via a fact skill. About 6 tailored cases: a core bullet
removed (core_dropped); the first bullet removed without a core mark (core_dropped); a non-core bullet replaced by a reserve bullet (clean);
core bullets reordered (clean); a core bullet present only after undoing a listed swap (clean); a core bullet moved to another entry
(core_dropped plus whatever else the spec says — list only core_dropped and new_sentence expectations). Use real action-verb sentences.
Show the reasoning in "why".
