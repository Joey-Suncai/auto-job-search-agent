# Workday file fields: résumé and cover letter (JSA-068)
Functions:
1. file_kind(label) -> "cover" | "reference" | "transcript" | "resume". "cover" when the label mentions a cover letter ("cover letter", "coverletter"), a motivation / motivational letter, or a letter of interest / letter of motivation. Else "reference" when it mentions reference or recommendation (letters of recommendation are the candidate's own documents). Else "transcript" when it mentions transcript. Everything else is "resume" ("Resume/CV", "Upload a file", "Attachments", "Upload Resume", empty label). Case-insensitive.
2. files_for_field(kind, field_text, resume, cover, want_cover, multiple) -> list of file names to upload into one field, in order. field_text = the visible text of the field (lists file names already uploaded and "Successfully Uploaded"). resume / cover = the folder's PDF names (cover may be null when no cover letter exists).
 - kind "cover": [cover] unless that exact name already appears in field_text; null cover -> [].
 - kind "resume": the résumé unless the field already shows a file (the text contains "successful", or a name ending in .pdf / .doc / .docx) — never a second résumé; then additionally the cover letter when want_cover is true AND the input accepts multiple files AND the cover name is not already in field_text AND cover is not null.
 - kind "reference" or "transcript": [] always (the candidate provides those).
 - Never returns null/empty names and never a name already shown in field_text.
