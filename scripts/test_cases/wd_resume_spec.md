# Workday checkpoint and resume — spec (JSA-392, plan C approved by Joey 2026-11-17)

A Workday application has pages shown in a progress bar (for example: My Information, My Experience, Application Questions,
Voluntary Disclosures, Self Identify, Review). When the runner stops and is run again, it must not walk and re-save the pages
it already saved (re-saving My Experience can drop the second school). It records the pages it saved, and on the rerun it jumps
the progress bar to the first page that is not saved yet.

## norm_step(name) -> str
A step name as the progress bar shows it, normalised: the screen-reader prefix "current step N of M" (any case, any numbers,
also "completed step N of M" and "step N of M") removed, whitespace collapsed to single spaces, trimmed, lower case. None or blank → "".

## checkpoint_update(cp, step, at) -> dict
`cp` is the saved checkpoint (a dict with "done": [normalised step names in the order they were saved] and "at"), or None / {}.
Returns a NEW dict {"done": [...], "at": at}: the old list followed by norm_step(step) when that is non-empty and not already
in the list (order kept, no duplicates). `cp` itself is not changed.

## resume_target(done, bar) -> str | None
`done` = the saved step names (normalised or not), `bar` = the progress bar's step names in bar order (as shown, not normalised).
Returns the bar entry (exactly as given in `bar`) of the FIRST step that is not in `done` (compare with norm_step), skipping steps whose
normalised name starts with "create account" or "sign in" (the account step is not an application page). Returns None when:
- `done` is empty (nothing saved yet: nothing to skip);
- the first such step is also the very first application page of the bar (nothing would be skipped);
- every step is in `done`.
