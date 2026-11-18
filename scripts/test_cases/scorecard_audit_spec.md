# Spec: JSA-258 — the independent audit as a certification bar

## 1. audit_gate(items, window, need=10, noncrit=0.95) → dict
items: audit items of ONE platform, each {"folder": str, "judged": "right"|"wrong"|null, "check": "right"|"wrong"|
"unsure"|null, "cls": "critical"|"non-critical"}. window: list of folder names that count. Only items whose folder is
in window count; all others are ignored.
An item's state: "wrong" when judged is "wrong"; "right" when judged is "right", or when judged is null/missing and
check is "right"; otherwise "pending" (e.g. judged null with check "wrong" or "unsure"). An item is critical when cls is
"critical", otherwise non-critical.
Result keys (exactly these):
- forms: number of DISTINCT folders among the counted items;
- pending: counted items in state pending;
- critical_wrong: critical items in state wrong;
- noncrit_right / noncrit_wrong: non-critical items in state right / wrong;
- noncrit_accuracy: noncrit_right / (noncrit_right + noncrit_wrong) rounded to 4 decimals; null when that sum is 0;
- ok: forms >= need AND pending == 0 AND critical_wrong == 0 AND (noncrit_accuracy is null OR noncrit_accuracy >=
  noncrit). Critical right items count toward forms but not toward any other number.

## 2. window_folders(results, recert) → {platform: sorted list of folders}
results: runner lines {"folder", "at" (ISO time string), "status", "url" (optional), "ats" (optional)}. Only lines whose
folder starts with a date "YYYY-MM-DD_" count. Lines are taken in order of "at". A folder's platform comes from its
EARLIEST line: url containing "greenhouse" → greenhouse, "myworkday" → workday, "lever.co" → lever, "ashbyhq" → ashby;
else that line's "ats"; else "other". A folder is in the result only if it has a line with status "submitted"; its
submit time is the earliest such line's "at". recert: {platform: {"since": time string}} or null. For a platform in
recert, a folder counts only when its submit time (first 19 characters) >= since (first 19 characters); for other
platforms every submitted folder counts. Platforms with no folder are absent.

## 3. sample(folders, audited, n, seed, first=None) → sorted list
The pool is the sorted set of folders minus audited. n <= 0 or an empty pool → []. With first=None: up to n folders
from the pool chosen at random (seeded). With first given: the result holds min(n, W) folders from the pool that are in
first (W = how many such pool folders there are), and only if that is less than n, further folders from the rest of the
pool up to n in total (or as many as exist). Result sorted ascending, no duplicates, never an audited folder.
(Which random folders are chosen is not specified — check only sizes and membership.)

## 4. audit_cell(g) → str
g null/empty → "—". Otherwise "<forms> forms · <pending> waiting · critical <critical_wrong>" + (when noncrit_accuracy
is not null: " · non-critical <accuracy × 100 with one decimal> %") + " ✅" when ok else " ❌".
Example: {"forms": 10, "pending": 0, "critical_wrong": 0, "noncrit_accuracy": 0.9667, "ok": true} →
"10 forms · 0 waiting · critical 0 · non-critical 96.7 % ✅".
