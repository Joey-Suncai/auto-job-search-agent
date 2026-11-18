# Spec: education / enrollment / language questions on application forms (JSA-295 / JSA-296)

The candidate's facts:
- Currently enrolled, full-time, in a Master of Science in Applied Data Science at the University of Chicago
  (Sep 2026 – Dec 2027). Finished a Bachelor of Arts in Economics at the University of Illinois Urbana-Champaign (May 2026).
- Lives in Chicago, IL. Works in English (professional level); native Chinese (Mandarin).

How the form-answer rules must answer (expect = the exact text, or an option exactly as written):
1. A question asking which school / university / college he is CURRENTLY enrolled at / attending / studying at, asked in a
   free-text box (no options) → "University of Chicago". Wording varies: "What university are you currently enrolled with?",
   "Which college are you currently attending?", "Name of the school you are currently enrolled in". These are NOT yes/no
   questions even though they contain "currently enrolled".
2. A yes/no question "Are you currently enrolled …?" (options Yes / No) → "Yes".
3. A question asking which degree he is currently pursuing / obtaining / working towards, or asking him to confirm his
   current degree, in a free-text box (no options) → "Master of Science in Applied Data Science, University of Chicago".
   "Can you please confirm the current degree that you are obtaining?" is a request for the degree, not a yes/no question.
   (A bare box labelled only "Degree" is not part of this spec — do not write cases for it.)
4. A question about his enrollment STATUS with options → the full-time option ("Fulltime Schedule", "Full-time",
   "Full Time Student", "Full-time graduate student"), never part-time, never an undergraduate option; when a
   "Master's" option exists, the Master's option.
5. "Language Preference" / "Preferred language" / "Preferred language of communication" with options such as English /
   Spanish / French Canadian → "English". A question about language PROFICIENCY or fluency is not this rule (do not
   write cases for proficiency).
6. A checkbox whose text is a plain attestation — "… certifies that I have read, understand, accept and agree with the
   above statements and that the information on my profile and on this application is complete and correct." (options:
   none; type checkbox) → "Yes" (ticked). Wording varies slightly; the text may mention "my electronic signature below".
7. "Are you local and able to work in-person in our <City>, <State> office?" with options like "Yes, I am" / "No, I am not"
   → when the city is not Chicago, the "No" option (he is not local there); when the city is Chicago → the "Yes" option.
Near misses (expect "none" only when no rule should answer; otherwise the right answer):
- "What is your current GPA?" is not a school question (do not write it).
- "Which high school did you attend?" must not answer "University of Chicago" (expect "none").
- "Are you currently enrolled in a business degree program or related field?" must not be "Yes" (he is not in business).
