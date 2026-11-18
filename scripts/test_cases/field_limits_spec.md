# Spec: judging a text answer against the web form's own limits (JSA-312)

An application robot fills a text box (input or textarea) on a job-application web form. Before typing, it must decide
whether the answer would be refused by the page. It knows, for each box:

- `label`: the question text shown above the box.
- `value`: the answer it plans to type.
- `maxlength` / `minlength`: the HTML attributes of the box (integer, or null when absent).
- `input_type`: the box's HTML type attribute ("text", "url", "email", …; may be empty).
- `hint`: text printed around the box by the page (character counters, help text, error messages). Examples of what the
  page may print: "4 out of 50 characters", "0/200 characters", "Enter a maximum of 200 characters.",
  "The value must have at least 5 characters.", "Enter Link 1 in the format: http://example.com.", "Up to 500 characters".
  In "N out of M characters" / "N/M characters" the M is the maximum; N is only the current length.
- `platform`: limits the platform's own question data gave for this question: {"max": int|null, "min": int|null}
  or null.

Decision (the output `expect`):
- Combine every source: the maximum is the SMALLEST maximum found in maxlength, hint and platform; the minimum is the
  LARGEST minimum found in minlength, hint and platform.
- Lengths count characters of the value after trimming leading/trailing whitespace.
- "too_long" when the value is longer than the maximum.
- else "too_short" when the value is shorter than the minimum.
- else "not_url" when the box wants a web address and the value does not start with http:// or https:// followed by a
  host containing a dot. A box wants a web address when input_type is "url", or the hint says the format is
  http://example.com (or asks for a valid URL), or the label is ONLY a link name: "Link 1", "Link 2", "URL", "Website",
  "Portfolio", "LinkedIn Profile", "LinkedIn URL", "GitHub" (case-insensitive, optional trailing "?"). A long question
  that merely mentions LinkedIn or a website ("How did you hear about us — LinkedIn, website, other?") does NOT want an
  address.
- else null (the answer is fine).
- An empty value (or only whitespace) is always null: emptiness is judged elsewhere.
- No limit known → only the url rule can apply.

Real incident to replay: an Oracle form refused, at submit, four answers that a value read-back had passed:
"None" in "What is your current degree minor? if applicable." (page: at least 5 characters, counter "4 out of 50
characters"); a 1086-character answer to a career-aspirations question whose platform maximum was 200; and
"linkedin.com/in/alexdoe" in "Link 1" and "github.com/alex-doe-example" in "Link 2" (page: "Enter Link 1 in the format:
http://example.com."). The fixed answers "Not applicable", a 194-character career answer, and the full https:// links
must pass.
