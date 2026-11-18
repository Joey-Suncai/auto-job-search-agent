# Spec: JSA-244 — three form-answer fixes

## 1. skipped(company, names)
True when the company name, trimmed and lower-cased, STARTS WITH any of the names (each trimmed and lower-cased; empty
names ignored). False for an empty / missing company, or when names is empty / None. "Leland" skips "Leland Inc" and
"leland"; it does not skip "Cleland" (no prefix match inside a word start other than the beginning).

## 2. pending(sheet, handled) — which sheet questions still wait
sheet: {"name": str, "accept_derived": bool, "questions": [{"id", "question", "answer", "block", "risk", "kind",
"suggested"}]}. A question "has an answer" when its "answer" is truthy, or when sheet.accept_derived is true and the
question has block "derived", no risk, kind != "high_risk" and a truthy "suggested".
Result: ids of questions with no answer, in sheet order — minus the handled ones:
- handled is a list / set / None of sheet NAMES: when the sheet's name is in it, nothing waits; otherwise every
  unanswered question waits.
- handled is a dict {name: set-or-list of question TEXTS, or None}: name missing → every unanswered question waits;
  value None → nothing waits; otherwise a question waits only when its "question" text is NOT in that collection.
Not a dict sheet, or no / empty name → [].

## 3. Language questions (rule "languages")
The candidate profile lists languages: [{"name": "Spanish", "re": "spanish|español", "level": "native"},
{"name": "English", "re": "english", "level": "professional"}]. These apply only when no other rule and no saved answer
answers the question. Not language questions (no answer from this rule): labels about programming / coding / code /
software / scripting / query language / frameworks.
a) A LIST of languages: the label contains "language" or "languages" and at least two options name a language, and no
   option starts with a level code (A1..C2, L1..L3). For each profile language (in profile order) pick the option that
   starts with it, else the first option that contains it. If the label says native / first / mother / primary: a
   single answer, the native language's option. Otherwise, when the field type is multi / checkbox, or the label
   contains "languages" (plural), "all that apply", "select all", "check all" or "fluency": the answer is all picks
   joined by " | " (e.g. "Spanish | English"). No pick → no answer from this rule.
b) A LEVEL for a language: at least three options are levels (native, mother tongue, fluent, proficient, professional,
   advanced, intermediate, beginner, elementary, basic, limited, conversational, expert, none, A1..C2, L1..L3) and the
   label mentions language / proficiency / fluency / CEFR / level / rate / speak.
   - The label names no language (e.g. "CEFR Level") → status unknown with ask = true (asked per job, not answered).
   - It names a profile language → the first option (ignoring options that mention a certification) matching, in
     order: native → native|mother tongue, C2, bilingual, fluent, expert, advanced; professional → "full professional"
     or "professional working", professional, fluent, C1, advanced or expert. None fits → unknown, ask = true.
   - It names another language → the option that starts with none / no proficiency / not applicable / n/a / I do not
     speak / no knowledge / no experience / not proficient; no such option → unknown, ask = true (never claim a level
     in a language the candidate does not speak).

## 4. "No" answers on a long statement list
When a rule answers No (e.g. "Have you previously been employed at X?" — the candidate never worked there) and the
options are more than two statements with no option starting with "No"/"False": pick the option when EXACTLY ONE option
starts with a negative statement ("I have not", "I haven't", "I have never", "I've never", "I am not", "I'm not",
"I do not", "I don't", "I did not", "I didn't", "I was not", "I wasn't", "I will not", "I can't", "I cannot", "Never").
Two or more negative statements, or none → no answer (unknown). Example: options "I have not previously been employed
at a Greenhouse employer" / "I have been employed at a Greenhouse employer as a full-time employee" / "... as an intern" → the first.
