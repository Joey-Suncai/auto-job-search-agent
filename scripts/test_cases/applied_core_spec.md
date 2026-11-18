# "Applied before" matches the full company name, never only its core (JSA-376)

The form-answer rules answer "Have you previously applied to <company>?" from the user's application tracker (a list of
companies he applied to, with dates). Company names often differ only by a generic suffix or word: Inc, LLC, Corp, Ltd,
Co, Group, Holdings, Technologies, Tech, Labs, Services, Global, International …

Rules:
1. The hiring company and a tracker company are **the same** when their names are equal after removing punctuation, case,
   "&"/"and", ".com" and only legal-form words (Inc, LLC, Corp, Corporation, Ltd, Limited, Co, Company, PLC, LP, LLP, "The")
   — "Acme Inc" = "Acme" = "ACME, Inc.".
2. Names that differ in a **descriptive word** (Labs, Technologies, Tech, Services, Group, Holdings, Global,
   International, Systems, Capital …) are **different companies**: "Prior Labs" is not "Prior Technologies"; "Nova Group"
   is not "Nova Capital". The tracker never proves "applied before" for a different company.
3. When only the core name (name without those words) matches and the full names differ, the rules do **not** answer Yes
   from the tracker. They do not invent a fact: the question is **asked** (answer unknown), or answered No when the tracker
   has no row for that company and no look-alike. Never Yes.
4. A tracker row with the same full name (rule 1) applied before today → Yes. No such row and no look-alike → No.
5. A look-alike (same core, different full name) with no same-name row → asked.
