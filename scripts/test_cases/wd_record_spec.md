# wd_record: what the Workday runner keeps for one form field (JSA-320)

Function record_field(f) -> dict. Input f is the runner's field after a page was handled, with keys:
label, section, type, required, answer (the planned answer), value (what the page held when the page was FIRST read,
before the runner filled anything — often a value parsed from the résumé), status ('ok' = the runner filled it,
'keep' = the page value was kept, 'skip', 'needs_user'), source, and optionally readback (the value read from the page
after the fill, a string, 'MISSING' when the field was gone) and readback_ok (bool, whether readback matched the answer).

Output dict keys:
- label, section, type, required, answer, status, source: copied unchanged (None when missing).
- before: the input's value (None when missing).
- page: readback when the input HAS a readback key (even if it is '' or 'MISSING'); otherwise the input's value.
- value: same as page.
- ok: only present when the input has readback_ok; then bool(readback_ok). Absent otherwise.
No other keys.
