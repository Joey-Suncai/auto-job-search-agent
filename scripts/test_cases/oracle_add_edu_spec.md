# Spec: filling a new Education item on an Oracle application form (JSA-328)

Four pure functions.

1. school_pick(want, options, alts) -> option | null
   - an option equal to `want` or to one of `alts` (case and runs of spaces ignored) wins;
   - else the ONE option whose words include all of the school's words (words split on anything not a letter/digit;
     "of", "the", "at", "and", "in" ignored): "University of Illinois Urbana-Champaign" → "University of Illinois at
     Urbana-Champaign". When two or more options contain all the words, or none, this step gives nothing;
   - else an option like "Other - School Not Listed" (starts with "Other", contains "School" and "not listed");
   - else null. A different campus ("University of Illinois at Chicago" for Urbana-Champaign) is never picked.
2. major_pick(major, prefs, options) -> option | null
   - the first of [major, ...prefs] that equals an option (case ignored) → that option;
   - else an option starting with "Other" that contains "not listed"; else null. Partial matches don't count
     ("Agricultural Economics" is not "Economics").
3. degree_pill(level, pills) -> pill | null
   - level "master" → the first pill starting with "Master" ("Masters", "Master's Degree");
     "bachelor" → starting with "Bachelor"; "phd" or "doctorate" → starting with "Doctor" or "Ph.D"/"PhD";
   - never "Postdoctorate", "Graduate Diploma", "Associates"; unknown level or no fit → null.
4. empty_required_lists(blocks) -> [titles]
   - blocks: [{title, required (bool), items (int), add (button text)}]; return the title (else the add text) of each
     block that is required and has 0 items, in order.
