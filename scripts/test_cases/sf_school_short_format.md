Return {"cases": [...]}. Each case is one call of one helper:
{"name": str (unique), "fn": "school_words" | "school_fits" | "school_query" | "pick_school",
 "args": {...}, "expect": ..., "spec_quote": str, "ambiguous": false}

- school_words: args {"name": str}; expect a list of strings.
- school_fits: args {"option": str, "entry": "A" | "B"}; expect true / false.
- school_query: args {"entry": "A" | "B"} or {"school": str} (an entry with only that school name); expect a string.
- pick_school: args {"options": [str, ...], "entry": "A" | "B"}; expect [option or null, "match" | "ambiguous" | "other" | null].

Write about 6 school_words, 7 school_fits, 3 school_query and 8 pick_school cases: realistic short inverted lists
("Chicago, U of", "Illinois, U of/ChUrb", "Illinois, U of/Chgo", "Chicago State U", "Loyola U Chicago", "Northwestern U",
"Other"), the Chgo campus never for B, two fitting options, a near fit with an Other option, placeholders, duplicates.
