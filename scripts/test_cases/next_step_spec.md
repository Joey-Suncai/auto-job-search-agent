# next_step — a concrete next step from a job e-mail when no model read it (JSA-265)

Joey's tracker shows, per application, "Action needed": what HE must do next. It must never be a generic line such as
"Read the email and act — see the link". Two pure Python functions:

## is_vague(text) -> bool
True when the text gives no concrete step: lower-case it, replace every character that is not a letter, digit or space
by a space, split into words, drop these filler words:
  read open check see the a an email mail message link it and act on take action follow instructions in as needed
  please accordingly respond your to do what asks
True when no word is left (an empty or blank text is vague). Otherwise False.
Examples: "Read the email and act — see the link" → True · "" → True · "Take the Coderbyte assessment" → False ·
"Check your email" → True · "Reply with your availability" → False.

## rules_action(kind, subject, body, date) -> {"action": str, "deadline": str, "reread": bool}
`kind` is the mail type: Assessment · Interview · Offer · Action · Rejection · Confirmation · Other. `date` is the message
date "YYYY-MM-DD". `subject` and `body` are plain text. The action text never contains the deadline (it is returned apart).

Kinds Rejection, Confirmation, Other → {"action": "", "deadline": "", "reread": false}, whatever the text says.

Deadline (Assessment, Interview, Offer, Action), from subject + " " + body:
- "within N days" → date + N calendar days. "within N business days" → the N-th weekday (Mon–Fri) after date.
  "within N hours" → date + ceil(N/24) days. N may be digits or a word one..ten.
- an explicit date after one of: by · before · no later than · due · deadline · deadline: · expires · expires on · until.
  Date forms: "November 12", "Nov 12", "November 12, 2026", "Nov. 12th", "11/12/2026", "11/12", "2026-11-12".
  A month-day with no year → the message year, or the next year when that date is before the message date.
- Several candidates → the earliest one that is on or after the message date. Candidates before the message date are
  ignored. None → "".
- Returned as "YYYY-MM-DD".

Assessment: "Complete the <P> assessment" + " (<D>)" when a duration is found + " via the link in the email".
- <P> = the first of these named in subject or body (case-insensitive), written exactly like this: HackerRank,
  CodeSignal, HireVue, Codility, CoderPad, Coderbyte, Karat, Pymetrics, SHL, Plum, Mettl, TestGorilla, Glider, Arctic Shores,
  Criteria, Pathstream, Vervoe; else "online".
- <D> = the first "N minutes" / "N mins" / "N min" / "N-minute" (→ "N min") or "N hours" / "N hour" / "N-hour" (→ "N h")
  that is NOT directly preceded by the word "within". None → no duration part.
Interview:
- the text names a scheduling tool or asks him to pick a time (calendly, goodtime, "schedule", "book a time", "select a
  time", "pick a time", "time slot") → "Book an interview time via the scheduling link in the email";
- else the text asks for availability ("availability", "available times") → "Reply with your availability for the interview";
- else → "Reply to confirm the interview".
Offer: "Review the offer and reply to the recruiter".
Action: the first sentence of the body (sentences end at . ! ? followed by a space, or the end) that asks him to do
something: it contains "please", "kindly", "you need to", "you must", "required to", or starts with one of complete, submit,
provide, upload, log in, sign, fill out, confirm, reply, respond, schedule, verify, access, review. Clean it: remove URLs
(http… up to the next space), remove a leading greeting ("Hi <name>, " / "Hello <name>, " / "Dear <name>, " — up to the
first comma; amended after the cases, see next_step_verdicts.json), then a leading "please " / "kindly " (case-insensitive), collapse spaces, strip trailing spaces and a trailing ":" or ",",
upper-case the first letter, and when longer than 160 characters cut at the last space before character 160 and add "…".
No such sentence → action = 'Open the email "<subject, first 80 characters>" and do what it asks — not read automatically
yet' and reread = true. reread is false in every other case.
