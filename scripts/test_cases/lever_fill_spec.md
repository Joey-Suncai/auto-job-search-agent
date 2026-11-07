# What the Lever one-click fill may serve for one application folder

Inputs: the folder's plan (ats, fields in form order: [{key}]), its dry-run read-back record (fields: [{key, type, want,
ok}], problems: list) and whether the folder is already submitted. Output: [data, null] or [null, reason].
Refuse, in this order (first match wins), with exactly these reasons:
1. already submitted → "already submitted"
2. plan ats is not "lever" → "not a Lever folder"
3. no read-back record, or it has no fields → "no dry-run read-back yet (run run_form.py first)"
4. the read-back has problems (a non-empty list) → "the dry-run had problems: " + problems joined by "; "
5. any read-back field has ok false → "a field did not read back: " + the keys of those fields joined by ", "
Otherwise data = {"fields": [...], "files": [...]}:
- Go through the keys in the plan's field order, then any read-back keys not in the plan (in read-back order).
- Skip a key with no read-back entry, or whose want is null or "".
- A read-back field of type "file" → files gets {"key", "name": want}.
- Any other → fields gets {"key", "type": its type (missing → "text"), "value": want as a string}.
