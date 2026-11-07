# Two checks

## citizenship(label) -> bool
True when a form question asks which COUNTRY the candidate holds citizenship (or citizenship / permanent residency) of —
e.g. "Do you hold Citizenship or Permanent Residency status from any of the following countries…?", "What is your country of
citizenship?", "Countries of citizenship", "Which country are you a citizen of?". False for yes/no status questions such as
"Are you a U.S. citizen?", "Are you a U.S. Citizen, a Lawful Permanent Resident …?", "Are you authorized to work…", and for
unrelated questions.

## followup(label) -> bool
True when an OPTIONAL question is a follow-up that only applies after a certain earlier answer, recognised by how the label
starts (case-insensitive): "If you selected Other", "If you chose …", "If you picked …", "If you answered …", "If other",
"If your selection …", "If your answer …", "If your response …", "If yes", "If no". False for labels that do not start that
way, including "If hired, …", "If offered employment, …", "If you are under 18 …" — wait: "If you are …" is NOT in the list,
so False — and any label where "if" appears later in the sentence.
