# Which saved fact answers an optional education / name question on an application form

The form filler answers a question from a saved fact only when the question clearly asks for that fact. For free-text
boxes (no options) it decides which fact, if any, the question label asks for:

- "discipline" — the candidate's field of study: labels that ask for the major, field of study, discipline, area of
  study, course of study, program of study, concentration, or "what are you studying". NOT when the label asks which
  school/university/college the candidate attends, NOT when it is about graduating ("When do you expect to graduate from
  your course of study?"), and NOT when it asks for the degree AND the area together ("Specify the degree and area of
  study you are pursuing") — those are other questions.
- "degree" — the degree being pursued: "Degree", "Degree type", "Degree level", "What degree are you pursuing?",
  "What degree are you currently working towards / seeking / enrolled in?".
- "grad_date" — expected graduation: "Expected graduation date", "Graduation year", "When will you graduate?",
  "When do you expect to graduate?", "When are you expected to graduate?", "What month and year are you expected to
  graduate?", "When do you expect to graduate from your current course of study?".
- "preferred_name" — "Preferred name", "Preferred first name", "Nickname", "Nick Name".
- null — anything else: age range, referral ("Who referred you?"), "Anything else you'd like us to know?", which school
  the candidate attends, GPA, start date, the degree-and-area combination above, open "why" questions, hobbies.

Labels are matched case-insensitively; extra words around the phrase (e.g. "(optional)") do not change the answer.
