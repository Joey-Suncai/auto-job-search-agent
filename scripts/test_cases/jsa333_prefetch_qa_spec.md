# Prefetch answers that could not be stored or answered (JSA-333)

Three behaviours of the application-form answering rules. A candidate's answers to a form question are saved in a
question-and-answer table (`qa`); the rules answer a form field from that table or from fixed rules.

## 1. "Have you applied before?" (rule applied_before) — the tracker decides
The candidate's tracker lists the companies he applied to with the date. For a question "Have you applied to <company> …?"
the rule answers Yes when the tracker holds an application to that company dated before today and inside the window the
question names ("within the last 12 months", "in the past 2 years"); otherwise No. A window written as a range
("within the last 12-18 months") means the LONGER bound (18 months): the question asks whether any application falls
inside the range's span. A question about ONE role or ONE season ("Have you applied for THIS position?", "during this
recruiting season") is not a state the tracker can answer: the rule asks the user instead ("ask").
The question's own asking sentence decides. A trailing reminder / note sentence that mentions "this position" or "the
current recruitment season" ("As a reminder, if you have already applied for this position during the current recruitment
season and were not selected, you may reapply when the next season begins") must NOT turn a question that also says
"or another role" into a one-role question. Example question: "Have you applied to this role or another role @a Greenhouse employer within
the last 12-18 months? As a reminder, if you have already applied for this position during the current recruitment season
and were not selected, you may reapply when the next recruitment season begins in 2027." Tracker: a Greenhouse employer applied 2026-10-31,
today 2026-11-17 → Yes. "Have you applied for this position?" (no "or another") with a hit → ask. A tracker application
older than the window (e.g. 20 months ago for "last 12-18 months") → No.

## 2. Standard Lever "Stay Connected" notice box (rule lever_safe_sender)
Lever forms end with ONE checkbox that only acknowledges a notice about e-mails: its label starts "Stay Connected |" and asks
the applicant to add the sender (no-reply@hire.lever.co, sometimes also the company's domain) to the safe sender list and
check spam. The box has exactly one option, an acknowledgement ("I understand that next steps will be sent via email and I
have marked the sender addresses above as safe."). The candidate always ticks it (it is an acknowledgement, no fact about him):
the answer is that single option, whatever company domain the notice names. A label that merely mentions "safe sender list"
inside another question, a field with several options, or a box that asks for a fact is NOT this rule (no answer from it).

## 3. Saving a new qa entry when an older entry overlaps (qa_add.py)
Before a new entry is saved it is checked against the table (an older entry catches the new question, or the new entry's
regex catches an old entry's question). With the SHAPE of the form field given (the field's option list; empty list = a
text box), an older entry that catches the question but gives NO answer on that shape (it is a list-answer entry whose
picks match none of the options, or a list-answer entry on a text box) does not block the save: the new entry answers that
shape (newest first) and the older entry keeps answering the shapes it can. An older entry that DOES answer on that shape
still blocks (two answers for one field = the user decides). When no shape is given the old behaviour holds: every
catching entry blocks. The "new entry catches an old entry's q" direction always blocks.
