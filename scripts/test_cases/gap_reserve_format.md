Return a JSON array of cases. Kinds, by "fn":
- {"name","why","fn":"tags","spellings":[..],"facts":{...},"expect":[[fact_id, skill], ...]}
- {"name","why","fn":"gaps","jd","title","role":{...},"facts":{...},"page","n":12,
   "expect":[{"term","jd_spelling","state","score","facts":[..]}, ...]}   (exact ordered list)
- {"name","why","fn":"aggregate","per_jd":[[{"term","jd_spelling","state","score","facts","competency":"c","spellings":[..]}...],...],
   "n_jds":N,"expect":[{"term","jds","share","score","spellings":{..},"states":{..},"facts":[..]}, ...]}
- {"name","why","fn":"deny","facts":{...},"spellings":[..],"fact_id","expect_removed":[..],"expect_skills":{fact_id_or_group: [..]}}
   (expect_skills: the skills after the call, for the facts / skills.true groups you name)
- {"name","why","fn":"candidates","role":{...},"master":{...},"candidates":[..],"expect_kinds":[[kinds of candidate 1], [..2], ...]}
   (kinds from: entry_not_on_master, not_new, no_gap_term)
- {"name","why","fn":"bank","bank","heading","lines":[..],"expect":"..."}
About 5 tags (token match inside a skill, plural vs singular spelling, resume_ok false, on_resume false, skills.true), 7 gaps (spelling on
page → dropped, other spelling → other_spelling, not-true term dropped, title doubling, the 3-hit cap, LLMOps trap, n cut), 4 aggregate
(ties, share rounding, n_jds 0), 4 deny (fact, skills.true, nothing matches, other facts untouched), 5 candidates, 5 bank (middle section,
last section, missing heading, blank lines kept, trailing newlines). Show arithmetic in "why". Keep inputs small.
