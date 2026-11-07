# Oracle blank profile cards (JSA-226, an employer 2026-11-06)

`blank_card(title)` — a card in the candidate's Oracle profile (license, certificate, education, experience …) whose
title is Oracle's placeholder for an item with no name holds no candidate data and may be deleted. The placeholder
starts with the word "Unnamed" ("Unnamed License", "Unnamed Certification", "unnamed education"), case-insensitive,
leading/trailing spaces ignored. Any other title is a real card and is never deleted: a title that merely contains
"unnamed" later ("The Unnamed Project"), a word that only starts with the letters ("Unnamedly"), an empty title or None
→ False.
