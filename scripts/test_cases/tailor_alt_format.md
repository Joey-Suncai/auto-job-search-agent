Return a JSON array of cases, all {"name","why","fn":"tailor","facts":{...},"role":{...},"master":{...},"jd","title":"",
"expect_bullets": {entry_id: [bullet texts in final order]}}.
(master shape: {"headline","summary","skills": [{"label","items"}],"entries": [{"entry_id","bullets": [{"text","fact_ids","competencies","bold"}]}],
 "reserve": [{"entry_id","text","fact_ids","competencies","bold"}]}; fact base shape: {"entries": [{"id","org","on_resume"}],
 "facts": [{"id","entry","skills","resume_ok"}], "skills": {"true": {...}, "not_true": []}})
Only about the alternates rule and the order rule after it: a reserve bullet bringing a missing term; one bringing only the JD's spelling
of a term the page says another way; one bringing nothing (skipped); a removal that would lose a term or a JD spelling (not allowed);
the lowest-weight choice and the tie → later bullet; an entry with one bullet (skipped); two reserve bullets in order. Keep the skills
empty ([]) and the headline / title empty so no swap, skill or headline step interferes; make every term true via a fact skill. Remember
the final order step: the first bullet stays, the others sorted by how many JD terms they hold (more first, stable). Show the reasoning
in "why".
