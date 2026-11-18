# Job-mail reader: rules, matching, and Claude failures (JSA-280)

The mail check reads each job mail. With a Claude reader, Claude's verdict decides; the keyword rules are a filter.
Without a reader (rules-only mode) the rules decide alone.

## 1. classify(subject, body) → type
Types: Rejection, Assessment, Interview, Action, Confirmation, Other; None = ignore (security / verification codes,
surveys, job alerts in the SUBJECT).
- A mail that says a draft was saved / asks him to "continue to apply" / "complete and submit your job application" → Other.
- A subject saying the application was received/submitted ("We received your application", "Application submitted") →
  Confirmation, even when the body lists later statuses such as "Not selected — we will not be moving forward".
- Rejection wording anywhere: "unfortunately", "not moving forward", "decided not to", "other candidates", "made the
  decision not to move you forward", "not able to move forward with your candidacy", "unable to move forward",
  "regret to inform", "position has been filled". A mail titled "Thank you for your application" whose body says
  they chose other candidates is a Rejection.
- Conditional sentences are not invites: a sentence with "if", "may", "might", "once", "upon", "should you", "will
  contact you", "will reach out", "potential fit" names a possible later step. "The next step may include a HireVue
  interview", "If selected you will receive a HackerRank assessment", "we will contact you to schedule an interview"
  do NOT make the mail an Assessment or Interview, and "If you were requested to provide additional info" does not make
  it an Action.
- Otherwise, first match wins: Assessment (assessment, HackerRank, CodeSignal, HireVue, coding challenge, take-home) →
  Interview (interview, phone screen, schedule a call, your availability) → Action (additional info, action required,
  please complete/provide/submit) → Confirmation ("thank you for applying", "we received your job application",
  "your application has been received") → Other.

## 2. match(apps, sender, subject, body, date) → application row or None
apps rows: {job_id, company, title, status, applied_on}. Rows with status Shortlisted or Archived are never matched.
- The full company name (lower-cased; punctuation removed; Inc / LLC / Corp / Company / Group / Technologies / Labs …
  removed) counts when it appears as whole words in the sender or subject, or — only when the sender is an
  applicant-tracking system (greenhouse, myworkday/workday, lever.co, ashbyhq, smartrecruiters, icims, workable,
  oraclecloud, or an address containing talent / recruit / hire.) — in the body.
- The first word of a multi-word company name counts alone only when ALL hold: it has ≥ 3 letters, it is not an ordinary
  English word (applied, base, human, major, dynamic …), no other company in the tracker starts with the same word, it
  appears in the sender or subject (never the body), and the sender is an applicant-tracking system or the word is a
  label of the sender's e-mail domain (e.g. "imc" in recruiting@imc.com).
- Several rows match → the one sharing the most title words with the subject + body, words compared by their first five
  letters (Science = Scientist, Analyst = Analytics), ignoring intern / internship / summer / years / program; ties → the
  row applied most recently on or before the mail date; rows applied after the mail date rank last.

## 3. apply_mail(apps, emails, m, reader) — bulk mail and Claude failures
- A bulk mail (List-Unsubscribe / newsletter, m.bulk true) from a sender that is not an applicant-tracking system is
  dropped (returns None, nothing stored) — even when the sender name is the company.
- reader.read(m) may raise (credit balance too low, bad key, API down). Then the application rows never change (no
  status, last_email or action), not even for a rejection. If the rules matched an application or the sender is an
  applicant-tracking system, one row is stored with type "Pending", job_id "", reread true, rules_type = the rules' type;
  else nothing is stored. Returns None.
- A stored row with reread true is read again by the next run with a reader. Success → Claude's verdict applies fully
  like a fresh read: the row gets Claude's type and job_id; a stage move the old row made is undone (Assessment →
  back to Applied); then Claude's type moves the stage (Rejection → Rejected; Assessment → Assessment only from Applied).
  applied_on never changes.

## 4. reader_health.update(state, fails, oks, now) → (state, alert)
- oks ≥ 1 → ok true, no alert. No reads (fails empty, oks 0) → state unchanged, no alert.
- Only failures → ok false; `since` = time of the first failure of this outage, kept across runs.
- One alert when the failures have lasted MORE than 2 hours since `since`; never a second alert for the same outage; a
  new outage (after a good read) may alert again. No alert at 2 hours or less, whatever the cause.
- The alert body names the cause: "credit" when the error says "credit balance is too low", "auth" for an
  authentication / API-key error, else "error".
