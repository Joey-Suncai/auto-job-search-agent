# facts_check — history and stale numbers (addition to facts_check_spec.md)

A fact may carry "history": a list of {"as_of": "YYYY-MM-DD", "A": "...", "R": "...", "numbers": [...]} — what was true at an earlier date.
For a bullet mapped to facts (same mapping rules as before: anchors of the CURRENT fact, case-insensitive substring):
- A bullet number found in a mapped fact's current S/T/A/R text or "numbers" → fine.
- A bullet number found only in a mapped fact's history (its A, R or numbers) → NOT a problem; it is reported as a "stale" warning (the result is still "pass" when nothing else is wrong).
- A bullet number found in neither → problem "unsupported number" (as before).
- History never adds anchors: a bullet that matches only words in a history entry is still "unmapped".
Number normalization is the same as before (¥ $ € £ % + and thousands commas removed; decimals kept; "0–100" = two numbers 0 and 100).
History entries are not schema-checked and their numbers are not checked against the fact's text (no "number drift" for history).
