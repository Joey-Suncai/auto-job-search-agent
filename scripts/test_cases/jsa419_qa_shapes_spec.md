SPEC — saved answers (qa entries) answer a form field by the field's SHAPE.
An entry has: q (question wording), optional yes (true/false), optional pick (list of case-insensitive regexes for the OPTIONS of a list field),
optional box (the text to type when the same question is a TEXT box).
1. A text box (no options) gets the entry's box value when it has one. A text box never gets the regex text of a pick.
2. A list field (select / radio / multi) gets the first option that the entry's picks match (picks tried in order, each against every option).
   No pick matches any option → no answer (the user is asked). An entry never picks an option that no pick / yes matches.
3. A field with exactly ONE option (a consent / acknowledgement tick box, any field type) is ticked by a Yes entry (yes = true) — the option text is returned.
   A No entry (yes = false) never ticks it. A Yes entry never ticks a one-option field whose option says no ("I do not agree", "I decline", "No").
4. Two or more options: a yes = true entry picks the option that starts with Yes; yes = false picks the one that starts with No; otherwise (options like "I agree" / "I disagree") no answer.
5. A question wording that matches no entry gets no answer.
Entries match a question when its wording equals q (case, punctuation and "required" ignored).
