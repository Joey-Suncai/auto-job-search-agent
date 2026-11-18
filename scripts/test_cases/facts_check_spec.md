# facts_check — specification (for writing test cases; you do not see the code)

A candidate's resume facts live in a JSON "fact base": {"entries": [...], "facts": [...]}.
- An entry = one job, project, school or club: {"id", "kind" (one of education | experience | project | leadership), "org", "role", "dates", optional "never": [phrases]}.
  All of id, kind, org, role must be non-empty strings; "dates" must be present (may be the empty string). Entry ids are unique.
- A fact = one atomic accomplishment: {"id", "entry", "S", "T", "A", "R", "numbers": [strings], "skills": [strings], "anchors": [strings], "never": [phrases], "source"}.
  id unique and non-empty; "entry" must be an existing entry id; "A" non-empty; "source" non-empty; "skills" and "anchors" non-empty lists; "numbers" a list.
  Every number written in a fact's "numbers" list must also appear in that fact's own S/T/A/R text (after normalization, see below).

A "bullet bank" is a markdown file: sections start with "## <org name>"; each bullet is a line starting with "- ". Other lines (e.g. "  *used in: … · tags: …*") are ignored.

The checker:
1. Schema problems (any rule above broken) → it reports them and stops (the bank is not checked).
2. Number drift: a number in a fact's "numbers" that is not in its S/T/A/R → problem.
3. Each bank section is matched to an entry: exact org name (case-insensitive), otherwise the entry sharing the most words with the heading if it shares at least 2 words (ignoring "the", "of", "and", "inc"). No match → problem "no entry".
4. Each bullet is mapped to the facts of that entry whose anchors appear in the bullet (case-insensitive substring). Zero facts → problem "unmapped".
5. Every number in the bullet must appear in the mapped facts' S/T/A/R text or "numbers" list → otherwise problem "unsupported number".
6. A bullet containing (case-insensitive, as a whole word/phrase, not inside a longer word) any "never" phrase of its entry or of a mapped fact → problem "never phrase".

Number normalization: currency signs (¥ $ € £), % , + and thousands commas are removed: "1,886" = "1886", "70%" = "70", "¥10,000" = "10000", "500+" = "500". Decimals stay ("2.169"). A range "0–5" or "2017–2018" is two numbers. Spelled-out numbers ("four") are not numbers.

Result: "pass" when there are no problems, else "fail" with the list of problem kinds.
