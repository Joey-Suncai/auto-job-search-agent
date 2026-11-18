# Consent to be contacted, and "do you have housing where the job is" (JSA-363)

Input: a question on a job application form plus its answer options (a list of option labels, may be empty).
Output: the option label to choose (copy it exactly from the options), or `"Yes"` / `"No"` when there are no options.

The candidate's facts:
- He lives in Chicago. He has **no** housing or place to live anywhere else (not Austin, not New York, not Houston …).
- He **agrees** to be contacted later about future job opportunities, and to a company keeping his application and
  personal information on file for future roles. So: "I consent" / "Yes, retain my application" → the consenting
  option; never an option that says "I do not consent", "No", "Decline".
- Questions asking whether he already **has** housing / a place to live / accommodation in some area (other than
  Chicago) → **No**. Questions asking whether he would arrange his own housing, or can find housing, are a different
  question: **Yes**. A question where "housing" is only an industry (conflict of interest) is out of scope.
- A question asking whether he has housing in Chicago → **Yes**.

Write varied real-looking form questions in both groups: consent to retain the application / contact about future
opportunities (options such as "I consent / I do not consent", "Yes / No", "I agree / I do not agree"), and "Do you
have housing accommodations in the <city> area?" style questions with Yes / No options or none.
