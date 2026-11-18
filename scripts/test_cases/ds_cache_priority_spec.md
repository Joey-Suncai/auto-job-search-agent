# ds_cache_may_answer(rule, ds_value) — spec (JSA-337, 2026-11-17)

A job-application form field can have a cached DeepSeek triage answer (`ds_answers.json`, written on an earlier run when
no rule could answer the question) and, now, an answer from the standard rules (`rule`: the answer rules, which include
Joey's saved question-and-answer table "qa"). Joey's saved facts and qa answers must always win over a cached model
answer; the cache only fills what the rules cannot answer.

`rule` is the rules' verdict for the field (a JSON object, possibly empty). `ds_value` is the cached answer (string or null).
Return true when the cached DeepSeek answer may be used for the field, false when it must be ignored.

- `ds_value` null or empty string → false (nothing cached).
- `rule.status == "ok"` and `rule.leave` is not true → false (the rules have an answer; it wins, even when it differs from the cache).
- `rule.no_auto` is true → false (a question Joey answers himself; a model never fills it).
- `rule.ask` is true (the rules know the question, the answer is Joey's) → false.
- `rule.status == "consent"` → false (consent boxes are the rules' business).
- Otherwise (empty rule, `status` "ok" with `leave` true, or any other status such as "none") → true.
