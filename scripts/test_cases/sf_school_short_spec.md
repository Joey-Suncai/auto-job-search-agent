# School lists with short, inverted names (SuccessFactors, 2026-11-05)

Some employers' College / University lists use short inverted names: "Chicago, U of", "Illinois, U of/ChUrb" (= the
Urbana-Champaign campus), "Illinois, U of/Chgo" (= the Chicago campus, a DIFFERENT school), "Chicago State U", "Loyola U
Chicago". Searching such a list for "University of Chicago" finds nothing. Helpers that match a candidate's school to such
options. The candidate's education entries (fixed for the tests):

- Entry A: school "University of Chicago", short "UChicago".
- Entry B: school "University of Illinois Urbana-Champaign", short "UIUC".

## 1. `school_words(name)` → list of words
Lower-case the name; drop a trailing parenthesised part ("(IL)"); "&" counts as "and"; split on every character that is
not a letter a–z; drop the words "university", "univ", "u", "of", "the", "at", "in", "and", "campus", "main"; replace the
campus hints "churb", "urb", "urbana", "champaign" by the two words "urbana", "champaign", "chgo" by "chicago", "spfld" by
"springfield"; keep the first occurrence of each word, in order.
Examples: "Chicago, U of" → ["chicago"]; "Illinois, U of/ChUrb" → ["illinois", "urbana", "champaign"];
"University of Illinois Urbana-Champaign" → ["illinois", "urbana", "champaign"]; "Illinois, U of/Chgo" → ["illinois",
"chicago"]; "Texas A&M University" → ["texas", "a", "m"].

## 2. `school_fits(option, entry)` → true / false
True when the SET of school_words(option) is non-empty and equals the set of school_words of the entry's school or of its
short name. So "Chicago, U of", "The University of Chicago", "Univ. of Chicago" fit A; "Illinois, U of/ChUrb",
"University of Illinois at Urbana-Champaign", "Illinois, U of/Urb" fit B; "Illinois, U of/Chgo", "Loyola U Chicago",
"Chicago State U", "Illinois State U", "Illinois, U of" (no campus) fit neither; nothing fits both.

## 3. `school_query(entry)` → string
The word to type into a searched list: the first word of the entry's school name (split on non-letters, a trailing
parenthesised part dropped) that is not one of the dropped words of rule 1, in the name's own spelling and case. A →
"Chicago", B → "Illinois"; "Northwestern University" → "Northwestern"; "The Ohio State University" → "Ohio".

## 4. `pick_school(options, entry)` → [option, how]
`options` are the texts a list shows. Placeholders are never options: "No Selection", "Select", "Select One", "Please
select", "-", "---", "There were no results", "No results", "No results found", "No matches", "Loading…", "Searching…".
In this order:
1. An option whose name equals the school or short name once case, a trailing "(…)", the words "the" / "at" and every
   non-letter are ignored ("University of Chicago (IL)", "UNIVERSITY OF CHICAGO") → [that option, "match"].
2. Else the options that fit by rule 2 (the same text listed twice counts once): exactly one → [it, "match"]; two or more
   different texts → [null, "ambiguous"].
3. Else, when an option NEARLY fits — its word set is non-empty, a proper subset of the words of the school or short name,
   and contains that name's first word (e.g. "Illinois, U of" for B) → [null, "ambiguous"] (the school may be in the list;
   a person decides).
4. Else an "Other" option: exactly "Other" first, then one starting with the word "Other", then one saying "not listed" /
   "not found" / "not in the list" → [that option, "other"]. "Other" is never chosen when rule 2 or 3 applied.
5. Else [null, null].
