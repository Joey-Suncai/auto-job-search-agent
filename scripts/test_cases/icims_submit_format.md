Return {"cases": [...]}. Each case: {"name": str (unique), "fn": "submit_gate" | "after_submit" | "consent_gate" | "posting_key",
"args": [ ... positional arguments in the order of the spec's signature ... ], "expect": <the return value: a 2-item list for
submit_gate, a string for the others>, "spec": "quote of the spec sentence", "ambiguous": false}.
- submit_gate args: [submit (bool), no_advance (bool), steps (list of step objects as in the spec), consent ("ok" | "ask")].
- after_submit args: [url (str), text (str), before (int or null)].
- consent_gate args: [text (str or null), approved (list)].
- posting_key args: [url (str)].
Write 24 cases: submit_gate 8 (each check in order, check order when two apply, the inactivity notice, earlier-step
errors, a field without "ok"), after_submit 8 (done with and without a step bar, a thank-you sentence on an ordinary
step, next, refused with a bar and without one, pending), consent_gate 5 (empty, privacy-only, interview terms, beyond
wording, beyond wording with an approved snippet), posting_key 3 (classic tenant with a slug, login.icims.com, a query).
