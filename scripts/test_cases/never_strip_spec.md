# ds_materials.strip_never(text, phrases) — JSA-264

A Confirmed story given to the letter writer may contain a name that must never appear in a letter or answer (e.g. the
school "XJTLU"). `strip_never(text, phrases)` takes each phrase out of the text, so the writer cannot copy it.
`phrases` is a list of names, longest first. For each phrase, in this order, case-insensitive, the phrase matched as a
whole word (word boundary right after it):
1. " in|at|of [the ]<phrase>" (with the whitespace before "in/at/of") is removed: 'the "Voice in XJTLU" flagship' →
   'the "Voice" flagship'.
2. ", <phrase>" (comma, optional spaces) is removed: "U-stage Voice Club, XJTLU, 2022–2024" → "U-stage Voice Club, 2022–2024".
3. " (<phrase>)" (optional space before the parenthesis, optional spaces inside) is removed.
4. Any remaining "<phrase>" plus the whitespace right after it is removed: "XJTLU students" → "students".
A text without the phrase is returned unchanged. A non-string (None, a number) is returned as it is. An empty phrases list
returns the text unchanged. Text after the removed part is kept exactly (punctuation, quotes, other words).
