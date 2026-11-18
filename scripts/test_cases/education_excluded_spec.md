# Ashby Education History with excluded sub-fields (JSA-330, ibotta 11-11)

An Ashby EducationHistory field can leave sub-fields out: its form config says `degree` / `startDate` "excluded" (no such
box on the page). The page then has no Degree box and only two selects (end month, end year).

Read-back (`edu_same(want, got)`): `want` is the plan's JSON list (first entry used), `got` the page's JSON object with keys
`school`, and `degree` / `major` **only when the page has that box**. A wanted part whose key is ABSENT from `got` is not
checked (the page cannot show it). A key that is present but empty ("") while the wanted part is non-empty still fails.
The school check is unchanged: the page's school must contain the wanted school (case-insensitive, whitespace collapsed).
An empty wanted part is never checked. Unreadable JSON → false.

Select values (`edu_select_values(ent, n_selects, excluded)`): `ent` = {start_month, start_year, end_month, end_year, …},
`n_selects` = how many `<select>` boxes the entry shows, `excluded` = list of excluded sub-field names (any of "degree",
"major", "startDate", "endDate"; may be empty). Returns the list of values to put into the selects, in page order:
- 4 selects → [start_month, start_year, end_month, end_year].
- 2 selects and "startDate" excluded → [end_month, end_year].
- 2 selects and "endDate" excluded → [start_month, start_year].
- 2 selects and neither excluded (unknown which pair) → [] (nothing is guessed).
- any other count (0, 1, 3 …) → [].
A value that is missing in `ent` is "" in the list.
