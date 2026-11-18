# SmartRecruiters multi-select ("select all that apply", JSA-387, Arista 11-11)
The "How did you hear about this position?" list is a `spl-multiselect-autocomplete`: its input stays empty and each pick shows
as a tag. The runner reads the tags joined by ", " (e.g. "Online job board, LinkedIn").
`multi_has(got, want)` is True when `want` is exactly one of the tags: compare case-insensitively with whitespace collapsed
(runs of spaces / newlines = one space, ends trimmed). A tag that only contains the wanted text does not count ("Online job
board - other" is not "Online job board"; "LinkedIn Jobs" is not "LinkedIn"). Tags are split at commas only. Empty or missing
`got` → False; empty or missing `want` → False (an empty want equals no tag, even if got has an empty piece such as "A, , B"
— judge it False). A wanted text that itself contains a comma never matches (it is split in `got`).
