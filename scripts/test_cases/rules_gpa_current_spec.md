# Current GPA vs. GPA on file — spec (2026-11-05, Joey: Erie "current cumulative GPA" = N/A)

An application form asks for a GPA. The candidate finished a bachelor's degree (it has a GPA on file, written
`GPA_ON_FILE` in the cases) and is now in a master's program that has no GPA yet.

Which answer a GPA question gets (the question label; "any case" everywhere):

1. **Current GPA → "N/A".** The label contains the word "current" or "present" and, within the next 40 characters
   (no "?" in between), "GPA" (as a word) or "grade point average" — e.g. "What is your current cumulative grade point
   average?", "Current overall GPA", "Current GPA (if applicable)", "Please enter your present GPA". The answer is the
   text "N/A". When the question shows a list of options, the pick is the first option that is exactly "N/A" or "NA"
   (slash optional), else one containing "not applicable", else one starting with "N/A", else one starting with
   "Other"; if none of those exists the question is left unanswered (`none`).
2. **Exception — the bachelor's GPA.** A label that mentions "undergrad" / "undergraduate" / "under grad", "bachelor",
   "bachelor's" or "high school" anywhere is never rule 1, even with "current" — e.g. "Current undergraduate GPA" →
   GPA_ON_FILE (rule 3).
3. **Any other GPA question → GPA_ON_FILE**: the label contains "GPA" as a word or "grade point average" and rule 1
   does not apply — e.g. "GPA", "Cumulative GPA", "What was your GPA?", "Grade point average (4.0 scale)", "GPA
   (current or most recent)"? — no: here "current" is followed by " or most recent)" and then nothing; "GPA" comes
   BEFORE "current", so rule 1 (which needs "current" first, then GPA) does not apply → GPA_ON_FILE.
4. "Are you currently enrolled …" questions are not GPA questions even if they mention GPA later — out of scope, do not
   write such cases.

Words order matters for rule 1: "current" / "present" must come before "GPA" / "grade point average".
