# Form replay (`replay.py --check`) — regression test of the answer rules on every stored form

Inputs: a corpus of stored form questions (each belongs to one run of one application folder); which folders were
SUBMITTED; a baseline (the accepted answer for each question); a reasons log; the current rules, which give each question
an answer {status: ok | unknown, value}.

Rules:
1. A question's answer "changed" when its status or value differs from the baseline. A question with no baseline entry
   yet is not a change. A different rule name alone with the same status and value is not a change.
2. A change on a question of a SUBMITTED folder needs a recorded reason for exactly the new answer. With no reason, or a
   reason recorded for a different value, `--check` fails (exit 1).
3. A change on a question of a folder that was not submitted is only reported; it never fails `--check`.
4. A current answer (status ok) on a high-stakes question that contradicts the candidate's facts (here: "Will you now or in
   the future require visa sponsorship?" answered "No" — the fact is Yes) fails `--check`, submitted or not — unless it was
   accepted as a known issue for exactly that value.
5. The first run with no baseline writes the baseline from the current answers; `--check` on that run passes (nothing has
   changed yet) unless rule 4 applies.
6. With no corpus at all, `--check` prints "skip" and passes.
7. Answers with status other than ok have no value (they compare by status only).
