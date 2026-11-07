# Spec: referral questions and the referrer pool (JSA-195, Joey 2026-11-05)

Joey's rule, his words: 「建一个推荐人池子，把我认识的所有相关推荐人都放进去，如果碰到真的岗位可以由他们推荐的话，你就问我，否则的话都写没有推荐人」
(Build a pool of referrers — everyone relevant I know. When a real job could be referred by one of them, ask me;
otherwise always answer "no referrer".)

## The pool
The pool lists the candidate's 1st-degree connections by the company they work at NOW. For these tests the pool is:

| company key | people |
| --- | --- |
| amazon | Pat Lee (Engineer @ an employer), Sam Ortiz (Solutions Architect @ AWS) |
| ernst and young | Dana Fox (Tax Analyst @ EY) |
| micron | Lee Chan (Product Manager @ Micron) |
| tiktok | Robin Wu (Product Manager @ TikTok) |
| bytedance | Kim Park (Product @ ByteDance) |
| goldman sachs | Alex Grant (Vice President) |
| university of chicago | Jordan Hale (Lecturer) |
| nvidia | Casey Moore (Product Manager @ a Workday employer) |

People who USED to work somewhere are not in the pool.

## Matching the hiring company to the pool
The application passes the hiring company's name. It matches a pool key when they are the same company after ignoring
case, punctuation, a trailing ".com", "&" versus "and", and legal or generic suffix words (Inc, Incorporated, LLC, LLP,
Corp, Corporation, Co, Company, Ltd, Limited, PLC, Group, Holdings, The, USA, US, Services, Technology / Technologies,
Labs, Global, International). A name that starts with a pool key's words is that company too ("Amazon Web Services").
Common short names count: "AWS" = an employer, "EY" = an employer, "UChicago" = University of Chicago.
Examples that are IN the pool: "an employer", "an employer", "AWS", "an employer LLP", "EY", "an employer,
Inc.", "TikTok", "TikTok Inc.", "ByteDance", "ByteDance Ltd", "an employer & Co. LLC", "The University of Chicago",
"a Workday employer Corporation". TikTok and ByteDance are separate keys (each one matches its own people).
Companies that share no whole word with a key are NOT in the pool: "Acme Corp", "Globex", "Initech", "Amazonia Foods",
"Micronesia Airlines" (a different word), "Northwind Traders".

## What counts as a referral question
- "Were you referred (by an employee)?", "Were you referred to this position by a current employee?"
- "Referral name", "Referred by", "Name of the employee who referred you", "Referrer", "Who referred you?"
- "Did someone from our company suggest you apply? If so, their name – if not type N/A"
- "Employee referral?" (Yes / No)
- "Do you know anyone who works at <Co>?" / "Do you know anyone that works for one of our companies?"
- A "How did you hear about us?" question whose own wording also asks about a referral ("…If you were referred, please
  give the employee's name").

NOT referral questions (left as they are):
- Recruiter questions: "Were you referred by a recruiter?", "Have you been contacted by a recruiter?" — always No, for
  every company (in the pool, not in the pool, or none given).
- A plain "How did you hear about us?" / "Referral source" / "Source" question: it is answered with the standard source
  answer — an option naming an online job board ("Online job board", "Job board"), else "Recruitment website", else
  "Other"; a text box gets "Online job board". It must NEVER pick an option that names a referral ("Employee referral",
  "Referred by an employee", "Referral"), whatever the company. When none of the allowed options exists the question is
  left unanswered (status unknown).

## Answers
1. Hiring company IN the pool → the referral question is not answered: status "unknown" with ask = true (the runner stops
   and the candidate is asked), and the explanation names the pool people at that company. A referrer's name is never
   filled in automatically. This also applies to the "how did you hear … if referred, name" question.
2. Hiring company NOT in the pool → "no referral":
   - Yes / No options → "No".
   - A list without Yes / No that has "None", "N/A", "Not applicable", "No referral" or "I was not referred" → that option.
   - A single checkbox ("I was referred by a current employee") → left unticked (leave = true, no value).
   - A text box → the word the form itself asks for when there is no referrer, exactly as the form writes it:
     "… if not type N/A" → "N/A"; "write None if no one referred you" → "None"; "(N/A if not applicable)" → "N/A".
     With no such instruction: a yes/no question in a text box ("Were you referred by an employee?") → "No"; a name
     box ("Referral name", "Referred by", "Name of the employee who referred you") → "N/A".
   - "Do you know anyone who works at <Co>?" → "No".
   - A plain "how did you hear" question → the standard source answer above.
3. Hiring company UNKNOWN (no company given, or an empty name) → status "unknown" with ask = true for every referral
   question; never assume "No". (Recruiter questions and plain how-did-you-hear questions are unaffected.)
