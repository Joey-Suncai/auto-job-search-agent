# Spec: JSA-260 — a wrong answer the current rules already fix is not counted as wrong

Joey 2026-11-09: when the audit finds a wrong answer on an old form, and the current rules now answer that question
right, it is not counted as wrong. A form submitted inside a platform's RE-CERTIFICATION window still counts (new
submissions must be right as submitted).

## 1. summary(items) → {platform: {...}, "all": {...}}
items: {"platform": str, "judged": "right"|"wrong"|null, "check": "right"|"wrong"|"unsure"|null, "covered": {...}|absent}.
State: "wrong" when judged "wrong"; "right" when judged "right", or judged null and check "right"; else "pending".
Per platform and for "all": answers = number of items; wrong = wrong items WITHOUT covered; covered = wrong items WITH a
truthy covered — the key "covered" is present ONLY when it is > 0; pending = pending items. Let n = answers − pending −
covered. accuracy = (n − wrong) / n rounded to 4 decimals, null when n = 0. low95 = the Wilson 95 % lower bound of that
rate (z = 1.96), floored at 0, 4 decimals, null when n = 0.

## 2. audit_gate(items, window, need=10, noncrit=0.95, keep_covered=False) → dict
items: {"folder", "judged", "check", "cls": "critical"|other, "covered"}; only items whose folder is in window count.
forms = distinct counted folders. For each counted item: if its state is wrong AND covered is truthy AND keep_covered is
false → adds 1 to "covered" (key present only when > 0) and to nothing else. Otherwise: pending → pending; wrong →
critical_wrong (cls "critical") or noncrit_wrong; right and not critical → noncrit_right (critical right adds nothing).
noncrit_accuracy = noncrit_right / (noncrit_right + noncrit_wrong), 4 decimals, null when 0. ok = forms >= need and
pending == 0 and critical_wrong == 0 and (noncrit_accuracy null or >= noncrit). With keep_covered true, covered wrong
items count as wrong like any other.

## 3. score(...) wrong-answer counting (only this part)
A platform's critical_wrong / noncrit_wrong count the wrong_answers lines {"folder", "field", "class", "covered"} of its
submitted folders. A line with a truthy "covered" is NOT counted — except when the platform has a re-certification
window {"since"} and the folder's first submit time (first 19 characters of "at") is >= since: then it counts (also as
recert_wrong when critical).
