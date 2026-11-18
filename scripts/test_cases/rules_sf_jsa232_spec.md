# Spec: three SuccessFactors questions the answer rules must answer (JSA-232, an employer 2026-11-10)

The candidate's facts: he has NO relatives or family members working at any company he applies to; he agrees to every
"I have read and agree" statement at the end of an application form (it is a consent/acknowledgement, like a privacy
acknowledgement); on equal-employment (EEO) sections he DOES wish to provide his self-identification information
(he answers gender and race), so "Do you wish to furnish this information?" is Yes.

The rules see a question text (label), its type ("select" or "radio") and its options; they return the option to pick.

1. Relatives: questions asking whether the candidate is related to someone who works for the company → "No".
   Wordings include: "Are you related to anyone that works for <Company>?", "Are you related to someone who works at
   <Company>?", "Are you related to or associated with anyone who is employed by <Company>?", "Do you have any relatives
   working for <Company>?", "Are you related to any employee of <Company>?".
   Near misses that are NOT this question (the rules must not answer them "No" as a relatives question): "If yes, please
   identify the name of the employee" (a name box, type text — expect "none"), "Were you referred by a current employee?"
   (a referral question — expect "No" too, but not because of relatives; still expect "No").
2. Read-and-agree statement: "I HAVE READ AND AGREE WITH THE ABOVE STATEMENTS", "I have read and agree to the terms
   above", "I have read and accept the privacy notice" with options No / Yes → "Yes"; with options like "I Agree" →
   that option.
3. EEO furnish: "Do you wish to furnish this information?", "Do you wish to provide this information?", "Do you wish to
   self-identify?" with options No / Yes → "Yes".
   Near miss: "Do you wish to receive job alerts by email?" is NOT this question (expect "none" or anything but a
   furnish answer — write expect "none").
