# Form replay — the baseline grows by audit, reasons cite a source, a saved answer stamps only its own questions (JSA-351)

Builds on replay_spec.md (a corpus of stored form questions per application folder; which folders were SUBMITTED; a
baseline = the accepted answer per question; a reasons log; the current rules give each question {status: ok | unknown,
value}; a question's answer "changed" when status or value differs from its baseline entry; a question with no baseline
entry is not a change).

Rules:
1. **Audit merge.** A SUBMITTED form whose questions are not in the baseline at all, and whose folder has at least one
   independent-audit item that was judged (an audit item with a `check` of right / wrong / unsure, or a `judged` value),
   is merged into the baseline on the next replay: every one of its questions gets the current answer as its baseline
   entry. Only that form is merged — other forms' questions and other pending changes are not touched (a pending change
   on another form still needs its reason).
2. A form that was NOT submitted is never merged, audited or not. A submitted form without any judged audit item is not
   merged.
3. **New forms are compared too.** A submitted form not in the baseline (and not merged by rule 1) is reported as
   "new, not in baseline": the current answer is compared with the answer that was filled on the form, and the
   questions where they differ are listed. This is information only: it never fails `--check`.
4. **Reasons cite a source.** A reason counts only when its text cites where the decision came from: a dated decision of
   the user ("Joey 2026-11-16 …" — the user's name or "user"/"decision"/"decided", then a date YYYY-MM-DD), an audit
   item ("audit:" followed by the item's hex key), or a saved answer ("qa#" followed by its number). A changed answer on
   a submitted form whose only reasons cite no source still fails `--check` (exit 1), even when the reason was recorded
   for exactly the new value.
5. Recording a reason with no source (`--reason "because"`) is refused: exit 2, nothing written.
6. **A saved answer stamps only its own questions.** When the user saves an answer (the qa table gets one more entry),
   the replay is run with the rules before and after the new entry; the reason ("qa#N …") is recorded only for the
   questions whose answer differs between before and after AND that changed since the baseline on a submitted form.
   Questions that were already pending before the entry (changed since the baseline, but answered the same before and
   after) get no reason and keep failing `--check` until they get their own.
7. If the new entry changes no answer, nothing is recorded.
8. A rule whose answer is today's date (signature date) is not a change when only the date differs.
