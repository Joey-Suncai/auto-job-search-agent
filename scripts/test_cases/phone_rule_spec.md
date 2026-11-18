# Phone-number answer on job application forms (JSA-315)

The applicant's phone number is 555-010-2030. The phone rule puts this number into a field ONLY when the field asks for
his phone number: labels such as "Phone", "Phone Number", "Mobile Phone", "Cell", "Home Phone", "Primary phone",
"What is your phone number?", "Please provide your phone number", "Best phone number to reach you". A question that asks
whether he HAS a number ("Do you have a phone number where we can reach you?") in a text box also gets the number.
It must NOT put the number into:
- yes / no questions about capability, equipment or access that merely mention a phone, phone line or telephone
  ("Do you have the capability to successfully Work From Home if required (i.e. internet access, dedicated phone line,
  secured working area, etc.)", "Do you have reliable access to a phone and internet?", "Telephone line available at
  home?", "Will you have a phone line dedicated to work?") — even when the field is a free-text box;
- phone interview / phone screen questions, name pronunciation ("phonetic") questions, phone extension boxes.
For those the expected result is "NOT_PHONE" (some other rule, a saved answer or the applicant answers).
Phone type / device type and country phone code fields are other rules: "NOT_PHONE" as well.
