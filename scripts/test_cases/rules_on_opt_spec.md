# "Are you on OPT?" vs. OPT named as an example — spec (2026-11-05, Goldman)

The candidate is an F-1 student, NOT on OPT now (internship on CPT). Rule `on_opt` answers **No** to questions that ask
whether the candidate is currently on OPT: the label has "currently" or "now" and, within the next 60 characters,
"OPT" (as a word) or "optional practical training"; or the label says "on OPT" / "on STEM OPT" (any case).

Exception (added 2026-11-05): `on_opt` does NOT take a label that asks about work authorization in general and names
OPT only as one example — any label containing "legally authorized to work" / "legally authorised to work" / "legally
able to work", or "hold valid work authorization" / "obtain valid work authorization" (optionally "US" / "U.S." before
"work"), or "can obtain" / "can you obtain" / "can commence", or "e.g." followed (within 80 characters, before any ")")
by "OPT". Such a label is then answered by no rule here (expected answer "none": the runner stops for the candidate).

Expected answers in the cases: "No" (on_opt answers) or "none" (not answered by on_opt — some other rule may exist, but
for these cases write only labels where the exception or a non-OPT wording applies and expect "none").
