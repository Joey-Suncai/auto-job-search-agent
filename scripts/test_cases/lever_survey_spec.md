# Reading Lever's demographic survey from the apply page, and which survey questions go into the plan

Lever apply pages (jobs.lever.co/<site>/<id>/apply, server-rendered HTML) can carry a "Demographic Survey" after the EEO
block. Its HTML looks like this (attributes appear in this order; JSON in value="" is HTML-escaped with &quot;):

    <div class="application-question"><label><div class="application-label">What is your location?</div>
      <div class="application-field"><div class="application-dropdown">
        <select class="candidate-location" data-qa="candidate-location-select">
          <option value="">Select...</option><option value="CA">Canada</option><option value="US">United States</option> …
        </select></div></div></label></div>
    <div class="section page-centered application-form hidden" id="countrySurvey
    _all-candidate-locations
    "><h4>Demographic Survey for Acme</h4>
      <input type="hidden" value="{&quot;text&quot;:&quot;Demographic Survey&quot;,&quot;type&quot;:&quot;survey&quot;,
        &quot;fields&quot;:[{&quot;type&quot;:&quot;multiple-choice&quot;,&quot;text&quot;:&quot;What is your age range?&quot;,
        &quot;required&quot;:false,&quot;options&quot;:[{&quot;text&quot;:&quot;18-20&quot;},…]}, …],&quot;id&quot;:&quot;bac3…&quot;}"
        data-name="surveysResponses[bac3…][baseTemplate]" name="surveysResponses[bac3…][baseTemplate]">
      … radios named surveysResponses[bac3…][responses][field0] …
    </div>
    <div class="section … hidden" id="countrySurvey_US"> … another template input for a US-only survey … </div>

## lever_survey(html) → list of fields
- No `<select class="candidate-location"` on the page → [] (no survey fields at all, even if survey sections exist).
- First field: key "candidate-location", type "select", required false, options = the visible texts of the select's
  options whose value is non-empty (the "Select..." placeholder is dropped), in page order; label =
  "Country of residence (<text of the last application-label div before the select>)" — e.g.
  "Country of residence (What is your location?)"; when no label div precedes it, "(What is your location?)".
  option_values maps each option text to its value (e.g. "United States" → "US").
- Then, for every section whose id starts with "countrySurvey" (whitespace and newlines inside the id are ignored, and
  leading underscores of the remainder are dropped): the section's code = the rest of the id
  ("all-candidate-locations", "US", …). survey_for = "*" when the code starts with "all", else the code.
  For each template input inside that section (up to the next countrySurvey section), for each entry i of its "fields":
  key = "surveysResponses[<id>][responses][field<i>]" where <id> is the bracket text of the template input's name;
  label = the field's "text" (spaces normalised); required = the field's "required"; options = the texts of its
  "options" (or [] when none); type by the template type: multiple-choice → "radio", multiple-select → "multi",
  dropdown → "select", text → "text", textarea → "textarea", anything else → "text". Each has survey true.
- A template whose value is not valid JSON is skipped.

## Which survey fields go into the plan (build)
Fields are processed in order. "candidate-location" is answered like any other field (rules, or the per-application
answers file). After it, a survey field with survey_for is kept only when a country was chosen and survey_for is "*" or
equals the chosen option's value (compared case-insensitively). When candidate-location got no answer, every field with
survey_for is dropped (the sections stay hidden). Fields without survey_for are never dropped by this rule.
