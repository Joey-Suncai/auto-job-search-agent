Return a JSON array of cases. Kinds of case, by "fn":
- {"name","why","fn": "terms","jd","title","role": {...},"n": 12,"expect": [[term, jd_spelling, score], ...]}  (the exact ordered list)
- {"name","why","fn": "parse","text","folder","expect": [title, company]}
- {"name","why","fn": "tailor","facts": {...},"role": {...},"master": {...},"jd","title",
   "expect_swaps": [[from, to], ...], "expect_added": [item, ...], "expect_headline": "...", "expect_first_bullets": {entry_id: text}}
  (master shape: {"headline","summary","skills": [{"label","items"}],"entries": [{"entry_id","bullets": [{"text","fact_ids","competencies","bold"}]}],"reserve": []};
   fact base shape: {"entries": [{"id","kind","org","role","dates","on_resume"}], "facts": [{"id","entry","S","T","A","R","numbers","skills","resume_ok"}],
   "skills": {"true": {...}, "not_true": [...]}})
About 8 terms cases (title doubling, the 3-hit cap, ties, whole-token traps like LLMOps, spelling choice), 8 parse cases (company first /
last, en dash inside a title, no heading, one part), 6 tailor cases (acronym swap, a plural pair that must not swap, a not-true term never
added, a not-used tool, a skill added, headline building). Show score arithmetic in "why". Keep tailor cases small (1–2 entries, empty reserve).
