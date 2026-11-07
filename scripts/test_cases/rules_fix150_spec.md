# Answer-rule fixes from the 11-04 Lever prep (JSA-150)
The candidate's facts: graduated high school in 2022; current degree program started 09/2026, ends 12/2027 (expected
graduation "December 2027"); school "University of Chicago"; field of study "Data Science"; phone 555-010-2030; needs
sponsorship (F-1); sponsorship explanation "F-1 student; summer internship on CPT, would need H-1B sponsorship for full-time".

answer(label) gives (rule, value) or unknown:
1. A high-school graduation year question ("Year of High School Graduation", "What year did you graduate high school?",
   "High school graduation date") → hs_grad_year "2022" — never the university graduation date.
2. "If yes, what type of sponsorship?" / "What kind of visa sponsorship will you require?" / "Sponsorship type" →
   sponsorship_type with the explanation text above — never "Yes". A plain "Will you now or in the future require
   sponsorship?" stays spons_future "Yes".
3. A label ending with "Major" / "Minor" / "Concentration" (optionally followed by ":"), and "School City / State /
   Location / Address / Country / Zip / Year / GPA", or anything about high school, is NOT the school-name question.
   "School Major:" → the field of study ("Data Science"). "What school are you attending for your major?" IS the school
   question → "University of Chicago". "School Minor:" → unknown (no minor).
4. The phone question matches "phone", a label that ends with "mobile" / "mobile number", or the whole word "cell" — not
   "cell" inside another word ("excellence", "cancellation"): such labels must not get the phone number.
5. A question asking when the current degree program began, in MM/YYYY format → degree_start_mmyyyy "09/2026"; when it
   will be completed / when the candidate graduates, in MM/YYYY format → degree_end_mmyyyy "12/2027". The same question
   without an MM/YYYY format → grad_date "December 2027".
