# Workday prompt (search-and-pick list) helpers — spec (JSA-283, 2026-11-17)

A Workday "prompt" field (for example Field of Study, a list of 322 options, shown as a virtualized list) is filled by
typing a search text into its box and clicking the option whose text equals the wanted text. Typing a long text with
commas does not always find the option, so the runner searches with several shorter texts, and it must pick, among the
options a preference matches, the closest one.

## prompt_queries(want) -> list of search texts, in the order they are tried
- The first entry is `want` itself (whitespace trimmed and collapsed).
- If `want` contains one of `,` `(` `:` `;` `/` and the text before the first of them (trimmed) has at least 3 characters,
  that text is the next entry ("Python (Programming Language)" → "Python"; "Computer Sciences, Technology, or Business" → "Computer Sciences").
- If `want` has two or more words, the first two words (punctuation removed from them, joined with one space) are the next entry.
- The first word of `want` (punctuation removed) is the next entry when it has at least 4 characters.
- The last entry is always the empty string "" (no search: the whole list is scrolled).
- No entry appears twice (compare case-insensitively; the first occurrence stays). An empty or blank `want` returns [""].

## pick_by_prefs(opts, prefs) -> option text or None
`prefs` is Joey's ordered list of wanted fields of study; `opts` the options the form offers. Go through the
preferences in order; the first preference that matches any option decides (a lower preference never jumps the queue).
Comparison ignores case, repeated spaces and a trailing dot. Preferences "" and "other" are ignored; a preference
shorter than 4 characters only matches exactly.
For one preference:
1. an option equal to it → that option (first in list order).
2. otherwise the candidates are the options that contain the preference as a substring, plus the options (with at least
   two words) contained in the preference, plus the options that contain every word of the preference (words are
   letters/digits; the words "and of the a an or in for" do not count). A bare one-word option contained in the preference
   (e.g. "Science" in "Data Science") is never a candidate by containment.
3. among the candidates the CLOSEST wins: the smallest number of words in the symmetric difference of the two word sets
   (option words vs preference words, stop words removed); on a tie the first in list order.
4. no candidate → try the next preference; no preference matches → None.
Example: prefs ["Data Science", "Computer Science"], options ["Accounting", "Computer Sciences, Technology, or Business",
"Computer and Information Science"] → "Computer and Information Science" (word difference 1 versus 4).
