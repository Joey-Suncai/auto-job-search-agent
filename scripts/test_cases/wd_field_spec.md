# wd_field: the submitted value of one field from an old or new Workday log (JSA-320)

Function wd_field(f, failed) -> dict. f is one field dict from a Workday run log: label, section, type, required,
answer (what the runner meant to type, a string or None), value, status ('ok' = the runner filled it, 'keep', 'skip',
'needs_user'), source, and in NEW logs also `page` and `before`. failed is a set of (section, label) tuples: fields whose
read-back check failed.

Rules:
1. If f has a 'before' key or a 'page' key (a new log), return f unchanged.
2. Else, if f['status'] == 'ok' AND (f.get('section'), f.get('label')) is not in failed AND f['answer'] is a string
   (empty string counts as a string): return a copy of f with two added keys: 'before' = f.get('value') and
   'page' = f['answer']. All other keys unchanged.
3. Otherwise return a copy of f unchanged (no added keys).
The input dict is never modified.
