# Work-authorization answers for an F-1 student (summer internship on CPT)

The candidate is an F-1 student. He is authorized to work only with restrictions (CPT for the internship) and will need
sponsorship later. Given a work-authorization question and its options, the answer engine must:
- never choose an option claiming unrestricted / permanent authorization ("Yes, without restrictions", "Yes, unrestricted",
  "I am authorized to work permanently", "Yes, I am a U.S. citizen or permanent resident");
- choose "Yes, with restrictions" (or "Yes, but with restrictions") when it is offered;
- with only "Yes, without restrictions" and "No" → "No";
- with plain "Yes" / "No" for "Are you legally authorized to work in the United States?" → "Yes".
Return the exact option.
