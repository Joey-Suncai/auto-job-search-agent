# Which saved answer applies to a form field

A folder's answers.json maps keys to answers. Keys are either a form field's own key (e.g. "question_123",
"cards[1a2b-…][field3]", a UUID) or a pattern matched against field labels. Given one field (key, label), the saved
answers (an ordered mapping) and the set of all field keys on this form, return [value] or null:
1. If the field's own key is a key in the answers, return that answer (even when the answer is null).
2. Otherwise go through the answers in order and return the first one whose key (a) is not the key of any field on this
   form, (b) does not start with "question_", and (c) matches the field's label as a case-insensitive regular
   expression (search anywhere in the label). A key that is not a valid regular expression (e.g. "cards[1a2b-c3d4][field3]"
   has the character range "b-c3"… that may be invalid) simply does not match — it must not cause an error.
3. Nothing applies → null.
