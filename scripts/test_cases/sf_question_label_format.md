Return {"cases": [...]}. Each case: {"name": str (unique), "label": str, "rows": [str, ...] or null,
"expect": str (the exact returned text), "spec_quote": str (the spec rule that decides it), "ambiguous": false}.
Write about 26 cases: 8 placeholder labels with one short question row (vary wording and case: "Please select one of
the options*", "Please Select One of the Options", "No Selection", "Select one:"); 4 with several rows where the nearest
is short or the nearest is long and a farther one is short (a heading); 3 where every row is longer than 300 characters
(with and without a question sentence — write the long rows out in full so their length is really over 300); 4 real
labels with rows present (near misses: "Please select your gender", "Select your country of residence"); 2 empty labels
with rows; 3 placeholder labels with rows that are empty, null, or only symbols/digits; 2 labels with stars, colons and
odd whitespace. Use realistic SuccessFactors employer wording (age, work authorization, sponsorship, relatives,
non-compete, veteran / disability headings).
