# Spec: JSA-246 — five form-answer fixes found by the independent audit

All cases run ONE form field through the full rule set with a fictional candidate's profile and no saved answers:
- home city Springfield (lives in Springfield; willing to relocate anywhere in the U.S.; willing to work on-site);
- needs NO visa sponsorship NOW (the internship is on CPT) but WILL need sponsorship in the FUTURE (after graduating);
- marketing opt-ins: always No; required privacy / data-processing consent boxes: Yes;
- pay: a free-text pay question gets "Open / per internship program standard"; a DIGITS-ONLY pay box gets 25 for an
  hourly rate and 52000 for an annual / yearly salary;
- reason for leaving past jobs: "Fixed-term internship that ended as scheduled; returned to school full time.";
- current / most recent employer: "Example State University".

## 1. Sponsorship asked about THIS internship = the NOW answer
A question whose wording asks whether the candidate needs sponsorship "for this internship", "during the internship" or
"to begin / start working" (and does NOT also say future / ever / after graduation / at any time / later / eventually)
is the NOW question → No. With options Yes / No → "No". A question that says "now or in the future", "in the future",
"ever", "after graduation" or "at any time" is the FUTURE question → Yes. "Are you eligible to work ... WITHOUT
sponsorship for this internship?" is the opposite wording → Yes.

## 2. Marketing consent
A checkbox or Yes/No question that is a marketing opt-in → No (a checkbox with no options answers "No", which leaves it
unchecked). Marketing opt-ins include labels like "Consent: marketing", "I consent to receive marketing
communications", "Opt in to marketing emails", "marketing purposes". A consent to the processing of personal data /
privacy notice that does not mention marketing stays Yes.

## 3. Options that claim the candidate already lives somewhere
For a relocation, on-site, commute or local-area question with options: an option saying the candidate already is /
lives / is located / is based in a place ("Yes, I'm in SF / Bay Area ...", "Yes, I am located in Idaho ...",
"I live in Boston") is false unless that place is Springfield. Instead the rule picks the option about relocating
("Yes, I'm willing to relocate ...", "planning on relocating") that is not negative (not "not willing", "unable",
"cannot", "no"). No such option → status unknown. An option that claims Springfield is true and may be picked. Options
that claim no place ("Yes", "Yes, I can commute") work as before (Yes).

## 4. Digits-only pay box
A pay / salary / compensation text box (no options) whose label says the answer must be digits only — "numerical
format", "numbers only", "digits only", "without special characters", "whole number" — gets "25" when the label says
hourly / per hour, "52000" when it says annual / yearly / per year / salary (and not hourly). A digits-only pay box
naming neither hour nor year nor salary → unknown. A pay text box with no digits-only wording → "Open / per internship
program standard".

## 5. Reason for leaving
"Reason for leaving", "reason(s) for leaving any job(s) held ...", "Why did you leave your last job?" → the reason-for-
leaving text above, never the employer name. "Current or most recent employer" still → "Example State University".
