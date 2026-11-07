# Workday Review gate: a real EEO question left empty (JSA-206, 2026-11-05)
Function eeo_left_empty(review_text, free_text_labels) -> list of strings: the labels of REAL EEO questions that the Workday Review page shows unanswered. An empty list means nothing blocks the submit.

Review text = the visible text of the Review page, with line breaks. Each question appears as its label on one line and its answer on the next line; an unanswered question's answer line is exactly "No Response". A trailing "*" after a label marks a required question. Label and "No Response" may also stand on the same line, separated by whitespace.

A question is a real EEO question when its label asks about the candidate's gender (or sex), race, ethnicity, Hispanic / Latino origin, veteran (protected veteran) status, or disability. Topic words: gender, race, ethnicity, veteran, disability, Hispanic, Latino — case-insensitive, any form ("disabilities", "Veteran Status", "Race/Ethnicity"). Only real EEO questions whose answer is "No Response" are returned.

NOT EEO — never returned, even when unanswered and even though topic words appear:
1. A label that mentions the protected categories only inside an instruction NOT to disclose them. The part of the label that starts at "exclude", "excluding", "do not include / list / mention / disclose / provide / reveal" (also "don't …"), "which would reveal", "that would reveal / indicate / identify", or "other protected status / characteristic / class", and runs to the closing parenthesis or to the end of that sentence, is ignored when looking for topic words. Example: "Please list professional, trade, business or civic activities and offices held: (Exclude those which would reveal sex, race, religion, national origin, age, ancestry, sexual orientation, physical or mental disability or other protected status)." + "No Response" → not EEO (nothing returned).
2. A question whose label is in free_text_labels — the labels of fields the runner recorded as free-text boxes (textarea or text input). Compare ignoring case and surrounding whitespace; the same first 60 characters count as a match. EEO questions are always pick lists or check boxes, never free text.

Still EEO (returned when "No Response"):
- an equal-opportunity statement followed by a real question: "We are an equal opportunity employer and do not discriminate on the basis of race, gender, disability or veteran status. Please select your gender." → returned ("discriminate", "on the basis of", "without regard to" are not instructions not to disclose);
- "Are you Hispanic or Latino (regardless of race)?" ("regardless of" is not an exclusion instruction);
- "Veteran Status", "Disability Status*", "Race/Ethnicity", "Gender".

Never returned: a question with any other answer ("I do not wish to answer", "Male", "I am not a protected veteran", "No, I do not have a disability"); a question without topic words, even with "No Response" ("Middle Name", "List relevant certifications and/or specialized technical licenses.").

Each returned item is the label text with whitespace collapsed and a trailing "*" removed, in page order.
