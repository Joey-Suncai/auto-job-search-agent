# Spec: SuccessFactors education rows and heading-labelled checkboxes (JSA-295, an employer 2026-11-10)

Four pure functions. Each case names one of them in "fn".

A. label_key(label) — an education-row box label → the key the filler uses:
   "School Name" for the school list: "School", "School Name", "College/University", "School/Institution Name",
   "School / Institution Name", "University/College", "Institution Name".
   "Type" for the degree type list: "Degree", "Degree Type", "Education Type", "Type of Education", "Education Level",
   "Level of Education", "Degree Level", "Degree/Certificate".
   "Achieved" for "Degree Achieved", "Degree Earned", "Degree Obtained", "Degree Received", "Degree Awarded".
   "Subject" for "Major", "Area of Study", "Field of Study", "Major (Legacy)", "Subject".
   Anything else comes back as the label itself (star and colon dropped): "If other, enter School / Institution Name",
   "If other, enter Area of Study", "Do you have previous Craft experience", "GPA".
B. other_school_box(fields) — fields = [{key, label, type}] of one education row → the key of the text box that takes the
   school's name when the School list is set to "Other": a text / textarea box whose label says other / not listed /
   specify AND names school / institution / college / university, and does NOT name area of study / major / field of study /
   subject / discipline / degree. None (null) when the row has no such box. A combo (type "combo") never counts.
C. question_label(label, rows, kind) — the question text of a form field. rows = the text-only table rows right above the
   field, nearest first. When kind is "checkbox" and the label is only a heading word — "Acknowledgement",
   "Acknowledgment", "I Acknowledge", "Acknowledge", "Statement", "Applicant Statement", "Attestation", "Certification",
   "Agreement" (case-insensitive, optional trailing period) — the answer is the nearest row that is at most 1200 characters
   and is not itself such a heading word; no such row → the label unchanged. For any other kind (text, combo) or any other
   label, a real label is returned unchanged (whitespace collapsed). Rows never replace a real label like
   "I certify." or "Electronic Signature".
D. school_other_ok(records) — records = [{label, value}] read back from the page; labels look like
   "Education (University of Chicago): School/Institution Name". Returns the list of labels the school check REJECTS.
   A school field is any label whose part after the colon names school / university / institution. Accepted values name
   Chicago or Illinois. A School list whose value is "Other" is accepted ONLY when the same entry (the text before the
   colon, e.g. "Education (University of Chicago)") has an "If other …" school box whose value names Chicago or Illinois.
   An "Other" in an entry without such a box, or whose box is empty or names another school, is rejected. Values like
   "Northwestern University" are rejected.
