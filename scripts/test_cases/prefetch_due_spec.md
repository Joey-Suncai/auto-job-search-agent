# Spec: form-prefetch questions waiting for Joey (JSA-243)

A daily routine writes a question sheet (JSON). A session must ask Joey the questions that still need him.

## answer_of(sheet, q)
The answer that would be applied for one sheet entry q:
- q's own "answer" when it is truthy (a non-empty dict such as {"yes": true} or {"pick": "..."}).
- otherwise, only when sheet["accept_derived"] is true AND q["block"] == "derived" AND q["risk"] is falsy AND
  q["kind"] != "high_risk": q["suggested"] if it is truthy, else None.
- otherwise None. An empty dict / null answer counts as no answer.

## pending(sheet, handled)
Ids (q["id"]) of the sheet's questions whose answer_of is None, in the order they appear in sheet["questions"].
Returns [] when: sheet is not a dict (None, a list, a string), sheet has no "name" or an empty name, or sheet["name"] is
in `handled` (a list or set of sheet names that were already handled; None means none handled).
Entries of "questions" that are not dicts are ignored. A missing "questions" key means no questions.

## line(sheet, ids)
One status line.
- ids empty → exactly "prefetch questions: none waiting (<name>)" where <name> is sheet["name"], or "no sheet" when the
  sheet is not a dict or has no name.
- otherwise it starts with "prefetch questions: <len(ids)> waiting on <name> — answering them makes <G> more of <J>
  prefetched jobs ready (<N> ready now)." where N = summary.ready_now, J = summary.jobs, G = max(summary.ready_after -
  summary.ready_now, 0); missing summary values count as 0.

## recheck(recs, answer, today)
recs: list of job records {"id", "status", "questions": [...], "files": [...], "joey_tasks": [...], "needs", "ready"}.
Each question: {"label", "type", "options", "required", "route", "rule"}.
A question is a CANDIDATE when the record's status is "ok", question.required is true, question.route != "used", and
question.rule is "none" or "per_job" (rule "uncertain" or anything else is never a candidate).
`answer` is called ONCE with a list of unique {key, label, type, options} (unique by label + type + options; type
missing → "text"; options missing → []), and returns {key: result}. It is not called at all when there are no candidates.
A candidate whose result has status "ok" and no truthy "ask" and no truthy "uncertain" becomes route "used", gets
"rechecked" = today and "rule_now" = result["rule"]. Every other question is left unchanged.
For every record that changed: needs = (number of required questions whose route != "used") + len(files) +
len(joey_tasks); ready = (status == "ok" and needs == 0). Records that did not change keep their needs / ready.
Returns the list of ids of changed records, each id once, in the order of recs.

## push_line(summary)
None when summary.questions is 0 / missing / summary is None. Otherwise a (title, body) pair: title
"求职助手：<questions> 道表单题待答"; body contains "答完可多投 <G> 个职位" with G = max(ready_after - ready_now, 0)
and "现在 <ready_now> 个可直接投".

## due_note(mode, status_line)
mode is "using", "developing", "release" or "unknown". status_line is the output of line().
Returns "" when status_line is empty, when mode is not "using"/"developing", or when the line says "none waiting".
mode "using" → a string that starts with "FORM QUESTIONS WAITING (JSA-243) — " followed by status_line, and contains
"AskUserQuestion". mode "developing" → a string that starts with "Note for Joey (JSA-243): ", contains the count part of
status_line, says the questions are answered in a using session (contains "using session"), and does NOT contain
"AskUserQuestion".
