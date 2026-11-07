# Is this form question asking for his immigration / visa status?

An answer audit only checks questions that ask the applicant to STATE his immigration or visa status / work-authorization
type (expected answer for him: "F-1"). Given a question label, say whether it is such a question (true) or not (false).
True: "What is your current immigration status?", "Visa Status", "Visa type", "Visa category", "Work authorization type",
"Please indicate your current status" (when about immigration), "Immigration Status".
False: yes/no questions that merely mention visas or status — "Are you legally qualified to work in the United States? (If
hired, you will be required to submit proof of U.S. citizenship or visa status.)", "Are you legally authorized to work in
the U.S.?", "Will you require immigration sponsorship now or in the future?", "Do you hold a visa that allows you to work?",
"Have you ever been sponsored for a visa?", and unrelated questions (e.g. "Marital status", "Employment status" are false only
if they are yes/no; treat any question starting with Are/Will/Do/Does/Have/Can/Would/Is you as false).

Additional rule (2026-11-01, Arch Capital): a question asking WHICH TYPE / KIND / CATEGORY of sponsorship he needs
("Please select the type of sponsorship you require", "What kind of sponsorship will you need?") is neither the
immigration-status question nor the yes/no sponsorship question — its answer is a type such as "F1-CPT" or "H-1B".
For this test, label such questions false (not immigration status).

Additional rule (2026-11-01, a Workday employer): a free-text request for DETAILS ("Please provide details on your visa status
(including visa type and expiry date), residential and citizenship status", "Please describe your immigration status",
"Explain your visa situation") is answered with a sentence, not a single status — label it false.
