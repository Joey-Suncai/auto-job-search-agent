# indeed_search.py — spec (JSA-110)

Indeed search result cards become job rows for a student who wants Summer 2027 internships or 2027/2028 new-grad roles
in the United States in data / analytics / BI / product / AI.

## keep_card(title, location, job_types) → bool
True only when ALL hold:
1. Track: the title contains one of these words (case-insensitive, whole word): data, analyst / analytics / analysis
   (any word starting with "analy"), AI, A.I., machine learning, ML, LLM, GenAI, agent / agentic, product,
   business intelligence, BI, insight / insights.
2. Not senior: the title has none of senior, sr, sr., staff, principal, lead, director, head of, VP, vice president,
   manager II, architect, PhD, Ph.D, postdoc, MBA.
3. Location is not clearly outside the U.S. (e.g. "Toronto, ON", "London, UK", "Bangalore, India" → False;
   "Remote", "" and U.S. cities / states → fine).
4. level_of(title) is not None.

## level_of(title, job_types) → "Internship" | "New Grad / Entry" | None
- A title with fall, autumn, spring, winter, co-op / coop, year-round, part-time or "sprint season" → None.
- A title with the word intern / interns / internship / internships (not "internal") → "Internship", unless the title
  names a year other than 2027 (e.g. "Summer 2026 Intern" → None; "2027 Summer Intern" → "Internship";
  "Intern" with no year → "Internship").
- Otherwise: a title naming any year other than 2027 or 2028 → None.
- Otherwise a title with one of: new grad, new graduate, new college grad, recent grad, recent graduate, entry level,
  entry-level, junior, associate product manager, APM, early career, university grad, university graduate,
  graduate program, rotational, class of 2027, class of 2028, 2027 start, 2028 start → "New Grad / Entry".
- Anything else (e.g. plain "Data Analyst", "Product Manager") → None.

## title_key(title) → str
Lower case; text in ( ) or [ ] removed; the words / numbers 20xx years, summer, intern, interns, internship,
internships, new grad, new graduate, remote, us, usa removed; every run of non-alphanumeric characters becomes one
space; trimmed. Examples: "Data Analyst Intern (Summer 2027)" → "data analyst"; "2027 Summer Intern - Business
Intelligence" → "business intelligence".
