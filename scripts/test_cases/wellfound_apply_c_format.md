Each case is one of:
{"name": "...", "fn": "classify", "args": {"page": {<page record>}}, "expect": {"via": "...", "ats_url": "...", "apply_url": "..."}, "spec_quote": "...", "ambiguous": false}
{"name": "...", "fn": "pick_external", "args": {"page": {<page record>}}, "expect": "<url or empty string>", "spec_quote": "...", "ambiguous": false}
Test only steps 4a and 4b of classify and the `modal_links` part of pick_external rule (b), and how they interact with
the steps before and after them: about 12 classify cases (dialog text with real line breaks "\n", the outside-Wellfound
wording variants, an outside dialog that also has an external apply link in modal_links or opened, the missing-profile
dialog, a plain in-site dialog, a closed page with an outside dialog) and 4 pick_external cases with modal_links. Page
urls are Wellfound job pages like https://wellfound.com/jobs/4964451-data-intern unless a case needs otherwise.
