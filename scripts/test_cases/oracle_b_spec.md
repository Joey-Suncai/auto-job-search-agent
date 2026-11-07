# consent_approved(text, cli, approved) — spec (run_oracle.py, 2026-11-03)

`text`: the consent box text on an Oracle e-mail step (string, may be empty). `cli`: a text the candidate approved on the
command line (string, may be ""). `approved`: a list from the profile, each item either an object with a "contains"
string (other keys ignored) or a plain string; items may be null / missing "contains".
Normalise every string by collapsing whitespace runs to one space, trimming, and lower-casing. Return true when the
normalised `cli` or any item's normalised snippet is NON-empty and occurs inside the normalised `text`; otherwise false.
