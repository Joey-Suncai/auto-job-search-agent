# SuccessFactors page helpers (2026-11-05)

An application runner fills SAP SuccessFactors application forms. Four small helpers.

## 1. Chat widgets over the Apply button — `chat_overlay(el)` → true / false
`el` = {"tag", "id", "cls", "title", "name", "src"} of an iframe (or a fixed-position element) on a job page. True when it is
a chat widget that may cover the "Apply now" button and should be hidden: any of id / class / title / name / src mentions a
chat bot ("chatbot", "chat bot", "phenomChatbotIframe", "Phenom Career Bot", "career bot"), live chat ("livechat", "live
chat", "chat-widget", "chat_widget", a word "chat"), or a known chat vendor ("intercom", "drift", "zendesk", "messenger",
"ada-embed"). Never true for a cookie / consent banner (cookie, consent, OneTrust, TrustArc, GDPR, privacy), a CAPTCHA
(recaptcha, hcaptcha, captcha), a video (YouTube, Vimeo, "video") or a map — even when the element also mentions chat. An
element with none of these words → false. Case does not matter.

## 2. Placeholder labels — `label_from_options(label, options)` → string
Some list boxes have only a placeholder as their label ("Please Select:" under a long veteran-status paragraph). When the
label — after dropping a leading "*", a trailing ":" and extra spaces — is exactly one of "Select", "Please select",
"Choose", "Please choose", "Select one", "Please select one", "Select an option", "Choose from the list", "No Selection",
or only dashes (case-insensitive), and there is at least one non-empty option, return the cleaned label followed by a space
and the options in parentheses joined by " / ": "Please Select (I Am Not a Protected Veteran / I Choose Not to Self Identify)".
Empty options are left out. Any other label (a real question, even one that contains "please select", e.g. "Please select
your gender") is returned unchanged; with no non-empty options the label is returned unchanged.

## 3. Split words from the resume parser — `split_fix(field)` → true / false
`field` = {"type", "label", "value"}. The resume parser splits words after a capital letter ("HYDE P ARK INVESTMENT S
ERVICES", "FROST & S ULLIVAN", "U NIVERSITY OF C HICAGO"). A repair joins a lone capital letter to the ALL-CAPS word (two or
more capitals) that follows it after one space ("HYDE PARK INVESTMENT SERVICES"); "100 Main St" stays (Indiana is
not all caps). True when ALL hold: type is "text" or "textarea"; the value is not empty; the repair changes the value; the
label names an employer, company, school, college, university, institution, organisation / organization, job title or
title (case-insensitive, anywhere in the label). Otherwise false (e.g. an address box, a combo list, an already-correct value).

## 4. Row box labels — `canon_label(label, kind)` → string
kind "work" (Previous Employment rows) or "edu" (Education rows). The label (a leading "*" and trailing ":" dropped, spaces
trimmed, case-insensitive whole-label match) maps to a key:
- work: "Company", "Company Name", "Employer", "Employer Name", "Name of Company", "Name of Employer", "Organization",
  "Organization Name" → "Company"; "Job Title", "Title", "Position", "Position Title", "Job Position" → "Job Title";
  "Present Employer", "Current Employer", "Present Employer?", "Currently employed here?" → "Current"; "Start Date",
  "From Date", "From" → "Start Date"; "End Date", "To Date", "To" → "End Date"; "Location", "City" → "Location".
- edu: "School", "School Name", "Name of School", "College", "College/University", "University", "Institution",
  "Institution Name" → "School Name"; "Type", "Degree", "Degree Type", "Degree/Certificate" → "Type"; "Subject", "Major",
  "Field of Study", "Area of Study" → "Subject"; "Still Attending?", "Currently Attending", "Attending" → "Attending";
  "Degree/Certificate Completion Date", "Completion Date", "Graduation Date" → "Completion Date"; "Start Date", "From Date",
  "From" → "From Date"; "End Date", "To Date", "To" → "End Date"; "Result" → "Result".
- Anything else, or another kind: the cleaned label unchanged (e.g. work "Type of Business" → "Type of Business"; work
  "Degree" → "Degree"; edu "Company Name" → "Company Name").
