# Spec: graduate-transcript file slots and secondary e-mail (2026-11-05)

Candidate: has an UNDERGRADUATE transcript (B.A. finished); a master's program is in progress, so there is NO graduate
transcript yet. Main e-mail on file plus a different secondary e-mail.

1. `slot_kind(label)` for an application file-upload slot returns "grad_transcript" when the label asks for a GRADUATE /
   master's / M.S. / post-graduate / grad-school transcript, including "Transcript (Graduate, if applicable)" and
   "undergraduate and graduate transcripts" (it asks for a graduate one too). "Undergraduate transcript", "Unofficial
   transcript", "Most recent transcript", "Academic record" return "transcript". A résumé / cover letter slot keeps its
   kind; anything else (portfolio, writing sample) is "other_file".
2. A job whose form has any grad_transcript slot (required or optional) is skipped before anything is filled.
3. Secondary e-mail question ("Secondary email", "Alternate email address", "Backup e-mail", "Additional email") → the
   secondary e-mail; plain "Email" / "Email address" / "Confirm email" → the main e-mail.
