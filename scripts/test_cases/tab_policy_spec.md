# Spec: does a runner's browser tab stay open when the run ends?

Rule (the user, 2026-11-05: too many tabs; close them after dry runs too): when an application run ends, its tab is
CLOSED whatever the outcome — dry run finished, submitted, blocked by a check, needs the user's answer to a question,
failed, unconfirmed, login timed out, stopped mid-way ("filled", "review", "handoff"), closed posting — because a stopped
run is always started again later in a fresh tab. The ONE exception is a run parked on a CAPTCHA / human check (status
"captcha"): that tab stays, since the user solves it in that very page. A keep-tab option set by the user keeps the tab
whatever the status. Status text may come in any case or with surrounding spaces.
