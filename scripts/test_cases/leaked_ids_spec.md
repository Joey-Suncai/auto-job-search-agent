# leaked_ids(text, known) -> sorted list

known = a set of story-bank IDs such as "S1", "S6", "S8ctx", "M2", "JSA05", "HP07", "PROFILE", "SK20", "FS04".
Return, sorted, every ID in known that appears in text as a whole token: case-sensitive (so "profile" or "m2" do not count),
not inside a longer word or number ("S10" does not contain "S1"; "M2M" does not contain "M2"), and not joined by a hyphen
("S6-like" does not count, "co-M2" does not count). Punctuation or parentheses around it are fine ("(M2).", "S6,", "[JSA05]").
Empty or missing text → [].
