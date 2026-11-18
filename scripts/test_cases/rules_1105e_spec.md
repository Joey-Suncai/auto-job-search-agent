# Spec: five answer-rule fixes (2026-11-05) — saved answers, references, OPT as an example, degree + major, combined majors

The candidate: F-1 student. Current program: **M.S. Applied Data Science** (University of Chicago, Sep 2026 – Dec 2027,
in progress; level = master). Completed: **B.A. Economics** (UIUC, May 2026; level = bachelor). No minor on file. His own
e-mail is alex.doe@example.com, phone 555-010-2030, name Alex Doe. He is legally authorized to work in the U.S.
for the internship (on CPT); he does NOT need sponsorship now (for the internship) but WILL need it in the future (after
graduation, H-1B). He is not on OPT. Field-of-study preference, in this order: Data Science → Applied Data Science → Data
Analytics → Computer Science → Information Systems → Statistics → Other.

Each question has a label, a type (text / textarea / radio / select) and options (empty for text boxes). The rules give
either an answer (a value) or "ask" (left for the candidate, nothing filled).

The saved-answer table (answers the candidate gave earlier for one exact question) holds these entries:
- Q1: the question containing both "rank your preferred work locations" and "Huntersville" → text "Huntersville, NC (USA)".
- Q2: "What is your preferred shift?" → text "Day shift".

1. **A saved answer must not lose to a generic rule whose answer does not fit the box.** A generic rule (e.g. "willing to
   relocate?" → Yes, "authorized to work?" → Yes) gives a bare Yes / No. When the field is a free TEXT box with no options
   and a saved text answer exists for that very question, the saved text answer is used. Example: a required textarea
   "This position is available in the following locations: Huntersville, NC (USA); Brampton, ON (CAN); Please rank your
   preferred work locations in order of interest. Important: You must be legally authorized to work in the Country for any
   location you select. Relocation assistance, if available, will be discussed during the recruiting process." →
   "Huntersville, NC (USA)", never "Yes". A question with no saved answer keeps the rules' behaviour (a Yes / No on a text
   box that is not a yes/no question → ask). A radio / select question with Yes / No options still gets the rule's
   Yes / No (a Yes / No fits there). A question that no rule answers gets its saved answer ("What is your preferred
   shift?" → "Day shift").
2. **References.** A question that asks for references / referees (their names, companies, positions, phone numbers,
   e-mail addresses — "Enter three professional references …", "Reference 1 – Email", "Please list two referees") is
   never answered with any of the candidate's own facts (his name, e-mail, phone, address, school). No references are on
   file → ask. A sentence that only mentions "reference checks" as part of the hiring process (a consent / acknowledgement
   box), a "job reference number" / "requisition reference" box, or "with reference to …" is NOT a references question
   (it keeps whatever the other rules do, and must never be "ask" because of references).
3. **OPT named only as an example.** "Are you legally authorized to work in the United States (e.g., U.S. citizen,
   permanent resident, F-1 OPT)?" — OPT / CPT appear only as examples of authorization → it is the work-authorization
   question → **Yes**. Parenthesised example lists ("(U.S. citizen, green card holder, OPT, etc.)", "(such as OPT or
   CPT)") count as examples too. A question that asks whether he is ON OPT ("Are you currently authorized to work on
   OPT?", "Are you currently on OPT?") is not answered Yes by this rule (he is not on OPT: No, or ask).
   **Work WITHOUT sponsorship**: "Are you legally able to work in the U.S. without sponsorship? (e.g., OPT, CPT)" — the
   sponsorship answer flipped: the question covers only now / this internship → **Yes**; when it also covers the future
   ("now or in the future", "at any time", "after graduation") → **No**.
4. **Degree and major in one text box.** "Please include what degree you are currently pursuing in addition to major(s)
   and any minor(s)." → **"M.S. Applied Data Science"** (degree and major together, from his education; nothing about a
   minor is added). A degree + major question about the completed / highest / undergraduate (bachelor's) degree →
   "B.A. Economics". A plain "Degree and major" text box (no tense) → the current program "M.S. Applied Data Science".
   The same box with options, or a box that also asks a date / GPA / school name ("Degree, major and expected graduation
   date") → ask. A question about only the degree, or only the major, keeps its own answers (degree → "Master's Degree",
   major → "Data Science").
5. **Combined major options.** A major / field-of-study list whose options combine fields with "/", "&", "," or "and"
   ("Data Science / Analytics", "Applied Data Science / Economics", "Statistics and Data Science") is matched by the parts
   of each option, in the preference order: the option holding the earliest preferred field wins, before any later field
   and before "Other". A whole option that equals a preferred field wins over a combined option that holds only the same
   or a later field ("Data Science" over "Statistics and Data Science"). A list with no preferred field anywhere →
   "Other" when offered.
