# Spec: independent audit of submitted applications (JSA-245)

Profile used by every case (fictional): {"name": {"first": "Alex", "last": "Rivera", "full": "Alex Rivera", "preferred": "Al", "signature": "Alex (Al) Rivera"},
 "contact": {"email": "alex@example.com", "secondary_email": "a.r@example.org", "phone": "312-555-0142", "linkedin": "linkedin.com/in/alexrivera", "website": "github.com/alexr"},
 "answers": {"has_preferred": {"yes": true}, "phone_device": {"text": "Mobile"}, "city": {"text": "Chicago"}, "state": {"text": "Illinois", "pick": ["/^illinois$/i", "/^il$/i"]},
  "zip": {"text": "60601"}, "country": {"text": "United States", "pick": ["/^united states( of america)?$/i"]}, "address": {"text": "1200 S Sample Ave"},
  "permanent_address": {"text": "12 Calle Sol, Madrid"}, "county": {"text": "Cook"},
  "gender": {"pick": ["/^male$/i", "/^man$/i"], "text": "Male"}, "race": {"pick": ["/asian/i"], "text": "Asian"}, "hispanic": {"yes": false, "text": "No", "pick": ["/^no\\b/i", "/^(i am )?not hispanic/i"]},
  "veteran": {"pick": ["/^i am not a (protected )?veteran/i"]}, "disability": {"pick": ["/^no,? i do(n't| not) have a disability/i"]}, "transgender": {"yes": false},
  "orientation": {"pick": ["/heterosexual|straight/i"], "text": "Heterosexual"}, "pronouns": {"pick": ["/he\\s*\\/\\s*him/i"], "text": "He/Him"}}}
(no name.middle). EEO_KEYS order: hispanic (hispanic|latino/latina/latinx), transgender, sexual orientation, pronoun, veteran, disab, gender (\bgender\b or \bsex\b), race (race / ethnic).

## submitted_by_platform(results, platform_of)
Pure (tested). results.jsonl lines → {platform: sorted folder names whose LATEST line has status 'submitted'}.
Lines without a folder are ignored; platform_of(line) names the platform of a folder's latest line.

## sample(folders, audited, n, seed)
Pure (tested). Up to n folders not in `audited`, chosen by random.Random(seed) from the sorted list; result sorted.

## answers_of(lines, folder)
Pure (tested). Fields-corpus lines → the answers on the folder's LATEST run (by "at", then run_id):
[{"question", "answer", "options", "type"}], answer = "page" when non-empty else "planned". Skipped: types file /
account / hidden / password (any case), a question starting with "Account:", an empty answer, an answer longer than
300 characters (prose — ds_materials checks it), and a repeat of the same question on that run (first kept).
Each answer also carries "at" (the run's time).

## norm_answer(a)
Pure (tested). The form's stored value as text: "True" / "False" (any case) → "Yes" / "No"; a list written as
"['Asian']" or '["A", "B"]' → "Asian" / "A | B"; surrounding spaces trimmed.

## contact_check(question, answer, prof)
Pure (tested). A contact / link / location answer against the profile → 'right' | 'wrong' | 'unsure', or None when
the question is none of these (then another check decides). In this order:
e-mail: equal (case-insensitive) to contact.email or contact.secondary_email, else 'wrong';
phone ... code (country phone code): 'right' when the answer holds "+1" or "United States", else 'unsure';
phone device / type: equal to answers.phone_device "text", else 'unsure'; phone: the same last 10 digits as
contact.phone, else 'wrong'; LinkedIn: the same profile path as contact.linkedin (scheme, www, trailing slash
ignored), else 'wrong'; website / portfolio / GitHub / URL / link: the same as contact.website or contact.linkedin,
else 'unsure';
"I have a preferred name" (or "do you have a preferred name"): 'right' when the answer is checked / yes / true and
answers.has_preferred is yes; middle name / initial: 'right' when the profile has no middle name and the answer is
blank-like (N/A, NA, None, -); first / last / full / preferred name: equal (case-insensitive) to the matching name.*
value, a name question naming neither first nor last accepts any of first / last / full / preferred / signature,
else 'wrong';
permanent address, zip / postal, county, country, state / province, city / town, street address: the answer equals
answers[key]."text" (case-insensitive), matches one of its "pick" patterns, or starts with its "text" followed by a
comma ("Chicago, IL, US"; "1200 S Sample Ave, Chicago, IL 60601") → 'right', else 'unsure'.

## eeo_key(q, a)
Pure (tested). Which self-identification answer a question asks: 'race' when it names race(s); else the first of
EEO_KEYS that matches; an "ethnicity" question is 'hispanic' when the answer is a yes / no or names Hispanic / Latino,
else 'race'. None = not recognised.

## eeo_check(question, answer, prof)
Pure (tested). An EEO answer against the profile's own self-identification answers (profile.answers[key], key from
the question by eeo_key()) → 'right' when the answer matches one of the key's "pick" patterns, or its "text" (case-insensitive), or —
for a "yes": false key — starts with "No"; 'unsure' otherwise (no key, no profile answer, a decline, anything else).
Never 'wrong': the judge decides; the code only clears the answers that plainly match.

## date_check(question, answer, at)
Pure (tested). "Date signed" / "today's date" / "signature date" questions: 'right' when the answer is that run's
date (MM/DD/YYYY, YYYY-MM-DD or M/D/YYYY) or the day before / after; 'wrong' for another date; None when the question
is not such a question or the run time is unknown.

## summary(items)
Pure (tested). Items → {platform: {"answers", "wrong", "pending", "accuracy", "low95"}} plus "all".
An item counts as wrong when judged 'wrong', right when judged 'right' or when its check said 'right' with no
judgment; anything else is pending (not in the accuracy). accuracy = right / (right + wrong), None when 0 judged;
low95 = the Wilson 95 % lower bound of that rate (z = 1.96), None when 0 judged. Values rounded to 4 places.
