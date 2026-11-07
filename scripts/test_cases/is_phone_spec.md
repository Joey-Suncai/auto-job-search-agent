# Is a form field a phone-NUMBER box?

When the runner reads back a form, a phone-number box is compared by its digits (formatting ignored); every other field
is compared as text. Given a field (key, type, label, options) decide whether it is a phone-number box:
- key "phone" → yes, always.
- Otherwise yes only when the type is "text" or "tel" (a missing type counts as "text"), the label contains "phone" as a
  separate word ("Phone", "Mobile phone", "Phone number", "Cell phone"), and the field has no options.
- "telephone" / "smartphone" / "headphones" are not the word "phone". A Yes/No or other choice question (type combo,
  select, radio, checkbox, or any field with options) is never a phone box, even when its text talks about phones, e.g.
  "Would you like to receive SMS… we will only contact you via email and/or phone calls" with options Yes/No.
