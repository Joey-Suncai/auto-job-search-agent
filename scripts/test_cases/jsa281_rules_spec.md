# Form-answer rules for critical questions (JSA-281)

The rules answer job-application questions for one candidate from his facts. Each question has a label, optional options
(a list the form offers) and the hiring company. The answer is one option text (exactly as offered), a text (for a box
with no options), "empty" (the field is deliberately left blank), or "unknown" (the rules do not answer: the candidate
is asked).

## The candidate's facts
- Never convicted of any crime (fact: conviction = No). He agrees to background checks and drug screens (Yes).
- F-1 student. Authorized to work in the U.S. for the internship (CPT through his school) = Yes, but NOT authorized to
  work for ANY / ALL employers without restriction (F-1 / CPT is employer-specific) = No.
- Education: B.A. Economics, University of Illinois (completed 2026-05). M.S. Applied Data Science, University of
  Chicago (current, 2026-09 to 2027-12). No second major, no minor.
- Name pronunciation: "AL-ex DOH (I go by Lex)". Full name: "Alex Doe".
- Pay expectation: "Open / per internship program standard".
- Applications so far (the tracker): Acme Corp applied 30 days ago; Globex Inc applied 400 days ago. No other company.

## What the rules must do
1. Conviction questions ("Have you (ever) been convicted of …?", felony, "pleaded guilty", "criminal record") are answered
   from the conviction fact: No. A long notice that mentions a "criminal background check" before the actual question
   does not make it a background-check question: the sentence that asks (ending in "?") decides. A question that only
   asks for consent to a background check or drug screen is answered Yes. When the asking part names both a conviction
   and a background check, or it is unclear, the answer is unknown.
2. "Are you authorized to work for any employer / all employers / any U.S. employer / any US Employer?" = No (F-1),
   also when the label writes "U.S" without the final dot. Plain "Are you legally authorized to work in the United
   States?" = Yes.
3. Major questions: an undergraduate major ("Undergrad Discipline(s)", "Undergraduate major", "Bachelor's major") is
   Economics — pick the option "Economics" when offered; if the options have no Economics, unknown. A "Secondary Major",
   "Second major", "Double major" or "Minor" question is left empty (he has none). A plain "Major" / "Field of study"
   question is his current degree's field (Data Science family).
4. Name pronunciation questions — also misspelled "pronounciation" — get the pronunciation text, never the full name.
5. Pay questions, including "What is your target compensation (salary and bonus)?", get the pay text. A question only
   about a bonus ("What are your bonus expectations?") is not this pay question.
6. "Have you previously applied to <company>?" / "ever applied … before" / "applied … in the last N months" are answered
   from the tracker for the hiring company (or a tracker company named in the question): an application before today
   (inside the window when the question gives one) → Yes; none → No. An unknown company (none given, none named) →
   unknown. When the tracker has the company but the question asks about "this role / this position" or "this recruiting
   season", the answer is unknown. "Have you previously been employed by or applied to <company>?" is Yes when the
   tracker has an application. "Have you previously worked at <company>?" is NOT an application question (No — he never
   worked there).
