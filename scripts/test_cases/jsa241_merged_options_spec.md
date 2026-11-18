# Merged prefetch question: options of every wording, saved without losing options (JSA-241)

The morning question sheet merges the same question asked with different wordings by different companies into ONE entry.
Each company's form shows its own option list for it (one list per form; the lists often differ: one company's list is
cities, another's is countries). The entry keeps `options` = every distinct option of all the lists (first-seen order, no
duplicates, never cut, never limited to 12 / 60 / 400) and `option_sets` = the distinct per-form lists (each in the form's
own order), only when the merged forms have MORE than one distinct non-empty list; with one list (or none) `option_sets` is
absent. An entry whose forms show no options (a text box) has options [].

When the user's answer is saved (qa_add.py), the answer is checked against the form's options: it must be answerable on at
least ONE of the option lists the question was seen with (a pick that matches an option of any list is fine; an answer that
matches no option of any list is refused, nothing saved). Option texts may contain the character "|" (e.g. a bilingual option
"Yes (full-time) | はい（フルタイム）"); lists therefore travel as JSON, never split on "|".
