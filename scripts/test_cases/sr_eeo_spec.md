# Two helpers

## plan_questions for an EEO block
A raw question {idx, type: "eeo", label, text, id, tag, required, radios: [], boxes: [], subs: [ids]} becomes one select
question per sub-list id: an id ending in "_gender" → {key: id, label: "What is your gender?", type: "select", required,
options: [], tag: "spl-autocomplete"}; an id ending in "_ethnicity" or "_race" → label "What is your race/ethnicity?";
other ids are skipped. Order = order of subs. An EEO block with no subs produces nothing.

## other_text(label) -> bool
True for a free-text follow-up that asks to spell out an "Other" choice: the label starts (case-insensitive) with "Other"
and within 30 characters has "free text", "specify", "please" or "describe" ("Other (free text)", "Other - please
specify"), or starts with "If other" or "Please specify". False for anything else ("Other information", "Others in your
household", "Specify your degree", "Additional information").
