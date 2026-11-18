# truth_check — tailored resumes and letters must trace to the candidate's facts (for writing test cases; you do not see the code)

Fact base shape: {"entries": [{"id","kind","org","role","dates","on_resume": bool,"never": [...]}], "facts": [{"id","entry","S","T","A","R",
"numbers": [...],"skills": [...],"anchors": [...],"never": [...],"pairs": [[a,b]],"resume_ok": bool,"history": [{"as_of","A","R","numbers"}]}],
"skills": {"true": {"Group": [...]}, "not_true": [...]}}.

## 1. is_variant(a, b) → bool, and is_bullet_variant(a, b) → bool
Words = the text lower-cased, with "-", "‐", "–", "_", "/" turned into spaces, split on spaces. A word longer than 3 letters ending in "s"
but not "ss" loses that "s" (plural). is_variant is true when:
- the two word lists are equal after that (e.g. "AI tools" / "ai-tools", "workflow" / "Workflows", "data pipeline" / "data pipelines"), or
- one side is an acronym — 2 to 6 capital letters, optionally followed by one lower-case "s" ("LLM", "LLMs", "RAG") — and the other side has at
  least 2 words whose first letters (skipping the words and, of, the, for) spell the acronym's capitals ("large language models" → l l m).
Otherwise false ("GenAI" / "generative AI" is false: "GenAI" is not all capitals; "prompts" / "prompt engineering" is false).
is_bullet_variant(a, b) = is_variant(a, b) AND both sides have the same grammatical number. A side is plural when its last word ends in "s"
but not "ss", or when it is an all-capital acronym followed by "s" ("LLMs"). So "LLM" / "large language model" → true; "LLMs" / "large
language models" → true; "workflow" / "workflows" → false; "LLM" / "large language models" → false.

## 2. check_text(text, facts, jd, profile) → list of problems (a letter or other prose)
The text is split into sentences (after . ! ? followed by whitespace, and at line breaks). Before that, e-mail addresses, URLs, words ending
in .com/.edu/.org/.io and phone numbers like 555-010-2030 or (555) 010-2030 are removed. Number normalization: ¥ $ € £ % + and thousands
commas removed, decimals kept; "0–5" and "2017–2018" are two numbers each; digits inside words count ("12-week" holds 12).
Kinds:
- number: a number in a sentence that is not among: every resume_ok fact's numbers (its "numbers" list, the numbers in its S/T/A/R text,
  and its history entries' A/R/numbers); the numbers in any entry's org, role or dates text; the numbers in the jd text; the numbers in
  the profile text. (A fact with resume_ok false does not count.)
- never: a sentence contains (case-insensitive, whole phrase: no letter right before or after) any "never" phrase of ANY entry or ANY fact.
- pair: a fact has pair [a, b]; a sentence is "about" that fact when it contains one of the fact's anchors (case-insensitive substring) or
  when a contains a digit and the sentence contains a (case-insensitive). A sentence about the fact that contains a (substring) but not b
  is a pair problem. A sentence that holds a but is not about the fact is fine.
- banned: a sentence contains (whole word, case-insensitive) one of: leverage, leveraged, leveraging, spearhead, spearheaded, orchestrate,
  orchestrated, synergy, synergies, dynamic, passionate, results-driven, cutting-edge, go-getter, detail-oriented, team player, utilize,
  utilized, seamlessly, robust — unless the jd text contains the same whole word (a company name such as "a Lever employer").
Each problem is reported per sentence; one sentence can produce several kinds.

## 3. check_tailored(tailored, approved, facts, direction=None, title) → list of problems
A master = {"headline","summary","skills": [{"label","items": [...]}],"entries": [{"entry_id","bullets": [{"text","fact_ids",
"competencies","bold"}]}],"reserve": [{"entry_id","text","fact_ids","bold"}]}. The tailored master may also carry "swaps": [{"from","to"}].
The tailored master must be the approved master changed only mechanically. Kinds (only these are tested here):
- swap_not_variant: a listed swap whose from/to fail is_bullet_variant. (With direction None there is no keyword-cluster test.)
- new_sentence: a tailored bullet whose text is not the text of an approved bullet or approved reserve bullet, and is still not one after
  undoing every swap (replace each "to" by its "from", case-insensitive, in order).
- entry_moved: a tailored bullet that matches an approved (or reserve) bullet listed under a different entry_id.
- fact_ids_changed: a tailored bullet that matches an approved (or reserve) bullet but whose fact_ids (as a sorted list) differ from it.
  (new_sentence, entry_moved and fact_ids_changed: when a bullet is a new_sentence, the other two are not judged for it.)
- core_dropped: a core bullet of the approved master (index 0 of its entry, or "core": true) whose text is not the text of some bullet
  of the same entry in the tailored master, nor equal to one after undoing every swap. Reordering is fine; only absence counts.
- summary_changed: the tailored summary differs from the approved summary, also after undoing the swaps.
- headline_term: split the tailored headline on "·"; trim each part; drop empty ones. Part 0 is fine when title is None or equals the title
  (case-insensitive). Every other part is fine when it equals (case-insensitive) a part of the approved headline, the title, a skill in
  skills.true (any group), or a skill of any fact with resume_ok not false — or matches "Summer|Fall|Spring|Winter 20NN". Else headline_term.
- skill_added_untrue: a tailored skills item that is not (case-insensitive) in skills.true or in the skills of a resume_ok fact.
