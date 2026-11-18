# Fact gate before submit (JSA-281)

Before a job application is submitted, every answered field (label, value, field type, the options the form offered,
and which source wrote the value) is checked against the candidate's facts. A field that contradicts a fact BLOCKS the
submit (the candidate is asked). Everything else PASSES — the gate must not block correct answers or questions it is not
about. Each block names its kind: conviction, any_employer, degree_level, major, start_date, pattern, qa.

## The candidate's facts
- Never convicted (conviction = No).
- F-1 student with restricted authorization (CPT): authorized to work for ANY / ALL employers = No.
- Education: B.A. Economics (completed 2026-05); M.S. Applied Data Science (current; graduates 2027-12). No second major
  or minor.
- Internship start date: 06/14/2027. Full-time start: January 2028 or later.
- Saved answers (exact questions): "Do you have a valid driver's license?" = Yes. "What best describes the type of
  opportunities you're interested in:" = an option matching "product" (e.g. "Product").

## Rules
1. conviction: a question that ASKS whether he was convicted / pleaded guilty / has a criminal record (the sentence
   ending in "?" decides; a notice before it only explains) blocks unless the value is No (or "I have not …", "Never").
   A statement like "I certify that I have never been convicted" is not checked. A question about consenting to a
   background check is not a conviction question.
2. any_employer: an authorization question for "any employer", "all employers", "any U.S. employer" or "without
   restriction" blocks a Yes. A question that is about sponsorship is not checked here.
3. degree_level: a question about the degree he will hold once graduated / is currently pursuing blocks a Bachelor's
   (or lower / Doctorate) value; a question about his HIGHEST COMPLETED education blocks a Master's / MBA / Doctorate
   value (the M.S. is in progress). Text in parentheses only explains. A Yes/No "Are you currently pursuing a
   Bachelor's, Master's, or PhD in Data Science, Statistics …?" blocks No; "Are you currently pursuing a bachelor's
   degree in Business?" blocks Yes. A value that names both ("undergraduate or graduate program") passes.
4. major: an undergrad major question blocks any value that is not Economics; a second major / secondary major / minor
   question blocks any field value (empty, "None", "N/A" pass); a question that asks "major and minor" together, or a
   plain "Major" / "Field of study", passes either of his fields.
5. start_date: an "availability to start" / "start date" / "when can you start" question with a date value blocks a
   date other than 06/14/2027 (a month-only value June 2027 passes; a date in January 2028 or later passes — full-time).
   A "Start Date" inside a work-history or education entry ("Previous Employment (Acme): Start Date") is not checked.
6. pattern: a value that is a regular expression (like "^agree$" or "AI\ product") blocks, on any question.
7. qa: a saved Yes / No answer for the exact question blocks a contradicting value whatever wrote it. A saved option
   answer is checked only when the value came from the folder's answers.json (source "answers.json"), or when the
   offered options include the saved option and another was taken; otherwise it passes.
8. Empty values, unticked boxes and questions that are none of the above pass.
