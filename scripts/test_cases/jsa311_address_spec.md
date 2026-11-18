# Spec: answering address questions on job application forms (JSA-311)

The candidate's facts:
- street: "1200 S Sample Ave"
- city, state and ZIP: "Chicago, IL 60601" (city "Chicago", state "IL", ZIP "60601")
- permanent (home-country) address: "Apt 12, Building 3, Willow Apartments, Lakeside Subdistrict, Eastfield District, Springtown, Zhejiang 310000, China"

Rules for a free-text box (no options):
1. A box that asks for the street only — e.g. "Street address", "Address Line 1", "Address", "Mailing address" — gets the street: "1200 S Sample Ave".
2. A single box that asks for the street AND the city / state / ZIP together — e.g. "What is your street address? Please also include your city, state, and zip code.", "Full address", "Complete mailing address", "Home address (street, city, state, zip)", "Street Address, City, State, ZIP" — gets the whole address in the form "1200 S Sample Ave, Chicago, IL 60601".
3. A box that asks for city, state and ZIP without the street (e.g. "City, State, Zip", "City, State and Zip Code") gets "Chicago, IL 60601".
4. Split address forms keep one fact per box: "City" → "Chicago"; "Zip code" / "Postal code" → "60601"; "Address Line 1" → the street.
5. A street box that says NOT to include the city / state / ZIP (e.g. "Street address (do not include city, state, or zip)") gets the street only.
6. A box that asks for the permanent address / home-country address gets the permanent address, whatever else it asks.
7. Boxes that are not about his home address (email address, school address, employer address, references' addresses, "Address Line 2") are never answered with the street or the whole address.
