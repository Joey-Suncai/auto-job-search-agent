# SmartRecruiters "Add" entry opener (JSA-221, an employer 2026-11-05)

`open_entry(page, label, first_box)` opens a collapsed section (Education / Experience) of a SmartRecruiters
oneclick-ui form. The section shows only an "Add" button whose aria-label is e.g. "Add education entry"; the button
lives inside a web component's shadow DOM and may be anywhere on a long page, including far below the visible window.
It clicks the button and waits for the entry form's first box (the Institution input). It returns True when the box
became visible, False otherwise. It clicks at most twice (one more click when the first did not open the form) and
must never hang: when the button does not exist it returns False at once; when the form never opens it returns False.
A button that is hidden (zero size) counts as not existing.
