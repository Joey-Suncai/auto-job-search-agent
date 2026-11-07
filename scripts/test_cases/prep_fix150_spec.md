# Prep fixes from the 11-04 Lever prep (JSA-150)
1. load_open_answers(text of open_answers.md) → [(label, answer)]: blocks start with "## <field id> — <label>" on one line;
   the id is any run of non-space characters ("question_123", "cards[0a6f-…][field0]", "eeo[gender]"); the answer is the
   following lines with lines starting "limit:" removed, trimmed. An empty answer or exactly "ASK" (any case) is skipped.
   Labels are whitespace-normalised.
2. canon.classify(label) says "school" only for a school-name question. A label containing (case-insensitive) "tell us",
   "describe", "accomplish", "example", "explain", "share", "walk us" or "from school or" is not the school field (an
   essay that mentions school), nor is anything with "?" (e.g. "What school do you attend?" is answered elsewhere).
   "School", "Name of School", "University" are the school field.
3. fact_format(label) (prep: such questions are never sent to the essay writer): true when the label asks for a value in a
   given format — "MM/YYYY", "MM/DD/YYYY" (spaces around "/" allowed), the word "YYYY", "in the format" / "in format",
   "date format". Otherwise false (e.g. "Describe a project", "Why this role?").
