# Mapping a yes/no fact onto a form question's options

Facts used (candidate): "Will you now or in the future require sponsorship?" → Yes (he will need H-1B later).
"Are you legally authorized to work in the United States?" → Yes. "Are you at least 18?" → Yes.
"Are you currently enrolled as a student?" → Yes.

Given the question label and its option list, pick the option that states the fact:
1. If an option starts with "Yes" (or "True") / "No" (or "False"), pick the one matching the fact, e.g. "Yes, I will
   require sponsorship" for a Yes fact.
2. Otherwise, if there are exactly two options phrased as statements — one affirmative ("I am…", "I do…", "I will…",
   "I can…") and one negative ("I am not…", "I do not…", "I don't…", "I will not…", "I can't…") — pick the affirmative one
   for a Yes fact and the negative one for a No fact.
3. Otherwise — more than two options and none starts with Yes/No/True/False (for example a list of visa situations such
   as "I am a U.S. citizen or permanent resident", "I currently hold OPT…", "I am authorized under CPT…") — the rule must
   NOT pick anything: the answer is "unknown" and the question goes to the candidate. Picking a sentence only because it
   begins with "I am" is wrong.
