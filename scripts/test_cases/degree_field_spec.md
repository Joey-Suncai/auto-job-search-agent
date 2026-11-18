# Spec: picking Joey's degree option on a Workday form (JSA-282)

Joey is earning an M.S. in Applied Data Science (UChicago) and holds a B.A. in Economics (UIUC). Workday Degree lists
are written many ways: "Master of Science", "M.S.", "Masters", "M.S. - Master of Science",
"M.S.T. - Master of Science in Taxation", "B.A. - Bachelor of Arts", "Bachelor of Arts in Philosophy", "M.S. in Finance".

An option may start with an abbreviation prefix: 1–6 letters with optional dots, then a hyphen, en dash, colon, slash or
bar (e.g. "M.S. - ", "BA – "). The full name after the prefix is what counts.

Field rule: an option that names a field — "<Master/Bachelor…> [of Science/Arts] in <field>" or "M.S. in <field>" /
"B.A. in <field>" — is Joey's only when the field starts with one of his: for a master's, data science, applied data
science, analytics, data analytics, statistics or computer science; for a bachelor's, economics. Any other field
(Taxation, Finance, Nutrition, Accounting, Engineering, …) is never his and is never chosen.

master_options(list) returns his master's options, best first:
 1. "Master of Science" / "Masters of Science" / "M.S." / "MSc" / "M.S. degree" (after any prefix);
 2. a plain "Master's" / "Masters" / "Master's Degree" / "Graduate Degree";
 3. "Master of Science in <his field>";
 4. anything else still allowed (e.g. a combined "Masters of Arts or Science", "M.A. - Master of Arts").
Never in the list: an MBA-only option, executive / law / education / engineering / technology / fine-arts masters, and
any option whose field is not his. Ties keep the page order.

bachelor_options(list) returns his bachelor's options, best first: "Bachelor of Arts" / "B.A." (after any prefix) →
a plain "Bachelor's (Degree)" or "Bachelor of Arts in Economics" → a combined option naming Arts. A Bachelor of Science
alone is never his. Specialty bachelor's (fine arts, music, engineering, BBA, technology, …) and options with a field
other than economics never appear.
