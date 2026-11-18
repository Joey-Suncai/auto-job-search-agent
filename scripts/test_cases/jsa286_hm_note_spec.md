# Optional "message to the hiring manager" box takes the first sentences of the job's cover letter (JSA-286)

Some application forms (Lever) end with an OPTIONAL free-text box such as "Message to the Hiring Manager:". The candidate
decided (2026-11-10) that such a box gets the first 2–3 sentences of THIS job's cover letter (cover.txt), and nothing when
there is no cover letter.

## Which fields
A text box (no options; type text / textarea) whose label, ignoring case, spaces and a trailing ":" / "(optional)" /
"(Optional)" / "*", is one of: "message to the hiring manager", "message to the hiring team", "message to the recruiter",
"message for the hiring manager", "note to the hiring manager", "add a message for the hiring manager",
"personal message to the hiring manager". A field with options, a checkbox, an upload ("cover letter"), or any other label
(e.g. "Why do you want to work here?", "Additional information", "Message") is NOT this rule: no answer from it.

## The answer
The cover letter text is given as `cover`. Take the BODY: drop the salutation line (a first line starting with "Dear", "Hello",
"Hi", "To whom") and everything from the sign-off on (a line starting "Sincerely", "Best regards", "Regards", "Thank you,",
"Kind regards", "Best,") — the sign-off line and the lines after it. Split the body into sentences (a sentence ends with
". ", "! " or "? " followed by a capital letter, or at the end of a paragraph; decimals like 2.169 and abbreviations like
"M.S." / "U.S." / "e.g." do not end a sentence). Take the first 3 sentences, joined by one space; when those 3 are longer than
500 characters take the first 2; when even the first 2 are longer than 500 characters take only the first sentence. Never cut
inside a sentence. Paragraph breaks inside the taken sentences become a single space.
No cover text (empty / missing) or a body with no sentence → the box is LEFT EMPTY: status "ok", value "", leave true
(the box is optional; nothing is typed, nobody is asked).
A box that is marked required is treated the same way (cover → answer, none → leave empty).
